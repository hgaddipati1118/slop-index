"""Stage 3: the go/no-go gate.

Answers, from the pilot run:
  A. Does ANY Pangram field separate the models?      (spread)
  B. Is the spread just output length?                (validity)
  C. Does the mechanical fallback separate them?      (safe harbor)
  D. What is Pangram's FPR on pre-AI human text?      (calibration, if --baseline scored)
  E. What did the run cost?                           (cost summary)

Runs on scored.jsonl if present; falls back to outputs.jsonl (mechanical only,
no Pangram key needed) so the fallback headline can be evaluated for free.

Usage: python3 analyze.py --run-id pilot-20260714-0930

v2 changes (post pilot-001):
  - DROPPED compression ratio: did not separate models (CIs overlapped).
  - FIXED opener repetition: now measured WITHIN a scenario (across the N
    samples of the SAME prompt) and averaged over scenarios, instead of
    across all scenarios globally (which saturates at ~1/n_samples no matter
    how repetitive a model actually is).
  - ADDED a cost summary table (total $ and $/1k output tokens per model),
    fed by providers.py's LiteLLM usage tracking.
  - ADDED length-inflation-over-band broken out per domain, not just overall.
"""
import argparse
import json
import math
import pathlib
import random
import re
import statistics as st
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"

# Descriptive tell counters (not a scored composite in v1; used here to see
# whether mechanical signals separate models if the detector does not).
TELLS = {
    "finds_you_well": r"hope (this|the) (email|message) finds you",
    "reach_out": r"\b(reach(ing)? out|reached out)\b",
    "circle_back": r"\b(circl(e|ing) back|touch base|following up on my)\b",
    "not_just_but": r"\bnot just [^.,;]{1,40},? but\b|\bit'?s not (just )?about [^.,;]{1,40}[,;] it'?s\b",
    "delve": r"\bdelv(e|ing|ed)\b",
    "tapestry_testament": r"\b(tapestry|testament to|underscore(s|d)?|pivotal)\b",
    "thrilled_excited": r"\b(thrilled|excited|delighted) to (announce|share)\b",
    "elevate_seamless": r"\b(elevate|seamless|streamline|leverage|robust|game[- ]chang)\w*\b",
    "dont_hesitate": r"don'?t hesitate",
    "let_that_sink": r"\b(let that sink in|read that again|agree\?)\b",
    "signoff": r"\b(best regards|kind regards|warm regards|sincerely|best,)\b",
    "greeting": r"^\s*(hi|hello|hey|dear)\b[^\n]{0,30}[,!]",
    # DASH METRICS: the em-dash-only counter was a trap. The EnronSent baseline
    # (1999-2002, plain-text ASCII email) contains ZERO em dashes in 5.98M words
    # -- but 5.41 dashes per 1k words in other forms (" - " at 4.43, "--" at
    # 0.98). Humans dashed constantly; they just could not type U+2014. Counting
    # only em dashes measures the writer's ERA AND KEYBOARD, not their slop, and
    # publishing "AI uses em dashes, humans do not" would be indefensible.
    # So we track both: the glyph (a typography fingerprint) and the rhetorical
    # move (any dash form, comparable across eras).
    "em_dash": r"—",                       # typography fingerprint only
    "any_dash": r"—|–|(?<!-)--(?!-)|\s-\s",  # the actual rhetorical move

    "rule_of_three": r"\b\w+ing\b,\s+\b\w+ing\b,?\s+and\s+\b\w+ing\b",
    "as_an_ai": r"\bas an ai\b",
    "apology": r"\b(i apologize|sorry for|apologies for|my apologies)\b",
}


def words(t):
    return re.findall(r"\b[\w']+\b", t)


