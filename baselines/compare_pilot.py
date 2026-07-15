"""Pilot-002 model outputs vs each domain's human baseline, all 4 domains.

Imports the same metric functions as analyze.py/compute_stats.py so nothing
is reimplemented -- this is a read-only report generator over already-
computed baselines/{domain}/stats.json files and runs/pilot-002/outputs.jsonl.
Does NOT touch runs/pilot-002 or runs/full-001 (full-001 is an ACTIVE run
and must not be read/written by this script beyond the pilot-002 read).

v2 (this revision): generalized from email-only to all four domains
(email/slack/essay/social), and added a cross-domain SYNTHESIS section
answering the four questions the baseline-build task set out to answer:
  1. Which tells pass the >=5x-over-human gate, per domain -- and which are
     busted folklore (present in humans too, or absent in models).
  2. Are the hand-set scenario length_target bands right, per domain?
  3. Does the email-domain MTLD reversal (models > humans) replicate in the
     other three domains, or is email the odd one out?
  4. Does paragraph-variance flattening (humans more structurally uneven
     than models) replicate outside email?

Usage: python3 baselines/compare_pilot.py [--domain email|slack|essay|social|all]
"""
import argparse
import json
import pathlib
import re
import statistics as st
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "harness"))
from analyze import TELLS, burstiness, mtld, para_variance, words  # noqa: E402

DOMAINS = ["email", "slack", "essay", "social"]


def family_of(model: str) -> str:
    if model.startswith("gpt"):
        return "gpt"
    if model.startswith("gemini"):
        return "gemini"
    if model.startswith("claude"):
        return "claude"
    if model.startswith("deepseek"):
        return "deepseek"
    if model.startswith("kimi"):
        return "kimi"
    return model


def load_baseline_stats(domain):
    path = ROOT / "baselines" / domain / "stats.json"
    if not path.exists():
        return None
    return json.loads(path.read_text())


def load_pilot_rows(domain):
    rows = [json.loads(l) for l in (ROOT / "runs" / "pilot-002" / "outputs.jsonl").read_text().splitlines()]
    return [r for r in rows if r.get("domain") == domain and r.get("text") and not r.get("error")]


def pooled_tell_rates(rows):
    hits = {k: 0 for k in TELLS}
    total_words = 0
    for r in rows:
        n = len(words(r["text"]))
        total_words += n
        for k, rx in TELLS.items():
            hits[k] += len(re.findall(rx, r["text"], re.I | re.M))
    return {k: (1000 * hits[k] / total_words if total_words else 0.0) for k in TELLS}, total_words


DASH_FORMS = {
    "em_dash": re.compile(r"—"),
    "en_dash": re.compile(r"–"),
    "ascii_double_dash": re.compile(r"(?<!-)--(?!-)"),
    "spaced_hyphen": re.compile(r"\s-\s"),
}


def dash_rates(rows):
    total_words = sum(len(words(r["text"])) for r in rows)
    out = {}
    for name, rx in DASH_FORMS.items():
        hits = sum(len(rx.findall(r["text"])) for r in rows)
        out[name] = 1000 * hits / total_words if total_words else 0.0
    any_hits = sum(len(re.findall(TELLS["any_dash"], r["text"])) for r in rows)
    out["any_dash"] = 1000 * any_hits / total_words if total_words else 0.0
    return out


