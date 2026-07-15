"""EnronSent -> clean.jsonl

Deterministic, seeded, documented human-email baseline filter for The Slop
Index. Source corpus: EnronSent v1.0 (Styler 2011), 96,106 messages from the
sent/sent_items folders of the Enron maildir, already stripped of headers,
subjects, and Enron-specific signature blocks by the corpus author. Public
domain. http://wstyler.ucsd.edu/enronsent/

## The core problem this script solves

EnronSent's own cleaning script concatenated every sent-mail body into 45
flat text files with NO per-message delimiter -- no blank-line convention
reserved for message boundaries, no ID, nothing. (Confirmed against the
shipped README.txt: "I chose to make the script more aggressive, and err to
the side of losing human generated data" -- boundaries were not a design
goal.) So step zero here is reconstructing plausible message boundaries
before any of the requested filters (30-400 words, English, dedupe, etc.)
can even be applied to "a message" rather than to an arbitrary window.

## Segmentation heuristic (documented, lossy, and said plainly)

Blank-line-delimited blocks are the finest unit the corpus gives us. We
walk them and treat two kinds of block as boundary signals:

  - GREETING block: "Hi Larry," / "Ina," / "Dear Team," etc. -- opens a new
    message. Closes and starts a fresh one.
  - SIGNOFF block: "Thanks," "Best regards," or a short bare name on its
    own line ("Phillip") -- closes the current message (block included).
  - NOISE/residual-header block: leftover Lotus-Notes/Outlook fragments
    that escaped the corpus author's header stripper, e.g.
    "Jeff Richter\n09/06/2000 07:39 AM" or
    "Enron-admin@FSDDataSvc.com on 09/06/2000 10:12:33 AM". These close
    the current message WITHOUT including the block, and no new message
    opens until the next greeting -- this is what keeps forwarded press
    clippings and mailing-list dumps (which commonly follow these residual
    headers) out of a legitimate personal message.
  - Safety valve: if 40 blocks or ~700 words accumulate with no boundary
    (long forwarded report with no greeting/signoff at all), force-close.
    The 30-400 word filter downstream discards these anyway; this just
    caps the cost of scanning them.

v1 of this segmenter required a greeting to open a message and silently
dropped any body block with nothing open (a "we'd rather under-recover
than mis-merge" bias). That recovered only ~42k candidates from 96k
messages (most real business email does not open "Hi X,") and produced
too few clean survivors. **Current version**: body blocks are also
allowed to open a new ("headless") message -- every span between two
boundary markers (greeting-start / signoff-end / noise-reset / file
start) becomes a candidate message, whether or not it happens to open
with a salutation. This roughly 2.5x's recovered candidates (~106k) at
the cost of an acknowledged risk: two genuinely separate short messages
sitting back-to-back with no greeting/signoff/residual-header between
them (rare, but it happens -- e.g. a quoted-reply digest of several short
notes) can get glued into one candidate. Spot-checked samples show this
is a minority pattern, not the norm; it is a disclosed, not hidden,
limitation of working with a corpus that shipped with zero message
delimiters.

## Per-message cleaning (line level)

Within an assembled candidate message, before word-counting:
  - Drop lines starting with ">" (quoted reply lines).
  - Truncate the message at the first line matching "-----Original
    Message-----", "-----Forwarded by-----"-style separators, or
    "Forwarded by" -- content after is someone else's writing, not the
    sender's.
  - Drop legal-boilerplate lines (confidentiality/privilege notices,
    "intended recipient", "please notify the sender", "unauthorized
    disclosure", etc.) -- Enron's own scrubber caught most of these but
    the README documents that some escaped ("no shortage of ... probably
    errant headers that escaped the scrubber").
  - Drop bare-URL lines (mailing-list/banner artifacts, not prose).
  - Drop residual date-time header lines that appear mid-message.
  - Drop ad-injection banner lines ("Get your FREE download of MSN
    Explorer...", "create your own public profile...") -- a known
    EnronSent-era Hotmail/MSN footer artifact that survived the corpus
    author's scrubber.
  - Drop pure separator lines (rows of 8+ underscores/dashes/equals/stars).

## Message-level filters (in this order; funnel counts reported)

  1. word count in [30, 400] (post line-cleaning)
  2. English heuristic (stopword-density + ASCII-alpha ratio)
  3. "plausibly business/personal register": at least one first- or
     second-person pronoun present (I, we, you, ...) -- screens out
     forwarded news articles / press releases / policy dumps that
     survived segmentation but contain no authorial voice at all.
  4. not a table/data dump (too many digit-heavy or ALL-CAPS lines)
  5. exact-duplicate removal (normalized-text hash)
  6. near-duplicate removal (5-gram-shingle MinHash-LSH, Jaccard >= 0.8)
  7. if the survivor pool exceeds the 60k target ceiling, a seeded
     deterministic downsample to 60,000 (reported separately -- this is
     a cap, not a quality filter)

Output: baselines/email/clean.jsonl, one JSON object per line:
  {"id": "enronsent-000001", "text": "...", "words": 87}

Run: python3 baselines/email/filter.py
"""
import hashlib
import json
import pathlib
import random
import re
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
from analyze import words as tok_words  # noqa: E402  (shared tokenizer w/ analyze.py)

