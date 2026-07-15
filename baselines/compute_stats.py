"""Compute baseline stats for a cleaned human-baseline corpus.

Imports the metric functions straight from harness/analyze.py so every
number here is computed with the EXACT SAME code that scores model
outputs -- MTLD, burstiness, paragraph variance, tell regexes, and the
word tokenizer are not reimplemented. This is the whole point: the
"215x over human baseline" claims are only honest if human and model text
go through the identical pipeline.

Domain-agnostic since the slack/essay/social baselines were added: corpus
name, source URL, and any extra caveats (license, mojibake fix, era
caveats, target-band notes) are read straight out of that domain's
filter_funnel.json -- written once by filter.py, not re-typed here --
and passed through into stats.json as "corpus_notes" so nothing about a
domain's known limitations goes missing between the filter and the report.

Usage:
    python3 baselines/compute_stats.py --domain email
    python3 baselines/compute_stats.py --domain slack
    python3 baselines/compute_stats.py --domain essay
    python3 baselines/compute_stats.py --domain social

Reads baselines/{domain}/clean.jsonl (id, text, words per line) and
baselines/{domain}/filter_funnel.json (corpus provenance/notes).
Writes baselines/{domain}/stats.json.
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
from analyze import TELLS, burstiness, mtld, para_variance, tells_per_1k, words  # noqa: E402


# ---------------------------------------------------------------------------
# Cheap, unvalidated intent-bucket classifier -- EMAIL DOMAIN ONLY.
# Regex-based, documented as approximate -- NOT the same thing as the
# hand-authored scenario `category` field; this exists only so email's
# length distribution can be sliced a little finer than "all email
# everywhere". The request/scheduling/decline shape is specific to email's
# register and is not meaningful for chat/essay/social turns, so those
# three domains skip bucketing entirely (see "overall" as authoritative).
# ---------------------------------------------------------------------------
BUCKET_PATTERNS = [
    ("scheduling", re.compile(
        r"\b(meeting|schedule|calendar|conference call|available|call at|"
        r"monday|tuesday|wednesday|thursday|friday|a\.?m\.?|p\.?m\.?)\b", re.I)),
    ("thanks", re.compile(r"^\s*(thank you|thanks)\b", re.I)),
    ("decline_negative", re.compile(
        r"\b(unfortunately|can'?t|cannot|won'?t be able|not able to|no longer)\b", re.I)),
    ("request", re.compile(r"\?\s*$|\b(could you|can you|would you|please (let me know|advise|send))\b", re.I)),
    ("update_fyi", re.compile(r"\b(attached|fyi|please find|per your request|as discussed|update)\b", re.I)),
]


def classify_bucket(text: str) -> str:
    first_line = text.strip().splitlines()[0] if text.strip() else ""
    for name, rx in BUCKET_PATTERNS:
        if name == "thanks" and rx.search(first_line):
            return name
    for name, rx in BUCKET_PATTERNS:
        if name != "thanks" and rx.search(text):
            return name
    return "other"


def percentiles(vals, ps=(0.10, 0.25, 0.50, 0.75, 0.90)):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return {f"p{int(p*100)}": None for p in ps}
    n = len(vals)
    out = {}
    for p in ps:
        idx = min(int(p * n), n - 1)
        out[f"p{int(p*100)}"] = vals[idx]
    return out


def iqr_summary(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return {"mean": None, "median": None, "q1": None, "q3": None, "n": 0}
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    return {
        "mean": st.mean(vals_sorted),
        "median": vals_sorted[n // 2],
        "q1": vals_sorted[int(0.25 * n)],
        "q3": vals_sorted[min(int(0.75 * n), n - 1)],
        "n": n,
    }


def sentence_lengths(text: str):
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text.strip()) if s.strip()]
    return [len(words(s)) for s in sents]


def paragraph_lengths(text: str):
    paras = [p for p in text.split("\n\n") if p.strip()]
    return [len(words(p)) for p in paras]


# ---------------------------------------------------------------------------
# Dash breakdown BY FORM. analyze.py's TELLS only has em_dash (the glyph)
# and any_dash (the rhetorical move, all forms combined) -- deliberately,
# since TELLS feeds the model-scoring pipeline and that's the axis that
# matters there. But the email baseline's headline finding was that
# em-dash-only counting is a trap: EnronSent has ZERO em dashes in 5.98M
# words yet 5.41 dashes/1k words in other forms (" - " 4.43, "--" 0.98) --
# the corpus's 2001-plain-text keyboard/encoding era, not its writers'
# style. Every domain baseline must report the SAME by-form breakdown so
# each corpus's typography era is characterized explicitly rather than
# assumed. These four regexes are additive to (not a replacement for)
# analyze.py's em_dash/any_dash tells -- em_dash+en_dash+ascii_double_dash+
# spaced_hyphen should roughly partition any_dash's hits (any_dash's
# pattern is the logical OR of these four).
# ---------------------------------------------------------------------------
DASH_FORMS = {
    "em_dash": re.compile(r"—"),
    "en_dash": re.compile(r"–"),
    "ascii_double_dash": re.compile(r"(?<!-)--(?!-)"),
    "spaced_hyphen": re.compile(r"\s-\s"),
}


def dash_breakdown(rows, total_words):
    out = {}
    for name, rx in DASH_FORMS.items():
        hits = sum(len(rx.findall(r["text"])) for r in rows)
        out[name] = {
            "total_hits": hits,
            "pooled_rate_per_1k_words": 1000 * hits / total_words if total_words else 0.0,
        }
    any_hits = sum(len(re.findall(TELLS["any_dash"], r["text"])) for r in rows)
    out["any_dash"] = {
        "total_hits": any_hits,
        "pooled_rate_per_1k_words": 1000 * any_hits / total_words if total_words else 0.0,
    }
    return out


def load_funnel_notes(domain_dir: pathlib.Path):
    """Pull corpus/source_url/license/caveats straight from filter_funnel.json
    (written once by filter.py) instead of re-typing them here -- keeps a
    single source of truth per domain and guarantees stats.json can't drift
    out of sync with what the filter actually documents."""
    funnel_path = domain_dir / "filter_funnel.json"
    if not funnel_path.exists():
        return {}, {}
    funnel = json.loads(funnel_path.read_text())
    known_keys = {"source", "source_url", "seed", "min_words", "max_words", "target_ceiling", "funnel", "final_count"}
    notes = {k: v for k, v in funnel.items() if k not in known_keys}
    return funnel, notes


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--domain", default="email")
    args = ap.parse_args()

    domain_dir = ROOT / "baselines" / args.domain
    clean_path = domain_dir / "clean.jsonl"
    rows = [json.loads(l) for l in clean_path.read_text().splitlines() if l.strip()]

    funnel, corpus_notes = load_funnel_notes(domain_dir)
    corpus_desc = funnel.get("source", "unknown corpus")
    source_url = funnel.get("source_url", "")

    total_words = sum(r["words"] for r in rows)
    n_msgs = len(rows)

    # ---- length distribution ----
    overall_len = percentiles([r["words"] for r in rows])
    if args.domain == "email":
        by_bucket = defaultdict(list)
        for r in rows:
            by_bucket[classify_bucket(r["text"])].append(r["words"])
        bucket_dist = {b: {**percentiles(v), "n": len(v)} for b, v in by_bucket.items()}
        bucket_note = (
            "Cheap regex classifier over the cleaned text, NOT validated "
            "against human-labeled categories. Order of precedence: "
            "thanks (first line only) > scheduling > decline_negative > "
            "request > update_fyi > other. A message can match multiple "
            "patterns; only the first in precedence order is used. "
            "For rigor, treat 'overall' as authoritative and buckets as "
            "directional color."
        )
    else:
        bucket_dist = None
        bucket_note = (
            "No intent-bucket classifier for this domain -- the email "
            "classifier's categories (scheduling/thanks/decline/request/"
            "update) are email-register-specific and not meaningful here. "
            "'overall' is the only length-distribution cut for this domain."
        )

    # ---- tell counters: pooled rate is the denominator for every ratio claim ----
    tell_hits = {k: 0 for k in TELLS}
    tell_msgs_with_hit = {k: 0 for k in TELLS}
    per_msg_rates = defaultdict(list)
    for r in rows:
        n = max(r["words"], 1)
        for k, rx in TELLS.items():
            c = len(re.findall(rx, r["text"], re.I | re.M))
            tell_hits[k] += c
            if c > 0:
                tell_msgs_with_hit[k] += 1
            per_msg_rates[k].append(1000 * c / n)

    tells_out = {}
    for k in TELLS:
        tells_out[k] = {
            "pooled_rate_per_1k_words": 1000 * tell_hits[k] / total_words,
            "mean_per_message_rate_per_1k_words": st.mean(per_msg_rates[k]),
            "pct_messages_with_hit": tell_msgs_with_hit[k] / n_msgs,
            "total_hits": tell_hits[k],
        }

    # ---- MTLD / burstiness / paragraph variance ----
    mtld_vals, burst_vals, parvar_vals = [], [], []
    all_sent_lens, all_para_lens = [], []
    for r in rows:
        toks = words(r["text"])
        mtld_vals.append(mtld(toks))
        burst_vals.append(burstiness(r["text"]))
        parvar_vals.append(para_variance(r["text"]))
        all_sent_lens.extend(sentence_lengths(r["text"]))
        all_para_lens.extend(paragraph_lengths(r["text"]))

    dash_out = dash_breakdown(rows, total_words)
    parvar_summary = iqr_summary(parvar_vals)
    if parvar_summary["n"] == 0:
        parvar_summary["null_reason"] = (
            "analyze.py's para_variance() splits strictly on a literal "
            "'\\n\\n' -- every document in this cleaned corpus has 0 or 1 "
            "such boundary, so pstdev() is undefined for all of them "
            "(pstdev needs >=2 values) and every row contributes None. "
            "This is an honest null, not a bug: the source register/export "
            "has no recoverable paragraph structure for this domain (see "
            "filter.py docstring for why). Do NOT treat this null as "
            "'0 variance' -- it is 'not measurable from this source', a "
            "different claim."
        )

    stats = {
        "corpus": corpus_desc,
        "source_url": source_url,
        "domain": args.domain,
        "n_messages": n_msgs,
        "n_words_total": total_words,
        "length_distribution": {
            "overall": {**overall_len, "n": n_msgs},
            "by_rough_intent_bucket": bucket_dist,
            "bucket_note": bucket_note,
        },
        "tells_per_1k_words": tells_out,
        "tells_note": (
            "pooled_rate_per_1k_words = total regex hits across the whole "
            "corpus / total corpus words * 1000 -- this is the denominator "
            "for every 'Nx over human baseline' ratio claim. "
            "mean_per_message_rate is the average of each message's own "
            "per-1k rate (more sensitive to short high-rate outliers); "
            "pct_messages_with_hit is the simplest 'how common is this tell "
            "at all' number."
        ),
        "dash_breakdown_per_1k_words": dash_out,
        "dash_breakdown_note": (
            "Report dash usage BY FORM, not just the em-dash glyph -- the "
            "email/EnronSent baseline found 0 em dashes in 5.98M words "
            "(1999-2002 plain-text email literally could not encode "
            "U+2014) but 5.41/1k words in other dash forms combined. A "
            "near-zero em_dash rate here may be a typography-era/encoding "
            "artifact of THIS corpus, not evidence the writers avoided the "
            "rhetorical dash move -- always read em_dash next to any_dash "
            "and the individual en_dash/ascii_double_dash/spaced_hyphen "
            "rates before concluding anything about em-dash usage."
        ),
        "mtld": iqr_summary(mtld_vals),
        "burstiness_sentence_len_std": iqr_summary(burst_vals),
        "paragraph_length_variance": parvar_summary,
        "sentence_length_words": iqr_summary(all_sent_lens),
        "paragraph_length_words": iqr_summary(all_para_lens),
        "greeting_rate": tells_out["greeting"]["pct_messages_with_hit"],
        "signoff_rate": tells_out["signoff"]["pct_messages_with_hit"],
        "em_dash_per_1k_words": tells_out["em_dash"]["pooled_rate_per_1k_words"],
        "corpus_notes": corpus_notes,
    }

    out_path = domain_dir / "stats.json"
    out_path.write_text(json.dumps(stats, indent=2))
    print(f"wrote {out_path}")
    print(json.dumps({k: v for k, v in stats.items() if k not in
                       ("tells_per_1k_words", "length_distribution")}, indent=2))
    print("\nlength_distribution.overall:", json.dumps(stats["length_distribution"]["overall"], indent=2))
    print("\ndash breakdown /1k words:", json.dumps(dash_out, indent=2))


if __name__ == "__main__":
    main()