def domain_report(domain, synthesis):
    """Print the full pilot-vs-baseline report for one domain. Accumulates
    cross-domain findings into the `synthesis` dict for the final section."""
    base = load_baseline_stats(domain)
    if base is None:
        print(f"\n[{domain}] SKIPPED -- no baselines/{domain}/stats.json found")
        return
    rows = load_pilot_rows(domain)
    if not rows:
        print(f"\n[{domain}] SKIPPED -- no pilot-002 rows for this domain")
        return
    models = sorted({r["model"] for r in rows})

    print("=" * 78)
    print(f"{domain.upper()}: pilot-002 ({len(rows)} outputs, {len(models)} models) vs human baseline")
    print(f"Human baseline: {base['corpus']}")
    print(f"  n={base['n_messages']:,} docs, {base['n_words_total']:,} words")
    print("=" * 78)

    base_tells = {k: v["pooled_rate_per_1k_words"] for k, v in base["tells_per_1k_words"].items()}
    model_tells = {}
    for m in models:
        rows_m = [r for r in rows if r["model"] == m]
        rates, _ = pooled_tell_rates(rows_m)
        model_tells[m] = rates
    pooled_all_rates, _ = pooled_tell_rates(rows)

    print("\n--- FREQUENCY RATIO TABLE (model pooled rate / human pooled rate) ---")
    print(f"{'tell':<20}{'human/1k':>10}", end="")
    for m in models:
        print(f"{m[:12]:>14}", end="")
    print(f"{'pooled/1k':>12}{'ratio':>10}{'families>=5x':>14}{'status':>12}")

    validated, busted, candidate = [], [], []
    for k in TELLS:
        hb = base_tells[k]
        row = f"{k:<20}{hb:>10.3f}"
        fams_elevated = set()
        for m in models:
            mr = model_tells[m][k]
            row += f"{mr:>14.2f}"
            if hb > 0 and mr / hb >= 5:
                fams_elevated.add(family_of(m))
            elif hb == 0 and mr > 0:
                fams_elevated.add(family_of(m))
        pooled_rate = pooled_all_rates[k]
        ratio = (pooled_rate / hb) if hb > 0 else (float("inf") if pooled_rate > 0 else 0.0)
        ratio_str = "inf(base=0)" if hb == 0 and pooled_rate > 0 else (
            "0/0" if hb == 0 and pooled_rate == 0 else f"{ratio:>9.1f}x")
        status = "n/a"
        if hb == 0 and pooled_rate > 0:
            status = "validated" if len(fams_elevated) >= 3 else "candidate"
        elif hb > 0:
            status = "validated" if (ratio >= 5 and len(fams_elevated) >= 3) else (
                "candidate" if ratio >= 5 else "busted")
        if status == "validated":
            validated.append((k, ratio, fams_elevated))
        elif status == "busted":
            busted.append((k, ratio))
        row += f"{pooled_rate:>12.3f}{ratio_str:>10}{len(fams_elevated):>14}{status:>12}"
        print(row)

    print(f"\nVALIDATED tells for {domain} (ratio>=5x pooled AND elevated in >=3/5 model families):")
    for k, ratio, fams in sorted(validated, key=lambda x: -x[1] if x[1] != float("inf") else 1e9):
        r_str = "inf (human=0)" if ratio == float("inf") else f"{ratio:.1f}x"
        print(f"  {k:<20} {r_str:<16} families: {sorted(fams)}")

    print(f"\nBUSTED for {domain} (pooled ratio < 5x -- not elevated vs human despite folklore):")
    for k, ratio in sorted(busted, key=lambda x: x[1]):
        print(f"  {k:<20} {ratio:.2f}x")

    synthesis["validated"][domain] = [k for k, _, _ in validated]
    synthesis["busted"][domain] = [k for k, _ in busted]

    # ---- DASH VERDICT (by form) ----
    print("\n" + "-" * 78)
    print(f"[{domain}] DASH VERDICT (by form)")
    print("-" * 78)
    base_dash = base.get("dash_breakdown_per_1k_words", {})
    print(f"{'form':<20}{'human/1k':>10}", end="")
    for m in models:
        print(f"{m[:12]:>14}", end="")
    print()
    model_dash = {m: dash_rates([r for r in rows if r["model"] == m]) for m in models}
    for form in ("em_dash", "en_dash", "ascii_double_dash", "spaced_hyphen", "any_dash"):
        hb = base_dash.get(form, {}).get("pooled_rate_per_1k_words", 0.0)
        row = f"{form:<20}{hb:>10.3f}"
        for m in models:
            row += f"{model_dash[m][form]:>14.2f}"
        print(row)
    synthesis["dash"][domain] = {"human": base_dash, "model": model_dash}

    # ---- MTLD / burstiness / paragraph variance: human vs model ----
    print("\n" + "-" * 78)
    print(f"[{domain}] MTLD / BURSTINESS / PARAGRAPH VARIANCE: human vs model")
    print("-" * 78)
    print(f"{'':<24}{'MTLD':>10}{'burstiness':>14}{'para_var':>12}")
    base_pv = base["paragraph_length_variance"]
    base_pv_str = f"{base_pv['mean']:.2f}" if base_pv.get("mean") is not None else "NULL(n=0)"
    print(f"{'HUMAN (' + domain + ')':<24}{base['mtld']['mean']:>10.2f}"
          f"{base['burstiness_sentence_len_std']['mean']:>14.2f}"
          f"{base_pv_str:>12}")
    model_mtld_means = {}
    for m in models:
        rows_m = [r for r in rows if r["model"] == m]
        mtld_vals = [v for v in (mtld(words(r["text"])) for r in rows_m) if v is not None]
        burst_vals = [v for v in (burstiness(r["text"]) for r in rows_m) if v is not None]
        parvar_vals = [v for v in (para_variance(r["text"]) for r in rows_m) if v is not None]
        mm = st.mean(mtld_vals) if mtld_vals else float("nan")
        model_mtld_means[m] = mm
        pv_str = f"{st.mean(parvar_vals):.2f}" if parvar_vals else "NULL(n=0)"
        print(f"{m:<24}{mm:>10.2f}"
              f"{(st.mean(burst_vals) if burst_vals else float('nan')):>14.2f}"
              f"{pv_str:>12}")
        if parvar_vals:
            synthesis["parvar_model"].setdefault(domain, {})[m] = st.mean(parvar_vals)

    n_above = sum(1 for m in models if model_mtld_means[m] > base["mtld"]["mean"])
    synthesis["mtld"][domain] = {
        "human_mean": base["mtld"]["mean"],
        "model_means": model_mtld_means,
        "n_models_above_human": n_above,
        "n_models_total": len(models),
    }
    if base_pv.get("mean") is not None:
        synthesis["parvar_human"][domain] = base_pv["mean"]

    # ---- length bands vs real distribution ----
    print("\n" + "-" * 78)
    print(f"[{domain}] LENGTH BANDS: hand-set scenario bands vs real human distribution")
    print("-" * 78)
    scen_path = ROOT / "scenarios" / "pilot" / f"{domain}.json"
    scen = json.loads(scen_path.read_text()) if scen_path.exists() else []
    ld = base["length_distribution"]
    print(f"Human overall (n={ld['overall']['n']:,}): "
          f"p10={ld['overall']['p10']} p25={ld['overall']['p25']} "
          f"median={ld['overall']['p50']} p75={ld['overall']['p75']} p90={ld['overall']['p90']}")
    band_los, band_his = [], []
    for s in scen:
        lo, hi = s["length_target"]["words"]
        band_los.append(lo)
        band_his.append(hi)
        print(f"  {s['id']:<26} hand-set=[{lo},{hi}]  "
              f"(human p25-p75=[{ld['overall']['p25']},{ld['overall']['p75']}], "
              f"p10-p90=[{ld['overall']['p10']},{ld['overall']['p90']}])")
    if band_los:
        recommended = (ld["overall"]["p10"], ld["overall"]["p90"])
        synthesis["bands"][domain] = {
            "hand_set_lo_range": [min(band_los), max(band_los)],
            "hand_set_hi_range": [min(band_his), max(band_his)],
            "human_p10_p90": [ld["overall"]["p10"], ld["overall"]["p90"]],
            "human_p25_p75": [ld["overall"]["p25"], ld["overall"]["p75"]],
            "recommended_overall_band": recommended,
        }
        print(f"\n  Hand-set lo range across {len(scen)} scenarios: [{min(band_los)}, {max(band_los)}]")
        print(f"  Hand-set hi range across {len(scen)} scenarios: [{min(band_his)}, {max(band_his)}]")
        print(f"  Human p10-p90 (a defensible overall outer band): "
              f"[{ld['overall']['p10']}, {ld['overall']['p90']}]")

    if "by_rough_intent_bucket" in ld and ld["by_rough_intent_bucket"]:
        print(f"\nBy rough intent bucket (cheap classifier, directional only, {domain} only):")
        for b, v in sorted(ld["by_rough_intent_bucket"].items(), key=lambda kv: -kv[1]["n"]):
            print(f"  {b:<20} n={v['n']:>6,}  p25={v['p25']:>4}  median={v['p50']:>4}  p75={v['p75']:>4}")


