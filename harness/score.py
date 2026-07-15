"""The Slop Index: the composite headline score.

Every axis is scored as DISTANCE FROM HUMAN, not distance from zero. A model
that writes like the pre-AI human baseline scores 0. The scale is anchored on
real human writing, which is the whole credibility claim.

Axes (only those that survived the pilots):
  conciseness   length inflation over the scenario's human-derived band
  templating    opener repetition across N samples of the SAME prompt
  rhythm        paragraph-length variance, scored as FLATTENING vs human.
                EMAIL ONLY. It does not generalize: the direction INVERTS in
                Slack (human turns are structurally flat at 3.59 variance;
                models are more varied), and it is unmeasurable in essay and
                social because the Blog Corpus and Sentiment140 have no
                recoverable paragraph structure. Scored where the baseline
                supports it, skipped (with weights renormalized) where it does
                not. Do not claim it as a universal "humans beat models" axis.
  tells         validated slop markers (>=5x human rate), per 1k words.

Deliberately excluded, with reasons:
  MTLD           models score HIGHER lexical diversity than humans in ALL FOUR
                 domains (28/28 model-domain pairs). The axis is wrong-signed;
                 the literature's "humans are more diverse" claim came from
                 greedy-decoded base models, not sampled chat models. Excluded.
  raw word count overlaps across models once GPT stopped padding.
  compression    overlapped in pilot-001.
  detectors      Pangram pins at 100% AI for every model (see PILOT_FINDINGS).

On the em dash (it stays IN the tells axis, and it earns its place):
  The worry was that "humans don't use em dashes" is an encoding artifact --
  EnronSent (1999-2002 plain ASCII) has zero em dashes but 5.41 dashes/1k in
  other forms, because you could not type U+2014. The DISCO Discord corpus
  settles it: those are 2019-2020 humans who COULD trivially type an em dash,
  and they used it at 0.04/1k. Across four corpora spanning 1999-2020, human
  em-dash use is ~0 regardless of era; every model runs 1.5-15/1k. It is the
  ONLY tell that validates in all four domains -- the entire classic slop
  lexicon (delve, tapestry, elevate, seamless, don't hesitate, not-just-but,
  thrilled to announce, as an AI, rule-of-three) is BUSTED in 2026 models.

Usage:
  python3 score.py --run-id full-001
  python3 score.py --run-id full-001 --domain email
"""
import argparse
import json
import pathlib
import random
import statistics as st
import sys
from collections import defaultdict

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from analyze import words, para_variance, tells_per_1k, boot_ci  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
BASELINES = ROOT / "baselines"

# Axis weights. Published with the board, alongside a sensitivity analysis:
# the ranking must be stable under reasonable reweighting or the weights are
# doing the work instead of the data.
WEIGHTS = {
    "conciseness": 0.35,
    "templating": 0.30,
    "rhythm": 0.20,
    "tells": 0.15,
}

# A model at or below the human rate scores 0. A model at CEILING x the human
# rate (or the band ceiling, for conciseness) scores 100. Linear in between,
# clipped. Chosen so a doubling of human slop is ~50, not ~5.
CEILING = 3.0


def _load_baseline(domain):
    """Adapter over baselines/{domain}/stats.json. Normalizes the corpus stats
    into the two things the score needs, so the scorer stays decoupled from the
    baseline file's schema."""
    p = BASELINES / domain / "stats.json"
    if not p.exists():
        return None
    raw = json.loads(p.read_text())
    tells = {}
    for tell, v in (raw.get("tells_per_1k_words") or {}).items():
        # pooled = total hits / total corpus words. This is the denominator for
        # every "Nx over human" claim; the per-message mean over-weights short
        # messages that happen to contain one hit.
        tells[tell] = v["pooled_rate_per_1k_words"] if isinstance(v, dict) else v
    return {
        "paragraph_variance_mean": (raw.get("paragraph_length_variance") or {}).get("mean"),
        "tells_per_1k": tells,
        "length_p50": ((raw.get("length_distribution") or {}).get("overall") or {}).get("p50"),
        "_raw": raw,
    }


