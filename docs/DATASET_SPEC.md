# The Slop Index — Dataset Specification v1

*The benchmark "dataset" is five artifacts, versioned together. Companion docs: SPEC.md (benchmark design), DATASETS.md (source corpora research).*

> **⚠️ v1 scope note (Pangram headline, lean axes)**: v1 axes are **Slop Score (Pangram AI-likelihood, version-pinned) · Open cross-check (off-the-shelf Binoculars) · Conciseness · Homogeneity · Human pass/Cringe Elo (phase 2)** — no LLM judges, and nothing of our own to maintain (no in-house detector, no self-built calibration corpora — the run's own outputs are the known-AI calibration set by construction). Consequences for this spec: scenario packs need only **one prompt style**; the `constraints[]`, `facts[]`, and `world` annotations plus the constraint-checker registry (artifact #2) are **deferred to sequels**; **marker lists (artifact #3) are demoted to descriptive tell counters** — they power red-pen views and Tell Counter charts with baseline ratios shown for context, but no longer produce a scored composite, so the ≥5×/≥3-family validation gate is informational rather than score-gating. Baseline bundles (artifact #4) now serve detector-FPR calibration, conciseness length norms, and tell base rates. Generation matrix: 112 scenarios × 10 samples × ~7 models ≈ **7,800 outputs per run**. Splits, run artifacts, and versioning stand as written.

## Artifact overview

| # | Artifact | Path | What it is |
|---|---|---|---|
| 1 | **Scenario packs** | `scenarios/` | The benchmark tasks — one JSON per scenario, the heart of the dataset |
| 2 | **Constraint/checker registry** | `constraints/` | Enum of machine-checkable constraint types + checker code + unit tests |
| 3 | **Marker lists** | `markers/` | Per-domain validated slop markers with frequency-ratio evidence |
| 4 | **Baseline bundles** | `baselines/` | Processing scripts + filter specs + derived n-gram tables per human corpus |
| 5 | **Run artifacts** | `runs/` | JSONL of every generated output + metrics (published, HF-mirrored) |

Plus `calibration/`: self-generated AI corpora per domain (detector calibration only, never leaderboard-scored).

---

## 1. Scenario packs

### Counts & structure

| Domain | Categories | Scenarios | Notes |
|---|---|---|---|
| Email | 10 (cold outreach, warm intro reply, scheduling, decline/pushback, bad news, follow-up, support reply, internal update, negotiation, thank-you) | 30 | |
| Social | 7 (LinkedIn announce, LinkedIn lesson/hiring, X post, X thread, X reply/QT, IG caption, launch post) | 28 | LinkedIn flavors flagged `no_ratio_baseline` |
| Essay | 9 (opinion, blog post, personal essay, review, argumentative, cover letter, newsletter intro, commentary, response essay) | 27 | |
| Slack | 9 (DM favor ask, standup, review request, delay-to-boss, decline via DM, channel announcement, quick question, urgent ping reply, missed-message apology) | 27 | |
| **Total** | | **112** | |

- **Split**: 80/20 public/held-out, stratified so every category contributes ≥1 held-out scenario. Held-out batch rotated quarterly; retired held-outs graduate to public (proves they were ordinary).
- **Subsets (flags)**: `spine` (decline/pushback scenarios across domains — cave-rate scored) · `voice` (~20% carry persona voice samples — voice-fidelity scored) · `temptation` (fabrication traps — all scenarios have a closed world, but these are designed to tempt).
- **Every scenario** has both prompt styles (lazy + detailed) → generation matrix: 112 × 2 styles × 10 samples × ~7 models ≈ **15,700 outputs per full run**.

### Scenario JSON schema (annotated example)

```json
{
  "id": "email.decline.007",
  "version": 1,
  "domain": "email",                       // email | social | essay | slack
  "category": "decline_pushback",
  "split": "public",                       // public | heldout
  "flags": ["spine", "temptation"],

  "persona": {
    "role": "founder of a 4-person devtools startup",
    "voice_samples": []                    // 3-5 writing samples, only in `voice` scenarios
  },
  "recipient": {
    "name": "Dana Kim",
    "role": "procurement lead at MidCo",
    "relationship": "3 emails over 2 weeks"
  },
  "context_thread": [                      // 0-3 prior messages, authored in-register
    { "from": "recipient", "text": "...asked for 40% off, mentioned budget approval takes 2 weeks..." }
  ],
  "goal": "Decline the 40% discount but keep the deal alive",

  "world": {                               // closed world → Fabrication axis
    "policy": "closed",                    // essay domain uses "closed_specifics"
    "facts": [
      { "id": "w1", "text": "List price is $500/mo", "type": "number" },
      { "id": "w2", "text": "Max discount ever offered: 10% for annual prepay", "type": "policy" }
    ]
  },

  "facts": [                               // planted context → Context-uptake axis
    {
      "id": "f1",
      "text": "Dana said budget approval takes 2 weeks",
      "type": "thread_fact",               // name | thread_fact | shared_history | timely | evidence
      "patterns": ["budget approval", "two weeks", "2 weeks"],
      "semantic_ref": "Dana's budget approval process takes two weeks"
    }
  ],

  "prompts": {
    "lazy": "reply to dana saying no to the discount",
    "detailed": "Reply to Dana declining the 40% discount but offer the annual-prepay option. Keep it to 3 sentences, don't apologize, and write like a human — no corporate speak."
  },
  "constraints": [                         // → Steerability axis (detailed prompt only)
    { "id": "c1", "type": "max_sentences", "param": 3, "surface": "Keep it to 3 sentences" },
    { "id": "c2", "type": "ban_lexicon", "param": "apology", "surface": "don't apologize" },
    { "id": "c3", "type": "anti_slop_steer", "surface": "write like a human — no corporate speak" }
  ],

  "length_target": { "words": [40, 120] }, // from domain baseline norms
  "qa": { "authored_by": "…", "reviewed_by": 2, "dry_run_models": 2, "date": "…" }
}
```

Notes:
- `constraints[c3].type=anti_slop_steer` is present in EVERY detailed prompt — it powers slop-elasticity and is never obedience-scored.
- `facts[]` ⊆ information derivable from `world` + `context_thread`; every fact has surface patterns AND a semantic ref for the validated matcher.
- `world.policy="closed_specifics"` (essay): general knowledge allowed; only specific checkable claims (stats, quotes, citations) outside the world are fabrication-flagged.

### Authoring & QA pipeline
1. Seed from real situations (Enron intent dataset (MIT) + thread-keyed Enron first messages; support-intent taxonomies for support scenarios).
2. Two-person review per scenario: realism, register, completeness of `world` (no "the model legitimately had to invent X" holes).
3. Dry-run against 2 models: constraints must be checkable, facts matchable, prompts unambiguous.
4. Pilot discriminative check: scenario retained only if models actually differ on it (variance check).

---

## 2. Constraint/checker registry (`constraints/registry.json` + `checkers/`)

Every constraint type = deterministic checker + unit tests. v1 enum:

| type | param | checker |
|---|---|---|
| `max_words` / `max_chars` | int | count |
| `max_sentences` | int | pySBD splitter |
| `ban_markdown_lists` / `ban_headers` / `ban_bold` | — | regex |
| `ban_emoji` | — | unicode ranges |
| `ban_hashtags` | — | regex |
| `ban_lexicon` | lexicon name (apology, pricing, greeting, signoff) | lexicon match |
| `require_string` | alias list | string/alias presence |
| `first_person_only` | — | pronoun check |
| `single_message` (social: not a thread) | — | structure check |
| `no_interrogative_opener` | — | first-sentence check |
| `no_prompt_restate` | ngram overlap τ | overlap of output's first para vs prompt |
| `anti_slop_steer` | — | NOT obedience-scored; marks slop-elasticity prompts |

Rule: if it can't be checked deterministically, it can't be a scored constraint.

---

## 3. Marker lists (`markers/{domain}.json`)

Per marker record:
```json
{
  "surface": "i hope this email finds you well",
  "kind": "phrase",                        // word | phrase | regex_pattern
  "regex": "hope this (email|message) finds you",
  "freq_per_1k_model_pooled": 4.31,
  "freq_per_1k_baseline": 0.02,
  "ratio": 215.5,
  "families_elevated": ["gpt", "gemini", "grok"],
  "status": "validated"                    // candidate | validated | busted
}
```
- Candidates seeded from EQ-Bench slop lists + Wikipedia AI-catchphrases + community lists (~300).
- **Validation rule**: `ratio ≥ 5` vs the domain baseline AND elevated in ≥3 model families → `validated` (enters scoring). Everything else stays `candidate` or `busted` — busted folklore published (em-dash verdict per domain).
- Rebuilt each major version from the pilot/full runs; marker tables are release artifacts.

---

## 4. Baseline bundles (`baselines/{domain}/`)

Each bundle = `source.md` (corpus + link + license) + `filter.py` (deterministic, seeded) + `stats.json` (published derived artifacts). **Where a license blocks redistribution (Blog corpus NC, Reddit), we ship the script + the derived n-gram frequency tables, not the raw text** — scoring stays reproducible without redistributing corpora.

| Domain | Source → filter | Target n |
|---|---|---|
| Email | EnronSent: already header/sig-stripped; keep 30–400 words, English, MinHash dedupe, drop legal boilerplate lines | ~50k msgs |
| Essay | Blog Authorship Corpus: 150–1,500 words, strip HTML, dedupe; + ASAP essays as graded-register slice | 50k posts + 13k essays |
| Social | Reddit per-subreddit slices (list published: career/startup/writing/finance/casual mix), comments 20–300 words + selfposts, ≤2022-10-31, bot-list + [deleted] removed → 100k; Sentiment140 as tweet register (as-is); HN comments 10–200 words, 2015–2022 → 100k | 200k+ items |
| Slack | DISCO Discord: ≥3 words, English, merge consecutive same-author runs → 200k msgs; Ubuntu IRC supplement | 200k msgs |

`stats.json` per bundle: message/word counts, length distribution percentiles (→ `length_target` bands and register-mismatch norms), 1–3-gram frequency tables, greeting/sign-off/emoji base rates. Every filter is seeded + versioned; changing a filter bumps the dataset minor version.

---

## 5. Run artifacts (`runs/{run_id}/`)

- `manifest.json`: run_id, date, harness version, scenario-set version, marker-set version, model list with exact API model IDs + api-date, scaffold text hash, detector versions (Pangram model/date, Binoculars commit).
- `{model}.{domain}.jsonl` — one record per output:
```json
{
  "scenario_id": "email.decline.007", "style": "detailed", "sample": 4,
  "model": "gpt-5.x-2026-06", "temp": "default", "seed": null,
  "raw_output": "…full text…",
  "usage": { "in": 412, "out": 96 },
  "metrics": {
    "slop": { "lexical": 3.1, "patterns": 1.2, "cliche": 1, "register": 0.4, "length_infl": 1.6 },
    "constraints": { "c1": true, "c2": false },
    "facts": { "f1": "surface" },          // surface | semantic | absent
    "fabrication": { "flags": [ { "claim": "…", "verdict": "ungrounded", "judges": ["a","b","c"] } ] },
    "detect": { "pangram": 0.97, "binoculars": 0.81, "mode": "single" }   // mode: single | bundle
  }
}
```
- All raw outputs published (repo + HF dataset). `slopbench score` recomputes every metric from `raw_output` alone — metrics in the file are convenience, not authority.

---

## 6. Calibration corpora (`calibration/`)

- **Self-generated AI sets per domain** (confirmed gap — nothing public exists for email/social/Slack): same scenario suite, broader free generation, labeled by model/date. Used ONLY for detector calibration and marker discovery — never leaderboard-scored.
- External: RAID (MIT) + MAGE (Apache) slices for essay/general; HC3 as Dec-2022 "generation-zero" anchor.
- Human-side calibration: 1,000 held-out baseline items per domain for detector FPR reports.

---

## 7. Versioning, licensing, governance

- **Semver on the dataset as a whole**: v1.0 frozen at launch. Quarterly held-out rotation = minor bump. New scenarios/domains = minor. Filter or schema changes = major. Leaderboard always states the dataset version it was scored on.
- **Licenses**: scenarios, markers, checkers, scripts → MIT. Derived baseline stats → CC BY 4.0 with source citations. Raw model outputs → released with model-provider ToS notes.
- **Community submissions**: scenario PRs accepted post-launch with the QA checklist (two-review + dry-run + world-completeness); accepted ones enter the next minor version's public split. Game-submitted scenarios (phase 2) feed the same pipeline.
- **Integrity**: held-out scenarios live in a private repo; their hashes published in the public manifest so post-hoc tampering is provable-negative.
