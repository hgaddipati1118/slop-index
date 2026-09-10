"""Build slop-game/public/bench.json from a run, so the site's data is
reproducible instead of hand-assembled.

Emits, per model: the four domain Slop Scores, `overall` (their unweighted
mean), the four axis means across domains, `rank` (1 = SLOPPIEST, matching
SPEC.md), the bootstrap rank `spread`, prices, and the Pangram result.

DIRECTION: every number written here is a SLOP measure, higher = sloppier.
The site flips it for display (see leaderboard.html computeScores). Do not
"fix" this file to a human-likeness orientation.

Usage:
  python3 build_bench.py --run-id full-merged                  # print only
  python3 build_bench.py --run-id full-merged --write          # write bench.json
  python3 build_bench.py --run-id full-merged --no-spread      # skip the bootstrap
"""
import argparse
import json
import pathlib
import statistics as st
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from score import _load_baseline, score_model, composite, WEIGHTS  # noqa: E402
import providers  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"
BENCH = ROOT / "slop-game" / "public" / "bench.json"
DOMAINS = ["email", "social", "essay", "slack"]

# Display name + lab per alias. Anything generated but missing here is a hard
# error, so a new model can never silently reach the site as a raw alias.
META = {
    "claude-fable-5":          ("Fable 5", "Anthropic"),
    "claude-opus-4-8":         ("Opus 4.8", "Anthropic"),
    "claude-opus-5":           ("Opus 5", "Anthropic"),
    "claude-sonnet-5":         ("Sonnet 5", "Anthropic"),
    "claude-haiku-4-5":        ("Haiku 4.5", "Anthropic"),
    "gpt-5.6-sol":             ("GPT-5.6 Sol", "OpenAI"),
    "gpt-5.6-terra":           ("GPT-5.6 Terra", "OpenAI"),
    "gpt-5.6-luna":            ("GPT-5.6 Luna", "OpenAI"),
    "gpt-5.4-mini":            ("GPT-5.4 Mini", "OpenAI"),
    "gemini-3.1-pro-preview":  ("Gemini 3.1 Pro", "Google"),
    "gemini-3.5-flash":        ("Gemini 3.5 Flash", "Google"),
    "gemini-3.6-flash":        ("Gemini 3.6 Flash", "Google"),
    "deepseek-v4-pro":         ("DeepSeek V4", "DeepSeek"),
    "kimi-k2p6":               ("Kimi K2.6", "Moonshot"),
    "kimi-k3":                 ("Kimi K3", "Moonshot"),
    # 2026-09-09 refresh
    "gpt-6-astra":             ("GPT-6 Astra", "OpenAI"),
    "claude-fable-5.1":        ("Fable 5.1", "Anthropic"),
    "gemini-3.8-flash":        ("Gemini 3.8 Flash", "Google"),
    "gemini-3.7-flash":        ("Gemini 3.7 Flash", "Google"),
    "qwen3.8-max":             ("Qwen3.8 Max", "Alibaba"),
    "qwen3.8-flash":           ("Qwen3.8 Flash", "Alibaba"),
    "muse-spark-1.3":          ("Muse Spark 1.3", "Meta"),
    "grok-4.6":                ("Grok 4.6", "xAI"),
    "glm-5.3":                 ("GLM-5.3", "Zhipu"),
    "deepseek-v4-pro-0813":    ("DeepSeek V4 (0813)", "DeepSeek"),
    "glm-5.2":                 ("GLM-5.2", "Zhipu"),
    "qwen3.7-max":             ("Qwen3.7 Max", "Alibaba"),
    "qwen3.7-flash":           ("Qwen3.7 Flash", "Alibaba"),
    "minimax-m3":              ("MiniMax M3", "MiniMax"),
    "mistral-large":           ("Mistral Large", "Mistral"),
    "muse-spark-1.1":          ("Muse Spark 1.1", "Meta"),
    "grok-4.5":                ("Grok 4.5", "xAI"),
}