RAW_DIR = pathlib.Path(__file__).resolve().parent / "raw" / "enronsent"
OUT_PATH = pathlib.Path(__file__).resolve().parent / "clean.jsonl"
FUNNEL_PATH = pathlib.Path(__file__).resolve().parent / "filter_funnel.json"

SEED = 20260114
MIN_WORDS, MAX_WORDS = 30, 400
TARGET_CEILING = 60_000
MAX_BLOCKS_PER_MSG = 40
MAX_WORDS_PER_MSG_RAW = 700  # safety valve during segmentation, not the real filter

# ---------------------------------------------------------------------------
# Segmentation regexes
# ---------------------------------------------------------------------------
GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|dear|good morning|good afternoon|good evening|greetings)\b",
    re.I,
)
NAME_COMMA_RE = re.compile(r"^\s*[A-Z][A-Za-z.\-']{1,20}(\s+[A-Z][A-Za-z.\-']{1,20}){0,2},\s*$")
SIGNOFF_WORD_RE = re.compile(
    r"^\s*(thanks|thank you|thx|best|best regards|kind regards|warm regards|"
    r"regards|sincerely|cheers|talk soon|take care|later)[.,!]?\s*$",
    re.I,
)
BARE_NAME_RE = re.compile(r"^\s*[A-Z][a-zA-Z.\-']{1,20}\s*$")
RESIDUAL_HEADER_RE = re.compile(
    r"(\b\S+@\S+\s+on\s+\d{1,2}/\d{1,2}/\d{2,4}\b)|"
    r"(^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*(AM|PM)\s*$)",
    re.I | re.M,
)

# ---------------------------------------------------------------------------
# Line-level cleaning regexes
# ---------------------------------------------------------------------------
QUOTE_LINE_RE = re.compile(r"^\s*>")
FORWARD_BOUNDARY_RE = re.compile(
    r"^\s*-{3,}\s*(original message|forwarded by|forwarded message)\s*-{0,3}\s*$"
    r"|^\s*forwarded by\b",
    re.I,
)
HEADER_LINE_RE = re.compile(r"^\s*(from|to|cc|bcc|subject|sent|date)\s*:\s*\S", re.I)
DATE_TIME_LINE_RE = re.compile(r"^\s*\d{1,2}/\d{1,2}/\d{2,4}\s+\d{1,2}:\d{2}\s*(AM|PM)\s*$", re.I)
URL_ONLY_LINE_RE = re.compile(r"^\s*(https?://|www\.)\S+\s*$", re.I)
LEGAL_BOILERPLATE_RE = re.compile(
    r"(confidential|privileged|intended recipient|please notify the sender|"
    r"unauthorized (review|use|disclosure)|delete (this|the) e?-?mail|"
    r"do not disseminate|this (e-?mail|message|communication) (is|may)|"
    r"disclaimer)",
    re.I,
)
AD_BANNER_RE = re.compile(
    r"(get your free|create your own public profile|click here to|"
    r"download msn explorer|unsubscribe|subscribe to)",
    re.I,
)
SEPARATOR_LINE_RE = re.compile(r"^\s*[_\-=*]{8,}\s*$")

PRONOUN_RE = re.compile(r"\b(i|i'm|i'll|i've|i'd|we|we're|we'll|we've|you|you're|your|yours)\b", re.I)
DIGIT_GROUP_RE = re.compile(r"\d")


