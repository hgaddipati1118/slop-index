"""Blog Authorship Corpus (Schler et al. 2006) -> clean.jsonl

Deterministic, seeded, documented human long-form/essay baseline filter for
The Slop Index. Source: 681,288 blogger.com posts / 19,320 bloggers,
scraped August 2004 (Schler, Koppel, Argamon, Pennebaker). HF mirror
`barilan/blog_authorship_corpus`, downloaded here as the auto-converted
parquet (2 shards, 689,793 rows total -- the mirror's row count is
slightly higher than the oft-cited 681,288 because of how the mirror
re-split the original per-blogger XML files; every row is one already-
segmented post, no reconstruction needed, unlike EnronSent).

## LICENSE -- why this baseline ships stats only, never raw text

Blog Authorship Corpus is released for **research / non-commercial use**
(Koppel et al., u.cs.biu.ac.il/~koppel/BlogCorpus.htm). Per DATASETS.md
and repo-wide .gitignore policy, baselines/*/raw/ and baselines/**/*.jsonl
are never committed for ANY domain -- for this domain specifically that
policy is not just house style, it's the thing keeping us license-compliant.
Only the derived aggregate stats.json and filter_funnel.json are published.

## Two corpus-specific problems this filter has to solve

### 1. Mojibake hides the exact typography this project's dash/quote
analysis depends on

The raw `text` field contains **zero literal U+2014 em dashes** anywhere
in the corpus -- sounds like another EnronSent-style "the keyboard couldn't
do it" story, EXCEPT it isn't: the corpus was authored in the WYSIWYG
blogger.com editor of 2004, which happily accepted curly quotes and em/en
dashes. What actually happened is a **mojibake bug in how the corpus (or
an intermediate re-encoding step) was produced**: Windows-1252 smart
punctuation got byte-copied into what's nominally a Unicode string, landing
in the C1 control range (U+0080-U+009F) instead of being decoded as
Windows-1252. Confirmed directly: `\\x97` (cp1252's em dash byte) appears
780+ times per 100k posts, `\\x96` (en dash) ~1,500 times, `\\x92` (right
single quote / apostrophe) is the single most common byte in that range at
21,000+ per 100k posts, `\\x93`/`\\x94` (curly double quotes) a few
thousand more. If we counted em dashes on the raw text we would print "0
em dashes in a quarter-million posts" and it would be **flatly wrong** --
the opposite failure mode from EnronSent (there the zero was real; here a
zero would be an artifact of not fixing a known, mechanically-reversible
encoding bug). So: every post is passed through a byte-for-byte cp1252
remap of the U+0080-U+009F range BEFORE any tell-counting, dash-counting,
or quote-counting happens. This is not a stylistic normalization choice --
it is recovering the punctuation the blogger actually typed. Documented
here loudly per the project's standing em-dash-lesson rule: always check
whether a zero is a real absence or an encoding artifact before reporting it.

### 2. "urlLink" placeholder text and quiz-meme template posts are not
prose

The scraper that built this corpus replaced `<a href=...>` anchor text
with the literal token `urlLink` (present in ~27% of posts) -- e.g. "What
Chinese Symbol Are You? urlLink Quizilla". Left in, it reads as authorial
word salad it never was. It's stripped as a token everywhere it appears
(not just quiz posts) since it's a corpus artifact, not blogger prose, full
stop. Separately, blogger.com circa 2004 had a viral "online quiz result"
meme (Quizilla, Blogthings, and similar sites generate a canned paragraph
like "SPIRIT is your Chinese symbol! ... brought to you by Quizilla" that
users pasted into their blogs verbatim) -- this is templated third-party
copy, not the blogger's own writing, and is dropped as a whole post
(pattern: "brought to you by" + a known quiz-site name, or a "You are
___! ... brought to you by ___" shape). Distinguished from ordinary quotes/
excerpts because it's copy-pasted output of an automated generator, the
same category of thing the email filter drops as "ad banner" content.

## Per-post cleaning (before word-counting)

  - HTML-unescape entities (`&nbsp;`, `&amp;`, etc. -- ~8% of posts have
    at least one; no literal `<tag>` markup survived the corpus's own prep,
    confirmed by direct scan, so no tag-stripping is needed).
  - cp1252 mojibake fix (see above) -- applied to ALL posts, not just ones
    that look affected, since the corruption is silent by nature.
  - Strip the literal "urlLink" placeholder token.
  - Collapse repeated whitespace (many posts have 3-8 spaces where a link
    or image used to be).

## Post-level filters (in this order; funnel counts reported)

  1. drop quiz-template posts (see above) -- BEFORE word-count filtering,
     since these are commonly long enough to pass the count filter and
     would otherwise contaminate the corpus with non-authorial text
  2. word count in [150, 1500] (per brief)
  3. English heuristic (stopword-density + ASCII-alpha ratio; same shape
     as the email filter -- long-form blog prose is closer to email
     register than to terse chat, so email's thresholds are reused as-is
     rather than the loosened slack ones)
  4. not spam/data-dump (digit-density and ALL-CAPS-word-density check
     over the WHOLE post -- NOT per-line like the email filter, because
     these posts are single flowing paragraphs with no internal newlines;
     see is_not_spam() docstring for the false-positive bug this fixed)
  5. exact-duplicate removal (normalized-text hash) -- blogger.com had
     heavy chain-letter and copy-paste-meme culture ("100 things about
     me", song lyrics posts) that gets reposted near-verbatim across many
     different bloggers, not just within one blogger's own archive
  6. near-duplicate removal (5-gram-shingle MinHash-LSH, Jaccard >= 0.8)
  7. if the survivor pool exceeds TARGET_CEILING (60,000 -- the same
     number and rationale as the email baseline: MTLD is computed twice
     per document (forward + backward pass) and essay posts run ~3-4x
     longer than email messages, so an uncapped ~150-200k-post survivor
     pool would make compute_stats.py's MTLD pass the long pole of this
     whole pipeline for no accuracy benefit -- 60k posts already gives
     tight IQRs), a seeded deterministic downsample to the ceiling
     (reported separately -- a cap, not a quality filter)

Output: baselines/essay/clean.jsonl, one JSON object per line:
  {"id": "blogcorpus-000001", "text": "...", "words": 412}

Run: python3 baselines/essay/filter.py
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
MIN_WORDS, MAX_WORDS = 150, 1500
TARGET_CEILING = 60_000  # same ceiling+rationale as the email baseline

# ---------------------------------------------------------------------------
# cp1252-as-Unicode mojibake fix (see docstring section 1)
# ---------------------------------------------------------------------------
_CP1252_MAP = {}
for _o in range(0x80, 0xA0):
    try:
        _CP1252_MAP[chr(_o)] = bytes([_o]).decode("cp1252")
    except UnicodeDecodeError:
        pass
_CP1252_TABLE = str.maketrans(_CP1252_MAP)


def fix_cp1252_mojibake(s: str) -> str:
    return s.translate(_CP1252_TABLE)


URLLINK_RE = re.compile(r"\burlLink\b")
WHITESPACE_RE = re.compile(r"[ \t]{2,}")
BLANKLINES_RE = re.compile(r"\n{3,}")

QUIZ_TEMPLATE_RE = re.compile(
    r"(brought to you by\s+(urlLink\s+)?(quizilla|blogthings|blogquiz|quiz\s?galaxy)|"
    r"take this quiz\s*!|"
    r"^\s*you (are|represent)\b.{0,80}\bwhat\b.{0,40}\bare you\??)",
    re.I,
)

STOPWORDS = set(
    "the and to of a in is that it for you was on are with as i this be at by "
    "have from or an will can not we your if please thanks my me our but "
    "there so what all would just about out up so no do did been were".split()
)


def clean_text(raw: str) -> str:
    t = html.unescape(raw)
    t = fix_cp1252_mojibake(t)
    t = URLLINK_RE.sub(" ", t)
    t = WHITESPACE_RE.sub(" ", t)
    t = BLANKLINES_RE.sub("\n\n", t)
    return t.strip()


def is_english(toks) -> bool:
    if len(toks) < MIN_WORDS:
        return False
    lower = [t.lower() for t in toks]
    stop_ratio = sum(1 for t in lower if t in STOPWORDS) / len(lower)
    alpha_chars = sum(1 for t in toks for c in t if c.isalpha())
    ascii_alpha = sum(1 for t in toks for c in t if c.isalpha() and c.isascii())
    ascii_ratio = ascii_alpha / alpha_chars if alpha_chars else 0
    return stop_ratio >= 0.08 and ascii_ratio >= 0.97


def is_not_spam(text: str, toks) -> bool:
    """Char/word-ratio spam check, NOT the email filter's per-LINE check.

    Blog Authorship Corpus posts are single flowing paragraphs -- the
    parquet mirror preserves zero internal newlines in any post sampled
    (confirmed directly: 0/5000). Reusing email's per-line digit/caps
    heuristic against a corpus with exactly one "line" per post degenerates
    to "does this post contain >=6 digit characters ANYWHERE" (1 line
    flagged / 1 line total > the 0.5 ratio threshold) -- which nukes any
    ordinary diary post that mentions a time, a date, an age, or a dollar
    amount. Caught this via spot-check: it was silently discarding ~38%
    of otherwise-valid English posts, almost all clearly legitimate prose
    ("I stayed up until 2:00 in the morning..."). Fixed by measuring
    digit/caps density over the WHOLE post (chars and words) instead of
    per line, which is the actually-meaningful signal for a single-
    paragraph corpus and only fires on genuine table/log/lyrics dumps.
    """
    if not toks:
        return False
    digit_chars = sum(1 for c in text if c.isdigit())
    alpha_chars = sum(1 for c in text if c.isalpha())
    if alpha_chars and digit_chars / (digit_chars + alpha_chars) > 0.15:
        return False
    long_toks = [t for t in toks if len(t) >= 3]
    caps_words = sum(1 for t in long_toks if t.isupper())
    if long_toks and caps_words / len(long_toks) > 0.3:
        return False
    return True


def load_rows():
    for shard in sorted(RAW_DIR.glob("blog_*.parquet")):
        table = pq.read_table(shard)
        for rec in table.to_pylist():
            yield rec["text"]


def main():
    shards = sorted(RAW_DIR.glob("blog_*.parquet"))
    if not shards:
        print(f"ERROR: no blog_*.parquet files found under {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    funnel = Counter()
    kept = []
    seen_hashes = set()
    ndi = NearDupIndex(seed=SEED)

    for raw in load_rows():
        funnel["1_raw_posts"] += 1
        if QUIZ_TEMPLATE_RE.search(raw):
            funnel["2_dropped_quiz_template"] += 1
            continue
        funnel["2_kept_not_template"] += 1

        cleaned = clean_text(raw)
        toks = tok_words(cleaned)
        n = len(toks)
        if not (MIN_WORDS <= n <= MAX_WORDS):
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
            rec = {"id": f"blogcorpus-{i:06d}", "text": m["text"], "words": m["words"]}
            f.write(json.dumps(rec) + "\n")

    funnel_report = {
        "source": "Blog Authorship Corpus (Schler, Koppel, Argamon, Pennebaker 2006), scraped Aug 2004",
        "source_url": "https://huggingface.co/datasets/barilan/blog_authorship_corpus",
        "license": "research / non-commercial -- stats-only output, raw text never committed",
        "seed": SEED,
        "min_words": MIN_WORDS,
        "max_words": MAX_WORDS,
        "target_ceiling": TARGET_CEILING,
        "mojibake_note": (
            "raw text has 0 literal U+2014 but nonzero cp1252-as-Unicode "
            "mojibake em/en dashes and curly quotes in the C1 control range "
            "(U+0080-U+009F); fixed via cp1252 remap before any tell-counting"
        ),
        "funnel": dict(funnel),
        "final_count": len(kept),
    }
    FUNNEL_PATH.write_text(json.dumps(funnel_report, indent=2))

    print("=" * 70)
    print("Blog Authorship Corpus filter funnel")
    print("=" * 70)
    for k, v in funnel.items():
        print(f"  {k:<40}{v:>10,}")
    print("-" * 70)
    print(f"  FINAL clean.jsonl posts:               {len(kept):>10,}")
    print(f"  -> {OUT_PATH}")
    print(f"  -> {FUNNEL_PATH}")


if __name__ == "__main__":
    main()
