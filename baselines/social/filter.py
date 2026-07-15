"""Sentiment140 -> clean.jsonl

Deterministic, seeded, documented human-social-post baseline filter for
The Slop Index. Source: Sentiment140 (Go, Bhayani, Huang, Stanford 2009),
1.6M tweets collected via the Twitter Search API in 2009 using emoticon
queries (:) / :( as a cheap sentiment label, full tweet text embedded --
no ID-only rehydration needed, unlike almost every other Twitter corpus of
this era. HF mirror `stanfordnlp/sentiment140`, downloaded as the
auto-converted parquet (single shard, 1,600,000 rows, 800k
positive-emoticon / 800k negative-emoticon by construction of the original
collection method -- the `sentiment` label is not used by this filter,
style is orthogonal to polarity).
https://huggingface.co/datasets/stanfordnlp/sentiment140

## THE HEADLINE CAVEAT: this is a 140-char-era, pre-@handle-reply-API corpus

Two things about 2009 Twitter do NOT generalize to "social media" broadly
and are flagged here loudly, not buried in a footnote:

  1. **140-character limit.** Twitter did not double the cap to 280 until
     Nov 2017. Every length percentile computed from this corpus is a
     ceiling artifact of the wire format, not a ceiling the writers chose.
     Modern X/LinkedIn/Instagram-caption posts (the actual registers the
     scenario pack targets) run measurably longer. Treat this baseline's
     length distribution as a FLOOR/lower-bound reference, not a target --
     compare_pilot.py must not silently import "p90 = 27 words" as if it
     were an honest ceiling for X posts today, let alone LinkedIn.
  2. **Reply convention, not the API field.** In 2009 there was no
     structured "in-reply-to" concept the API exposed the way it does now;
     addressing another user by leading "@handle" WAS the reply mechanic,
     and 43.5% of this corpus opens that way (696,753 / 1,600,000, measured
     directly). That is kept as authentic period style (see below), but it
     means the corpus skews heavily toward reply-register short bursts
     rather than standalone announcement/launch-post register, which is
     most of what the scenario pack's `social` domain actually asks models
     to write. Directional color, not a ratio-baseline-invalidating flaw --
     documented so nobody mistakes "mostly @-replies" for "mostly posts."

## What is cleaned vs. kept as authentic period style

KEPT, deliberately, because it IS the tweet as the author wrote it:
  - Inline "@handle" mentions/addressing (this is 2009 Twitter's actual
    reply grammar, not a header artifact the way an email's "To:" line is
    -- stripping it would misrepresent how much the author actually typed
    and would be over-cleaning, the same reasoning the email filter uses
    to keep salutations rather than strip them as noise).
  - Character elongation, ALL-lowercase, ellipses, emoticon-adjacent
    punctuation -- all authentic period texture.

CLEANED, because it is not authorial prose:
  - HTML entities (`&amp;`, `&lt;`, `&gt;`, `&quot;`) -- present in 94,458
    / 1.6M tweets (5.9%), an artifact of how the original API/scrape
    stored text, unescaped before word-counting or any tell regex runs.
  - Inline URLs -- stripped (not counted as words); a shortened link is
    not linguistic content and would otherwise inflate "word" counts with
    opaque tokens.
  - Literal "RT @handle:" retweet prefixes -- rare in this corpus (126 /
    1.6M, 0.008%; API-native retweets did not exist until 2010, this
    corpus predates that, so almost nothing here is a structural retweet)
    but dropped outright where present since it is not the poster's own
    sentence.

## Post-level filters (in this order; funnel counts reported)

  1. drop retweet-prefixed tweets ("RT @...")
  2. clean text (HTML-unescape, strip URLs, collapse whitespace)
  3. word count >= 3 (post-clean; matches the same floor used for the
     slack/chat domain -- no upper bound is imposed because the 140-char
     wire format already caps every tweet at roughly 25-30 words, see
     the headline caveat above)
  4. English heuristic (stopword-density + ASCII-alpha ratio; same
     loosened chat-register thresholds as the slack filter -- tweets drop
     articles/pronouns even more aggressively than chat)
  5. not spam/data-dump (digit-density and ALL-CAPS-word-density over the
     whole post, same whole-text shape as the essay filter's fix -- tweets
     are single-line by construction so a per-line check would be
     meaningless here too)
  6. exact-duplicate removal (normalized-text hash) -- catches
     automated/bot-app boilerplate (e.g. a since-defunct browser game's
     auto-tweet "isPlayer Has Died! Sorry", seen 210x verbatim in this
     corpus) WITHOUT needing a bespoke bot-username classifier, since
     Sentiment140 does not expose bot/verified flags -- the repeated exact
     text collapses to one representative sample, which is the correct
     style-baseline behavior whether the repetition came from a bot or
     from many different humans coincidentally posting "good morning"
  7. near-duplicate removal (5-gram-shingle MinHash-LSH, Jaccard >= 0.8)
  8. if the survivor pool exceeds TARGET_CEILING (120,000 -- chosen
     because tweets are short (compute is cheap either way) but a smaller
     cap keeps the corpus roughly comparable in scale to the other three
     domains rather than dwarfing them 2-10x for no statistical benefit),
     a seeded deterministic downsample to the ceiling (reported
     separately -- a cap, not a quality filter)

Output: baselines/social/clean.jsonl, one JSON object per line:
  {"id": "sent140-000001", "text": "...", "words": 14}

Run: python3 baselines/social/filter.py
"""
import html
import json
import pathlib
import random
import re
import sys
from collections import Counter