def print_synthesis(synthesis):
    print("\n\n")
    print("#" * 78)
    print("CROSS-DOMAIN SYNTHESIS")
    print("#" * 78)

    print("\n1. TELLS: validated (>=5x human, >=3/5 families) vs busted, per domain")
    print("-" * 78)
    for d in DOMAINS:
        v = synthesis["validated"].get(d, [])
        b = synthesis["busted"].get(d, [])
        print(f"  [{d}]")
        print(f"    validated: {v if v else '(none)'}")
        print(f"    busted:    {b if b else '(none)'}")
    all_validated_sets = [set(synthesis["validated"].get(d, [])) for d in DOMAINS]
    common_validated = set.intersection(*all_validated_sets) if all(all_validated_sets) else set()
    print(f"\n  Tells validated in ALL 4 domains: {sorted(common_validated) if common_validated else '(none)'}")

    print("\n2. LENGTH BANDS: hand-set vs real human distribution, per domain")
    print("-" * 78)
    for d in DOMAINS:
        b = synthesis["bands"].get(d)
        if not b:
            continue
        lo_lo, lo_hi = b["hand_set_lo_range"]
        hi_lo, hi_hi = b["hand_set_hi_range"]
        p10, p90 = b["human_p10_p90"]
        p25, p75 = b["human_p25_p75"]
        print(f"  [{d}] hand-set lo in [{lo_lo},{lo_hi}], hand-set hi in [{hi_lo},{hi_hi}]  "
              f"vs human p10-p90=[{p10},{p90}], p25-p75=[{p25},{p75}]")
        verdict = []
        if lo_lo < p10 * 0.5:
            verdict.append("some lo bands far BELOW human p10 (floor too permissive)")
        if hi_hi > p90 * 1.5:
            verdict.append("some hi bands far ABOVE human p90 (ceiling too permissive)")
        if hi_hi < p75:
            verdict.append("hi bands UNDERSHOOT human p75 (ceiling too tight vs real human length)")
        print(f"    -> {'; '.join(verdict) if verdict else 'roughly consistent with human distribution'}")

    print("\n3. MTLD REVERSAL: do models score higher lexical diversity than humans everywhere?")
    print("-" * 78)
    for d in DOMAINS:
        m = synthesis["mtld"].get(d)
        if not m:
            continue
        print(f"  [{d}] human={m['human_mean']:.1f}  models: " +
              ", ".join(f"{k}={v:.1f}" for k, v in sorted(m["model_means"].items(), key=lambda kv: -kv[1])))
        print(f"       {m['n_models_above_human']}/{m['n_models_total']} models scored ABOVE human MTLD")
    reversal_domains = [d for d in DOMAINS if synthesis["mtld"].get(d, {}).get("n_models_above_human", 0)
                        == synthesis["mtld"].get(d, {}).get("n_models_total", -1) and d in synthesis["mtld"]]
    partial_domains = [d for d in DOMAINS if d in synthesis["mtld"]
                        and 0 < synthesis["mtld"][d]["n_models_above_human"] < synthesis["mtld"][d]["n_models_total"]]
    no_reversal_domains = [d for d in DOMAINS if d in synthesis["mtld"]
                            and synthesis["mtld"][d]["n_models_above_human"] == 0]
    print(f"\n  ALL models above human in: {reversal_domains if reversal_domains else '(none)'}")
    print(f"  SOME models above human in: {partial_domains if partial_domains else '(none)'}")
    print(f"  NO models above human in: {no_reversal_domains if no_reversal_domains else '(none)'}")

    print("\n4. PARAGRAPH-VARIANCE FLATTENING: humans more structurally uneven than models?")
    print("-" * 78)
    for d in DOMAINS:
        hv = synthesis["parvar_human"].get(d)
        if hv is None:
            print(f"  [{d}] HUMAN paragraph variance is NULL (no measurable '\\n\\n' structure in this "
                  f"corpus/register -- see stats.json null_reason). Cannot assess flattening for {d}.")
            continue
        mv = synthesis["parvar_model"].get(d, {})
        print(f"  [{d}] human={hv:.2f}  models: " + ", ".join(f"{k}={v:.2f}" for k, v in sorted(mv.items(), key=lambda kv: -kv[1])))
        below = sum(1 for v in mv.values() if v < hv)
        print(f"       {below}/{len(mv)} models scored BELOW human paragraph variance (flattening replicated)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="all", choices=["all"] + DOMAINS)
    args = ap.parse_args()

    synthesis = {
        "validated": {}, "busted": {}, "dash": {}, "mtld": {},
        "parvar_human": {}, "parvar_model": {}, "bands": {},
    }
    domains = DOMAINS if args.domain == "all" else [args.domain]
    for d in domains:
        domain_report(d, synthesis)

    if args.domain == "all":
        print_synthesis(synthesis)


if __name__ == "__main__":
    main()