def mtld(toks, threshold=0.72):
    """Lexical diversity (McCarthy & Jarvis 2010). Higher = more varied."""
    def run(seq):
        factors, types, n = 0, set(), 0
        for w in seq:
            types.add(w.lower())
            n += 1
            if n and len(types) / n <= threshold:
                factors += 1
                types, n = set(), 0
        if n:
            ttr = len(types) / n
            factors += (1 - ttr) / (1 - threshold) if ttr < 1 else 0
        return len(seq) / factors if factors else len(seq)
    if len(toks) < 20:
        return None
    return (run(toks) + run(toks[::-1])) / 2


def burstiness(t):
    """Std of sentence lengths. Humans vary more."""
    sents = [s for s in re.split(r"(?<=[.!?])\s+", t.strip()) if s.strip()]
    lens = [len(words(s)) for s in sents]
    return st.pstdev(lens) if len(lens) > 1 else None


def para_variance(t):
    paras = [p for p in t.split("\n\n") if p.strip()]
    lens = [len(words(p)) for p in paras]
    return st.pstdev(lens) if len(lens) > 1 else None


def tells_per_1k(t):
    n = max(len(words(t)), 1)
    return {k: 1000 * len(re.findall(rx, t, re.I | re.M)) / n
            for k, rx in TELLS.items()}


def boot_ci(vals, n=2000):
    """Bootstrap 95% CI of the mean."""
    vals = [v for v in vals if v is not None]
    if len(vals) < 2:
        return (None, None, None)
    rnd = random.Random(7)
    means = sorted(st.mean(rnd.choices(vals, k=len(vals))) for _ in range(n))
    return (st.mean(vals), means[int(0.025 * n)], means[int(0.975 * n)])


def pearson(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return None
    xs, ys = zip(*pairs)
    mx, my = st.mean(xs), st.mean(ys)
    num = sum((x - mx) * (y - my) for x, y in pairs)
    den = math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))
    return num / den if den else None


def fmt(v, p=3):
    return "  n/a" if v is None else f"{v:.{p}f}"


def table(title, per_model, note=""):
    print(f"\n{title}")
    if note:
        print(f"  ({note})")
    print(f"  {'model':<26}{'mean':>9}{'95% CI':>20}{'n':>6}")
    for m, vals in sorted(per_model.items(), key=lambda kv: -(boot_ci(kv[1])[0] or 0)):
        mean, lo, hi = boot_ci(vals)
        ci = f"[{fmt(lo)}, {fmt(hi)}]" if lo is not None else "n/a"
        print(f"  {m:<26}{fmt(mean):>9}{ci:>20}{len([v for v in vals if v is not None]):>6}")
    # separation verdict
    cis = {m: boot_ci(v) for m, v in per_model.items()}
    ok = [(m, c) for m, c in cis.items() if c[1] is not None]
    if len(ok) >= 2:
        ok.sort(key=lambda kv: kv[1][0])
        lo_m, lo_c = ok[0]
        hi_m, hi_c = ok[-1]
        sep = lo_c[2] < hi_c[1]
        spread = hi_c[0] - lo_c[0]
        print(f"  -> spread {spread:.4f} ({lo_m} .. {hi_m}); "
              f"extremes {'SEPARATE (CIs disjoint)' if sep else 'OVERLAP'}")
        return sep, spread
    return False, 0.0