import pyarrow.parquet as pq

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "baselines"))
from analyze import words as tok_words  # noqa: E402
from _dedup import NearDupIndex, normalized_hash, shingles  # noqa: E402

RAW_DIR = pathlib.Path(__file__).resolve().parent / "raw"
OUT_PATH = pathlib.Path(__file__).resolve().parent / "clean.jsonl"
FUNNEL_PATH = pathlib.Path(__file__).resolve().parent / "filter_funnel.json"

SEED = 20260114
MIN_WORDS = 3
TARGET_CEILING = 120_000

RT_PREFIX_RE = re.compile(r"^\s*rt\s*@", re.I)
URL_RE = re.compile(r"(https?://\S+|www\.\S+)", re.I)
WHITESPACE_RE = re.compile(r"\s{2,}")

STOPWORDS = set(
    "the and to of a in is that it for you was on are with as i this be at by "
    "have from or an will can not we your if please thanks my me our but "
    "there so what all would just about out up so no do did been were".split()
)


def clean_text(raw: str) -> str:
    t = html.unescape(raw)
    t = URL_RE.sub(" ", t)
    t = WHITESPACE_RE.sub(" ", t)
    return t.strip()


def is_english(toks) -> bool:
    if len(toks) < MIN_WORDS:
        return False
    lower = [t.lower() for t in toks]
    stop_ratio = sum(1 for t in lower if t in STOPWORDS) / len(lower)
    alpha_chars = sum(1 for t in toks for c in t if c.isalpha())
    ascii_alpha = sum(1 for t in toks for c in t if c.isalpha() and c.isascii())
    ascii_ratio = ascii_alpha / alpha_chars if alpha_chars else 0
    if len(toks) <= 6:
        return ascii_ratio >= 0.90
    return stop_ratio >= 0.03 and ascii_ratio >= 0.90


def is_not_spam(text: str, toks) -> bool:
    """Same whole-text char/word-ratio shape as essay/filter.py's fix --
    tweets are single-line by construction (no internal newlines possible
    within a 140-char post), so a per-line check is meaningless here too."""
    if not toks:
        return False
    digit_chars = sum(1 for c in text if c.isdigit())
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars and digit_chars / (digit_chars + alpha_chars) > 0.15:
        return False
    long_toks = [t for t in toks if len(t) >= 3]
    caps_words = sum(1 for t in long_toks if t.isupper())
    if long_toks and caps_words / len(long_toks) > 0.5:
        return False
    return True


