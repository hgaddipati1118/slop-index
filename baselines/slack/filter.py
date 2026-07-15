"""DISCO Discord corpus -> clean.jsonl

Deterministic, seeded, documented human-workplace-chat baseline filter for
The Slop Index. Source: DISCO -- "A Dataset of Discord Chat Conversations
for Software Engineering Research" (Subash, Kumar, Vadlamani, Chatterjee,
Baysal; MSR 2022). 1,508,093 messages / 28,712 disentangled conversations
from 4 developer-help Discord servers (python-general, clojurians, gophers
golang, racket-general), Nov 2019 - Oct 2020. Zenodo record 5886240,
"Other (Open)" license, direct download (no auth, no gating).
https://zenodo.org/records/5886240

## Why Discord-as-Slack-proxy

The scenario pack's "slack" domain is workplace/team chat register generally
(favor asks, standup updates, decline-via-DM, channel announcements, quick
questions) -- not literally Slack-the-product. DISCO is a Q&A-help register
Discord (closer to a dev team's #general than to a support ticket queue),
which DATASETS.md identifies as "the one ethically-clean Discord option"
for this register. No public Slack export corpus of comparable scale and
provenance exists (Slack workspace exports require org-admin access, are
almost never published, and the closest DISCO-style prior art -- Chatterjee
et al.'s Slack disentanglement study -- has no released text corpus, only
the modified E&C classifier DISCO's own authors reused).

## Corpus shape and the two decisions this filter has to make

The raw XML gives one <message> per send: <ts>, <user> (already
pseudonymized by the corpus authors -- random first names, not real
handles), <text>. Two structural facts drive everything below:

  1. **A "Slack message" is a turn, not a line.** People send multi-part
     thoughts as 3-4 rapid-fire separate sends ("to develop mobile apps:" /
     "is it better to learn kivy or..." / "someone?"). Scoring each XML
     <message> as its own document would make every human turn look like a
     4-word fragment and crater every length/burstiness stat. So: messages
     are grouped into turns FIRST (same author, no other author's message
     in between, gap-bounded -- see below), and every filter downstream
     (word count, English, dedup) operates on the assembled turn.

  2. **The export flattened newlines.** Every <text> value is single-line,
     even where the original Discord message clearly had internal line
     breaks (numbered lists run together as "1.foo2.bar3.baz" with no
     separator). This is a disclosed, uncorrectable limitation of the
     source export (DiscordChatExporter -> XML, per the corpus README) --
     paragraph-level structure within one raw message cannot be recovered.
     Turns built from >1 merged message DO get "\\n\\n"-joined at the
     merge points (each original send treated as its own paragraph-like
     unit -- a deliberate choice so analyze.py's para_variance(), which
     splits strictly on "\\n\\n", has something real to measure for
     multi-message turns), so multi-message turns carry SOME paragraph
     signal; single-message turns carry none (para_variance() needs >=2
     paragraphs to return non-null, so single-message turns contribute no
     paragraph-variance datapoint, the same way a single-paragraph email
     contributes none in the email baseline). This asymmetry is real and
     is reported, not smoothed over.

## Turn assembly

Within one XML file (one channel/period), messages are sorted by
timestamp, then walked in order. A new turn opens on the first message
seen; each subsequent message extends the open turn if (a) same user as
the turn's messages, and (b) gap since the turn's last message <=
GAP_MAX (10 min) -- otherwise the open turn closes and a new one starts
(even for the same user; this is the same "don't glue unrelated
episodes together" logic as the Enron segmenter's safety valve). A
second safety valve force-closes a turn at MAX_MSGS_PER_TURN (40) or
MAX_WORDS_PER_TURN_RAW (400) raw messages/words, same numbers/rationale
as the email filter's segmentation valve. Merged messages are
"\\n\\n"-joined (see the paragraph-signal note above).

## Per-message cleaning (before merge, applied to each raw <text>)

  - Strip fenced code (```lang...code...```, language tag glued to the
    fence with no space in this export, e.g. "```pyclass Person...") and
    inline `code spans` -- these are software-engineering Discord's
    dominant register but are not prose; stripping (not blanket-dropping
    the message) preserves surrounding authored sentences where present.
  - Strip a leading "> " quote marker (Discord manual reply-quote
    convention). Because newlines are flattened we cannot reliably find
    where the quoted span ends and the reply begins in a multi-line quote
    -- this only strips the two leading characters, a shallow, disclosed
    fix, not a full quote-removal.
  - Drop the message outright if it is a bot/moderation command: starts
    with "!" immediately followed by a letter (e.g. "!warn", "!resources",
    "!rule5" -- all observed in the corpus). Bare "/" was deliberately NOT
    treated as a command prefix: spot-checking found real human sentences
    starting with it ("/nitro has their own bot doesn't catch it...").
    There is no bot/user-type flag in this export (usernames are
    anonymized, so bot accounts are indistinguishable from humans by
    name) -- command-syntax and template-text pattern matching are the
    only available signals.
  - Drop the message outright if it matches a server-automation template
    (join/leave/ban/kick/pin/embed-placeholder boilerplate).
  - Drop the message outright if, after code-stripping, it is nothing but
    a bare URL.

## Turn-level filters (in this order; funnel counts reported)

  1. word count >= 3 (post-merge, post-cleaning turn text; matches the
     brief's "messages >=3 words" applied to the turn as the unit of
     analysis, consistent with "a Slack message is a turn, not a line")
  2. English heuristic (stopword-density + ASCII-alpha ratio; thresholds
     are LOWER than the email filter's because chat register habitually
     drops articles/pronouns -- "moving to postgres now" is valid English
     with zero stopwords. See is_english() docstring.)
  3. not spam/log-dump: reject turns that are mostly digit-heavy or
     ALL-CAPS lines (same shape as the email filter's table/data-dump
     check; no pronoun/register requirement here, unlike email, because
     terse technical chat legitimately has no first/second-person pronoun)
  4. exact-duplicate removal (normalized-text hash) -- catches copy-paste
     canned replies and repeated links, common in a help channel
  5. near-duplicate removal (5-gram-shingle MinHash-LSH, Jaccard >= 0.8)
  6. if the survivor pool exceeds TARGET_CEILING (250,000, the top of the
     brief's 150-250k target band), a seeded deterministic downsample to
     the ceiling (reported separately -- a cap, not a quality filter)

Output: baselines/slack/clean.jsonl, one JSON object per line:
  {"id": "disco-000001", "text": "...", "words": 42, "n_messages": 3}

Run: python3 baselines/slack/filter.py
"""
import datetime as dt
import json
import pathlib
import random
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "harness"))
sys.path.insert(0, str(ROOT / "baselines"))
from analyze import words as tok_words  # noqa: E402
from _dedup import NearDupIndex, normalized_hash, shingles  # noqa: E402

