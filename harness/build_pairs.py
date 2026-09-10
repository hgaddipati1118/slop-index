"""Build slop-game/public/pairs.json (+ prompts.json) — the arena's blind matchups.

The README pointed at "the builder in the parent repo", which did not exist; the
original set was made ad hoc. This is that builder, written down.

Each pair is two DIFFERENT models' outputs for the SAME scenario, so a vote is
always a like-for-like comparison. Model appearances are balanced greedily, so no
model is systematically over- or under-exposed (Elo converges faster and a rarely
shown model does not sit on a noisy provisional rating).

Existing crowd Elo is stored per MODEL in Redis, not per pair, so regenerating
pairs does not invalidate any of the votes already cast.

AFTER RUNNING THIS: update the vote allowlist in slop-game/api/_models.js, or
every vote involving a new model is silently rejected (vote.js drops unknown
models to block fake-model injection). This script prints the exact block.

Usage:
  python3 build_pairs.py --run-id full-merged --per-scenario 12 --write
"""
import argparse
import json
import pathlib
import random
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
PUB = ROOT / "slop-game" / "public"
SCEN = ROOT / "scenarios" / "pilot"

MIN_WORDS = 12   # skip degenerate/near-empty outputs; they make the vote meaningless


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--per-scenario", type=int, default=12)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rows = [json.loads(l) for l in
            (RUNS / args.run_id / "outputs.jsonl").read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("text") and not r.get("error")
            and len(r["text"].split()) >= MIN_WORDS]

    setups = json.loads((SCEN / "setups.json").read_text())

    # one representative output per (scenario, model): the first sample, so the
    # arena shows a typical generation rather than a cherry-picked best.
    best = {}
    for r in sorted(rows, key=lambda r: (r["scenario_id"], r["model"], r["sample"])):
        best.setdefault((r["scenario_id"], r["model"]), r)

    by_scen = defaultdict(list)
    for (scen, model), r in best.items():
        by_scen[scen].append(r)

    rnd = random.Random(args.seed)
    appearances = defaultdict(int)
    pairs = []
    for scen in sorted(by_scen):
        cands = sorted(by_scen[scen], key=lambda r: r["model"])
        if len(cands) < 2:
            continue
        seen = set()
        for _ in range(args.per_scenario):
            # greedy balance: draw from the least-shown models, break ties randomly
            pool = sorted(cands, key=lambda r: (appearances[r["model"]], rnd.random()))
            picked = None
            for i in range(len(pool)):
                for j in range(i + 1, len(pool)):
                    key = tuple(sorted((pool[i]["model"], pool[j]["model"])))
                    if key not in seen:
                        picked = (pool[i], pool[j], key)
                        break
                if picked:
                    break
            if not picked:
                break                      # every distinct matchup for this scenario used
            a, b, key = picked
            seen.add(key)
            if rnd.random() < 0.5:         # randomise which side is A
                a, b = b, a
            appearances[a["model"]] += 1
            appearances[b["model"]] += 1
            pairs.append({
                "scenario": scen,
                "domain": a["domain"],
                "setup": setups.get(scen, ""),
                "a": {"model": a["model"], "text": a["text"]},
                "b": {"model": b["model"], "text": b["text"]},
            })

    rnd.shuffle(pairs)
    models = sorted({p[k]["model"] for p in pairs for k in ("a", "b")})

    print(f"{len(pairs)} pairs over {len(by_scen)} scenarios, {len(models)} models")
    print(f"appearances: min {min(appearances.values())}, max {max(appearances.values())}")
    for m in models:
        print(f"  {m:<26}{appearances[m]:>5}")

    prompts = {r["scenario_id"]: r["user_prompt"] for r in rows}

    print("\n--- paste into slop-game/api/_models.js ---")
    print("export const MODELS = new Set([")
    line = "  "
    for m in models:
        chunk = f'"{m}", '
        if len(line) + len(chunk) > 78:
            print(line.rstrip()); line = "  "
        line += chunk
    print(line.rstrip().rstrip(",") if line.strip() else "", "\n]);")

    if args.write:
        (PUB / "pairs.json").write_text(json.dumps(pairs))
        (PUB / "prompts.json").write_text(json.dumps(prompts))
        print(f"\nwrote {PUB/'pairs.json'} and {PUB/'prompts.json'}")
    else:
        print("\n(dry run, pass --write)")


if __name__ == "__main__":
    main()