def main():
    shard = RAW_DIR / "sentiment140_train.parquet"
    if not shard.exists():
        print(f"ERROR: {shard} not found", file=sys.stderr)
        sys.exit(1)

    funnel = Counter()
    kept = []
    seen_hashes = set()
    ndi = NearDupIndex(seed=SEED)

    rows = pq.read_table(shard).to_pylist()
    for rec in rows:
        raw = rec["text"]
        funnel["1_raw_tweets"] += 1
        if RT_PREFIX_RE.match(raw):
            funnel["2_dropped_retweet"] += 1
            continue
        funnel["2_kept_not_retweet"] += 1

        cleaned = clean_text(raw)
        toks = tok_words(cleaned)
        n = len(toks)
        if n < MIN_WORDS:
            funnel["3_dropped_word_count"] += 1
            continue
        funnel["3_kept_word_count"] += 1

        if not is_english(toks):
            funnel["4_dropped_non_english"] += 1
            continue
        funnel["4_kept_english"] += 1

        if not is_not_spam(cleaned, toks):
            funnel["5_dropped_spam_dump"] += 1
            continue
        funnel["5_kept_not_spam"] += 1

        h = normalized_hash(cleaned)
        if h in seen_hashes:
            funnel["6_dropped_exact_dup"] += 1
            continue
        seen_hashes.add(h)
        funnel["6_kept_exact_unique"] += 1

        sh = shingles(toks)
        if ndi.is_duplicate(sh):
            funnel["7_dropped_near_dup"] += 1
            continue
        ndi.add(sh)
        funnel["7_kept_near_unique"] += 1

        kept.append({"text": cleaned, "words": n})

    funnel["8_pre_downsample_total"] = len(kept)
    if len(kept) > TARGET_CEILING:
        rnd = random.Random(SEED)
        order = list(range(len(kept)))
        rnd.shuffle(order)
        keep_idx = set(order[:TARGET_CEILING])
        kept = [m for i, m in enumerate(kept) if i in keep_idx]
    funnel["9_downsampled_to_ceiling"] = len(kept)

    with OUT_PATH.open("w") as f:
        for i, m in enumerate(kept, start=1):
            rec = {"id": f"sent140-{i:06d}", "text": m["text"], "words": m["words"]}
            f.write(json.dumps(rec) + "\n")

    funnel_report = {
        "source": "Sentiment140 (Go, Bhayani, Huang; Stanford 2009), collected via Twitter Search API 2009",
        "source_url": "https://huggingface.co/datasets/stanfordnlp/sentiment140",
        "seed": SEED,
        "min_words": MIN_WORDS,
        "target_ceiling": TARGET_CEILING,
        "era_caveat": (
            "2009 tweets are 140-char-limit era (pre-Nov-2017 280-char change); "
            "length norms here are a lower-bound/floor reference, not a modern "
            "ceiling. 43.5% of the raw corpus (696,753/1,600,000) opens with a "
            "leading @handle -- 2009's reply convention -- so this baseline skews "
            "toward reply-register bursts, not standalone announcement posts."
        ),
        "funnel": dict(funnel),
        "final_count": len(kept),
    }
    FUNNEL_PATH.write_text(json.dumps(funnel_report, indent=2))

    print("=" * 70)
    print("Sentiment140 filter funnel")
    print("=" * 70)
    for k, v in funnel.items():
        print(f"  {k:<40}{v:>10,}")
    print("-" * 70)
    print(f"  FINAL clean.jsonl tweets:              {len(kept):>10,}")
    print(f"  -> {OUT_PATH}")
    print(f"  -> {FUNNEL_PATH}")


if __name__ == "__main__":
    main()