RAW_DIR = pathlib.Path(__file__).resolve().parent / "raw" / "extracted" / "data"
OUT_PATH = pathlib.Path(__file__).resolve().parent / "clean.jsonl"
FUNNEL_PATH = pathlib.Path(__file__).resolve().parent / "filter_funnel.json"

SEED = 20260114
MIN_TURN_WORDS = 3
TARGET_CEILING = 250_000  # top of the brief's 150-250k target band
GAP_MAX = dt.timedelta(minutes=10)
MAX_MSGS_PER_TURN = 40
MAX_WORDS_PER_TURN_RAW = 400

# ---------------------------------------------------------------------------
# Per-message cleaning regexes
# ---------------------------------------------------------------------------
FENCED_CODE_RE = re.compile(r"```[a-zA-Z0-9_+\-]{0,15}.*?```", re.S)
INLINE_CODE_RE = re.compile(r"`[^`]*`")
LEADING_QUOTE_RE = re.compile(r"^>\s?")
COMMAND_RE = re.compile(r"^!\s*[a-zA-Z]")
BOT_TEMPLATE_RE = re.compile(
    r"\b(has joined the (server|guild)|has been (banned|kicked|warned|muted)|"
    r"pinned a message|welcome to (the |)(server|guild)|\[embed\])\b", re.I)
