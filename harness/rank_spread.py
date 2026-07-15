"""Rank Spread — confidence-interval rank ranges for the Slop Index board.

The LMArena credibility pattern: never publish a false-precise "#3". Instead
report the RANGE of ranks a model plausibly occupies, and call two models a
TIE when their ranges overlap. We already know (from the sensitivity analysis)
that the middle of the board is not weight-stable; rank spread makes that
honesty visible in the primary number.

Method: scenario-level cluster bootstrap (the correct unit is the scenario,
since a model's samples for one scenario are correlated). Resample the scenario
set with replacement B times; for each resample recompute every model's overall
Slop Index and rank them; a model's rank spread is the 2.5-97.5 percentile of
its rank distribution.

Per-output metric inputs are precomputed ONCE, so each bootstrap is just cheap
re-aggregation, not a full re-scan.

Usage: python3 rank_spread.py --run-id full-merged
"""
import argparse
import json
import pathlib
import random
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analyze import words, para_variance, tells_per_1k  # noqa: E402
from score import _load_baseline, _scale, WEIGHTS, CEILING  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
B = 500  # bootstrap resamples


def precompute(rows, baseline):
    """Per-output inputs the axes need, computed once."""
    ht = {k: v for k, v in ((baseline or {}).get("tells_per_1k") or {}).items()
          if k != "any_dash"}
    out = []
    for r in rows:
        t = r["text"]; w = words(t); n = len(w)
        band = r.get("length_target")
        infl = max(0.0, n / band[1] - 1.0) if band else None
        rt = tells_per_1k(t)
        out.append({
            "scen": r["scenario_id"],
            "infl": infl,
            "opener": " ".join(w[:5]).lower(),
            "pvar": para_variance(t),
            "tells": {k: rt.get(k, 0.0) for k in ht},
        })
    return out, ht


def score_from_precomp(items, ht, human_pvar):
    """Recompute the 4 axes + composite from precomputed items (fast)."""
    if not items:
        return None
    # conciseness
    infl = [x["infl"] for x in items if x["infl"] is not None]
    conc = min(100.0, 100.0 * st.mean(infl)) if infl else None
    # templating: opener repetition within scenario
    by_scen = defaultdict(list)
    for x in items:
        by_scen[x["scen"]].append(x["opener"])
    ratios = []
    for ops in by_scen.values():
        if len(ops) < 2:
            continue
        c = defaultdict(int)
        for o in ops:
            c[o] += 1
        ratios.append(max(c.values()) / len(ops))
    if ratios:
        ns = st.mean([len(v) for v in by_scen.values()])
        floor = 1.0 / ns
        templ = min(100.0, max(0.0, 100.0 * (st.mean(ratios) - floor) / (1 - floor)))
    else:
        templ = None
    # rhythm: paragraph-variance flattening vs human
    pv = [x["pvar"] for x in items if x["pvar"] is not None]
    rhythm = min(100.0, 100.0 * max(0.0, 1.0 - st.mean(pv) / human_pvar)) if (human_pvar and pv) else None
    # tells
    tscores = []
    for tell, hr in ht.items():
        mr = st.mean([x["tells"][tell] for x in items])
        if hr and hr > 0:
            s = _scale(mr, hr)
            if s is not None:
                tscores.append(s)
        elif mr > 0:
            tscores.append(50.0)
    tells = st.mean(tscores) if tscores else None
    axes = {"conciseness": conc, "templating": templ, "rhythm": rhythm, "tells": tells}
    num = den = 0.0
    for a, wt in WEIGHTS.items():
        if axes[a] is not None:
            num += wt * axes[a]; den += wt
    return (num / den) if den else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    src = RUNS / args.run_id / "outputs.jsonl"
    rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("text") and not r.get("error")]

    domains = sorted({r["domain"] for r in rows})
    models = sorted({r["model"] for r in rows})
    baselines = {d: _load_baseline(d) for d in domains}
    hpvar = {d: ((baselines[d] or {}).get("_raw", {}).get("paragraph_length_variance", {}) or {}).get("mean")
             for d in domains}

    # precompute per (model, domain)
    pc = {}  # (model,domain) -> (items, ht)
    for m in models:
        for d in domains:
            mr = [r for r in rows if r["model"] == m and r["domain"] == d]
            if mr:
                pc[(m, d)] = precompute(mr, baselines[d])

    scen_by_domain = {d: sorted({r["scenario_id"] for r in rows if r["domain"] == d}) for d in domains}

    def board_ranks(scen_sample):
        """Given a resampled set of scenarios per domain, rank all models by overall."""
        overall = {}
        for m in models:
            dvals = []
            for d in domains:
                if (m, d) not in pc:
                    continue
                items, ht = pc[(m, d)]
                sset = scen_sample[d]
                sub = [x for x in items if x["scen"] in sset]  # note: multiset membership below
                # rebuild with multiplicity for cluster bootstrap
                if sub:
                    mult = []
                    counts = defaultdict(int)
                    for s in scen_sample[d]:
                        counts[s] += 1
                    byscen = defaultdict(list)
                    for x in items:
                        byscen[x["scen"]].append(x)
                    for s, k in counts.items():
                        for _ in range(k):
                            mult.extend(byscen.get(s, []))
                    sc = score_from_precomp(mult, ht, hpvar[d])
                    if sc is not None:
                        dvals.append(sc)
            overall[m] = st.mean(dvals) if dvals else None
        ranked = sorted([m for m in models if overall[m] is not None],
                        key=lambda m: -overall[m])
        return {m: i + 1 for i, m in enumerate(ranked)}, overall

    # point estimate (no resample)
    point_ranks, point_overall = board_ranks(scen_by_domain)

    # bootstrap
    rnd = random.Random(42)
    rank_dist = defaultdict(list)
    for _ in range(B):
        samp = {d: [rnd.choice(scen_by_domain[d]) for _ in scen_by_domain[d]] for d in domains}
        rk, _ = board_ranks(samp)
        for m, r in rk.items():
            rank_dist[m].append(r)

    def spread(m):
        rs = sorted(rank_dist[m])
        lo = rs[int(0.025 * len(rs))]; hi = rs[int(0.975 * len(rs))]
        return lo, hi

    print("=" * 70)
    print(f"SLOP INDEX — RANK SPREAD   run={args.run_id}   {B} bootstraps")
    print("higher Slop Index = sloppier. rank 1 = sloppiest.")
    print("=" * 70)
    print(f"{'rank':>10}  {'model':<24}{'slop':>7}   spread")
    order = sorted(point_overall, key=lambda m: -point_overall[m])
    for m in order:
        lo, hi = spread(m)
        rk = point_ranks[m]
        rng = f"{lo}" if lo == hi else f"{lo}–{hi}"
        print(f"{rk:>10}  {m:<24}{point_overall[m]:>7.1f}   ranks {rng}")

    # ties: models whose spreads overlap the sloppiest
    print("\nTIE GROUPS (overlapping rank spreads = statistically indistinguishable):")
    spreads = {m: spread(m) for m in order}
    groups, used = [], set()
    for m in order:
        if m in used:
            continue
        lo, hi = spreads[m]
        g = [x for x in order if x not in used and not (spreads[x][0] > hi or spreads[x][1] < lo)]
        for x in g:
            used.add(x)
        groups.append(g)
    for i, g in enumerate(groups, 1):
        print(f"  group {i}: {', '.join(g)}")


if __name__ == "__main__":
    main()