def _scale(value, human, ceiling=CEILING):
    """0 = human-like, 100 = `ceiling`x the human rate. Clipped to [0, 100]."""
    if human is None or human <= 0:
        return None
    ratio = value / human
    if ratio <= 1:
        return 0.0
    return min(100.0, 100.0 * (ratio - 1) / (ceiling - 1))


def score_model(rows, baseline):
    """rows: one model's outputs for one domain. Returns axis scores 0-100."""
    out = {}

    # --- conciseness: how far over the human-derived length band ---
    inflations = []
    for r in rows:
        band = r.get("length_target")
        if band:
            n = len(words(r["text"]))
            inflations.append(max(0.0, n / band[1] - 1.0))
    # 0% over band = 0; 100% over band (double the ceiling) = 100.
    out["conciseness"] = min(100.0, 100.0 * st.mean(inflations)) if inflations else None

    # --- templating: opener repetition within a scenario ---
    by_scen = defaultdict(list)
    for r in rows:
        by_scen[r["scenario_id"]].append(r["text"])
    ratios = []
    for texts in by_scen.values():
        if len(texts) < 2:
            continue
        openers = defaultdict(int)
        for t in texts:
            openers[" ".join(words(t)[:5]).lower()] += 1
        ratios.append(max(openers.values()) / len(texts))
    if ratios:
        n_samples = st.mean([len(v) for v in by_scen.values()])
        floor = 1.0 / n_samples  # no repetition at all
        rep = st.mean(ratios)
        out["templating"] = min(100.0, max(0.0, 100.0 * (rep - floor) / (1 - floor)))
    else:
        out["templating"] = None

    # --- rhythm: paragraph-variance FLATTENING vs human ---
    # Humans are structurally uneven (email: 22.5). Models flatten (13-20).
    # Score = how much of the human variance the model has LOST.
    hv = (baseline or {}).get("paragraph_variance_mean")
    mv = [para_variance(r["text"]) for r in rows]
    mv = [v for v in mv if v is not None]
    if hv and mv:
        loss = max(0.0, 1.0 - st.mean(mv) / hv)
        out["rhythm"] = min(100.0, 100.0 * loss)
    else:
        out["rhythm"] = None

    # --- tells: validated markers only, scaled against the human rate ---
    ht = (baseline or {}).get("tells_per_1k") or {}
    # Compute each output's tell rates ONCE (was O(tells x rows x 2) calls).
    row_tells = [tells_per_1k(r["text"]) for r in rows]
    scores = []
    for tell, human_rate in ht.items():
        if tell == "any_dash":
            continue  # counted via em_dash; keeping both would double-weight dashes
        vals = [rt[tell] for rt in row_tells if tell in rt]
        model_rate = st.mean(vals) if vals else 0.0
        if human_rate and human_rate > 0:
            s = _scale(model_rate, human_rate)
            if s is not None:
                scores.append(s)
        elif model_rate > 0:
            # Human baseline is zero for this marker. Cannot compute a ratio;
            # any occurrence is categorical. Score conservatively at 50 rather
            # than infinity, and flag it in the report.
            scores.append(50.0)
    out["tells"] = st.mean(scores) if scores else None

    return out