URL_ONLY_RE = re.compile(r"^\s*<?https?://\S+>?\s*$", re.I)

# ---------------------------------------------------------------------------
# English + spam heuristics (chat-tuned: lower stopword bar than email --
# terse technical chat legitimately drops articles/pronouns)
# ---------------------------------------------------------------------------
STOPWORDS = set(
    "the and to of a in is that it for you was on are with as i this be at by "
    "have from or an will can not we your if please thanks my me our but "
    "there so what all would just about out up so no do did been were".split()
)


def is_english(toks) -> bool:
    if len(toks) < MIN_TURN_WORDS:
        return False
    lower = [t.lower() for t in toks]
    stop_ratio = sum(1 for t in lower if t in STOPWORDS) / len(lower)
    alpha_chars = sum(1 for t in toks for c in t if c.isalpha())
    ascii_alpha = sum(1 for t in toks for c in t if c.isalpha() and c.isascii())
    ascii_ratio = ascii_alpha / alpha_chars if alpha_chars else 0
    # Short turns (3-6 words) get a pass on stop_ratio if ascii_ratio is very
    # high -- "moving to postgres now" is 0 stopwords / 100% ascii and is
    # obviously English; the email thresholds (0.08 stopword floor) would
    # wrongly reject this whole register.
    if len(toks) <= 6:
        return ascii_ratio >= 0.90
    return stop_ratio >= 0.03 and ascii_ratio >= 0.90


def is_not_spam(text: str) -> bool:
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