# Pangram scores were produced by hand in the pangram.com browser (v3.3.2), and
# the per-model record of WHICH models were scored was never written down: the
# published bench.json marks all 18 originals 100 while its own meta note says
# "15 of 18". Rather than guess which three were unscored, carry forward exactly
# what is already published and give genuinely new models null. Never copy a 100
# onto a model that was not run through the detector.
def carry_pangram():
    try:
        prev = json.loads(BENCH.read_text())
    except Exception:
        return {}
    return {m["id"]: m.get("pangram") for m in prev.get("models", [])}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--no-spread", action="store_true")
    args = ap.parse_args()

    src = RUNS / args.run_id / "outputs.jsonl"
    rows = [json.loads(l) for l in src.read_text().splitlines() if l.strip()]
    rows = [r for r in rows if r.get("text") and not r.get("error")]
    models = sorted({r["model"] for r in rows})

    unknown = [m for m in models if m not in META]
    if unknown:
        sys.exit(f"ERROR: no display name/lab for: {unknown}. Add them to META.")

    prev_pangram = carry_pangram()
    baselines = {d: _load_baseline(d) for d in DOMAINS}
    axes_by = {}   # (model, domain) -> axis dict
    for m in models:
        for d in DOMAINS:
            rs = [r for r in rows if r["model"] == m and r["domain"] == d]
            if rs:
                axes_by[(m, d)] = score_model(rs, baselines[d])

    spreads = {}
    if not args.no_spread:
        import rank_spread as rs_mod
        spreads = compute_spreads(rows, models, baselines, rs_mod)

    out = []
    for m in models:
        dom = {d: (composite(axes_by[(m, d)]) if (m, d) in axes_by else None)
               for d in DOMAINS}
        vals = [v for v in dom.values() if v is not None]
        overall = st.mean(vals) if vals else None
        rec = {"id": m, "name": META[m][0], "lab": META[m][1],
               "overall": r1(overall)}
        for d in DOMAINS:
            rec[d] = r1(dom[d])
        for axis in WEIGHTS:
            av = [axes_by[(m, d)].get(axis) for d in DOMAINS
                  if (m, d) in axes_by and axes_by[(m, d)].get(axis) is not None]
            rec[axis] = r1(st.mean(av)) if av else None
        pin, pout = providers.PRICES.get(m, (None, None))
        rec["price_in"] = pin
        rec["price_out"] = pout
        rec["blended"] = round((pin + pout) / 2, 2) if pin is not None else None
        rec["pangram"] = prev_pangram.get(m)   # None for models new to the board
        out.append(rec)

    out.sort(key=lambda r: -(r["overall"] or 0))   # rank 1 = SLOPPIEST
    for i, r in enumerate(out, 1):
        r["rank"] = i
        lohi = spreads.get(r["id"])
        r["spread"] = (str(lohi[0]) if lohi[0] == lohi[1] else f"{lohi[0]}–{lohi[1]}") if lohi else str(i)

    tie_groups = build_ties([r["id"] for r in out], spreads) if spreads else []

    bench = {
        "models": out,
        "tie_groups": tie_groups,
        "meta": {
            "n_models": len(out),
            "n_outputs": len(rows),
            "scenarios": len({r["scenario_id"] for r in rows}),
            "domains": DOMAINS,
            "weights": dict(WEIGHTS),
            "run_id": args.run_id,
            "pangram_note": (
                f"{sum(1 for r in out if r['pangram'] is not None)} of {len(out)} models carry a "
                "pangram.com (v3.3.2) browser score; every scored one = 100% AI, High confidence. "
                "Models added after that pass show null and have NOT been run through the detector."
            ),
        },
    }

    print(f"{'#':>3}  {'model':<24}{'overall':>9}  spread   pangram")
    for r in out:
        print(f"{r['rank']:>3}  {r['name']:<24}{r['overall']:>9}  {r['spread']:<8} {r['pangram']}")
    print(f"\n{len(out)} models, {len(rows)} outputs, {bench['meta']['scenarios']} scenarios")

    if args.write:
        BENCH.write_text(json.dumps(bench, indent=1))
        print(f"\nwrote {BENCH}")
    else:
        print("\n(dry run, pass --write to update bench.json)")


def r1(v):
    return round(v, 1) if v is not None else None


def compute_spreads(rows, models, baselines, rs_mod):
    """Reuse rank_spread's cluster bootstrap rather than reimplementing it."""
    import random
    from collections import defaultdict
    hpvar = {d: ((baselines[d] or {}).get("_raw", {}).get("paragraph_length_variance", {}) or {}).get("mean")
             for d in DOMAINS}
    pc = {}
    for m in models:
        for d in DOMAINS:
            mr = [r for r in rows if r["model"] == m and r["domain"] == d]
            if mr:
                pc[(m, d)] = rs_mod.precompute(mr, baselines[d])
    scen_by_domain = {d: sorted({r["scenario_id"] for r in rows if r["domain"] == d})
                      for d in DOMAINS}
    byscen = {}
    for (m, d), (items, ht) in pc.items():
        g = defaultdict(list)
        for x in items:
            g[x["scen"]].append(x)
        byscen[(m, d)] = g

    def ranks(sample):
        overall = {}
        for m in models:
            dvals = []
            for d in DOMAINS:
                if (m, d) not in pc:
                    continue
                _, ht = pc[(m, d)]
                mult = []
                for s in sample[d]:
                    mult.extend(byscen[(m, d)].get(s, []))
                sc = rs_mod.score_from_precomp(mult, ht, hpvar[d])
                if sc is not None:
                    dvals.append(sc)
            overall[m] = st.mean(dvals) if dvals else None
        ranked = sorted([m for m in models if overall[m] is not None],
                        key=lambda m: -overall[m])
        return {m: i + 1 for i, m in enumerate(ranked)}

    rnd = random.Random(42)   # same seed as rank_spread.py, so results match
    dist = defaultdict(list)
    for _ in range(rs_mod.B):
        samp = {d: [rnd.choice(scen_by_domain[d]) for _ in scen_by_domain[d]]
                for d in DOMAINS}
        for m, r in ranks(samp).items():
            dist[m].append(r)
    out = {}
    for m, rs in dist.items():
        rs = sorted(rs)
        out[m] = (rs[int(0.025 * len(rs))], rs[int(0.975 * len(rs))])
    return out


def build_ties(order, spreads):
    groups, used = [], set()
    for m in order:
        if m in used:
            continue
        lo, hi = spreads[m]
        g = [x for x in order if x not in used
             and not (spreads[x][0] > hi or spreads[x][1] < lo)]
        used.update(g)
        groups.append(g)
    return [g for g in groups if len(g) > 1]


if __name__ == "__main__":
    main()
