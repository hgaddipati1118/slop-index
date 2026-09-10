"""Stage 1: generate outputs for the pilot scenarios.

Usage:
  python3 generate.py --samples 5 --models gpt-5.1,claude-sonnet-5,...
Writes runs/<run_id>/outputs.jsonl
"""
import argparse
import json
import os
import pathlib
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import providers  # noqa: E402
import budget  # noqa: E402

# Measured $/generation, per model, from pilot-002 (696 gens, LiteLLM-tracked).
# Used ONLY for the pre-flight projection; actual spend is metered live.
COST_PER_GEN = {
    "gemini-3.1-pro-preview": 0.0138,
    "gemini-3.5-flash": 0.0105,
    "gpt-5.6-sol": 0.0078,
    "kimi-k2p6": 0.0064,
    "claude-sonnet-5": 0.0038,
    "deepseek-v4-pro": 0.0030,
    "gpt-5.4-mini": 0.0011,
    # Roster refresh 2026-07-31. No measured run yet, so these are extrapolated from the
    # closest-priced model in full-merged, rounded UP so the pre-flight never under-projects.
    "claude-opus-5": 0.0090,      # opus-4-8 measured 0.0086 at the identical $5/$25
    "kimi-k3": 0.0200,            # k2.6 measured 0.0049; k3 output is 3.75x dearer
    "gemini-3.6-flash": 0.0095,   # 3.5-flash measured 0.0105, 3.6 output is cheaper
    "qwen3.7-flash": 0.0005,      # qwen3.7-max measured 0.0120 at ~58x the token price
    # Roster refresh 2026-09-09. Extrapolated from the closest measured model, rounded UP.
    "gpt-6-astra": 0.0270,          # fable-5 measured 0.0222 at the identical $10/$50; reasoning default unknown
    "claude-fable-5.1": 0.0230,     # fable-5 measured 0.0222, same price, reasoning off by default
    "gemini-3.8-flash": 0.0050,     # 3.5-flash measured 0.0096 at 2x the price
    "gemini-3.7-flash": 0.0050,
    "qwen3.8-max": 0.0100,          # 3.7-max measured 0.0120 at $2.50/$7.50; 3.8 is $2/$6
    "qwen3.8-flash": 0.0010,
    "muse-spark-1.3": 0.0080,       # 1.1 measured 0.0072 at the same price
    "grok-4.6": 0.0045,             # 4.5 measured 0.0038
    "glm-5.3": 0.0030,              # 5.2 measured 0.0024
    "deepseek-v4-pro-0813": 0.0015, # v4-pro measured 0.0026 at a higher price
    # 2026-09-10 additions, rounded UP from the nearest measured model.
    "deepseek-v4.1-flash": 0.0010,
    "gpt-6-astra-pro": 0.0200,      # gpt-6-astra measured 0.0121 at the same price; pro likely reasons more
    "hy4-preview": 0.0040,
    "inkling-small": 0.0025,
    "seed-2.1-turbo": 0.0040,
    "mercury-2.5": 0.0005,
    "nemotron-3.5-lightning": 0.0008,
}
DEFAULT_COST_PER_GEN = 0.0100  # conservative for an unmeasured model

ROOT = pathlib.Path(__file__).resolve().parent.parent
SCEN = ROOT / "scenarios" / "pilot"
RUNS = ROOT / "runs"

# The scaffold is published verbatim as part of the methodology.
SCAFFOLD = {
    "email": "You are helping the user write an email. Output only the email body, no subject line, no commentary.",
    "social": "You are helping the user write a social media post. Output only the post text, no commentary.",
    "essay": "You are helping the user write. Output only the piece itself, no commentary.",
    "slack": "You are helping the user write a Slack message. Output only the message, as they would send it, no commentary.",
}


def build_user_prompt(s):
    """Scenario context + the natural prompt, exactly as specced."""
    parts = [f"About me: {s['persona']}"]
    if s.get("recipient"):
        parts.append(f"Who this is going to: {s['recipient']}")
    for m in s.get("context_thread", []):
        who = {"recipient": "They wrote", "persona": "I previously wrote",
               "other": "Context"}.get(m["from"], "Context")
        parts.append(f'{who}: "{m["text"]}"')
    parts.append(f"\n{s['prompt']}")
    return "\n".join(parts)


