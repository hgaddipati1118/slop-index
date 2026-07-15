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
import time
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

    # Pre-flight: refuse to start a run that would breach the project cap.
    projected = sum(COST_PER_GEN.get(m, DEFAULT_COST_PER_GEN) * len(scenarios)
                    * args.samples for m in models)
    budget.preflight(projected, args.run_id)
    if args.dry_run:
        for m in sorted(models):
            c = COST_PER_GEN.get(m, DEFAULT_COST_PER_GEN)
            print(f"  {m:<24} {len(scenarios) * args.samples:>5} gens  "
                  f"~${c * len(scenarios) * args.samples:.2f}")
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

    results, errors, halted = [], 0, False
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
            if n % 25 == 0 or n == len(jobs):
                print(f"  {n}/{len(jobs)} done ({errors} errors) "
                      f"${guard.run_cost:.2f}", flush=True)
    if halted:
        print("\n!! BUDGET CAP HIT: run halted early. Partial outputs kept below.")

    path = outdir / "outputs.jsonl"
    with path.open("w") as f:
        for r in sorted(results, key=lambda r: (r["model"], r["scenario_id"], r["sample"])):
            f.write(json.dumps(r) + "\n")

    ok = [r for r in results if not r.get("error")]
    print(f"\nwrote {len(ok)} outputs ({errors} errors) -> {path}")
    if errors:
        seen = {}
        for r in results:
            if r.get("error"):
                seen.setdefault(r["model"], r["error"])
        for m, e in seen.items():
            print(f"  ! {m}: {e}")

    # cost summary
    from collections import defaultdict
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