def read_file(path: pathlib.Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return path.read_text(encoding="latin-1")


def split_blocks(text: str):
    return [b for b in re.split(r"\n\s*\n+", text) if b.strip()]


def classify_block(block: str):
    stripped = block.strip()
    first_line = stripped.splitlines()[0].strip() if stripped else ""
    if RESIDUAL_HEADER_RE.search(stripped):
        return "noise"
    if GREETING_RE.match(first_line) or (NAME_COMMA_RE.match(first_line) and len(stripped.splitlines()) <= 2):
        return "greeting"
    if len(stripped.splitlines()) <= 2 and (SIGNOFF_WORD_RE.match(first_line) or BARE_NAME_RE.match(first_line)):
        return "signoff"
    return "body"


def segment_file(text: str):
    """Yield raw candidate-message strings (list of block strings joined)."""
    blocks = split_blocks(text)
    current, cur_words = [], 0
    for b in blocks:
        kind = classify_block(b)
        if kind == "noise":
            if current:
                yield "\n\n".join(current)
            current, cur_words = [], 0
            continue
        if kind == "greeting":
            if current:
                yield "\n\n".join(current)
            current, cur_words = [b], len(tok_words(b))
            continue
        if kind == "signoff":
            if current:
                current.append(b)
                yield "\n\n".join(current)
                current, cur_words = [], 0
            # signoff with no open message: drop it, nothing to close
            continue
        # body block: append to an open message, OR open a new "headless"
        # message (no greeting recovered -- still a real span of prose
        # bounded by the nearest greeting/signoff/noise boundary on each
        # side). Only a minority of real business email opens with "Hi X,";
        # requiring a greeting to start a message under-recovers badly (see
        # docstring/report), so headless spans are allowed, bounded by the
        # same boundary markers as everything else.
        current.append(b)
        cur_words += len(tok_words(b))
        if len(current) >= MAX_BLOCKS_PER_MSG or cur_words >= MAX_WORDS_PER_MSG_RAW:
            yield "\n\n".join(current)
            current, cur_words = [], 0
    if current:
        yield "\n\n".join(current)


# ---------------------------------------------------------------------------
# Line-level cleaning of one candidate message
# ---------------------------------------------------------------------------
def clean_message(raw: str) -> str:
    lines = raw.split("\n")
    kept = []
    for ln in lines:
        if FORWARD_BOUNDARY_RE.match(ln):
            break  # truncate: everything after is forwarded/quoted content
        if QUOTE_LINE_RE.match(ln):
            continue
        if HEADER_LINE_RE.match(ln):
            continue
        if DATE_TIME_LINE_RE.match(ln):
            continue
        if URL_ONLY_LINE_RE.match(ln):
            continue
        if LEGAL_BOILERPLATE_RE.search(ln):
            continue
        if AD_BANNER_RE.search(ln):
            continue
        if SEPARATOR_LINE_RE.match(ln):
            continue
        kept.append(ln)
    text = "\n".join(kept)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# English + register heuristics
# ---------------------------------------------------------------------------
STOPWORDS = set(
    "the and to of a in is that it for you was on are with as i this be at by "
    "have from or an will can not we your if please thanks my me our but "
    "there so what all would just about out up so no do did been were".split()
)


def is_english(toks) -> bool:
    if len(toks) < MIN_WORDS:
        return False
    lower = [t.lower() for t in toks]
    stop_ratio = sum(1 for t in lower if t in STOPWORDS) / len(lower)
    alpha_chars = sum(1 for t in toks for c in t if c.isalpha())
    ascii_alpha = sum(1 for t in toks for c in t if c.isalpha() and c.isascii())
    ascii_ratio = ascii_alpha / alpha_chars if alpha_chars else 0
    return stop_ratio >= 0.08 and ascii_ratio >= 0.97


def is_business_register(text: str, toks) -> bool:
    if not PRONOUN_RE.search(text):
        return False
    lines = [l for l in text.split("\n") if l.strip()]
    if not lines:
        return False
    digit_heavy = sum(1 for l in lines if sum(c.isdigit() for c in l) >= 6)
    caps_heavy = sum(1 for l in lines if len(l.strip()) >= 15 and l.strip().isupper())
    if digit_heavy / len(lines) > 0.5:
        return False
    if caps_heavy / len(lines) > 0.3:
        return False
    return True


# ---------------------------------------------------------------------------
# Dedup: exact normalized-hash + 5-gram-shingle MinHash-LSH
# ---------------------------------------------------------------------------
def normalized_hash(text: str) -> str:
    norm = re.sub(r"[^a-z0-9 ]", "", text.lower())
    norm = re.sub(r"\s+", " ", norm).strip()
    return hashlib.sha1(norm.encode()).hexdigest()


def shingles(toks, k=5):
    lower = [t.lower() for t in toks]
    if len(lower) < k:
        return {" ".join(lower)}
    return {" ".join(lower[i : i + k]) for i in range(len(lower) - k + 1)}


NUM_HASHES = 8
NUM_BANDS = 2
ROWS_PER_BAND = NUM_HASHES // NUM_BANDS
_rnd = random.Random(SEED)
_MERSENNE = (1 << 61) - 1
_COEFFS = [(_rnd.randrange(1, _MERSENNE), _rnd.randrange(0, _MERSENNE)) for _ in range(NUM_HASHES)]


def minhash_sig(sh: set):
    hashed = [int(hashlib.md5(s.encode()).hexdigest(), 16) for s in sh]
    sig = []
    for a, b in _COEFFS:
        sig.append(min((a * h + b) % _MERSENNE for h in hashed))
    return tuple(sig)


def jaccard(a: set, b: set) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


class NearDupIndex:
    def __init__(self):
        self.bands = [dict() for _ in range(NUM_BANDS)]
        self.shingle_sets = {}

    def is_duplicate(self, idx, sh: set, sig: tuple) -> bool:
        candidates = set()
        for bi in range(NUM_BANDS):
            key = sig[bi * ROWS_PER_BAND : (bi + 1) * ROWS_PER_BAND]
            candidates |= set(self.bands[bi].get(key, []))
        for cidx in candidates:
            if jaccard(sh, self.shingle_sets[cidx]) >= 0.8:
                return True
        return False

    def add(self, idx, sh: set, sig: tuple):
        self.shingle_sets[idx] = sh
        for bi in range(NUM_BANDS):
            key = sig[bi * ROWS_PER_BAND : (bi + 1) * ROWS_PER_BAND]
            self.bands[bi].setdefault(key, []).append(idx)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------
def main():
    files = sorted(RAW_DIR.glob("enronsent[0-9][0-9]"))
    if not files:
        print(f"ERROR: no enronsent* files found under {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    funnel = Counter()
    kept = []
    seen_hashes = set()
    ndi = NearDupIndex()

    for fp in files:
        text = read_file(fp)
        for raw_msg in segment_file(text):
            funnel["1_segmented_candidates"] += 1
            cleaned = clean_message(raw_msg)
            toks = tok_words(cleaned)
            n = len(toks)
            if not (MIN_WORDS <= n <= MAX_WORDS):
                funnel["2_dropped_word_count"] += 1
                continue
            funnel["2_kept_word_count"] += 1

            if not is_english(toks):
                funnel["3_dropped_non_english"] += 1
                continue
            funnel["3_kept_english"] += 1

            if not is_business_register(cleaned, toks):
                funnel["4_dropped_no_personal_voice_or_table"] += 1
                continue
            funnel["4_kept_register"] += 1

            h = normalized_hash(cleaned)
            if h in seen_hashes:
                funnel["5_dropped_exact_dup"] += 1
                continue
            seen_hashes.add(h)
            funnel["5_kept_exact_unique"] += 1

            sh = shingles(toks)
            sig = minhash_sig(sh)
            idx = len(kept)
            if ndi.is_duplicate(idx, sh, sig):
                funnel["6_dropped_near_dup"] += 1
                continue
            ndi.add(idx, sh, sig)
            funnel["6_kept_near_unique"] += 1

            kept.append({"text": cleaned, "words": n})

    funnel["7_pre_downsample_total"] = len(kept)
    if len(kept) > TARGET_CEILING:
        rnd = random.Random(SEED)
        order = list(range(len(kept)))
        rnd.shuffle(order)
        keep_idx = set(order[:TARGET_CEILING])
        kept = [m for i, m in enumerate(kept) if i in keep_idx]
        funnel["8_downsampled_to_ceiling"] = len(kept)
    else:
        funnel["8_downsampled_to_ceiling"] = len(kept)

    with OUT_PATH.open("w") as f:
        for i, m in enumerate(kept, start=1):
            rec = {"id": f"enronsent-{i:06d}", "text": m["text"], "words": m["words"]}
            f.write(json.dumps(rec) + "\n")

    funnel_report = {
        "source": "EnronSent v1.0 (Styler 2011)",
        "source_url": "https://wstyler.ucsd.edu/enronsent/",
        "seed": SEED,
        "min_words": MIN_WORDS,
        "max_words": MAX_WORDS,
        "target_ceiling": TARGET_CEILING,
        "funnel": dict(funnel),
        "final_count": len(kept),
    }
    FUNNEL_PATH.write_text(json.dumps(funnel_report, indent=2))

    print("=" * 70)
    print("EnronSent filter funnel")
    print("=" * 70)
    for k, v in funnel.items():
        print(f"  {k:<40}{v:>10,}")
    print("-" * 70)
    print(f"  FINAL clean.jsonl messages:            {len(kept):>10,}")
    print(f"  -> {OUT_PATH}")
    print(f"  -> {FUNNEL_PATH}")


if __name__ == "__main__":
    main()