def opener_ratios_within_scenario(rows_for_model):
    """For ONE model's rows (all scenarios/samples): for each scenario, the
    share of that scenario's samples that share the model's most common
    5-word opener for that scenario. Returns one ratio per scenario, so the
    resulting list can go straight through table()'s bootstrap CI (n =
    number of scenarios, not number of outputs)."""
    by_scenario = defaultdict(list)
    for r in rows_for_model:
        by_scenario[r["scenario_id"]].append(r["text"])
    ratios = []
    for sid, texts in by_scenario.items():
        openers = defaultdict(int)
        for t in texts:
            openers[" ".join(words(t)[:5]).lower()] += 1
        top = max(openers.values()) if openers else 0
        ratios.append(top / max(len(texts), 1))
    return ratios


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    args = ap.parse_args()
    d = RUNS / args.run_id
    scored = d / "scored.jsonl"
    src = scored if scored.exists() else d / "outputs.jsonl"
    rows = [json.loads(l) for l in src.read_text().splitlines()]
    rows = [r for r in rows if r.get("text") and not r.get("error")]
    model_rows = [r for r in rows if r.get("kind", "model") == "model"]
    human_rows = [r for r in rows if r.get("kind") == "human"]
    models_list = sorted({r["model"] for r in model_rows})
    domains_list = sorted({r["domain"] for r in model_rows})

    print("=" * 74)
    print(f"PILOT GATE  run={args.run_id}  source={src.name}")
    print(f"{len(model_rows)} model outputs, {len(human_rows)} human baseline texts")
    print("=" * 74)

    has_pangram = any("pangram" in r for r in model_rows)
    mech_verdicts = {}  # name -> (sep, spread), collected across section C

    # ---------- A. SPREAD: does any Pangram field separate models? ----------
    if has_pangram:
        print("\n" + "-" * 74)
        print("A. SPREAD  Does any Pangram field rank the models?")
        print("-" * 74)
        fields = ["ai_likelihood", "fraction_ai", "fraction_ai_assisted",
                  "fraction_human", "avg_ai_likelihood", "max_ai_likelihood"]
        verdicts = {}
        for fld in fields:
            per = defaultdict(list)
            for r in model_rows:
                v = (r.get("pangram") or {}).get(fld)
                if isinstance(v, (int, float)):
                    per[r["model"]].append(float(v))
            if any(per.values()):
                sep, spread = table(f"[{fld}]", per)
                verdicts[fld] = (sep, spread)

        # window-score dip: min window score per output
        per = defaultdict(list)
        for r in model_rows:
            ws = [w for w in (r.get("pangram") or {}).get("window_scores") or []
                  if isinstance(w, (int, float))]
            if ws:
                per[r["model"]].append(min(ws))
        if any(per.values()):
            sep, spread = table("[min window score]", per,
                                "lowest-confidence window per output; do any dip toward human?")
            verdicts["min_window"] = (sep, spread)

        # flagged rate (tail)
        per = defaultdict(list)
        for r in model_rows:
            v = (r.get("pangram") or {}).get("ai_likelihood")
            if isinstance(v, (int, float)):
                per[r["model"]].append(1.0 if v >= 0.5 else 0.0)
        if any(per.values()):
            sep, spread = table("[flagged rate @0.5]", per, "tail statistic")
            verdicts["flagged_rate"] = (sep, spread)

        # ---------- B. VALIDITY: is spread just length? ----------
        print("\n" + "-" * 74)
        print("B. VALIDITY  Is any spread just output length?")
        print("-" * 74)
        lens = [len(words(r["text"])) for r in model_rows]
        for fld in ["ai_likelihood", "fraction_ai", "fraction_human"]:
            vs = [(r.get("pangram") or {}).get(fld) for r in model_rows]
            rho = pearson(lens, [v if isinstance(v, (int, float)) else None for v in vs])
            print(f"  corr(words, {fld:<22}) = {fmt(rho)}"
                  f"{'   <-- length artifact risk' if rho is not None and abs(rho) > 0.4 else ''}")

        # ---------- D. CALIBRATION ----------
        if human_rows:
            print("\n" + "-" * 74)
            print("D. CALIBRATION  Pangram on genuinely pre-AI human writing")
            print("-" * 74)
            per_src = defaultdict(list)
            for r in human_rows:
                v = (r.get("pangram") or {}).get("ai_likelihood")
                if isinstance(v, (int, float)):
                    per_src[r.get("source", "human")].append(float(v))
            for s, vals in per_src.items():
                fpr = sum(1 for v in vals if v >= 0.5) / len(vals)
                print(f"  {s:<22} mean ai_likelihood {fmt(st.mean(vals))}  "
                      f"false-positive rate {fpr:.1%}  (n={len(vals)})")
    else:
        verdicts = {}
        print("\n[no Pangram scores in this run: set PANGRAM_API_KEY and run detect.py]")
        print("[mechanical fallback analysis below runs for free]")

    # ---------- C. MECHANICAL FALLBACK ----------
    print("\n" + "-" * 74)
    print("C. MECHANICAL FALLBACK  Do the free metrics separate the models?")
    print("-" * 74)

    metrics = {
        "words": lambda t: len(words(t)),
        "MTLD (lexical diversity)": lambda t: mtld(words(t)),
        "burstiness (sent-len std)": lambda t: burstiness(t),
        "paragraph-len variance": lambda t: para_variance(t),
    }
    for name, fn in metrics.items():
        per = defaultdict(list)
        for r in model_rows:
            per[r["model"]].append(fn(r["text"]))
        sep, spread = table(f"[{name}]", per)
        mech_verdicts[name] = (sep, spread)

    # length inflation vs the scenario band (Conciseness axis) — overall
    per = defaultdict(list)
    for r in model_rows:
        band = r.get("length_target")
        if band:
            n = len(words(r["text"]))
            per[r["model"]].append(max(0.0, n / band[1] - 1.0))
    sep, spread = table("[length inflation over band -- OVERALL]", per,
                        "0 = within human-norm band; 1.0 = double the ceiling")
    mech_verdicts["length inflation (overall)"] = (sep, spread)

    # length inflation vs the scenario band — per domain
    for dom in domains_list:
        per = defaultdict(list)
        for r in model_rows:
            if r["domain"] != dom:
                continue
            band = r.get("length_target")
            if band:
                n = len(words(r["text"]))
                per[r["model"]].append(max(0.0, n / band[1] - 1.0))
        sep, spread = table(f"[length inflation over band -- domain={dom}]", per)
        mech_verdicts[f"length inflation ({dom})"] = (sep, spread)

    # descriptive matrix: mean length inflation, model x domain (quick-scan table)
    print("\n[length inflation over band, mean %, model x domain]")
    hdr = "  " + "model".ljust(26) + "".join(d.rjust(10) for d in domains_list) + "overall".rjust(10)
    print(hdr)
    for m in models_list:
        row = "  " + m.ljust(26)
        overall_vals = []
        for dom in domains_list:
            vals = []
            for r in model_rows:
                if r["model"] == m and r["domain"] == dom:
                    band = r.get("length_target")
                    if band:
                        n = len(words(r["text"]))
                        vals.append(max(0.0, n / band[1] - 1.0))
            overall_vals.extend(vals)
            row += f"{(st.mean(vals) if vals else 0.0):>+10.0%}"
        row += f"{(st.mean(overall_vals) if overall_vals else 0.0):>+10.0%}"
        print(row)

    # tell counters
    print("\n[tell counters, per 1k words]")
    per_model_tells = defaultdict(lambda: defaultdict(list))
    for r in model_rows:
        for k, v in tells_per_1k(r["text"]).items():
            per_model_tells[r["model"]][k].append(v)
    keys = [k for k in TELLS if any(
        st.mean(per_model_tells[m][k]) > 0 for m in per_model_tells)]
    hdr = "  " + "model".ljust(26) + "".join(k[:9].rjust(10) for k in keys)
    print(hdr)
    for m in sorted(per_model_tells):
        row = "  " + m.ljust(26)
        for k in keys:
            row += f"{st.mean(per_model_tells[m][k]):>10.1f}"
        print(row)

    # homogeneity: opener repetition WITHIN a scenario (across the N samples
    # of the SAME prompt), averaged over scenarios. v1 measured this across
    # all scenarios/samples globally, which saturates near 1/n_samples
    # regardless of true repetitiveness -- fixed here.
    per = defaultdict(list)
    for m in models_list:
        rows_m = [r for r in model_rows if r["model"] == m]
        per[m] = opener_ratios_within_scenario(rows_m)
    sep, spread = table(
        "[opener repetition WITHIN scenario]", per,
        "mean over scenarios of (count of most-common 5-word opener / n_samples for that scenario); "
        "1/n_samples = no repetition, 1.0 = identical opener every sample")
    mech_verdicts["opener repetition (within-scenario)"] = (sep, spread)

    # ---------- E. COST SUMMARY ----------
    print("\n" + "-" * 74)
    print("E. COST SUMMARY  (from providers.py / LiteLLM usage tracking)")
    print("-" * 74)
    print(f"  {'model':<26}{'total $':>10}{'gens':>6}{'out tok':>10}"
          f"{'$/1k gens':>12}{'$/1k out tok':>14}{'flags':>16}")
    total_all, total_gens, total_tok = 0.0, 0, 0
    for m in models_list:
        rows_m = [r for r in model_rows if r["model"] == m]
        usages = [r.get("usage") or {} for r in rows_m]
        known_costs = [u["cost_usd"] for u in usages if u.get("cost_usd") is not None]
        unknown = sum(1 for u in usages if u.get("cost_usd") is None)
        estimated = sum(1 for u in usages if u.get("cost_estimated"))
        retried = sum(1 for u in usages if u.get("retried_8k"))
        out_tok = sum(u.get("completion_tokens") or 0 for u in usages)
        total_m = sum(known_costs)
        total_all += total_m
        total_gens += len(rows_m)
        total_tok += out_tok
        # two readings of "$ per 1k outputs": per 1k generations, and per 1k
        # output tokens. Report both -- they rank models differently, because
        # a model can be cheap per token and still expensive per task if it
        # burns tokens on hidden reasoning.
        per1k_gen = 1000 * total_m / len(rows_m) if rows_m else None
        per1k_tok = 1000 * total_m / out_tok if out_tok else None
        flags = []
        if estimated:
            flags.append(f"{estimated} est")
        if unknown:
            flags.append(f"{unknown} unk")
        if retried:
            flags.append(f"{retried} retried")
        print(f"  {m:<26}{f'${total_m:.4f}':>10}{len(rows_m):>6}{out_tok:>10,}"
              f"{(f'${per1k_gen:.2f}' if per1k_gen is not None else 'n/a'):>12}"
              f"{(f'${per1k_tok:.4f}' if per1k_tok is not None else 'n/a'):>14}"
              f"{', '.join(flags):>16}")
    print(f"  {'-' * 78}")
    all_gen = 1000 * total_all / total_gens if total_gens else 0
    all_tok = 1000 * total_all / total_tok if total_tok else 0
    print(f"  {'TOTAL':<26}{f'${total_all:.4f}':>10}{total_gens:>6}{total_tok:>10,}"
          f"{f'${all_gen:.2f}':>12}{f'${all_tok:.4f}':>14}")
    if not has_pangram:
        pass  # no scoring cost to add; Pangram cost (if any) would go here

    # ---------- SEPARATION SUMMARY ----------
    print("\n" + "=" * 74)
    if has_pangram:
        wins = [f for f, (sep, _) in verdicts.items() if sep]
        if wins:
            print(f"VERDICT: GO. Pangram fields that separate models: {', '.join(wins)}")
            print("         (confirm section B shows the spread is not a length artifact)")
        else:
            print("VERDICT: NO-GO on the Pangram headline. No field separated the models.")
            print("         Fall back to the mechanical composite (section C) as the headline;")
            print("         keep Pangram as a corroborating column. This is a publishable finding.")
    else:
        print("Run detect.py with a Pangram key to complete the gate (sections A, B, D).")

    mech_wins = [f for f, (sep, _) in mech_verdicts.items() if sep]
    mech_losses = [f for f, (sep, _) in mech_verdicts.items() if not sep]
    print(f"\nMechanical axes with disjoint CIs (models separate): {', '.join(mech_wins) if mech_wins else 'none'}")
    print(f"Mechanical axes that OVERLAP (no separation): {', '.join(mech_losses) if mech_losses else 'none'}")
    print("=" * 74)


if __name__ == "__main__":
    main()