def clean_message_text(raw: str) -> str:
    t = FENCED_CODE_RE.sub(" ", raw)
    t = INLINE_CODE_RE.sub(" ", t)
    t = LEADING_QUOTE_RE.sub("", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def parse_ts(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


def load_messages(fp: pathlib.Path):
    """Parse one DISCO XML file -> sorted list of (ts, user, raw_text)."""
    tree = ET.parse(fp)
    root = tree.getroot()
    msgs = []
    for m in root.findall("message"):
        ts_el, user_el, text_el = m.find("ts"), m.find("user"), m.find("text")
        if ts_el is None or user_el is None or text_el is None:
            continue
        text = text_el.text or ""
        if not text.strip():
            continue
        try:
            ts = parse_ts(ts_el.text.strip())
        except Exception:
            continue
        msgs.append((ts, user_el.text.strip(), text))
    msgs.sort(key=lambda r: r[0])
    return msgs


def messages_to_turns(msgs, funnel: Counter):
    """Apply per-message drops, then merge consecutive same-author runs
    (gap-bounded) into turns. Yields raw turn dicts: {"user", "texts"}."""
    filtered = []
    for ts, user, raw in msgs:
        funnel["1_raw_messages"] += 1
        if COMMAND_RE.match(raw.strip()):
            funnel["2_dropped_bot_command"] += 1
            continue
        if BOT_TEMPLATE_RE.search(raw):
            funnel["2_dropped_bot_template"] += 1
            continue
        cleaned = clean_message_text(raw)
        if not cleaned:
            funnel["2_dropped_code_only"] += 1
            continue
        if URL_ONLY_RE.match(cleaned):
            funnel["2_dropped_url_only"] += 1
            continue
        funnel["2_kept_message"] += 1
        filtered.append((ts, user, cleaned))

    turns = []
    cur_user, cur_texts, cur_last_ts, cur_words = None, [], None, 0
    for ts, user, text in filtered:
        n_words = len(tok_words(text))
        if (cur_user == user and cur_last_ts is not None
                and ts - cur_last_ts <= GAP_MAX
                and len(cur_texts) < MAX_MSGS_PER_TURN
                and cur_words < MAX_WORDS_PER_TURN_RAW):
            cur_texts.append(text)
            cur_words += n_words
            cur_last_ts = ts
        else:
            if cur_texts:
                turns.append({"user": cur_user, "text": "\n\n".join(cur_texts), "n_messages": len(cur_texts)})
            cur_user, cur_texts, cur_last_ts, cur_words = user, [text], ts, n_words
    if cur_texts:
        turns.append({"user": cur_user, "text": "\n\n".join(cur_texts), "n_messages": len(cur_texts)})
    return turns


def main():
    files = sorted(RAW_DIR.glob("**/*.xml"))
    files = [f for f in files if not f.name.endswith(".xml.out")]
    if not files:
        print(f"ERROR: no DISCO xml files found under {RAW_DIR}", file=sys.stderr)
        sys.exit(1)

    funnel = Counter()
    kept = []
    seen_hashes = set()
    ndi = NearDupIndex(seed=SEED)

    for fp in files:
        msgs = load_messages(fp)
        turns = messages_to_turns(msgs, funnel)
        for turn in turns:
            funnel["3_segmented_turns"] += 1
            text = turn["text"]
            toks = tok_words(text)
            n = len(toks)
            if n < MIN_TURN_WORDS:
                funnel["4_dropped_word_count"] += 1
                continue
            funnel["4_kept_word_count"] += 1

            if not is_english(toks):
                funnel["5_dropped_non_english"] += 1
                continue
            funnel["5_kept_english"] += 1

            if not is_not_spam(text):
                funnel["6_dropped_spam_logdump"] += 1
                continue
            funnel["6_kept_not_spam"] += 1

            h = normalized_hash(text)
            if h in seen_hashes:
                funnel["7_dropped_exact_dup"] += 1
                continue
            seen_hashes.add(h)
            funnel["7_kept_exact_unique"] += 1

            sh = shingles(toks)
            if ndi.is_duplicate(sh):
                funnel["8_dropped_near_dup"] += 1
                continue
            ndi.add(sh)
            funnel["8_kept_near_unique"] += 1

            kept.append({"text": text, "words": n, "n_messages": turn["n_messages"]})

    funnel["9_pre_downsample_total"] = len(kept)
    if len(kept) > TARGET_CEILING:
        rnd = random.Random(SEED)
        order = list(range(len(kept)))
        rnd.shuffle(order)
        keep_idx = set(order[:TARGET_CEILING])
        kept = [m for i, m in enumerate(kept) if i in keep_idx]
    funnel["10_downsampled_to_ceiling"] = len(kept)

    with OUT_PATH.open("w") as f:
        for i, m in enumerate(kept, start=1):
            rec = {"id": f"disco-{i:06d}", "text": m["text"], "words": m["words"], "n_messages": m["n_messages"]}
            f.write(json.dumps(rec) + "\n")

    funnel_report = {
        "source": "DISCO (Subash, Kumar, Vadlamani, Chatterjee, Baysal; MSR 2022)",
        "source_url": "https://zenodo.org/records/5886240",
        "seed": SEED,
        "min_turn_words": MIN_TURN_WORDS,
        "target_ceiling": TARGET_CEILING,
        "target_band_note": "brief target was 150-250k turns; ceiling is the band's top edge",
        "gap_max_minutes": GAP_MAX.total_seconds() / 60,
        "funnel": dict(funnel),
        "final_count": len(kept),
    }
    FUNNEL_PATH.write_text(json.dumps(funnel_report, indent=2))

    print("=" * 70)
    print("DISCO Discord filter funnel")
    print("=" * 70)
    for k, v in funnel.items():
        print(f"  {k:<40}{v:>10,}")
    print("-" * 70)
    print(f"  FINAL clean.jsonl turns:               {len(kept):>10,}")
    print(f"  -> {OUT_PATH}")
    print(f"  -> {FUNNEL_PATH}")


if __name__ == "__main__":
    main()