def _usable(r):
    """A row that actually contributes to scoring: real text, no error."""
    return bool((r.get("text") or "").strip()) and not r.get("error")


def give_up_for(give_up, model):
    return [k for k in give_up if k[0] == model]


def load_scenarios():
    out = []
    for domain in ("email", "social", "essay", "slack"):
        out.extend(json.loads((SCEN / f"{domain}.json").read_text()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", type=int, default=5)
    ap.add_argument("--models", default=",".join(providers.MODELS))
    ap.add_argument("--run-id", default=time.strftime("pilot-%Y%m%d-%H%M"))
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the projected cost and exit without calling any API")
    args = ap.parse_args()

    scenarios = load_scenarios()
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    outdir = RUNS / args.run_id
    outdir.mkdir(parents=True, exist_ok=True)

    jobs = [(m, s, i) for m in models for s in scenarios
            for i in range(args.samples)]
    print(f"{len(scenarios)} scenarios x {len(models)} models x {args.samples} "
          f"samples = {len(jobs)} generations -> {outdir}")

    # RESUME: outputs are streamed to disk as they land (see below), so a killed
    # run keeps everything it paid for. Re-invoking with the same --run-id skips
    # whatever is already on disk instead of buying it twice.
    path = outdir / "outputs.jsonl"
    done, attempts = set(), defaultdict(int)
    if path.exists():
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue          # a torn final line from a hard kill; it gets regenerated
            key = (r["model"], r["scenario_id"], r["sample"])
            attempts[key] += 1
            if (r.get("text") or "").strip() and not r.get("error"):
                done.add(key)
    # Some model/prompt combinations return NO text no matter how often you ask
    # (claude-opus-5 emits a thinking-only block with no text block for
    # social.x_post.002, confirmed against the raw Anthropic API, and the 8k
    # retry in providers.py does not help). Retrying those on every resume just
    # buys the same nothing again, so give up after 2 attempts and let the run
    # report the gap instead.
    give_up = {k for k, n in attempts.items() if n >= 2 and k not in done}
    if done or give_up:
        skip = done | give_up
        jobs = [j for j in jobs if (j[0], j[1]["id"], j[2]) not in skip]
        print(f"[resume] {len(done)} already on disk, {len(jobs)} left to generate")
        if give_up:
            bad = defaultdict(set)
            for m, s, _i in give_up:
                bad[m].add(s)
            for m, scens in sorted(bad.items()):
                print(f"[resume] {m}: giving up on {len(give_up_for(give_up, m))} sample(s) "
                      f"across {len(scens)} scenario(s) that return no text: {sorted(scens)}")

    # Pre-flight: refuse to start a run that would breach the project cap.
    # Projected off the REMAINING jobs, not the nominal matrix, or a resume would
    # re-project work already paid for and could refuse to finish itself.
    todo = defaultdict(int)
    for m, _s, _i in jobs:
        todo[m] += 1
    projected = sum(COST_PER_GEN.get(m, DEFAULT_COST_PER_GEN) * n
                    for m, n in todo.items())
    budget.preflight(projected, args.run_id)
    if args.dry_run:
        for m in sorted(todo):
            c = COST_PER_GEN.get(m, DEFAULT_COST_PER_GEN)
            print(f"  {m:<24} {todo[m]:>5} gens  ~${c * todo[m]:.2f}")
        print("[dry-run] no API calls made.")
        return
    guard = budget.Guard(args.run_id)

    def run(job):
        model, s, i = job
        guard.check()  # hard stop if the cap was crossed by in-flight calls
        system = SCAFFOLD[s["domain"]]
        user = build_user_prompt(s)
        for attempt in range(3):
            try:
                text, usage = providers.generate(model, system, user)
                guard.add(usage.get("cost_usd"))
                return {
                    "scenario_id": s["id"], "domain": s["domain"],
                    "category": s["category"], "model": model, "sample": i,
                    "system": system, "user_prompt": user,
                    "text": (text or "").strip(),
                    "length_target": s["length_target"]["words"],
                    "usage": usage,
                }
            except budget.BudgetExceeded:
                return None  # stop spending immediately, keep what we have
            except Exception as e:  # noqa: BLE001
                if attempt == 2:
                    return {"scenario_id": s["id"], "domain": s["domain"],
                            "model": model, "sample": i, "error": str(e)[:200]}
                time.sleep(2 * (attempt + 1))

    # Stream every result to disk the moment it lands. Buffering the whole run in
    # memory and writing once at the end meant a kill threw away everything the
    # run had already paid for (full-006 lost 1,350 generations and $20.05 that
    # way). Append + flush per line, so the file is always a valid resume point.
    results, errors, halted = [], 0, False
    write_lock = threading.Lock()
    sink = path.open("a")
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            futs = [ex.submit(run, j) for j in jobs]
            for n, f in enumerate(as_completed(futs), 1):
                r = f.result()
                if r is None:  # budget guard tripped this job
                    halted = True
                    continue
                if r.get("error"):
                    errors += 1
                results.append(r)
                with write_lock:
                    sink.write(json.dumps(r) + "\n")
                    sink.flush()
                    os.fsync(sink.fileno())
                if n % 25 == 0 or n == len(jobs):
                    print(f"  {n}/{len(jobs)} done ({errors} errors) "
                          f"${guard.run_cost:.2f}", flush=True)
                    # Checkpoint spend to the ledger as we go. A SIGKILL cannot run
                    # the `finally` below, and full-006 died that way with $20.05
                    # unrecorded. record() overwrites by run_id, so this is idempotent
                    # and the ledger is never behind by more than 25 generations.
                    guard.commit()
    finally:
        sink.close()
        # Record spend even on an abnormal exit, so a killed run can never again
        # leave real money off the ledger.
        guard.commit()
    if halted:
        print("\n!! BUDGET CAP HIT: run halted early. Partial outputs kept below.")

    # Rewrite once, sorted and de-duplicated, so the finished artifact is
    # deterministic regardless of completion order or how many resumes it took.
    # Keep the BEST row per key, not the first: a resume can append a good
    # generation after an earlier empty one, and first-wins would throw the good
    # one away and keep the empty.
    best = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        try:
            r = json.loads(line)
        except json.JSONDecodeError:
            continue
        key = (r["model"], r["scenario_id"], r["sample"])
        prev = best.get(key)
        if prev is None or (not _usable(prev) and _usable(r)):
            best[key] = r
    final = list(best.values())
    with path.open("w") as f:
        for r in sorted(final, key=lambda r: (r["model"], r["scenario_id"], r["sample"])):
            f.write(json.dumps(r) + "\n")
    results = final

    ok = [r for r in results if not r.get("error")]
    print(f"\nwrote {len(ok)} outputs ({errors} errors) -> {path}")
    if errors:
        seen = {}
        for r in results:
            if r.get("error"):
                seen.setdefault(r["model"], r["error"])
        for m, e in seen.items():
            print(f"  ! {m}: {e}")

    # cost summary  (defaultdict is imported at module scope; a local re-import
    # here would shadow it and make the pre-flight's use of it unbound)
    by_model = defaultdict(lambda: {"cost": 0.0, "n": 0, "unknown": 0, "estimated": 0, "retried": 0})
    total_cost, total_unknown = 0.0, 0
    for r in ok:
        u = r.get("usage") or {}
        m = by_model[r["model"]]
        m["n"] += 1
        if u.get("retried_8k"):
            m["retried"] += 1
        c = u.get("cost_usd")
        if c is None:
            m["unknown"] += 1
            total_unknown += 1
        else:
            m["cost"] += c
            total_cost += c
            if u.get("cost_estimated"):
                m["estimated"] += 1
    print(f"\ncost: ${total_cost:.4f} total"
          f"{f' ({total_unknown} generations with unknown cost)' if total_unknown else ''}")
    for m, v in sorted(by_model.items()):
        tag = f" [{v['estimated']} estimated]" if v["estimated"] else ""
        tag += f" [{v['unknown']} unknown]" if v["unknown"] else ""
        tag += f" [{v['retried']} retried@8k]" if v["retried"] else ""
        print(f"  {m:<24} ${v['cost']:.4f}  (n={v['n']}){tag}")


if __name__ == "__main__":
    main()