def composite(axis_scores):
    """Weighted mean over the axes that could be computed. Renormalizes the
    weights over available axes so a missing baseline does not silently
    deflate a model's score."""
    num, den = 0.0, 0.0
    for axis, w in WEIGHTS.items():
        v = axis_scores.get(axis)
        if v is not None:
            num += w * v
            den += w
    return num / den if den else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--domain", help="restrict to one domain")
    args = ap.parse_args()

    src = RUNS / args.run_id / "outputs.jsonl"
    rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("text") and not r.get("error")]
    if args.domain:
        rows = [r for r in rows if r["domain"] == args.domain]

    domains = sorted({r["domain"] for r in rows})
    models = sorted({r["model"] for r in rows})
    baselines = {d: _load_baseline(d) for d in domains}
    missing = [d for d, b in baselines.items() if b is None]

    print("=" * 78)
    print(f"THE SLOP INDEX  run={args.run_id}   0 = writes like a pre-AI human")
    print("=" * 78)
    if missing:
        print(f"! no human baseline yet for: {', '.join(missing)}")
        print("  (rhythm + tells axes are skipped there; weights renormalized)")

    # per-domain, then overall
    per_model_domain = defaultdict(dict)
    for d in domains:
        for m in models:
            rs = [r for r in rows if r["domain"] == d and r["model"] == m]
            if rs:
                per_model_domain[m][d] = score_model(rs, baselines[d])

    print(f"\n{'model':<24}" + "".join(d[:8].rjust(9) for d in domains) + "    OVERALL")
    board = []
    for m in models:
        dom_scores = {}
        for d in domains:
            axes = per_model_domain[m].get(d)
            dom_scores[d] = composite(axes) if axes else None
        vals = [v for v in dom_scores.values() if v is not None]
        overall = st.mean(vals) if vals else None
        board.append((overall, m, dom_scores))
    for overall, m, dom in sorted(board, key=lambda x: -(x[0] or 0)):
        row = f"{m:<24}"
        for d in domains:
            v = dom[d]
            row += f"{v:>9.1f}" if v is not None else "      n/a"
        row += f"    {overall:>7.1f}" if overall is not None else "      n/a"
        print(row)

    # axis breakdown, overall
    print(f"\n{'model':<24}" + "".join(a[:11].rjust(13) for a in WEIGHTS))
    for _, m, _ in sorted(board, key=lambda x: -(x[0] or 0)):
        row = f"{m:<24}"
        for axis in WEIGHTS:
            vals = [per_model_domain[m][d].get(axis) for d in domains
                    if d in per_model_domain[m]
                    and per_model_domain[m][d].get(axis) is not None]
            row += f"{st.mean(vals):>13.1f}" if vals else "          n/a"
        print(row)

    # ---- sensitivity: is the ranking the data's, or the weights'? ----
    # Published with the board. If the ranking flips under reasonable
    # reweighting, the weights are doing the work and we must say so.
    rnd = random.Random(13)
    base_order = [m for _, m, _ in sorted(board, key=lambda x: -(x[0] or 0))]
    flips, trials = 0, 500
    top_counts, bottom_counts = defaultdict(int), defaultdict(int)
    for _ in range(trials):
        w = {a: rnd.uniform(0.10, 0.45) for a in WEIGHTS}
        tot = sum(w.values())
        w = {a: v / tot for a, v in w.items()}
        scores = []
        for m in models:
            num = den = 0.0
            for d in domains:
                axes = per_model_domain[m].get(d) or {}
                for a, wt in w.items():
                    if axes.get(a) is not None:
                        num += wt * axes[a]
                        den += wt
            scores.append(((num / den) if den else 0.0, m))
        order = [m for _, m in sorted(scores, key=lambda x: -x[0])]
        if order != base_order:
            flips += 1
        top_counts[order[0]] += 1
        bottom_counts[order[-1]] += 1
    print(f"\nsensitivity ({trials} random reweightings, each axis 0.10-0.45):")
    print(f"  exact ranking preserved in {100 * (trials - flips) / trials:.0f}% of trials")
    top = max(top_counts, key=top_counts.get)
    bot = max(bottom_counts, key=bottom_counts.get)
    print(f"  sloppiest  = {top:<24} in {100 * top_counts[top] / trials:.0f}% of trials")
    print(f"  cleanest   = {bot:<24} in {100 * bottom_counts[bot] / trials:.0f}% of trials")
    if flips / trials > 0.5:
        print("  ! ranking is weight-sensitive. Report the axes separately, not one index.")

    print(f"\nweights: {WEIGHTS}   ceiling: {CEILING}x human rate = 100")
    print("excluded axes and why: see the module docstring (MTLD is wrong-signed,")
    print("em-dash-alone measures typography era, detectors pin at 100% for all).")


if __name__ == "__main__":
    main()
