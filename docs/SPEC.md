# The Slop Index — v1 Spec

> ## ⚠️ SUPERSEDED HEADLINE — read PILOT_FINDINGS.md first
> **Pilot 001 (2026-07-14) returned NO-GO on the Pangram headline.** 18 texts across 6 models and 65–544 words all scored **100% AI, Confidence High** — zero variance. Pangram's number is a *composition* score that pins at 100 for any fully-AI text by construction: a great detector, a useless ranking axis.
>
> **The headline is therefore the mechanical composite** (validated in the same pilot: conciseness, homogeneity/opener-repetition, lexical diversity, burstiness, paragraph variance, and tell counters all separate the models with disjoint CIs). Pangram becomes a corroborating column and the null result becomes the launch story: *"the best AI detector in the world says all six frontier models are 100% AI, every time. It cannot tell them apart. So we built something that can."*
>
> Also falsified: register mismatch ("every model Slacks like a cover letter") — 0% sign-offs, in-band lengths. Do not build on it; publish it as busted folklore.
>
> Everything below still describes the Pangram-headline design; treat the scoring section as superseded by PILOT_FINDINGS.md until this spec is rewritten for v2.

*Working name: **The Slop Index** (slopindex.ai). Four domains: **Email · Social media · Essay/long-form · Slack/workplace chat**. Game surface later: findsyouwell.ai. Companion docs: IDEAS.md (concepts), RESEARCH.md (sources), DATASETS.md (verified corpora), DATASET_SPEC.md (schemas), RUBRICS.md (scoring rules).*

## One-liner

Measures how much AI slop each frontier model produces across the four places people actually make it write — email, social posts, essays, and Slack messages — **scored by the industry's most accurate independent AI detector (Pangram)**, calibrated on provenance-clean pre-AI human baselines, with conciseness, homogeneity, and (phase 2) human judgment as companion axes. No LLM judges anywhere.

## v1 scoreboard (final axis set)

| # | Axis | Question | Method | Shareable line |
|---|---|---|---|---|
| 1 | **Slop Score** (headline) | How AI does it read? | **Mean Pangram AI-likelihood (0–100)**, version-pinned + date-stamped; % flagged at default threshold also reported; bundle mode for short-form (labeled) | "Model X's emails read 98% AI; Model Y's, 71%" |
| 2 | **Open cross-check** | Same verdict from an open detector? | **Binoculars, off-the-shelf, run as-is** — nothing of our own to build or maintain; the free-to-reproduce sibling column | "Two independent detectors agree" |
| 3 | **Conciseness** | Does it get to the point? | Words vs the scenario's human-norm band (from baseline length distributions); log-scaled inflation; short never penalized | "96 words for a two-sentence job" |
| 4 | **Homogeneity** | Does it all sound the same? | Pairwise embedding similarity + self-BLEU across 10 samples/scenario; **opener entropy**; cross-model centroid distance (fingerprint tree) | "Every cold email 84% identical to every other one" |
| 5 | **Human pass / Cringe Elo** *(crowd, phase 2)* | Do people fall for it? | Spot the Slop game: blind pairwise votes — Turing vote, reply vote (email/Slack), cringe vote (social) → Elo | "Passes as human 47% of the time" |

**Descriptive tell counters (not scored — the red-pen/content layer):** em-dashes per 1k words · "I hope this email finds you well" % · "thrilled to announce" % · "delve" per essay · % of Slack messages with a formal sign-off · emoji per message · hedge density · apology rate · "As an AI…" disclaimer rate · greeting/sign-off entropy · refusal + error rates. Shown with their frequency ratios vs the pre-AI baselines for context; they power the highlighted "red-pen" views and the Tell Counter charts, but the leaderboard rank comes from Pangram.

**Deferred axes (sequel bank, designs preserved):** Steerability/slop-elasticity, Context uptake, Voice fidelity, Fabrication rate (ensemble-judge pipeline in RUBRICS.md), Spine Test / cave rate, marker-composite index (the original mechanical Slop Index design — retained in git history if we ever want a detector-free score).

## 1. Structure

- **Overall Slop Score** = unweighted mean of the four domain Slop Scores. Headline number.
- **Four domain boards**, independently sortable; Conciseness and Homogeneity per domain; domain crowns ("Slop King of LinkedIn").

## 2. Task suites (~25–30 scenarios per domain, ~110 total)

**Email:** cold outreach, warm intro reply, scheduling, decline/pushback, bad news, follow-ups, support reply, internal update, negotiation, thank-you.
**Social media:** LinkedIn post (announcement, lesson-learned, hiring), X post + thread, X reply/QT, IG caption, community announcement, launch post.
**Essay/long-form:** opinion piece, blog post, personal essay, product review, argumentative essay, cover letter, newsletter intro, commentary.
**Slack/workplace chat:** DM favor ask, standup, review request, delay-to-boss, decline via DM, channel announcement, quick question, urgent-ping reply, missed-message apology, group scheduling.

Each scenario = lightweight pack: persona, recipient, prior context (0–3 messages), goal, **one natural prompt**, `length_target` band from baseline norms. **Scenario design note (detector floor + bundle quality):** target ≥80-word outputs where the medium allows; Slack/short-social scored in bundle mode (10 messages concatenated, labeled).

**Split:** ~80% public, ~20% held out privately, rotated quarterly; retired held-outs graduate to public.

## 3. Models & generation

- 6–8 models (latest GPT-5.x, Claude top + Sonnet tier, Gemini, Grok, DeepSeek, top open Llama), official APIs, default settings, identical minimal scaffold per domain (published verbatim).
- **n = 10 samples × ~28 scenarios ≈ 280 outputs per model per domain** (~1,120/model; ~7,800 total). Bootstrap 95% CIs on mean AI-likelihood; within-CI = reported tie.
- Full run: **<$100 model APIs + ~$20 Pangram** (~250k words × $0.05/1k, plus calibration). Release-day rerun = one command.

## 4. Human baselines (provenance-clean — now serving calibration + norms)

Roles: (a) **detector calibration** — published FPR of Pangram + the open detector on each pre-AI human corpus, before any leaderboard ("does Pangram accuse 2001 Enron employees of using ChatGPT?"); (b) **conciseness norms** — length bands per category; (c) **tell-counter base rates** — the context ratios shown in red-pen views.

| Domain | Baseline corpus | Notes |
|---|---|---|
| Email | **EnronSent** (96k sent-only, public domain) + CMU Enron maildir | Supplements: W3C mirror, Apache mbox |
| Essay/long-form | **Blog Authorship Corpus** (2004, NC — derived stats only) + ASAP-AES (2012) | Supplements: PERSUADE 2.0, BNC, IMDb 2011 |
| Social media | **Twitter: Sentiment140** (2009) + archive.org Twitter Stream slices (prefer 2018, post-280-char; derived stats only) | LinkedIn: no corpus exists (disclosed); supplements: HN BigQuery, optional Reddit slices |
| Slack/workplace chat | **DISCO Discord** (1.5M dev-server messages) + Ubuntu IRC | No public Slack corpus exists; structural norms + crowd votes as modern check |

Rule: nothing post-Oct-2022, ever. Filters published; derived stats shipped where licenses block raw redistribution.

**AI-side calibration** (detector recall checks): off-the-shelf RAID (MIT) + MAGE (Apache); HC3 as generation-zero anchor. No self-built calibration corpora — **the benchmark's own run outputs are AI-labeled by construction** and serve as the domain-specific known-AI set for free.

## 5. Scoring

### Axis 1 — Slop Score (Pangram)
- **Metric**: mean Pangram AI-likelihood (continuous 0–100) across a model's outputs, per domain — continuous scores give spread even where binary flags saturate. % flagged at default threshold reported alongside.
- **Version discipline**: Pangram model/version + scoring date pinned in the run manifest; on Pangram version changes, transition runs report both versions.
- **Short-form**: Slack + short social scored in bundle mode (10 messages per scenario concatenated), labeled, never mixed with per-item numbers.
- **Calibration first**: FPR on each pre-AI human baseline + recall on RAID/MAGE (and the run's own outputs), published before the board.
- **Pre-registered pilot checks**: (1) *Spread* — does mean AI-likelihood meaningfully separate models (CIs non-overlapping for at least some pairs)? (2) *FPR* — baseline false-positive rates published regardless of outcome.

#### ⚠️ Saturation risk: the central design question, test it first

**The mechanism.** Pangram is a binary classifier trained to answer "was this written by an LLM?" Cross-entropy training pushes outputs to the extremes; its 99.98%-accuracy claim *is* a claim of confident separation. Every output we score has the same true label (AI), so a good detector says ~1.0 to all of them. The variance we need for a ranking is variance the detector was explicitly optimized to erase. Spread is therefore not guaranteed — and even if some spread exists, it must be shown to track slop rather than output length (short texts are inherently less detectable, so a terse model could score "less AI" without being less sloppy). **Spread and validity are separate hurdles.**

**Which field.** Pangram V3 exposes (docs: pangram.readthedocs.io):
- `ai_likelihood` — continuous 0–1 document confidence. **The field we score on.**
- `fraction_ai` / `fraction_ai_assisted` / `fraction_human` — fraction of the *text* per bucket (sums to 1). Naturally saturates at 1.00 for fully-AI text; the wrong field to rank on. (An independent measurement showing "Pangram = 1.00 on raw LLM output" used this field, so it is NOT evidence that `ai_likelihood` saturates.)
- Window-level: per-window label, score, confidence, `ai_assistance_score`, char ranges.

**Go/no-go gate — run before building anything else** (~$5, one afternoon): 20 outputs × 5 models → Pangram → examine ALL four sources of resolution:
1. `ai_likelihood` distribution across models (calibrated or pinned at 0.999?)
2. The three-way `fraction_*` mix (does `fraction_ai_assisted` differentiate?)
3. Window-score distributions within long outputs (do some models dip toward human?)
4. % of outputs below the flag threshold (tail statistic; noisy, needs n)
Plus the validity check: does any observed spread correlate with output length rather than slop?

- **GO** (a field spreads, spread isn't just length): Pangram headline as specced.
- **NO-GO** (all pinned, or spread is a length artifact): **mechanical composite becomes the headline** (marker index + the continuous metrics below), Pangram demoted to a corroborating column. Design intact in git history.
- Either outcome is publishable: *"we tested whether the best AI detector can tell frontier models apart"* is a launch-worthy finding in both directions.

#### Continuous mechanical metrics (fallback headline components / extra columns)
All from public, citable sources; all graded rather than binary, with known human-vs-AI gaps:
- **Base-model perplexity / mean log-prob** (fixed scorer) — the core statistical gap (~16.8 human vs ~2.1 base LLM)
- **MTLD lexical diversity** (McCarthy & Jarvis 2010) — vocabulary breadth (~90.9 vs ~65.3)
- **Sentence burstiness** (std of sentence lengths; Altmann et al. 2009) — rhythm variation (~8.8 vs ~7.2)
- **Paragraph-length variance** — structural uniformity (~21.5 vs ~14.1)
- **Compression ratio (zlib)** — repetition/templatedness; the same measure used in "Measuring AI Slop" (arXiv:2509.19163) (~0.52 vs ~0.50)
- **Emotional-arc variance** (VADER across windows) — flat affect (~0.20 vs ~0.12)
Note: these gaps are human-vs-AI, not model-vs-model; the pilot must confirm they also separate *models from each other*, which is the harder requirement.

### Axis 2 — Open cross-check
Binoculars, off-the-shelf, run as-is (pinned commit). Anyone can recompute this column free; correlation with Pangram published. Nothing of our own to train, host, or maintain.

### Axis 3 — Conciseness
Words vs `length_target` band; within band = 0; above, log-scaled ratio-to-band-top. Under-length never penalized. Raw "median words per task" shown.

### Axis 4 — Homogeneity
Intra-model pairwise embedding similarity + self-BLEU; opener entropy (share of outputs opening with the model's top 5-word stem across scenarios); cross-model centroid distances → fingerprint tree.

### Axis 5 (phase 2) — Human pass / Cringe Elo
Spot the Slop game per domain; Turing/reply/cringe votes; Bradley-Terry with attention-check filters. The human-vs-detector gap is itself content ("Pangram catches 98%; humans catch 54%").

## 6. Harness & artifacts (SWE-bench shape)

- Open-source Python: `slopbench run --model X --domain slack` → JSONL artifacts (prompt, params, raw output, scores); `slopbench score` recomputes conciseness/homogeneity/tell counters from raw text free, and re-queries detectors given an API key.
- **Every raw output published** (repo/HF) — anyone can re-score with any detector they trust; the board is re-derivable, the raw data is the authority.
- No Docker, no judges.

## 7. Site

- Main table: Overall Slop Score + four domain boards; Conciseness + Homogeneity columns; open-detector agreement badge.
- Charts: Slop Score vs price scatter ("premium tokens, premium slop") · Pangram × open-detector agreement plot · human-vs-detector gap (phase 2) · opener-entropy bars · Tell Counter bar charts (descriptive).
- Per-model pages: worst outputs with **tells highlighted inline** (red-pen view, with baseline frequency ratios for context) + the model's Pangram distribution.
- Methodology page, disclosure up top: *"We sell an AI email client. Slashy isn't on this board — it ranks models; 3 of 4 domains aren't our product. Scored by Pangram (independent, no relationship with us), version-pinned, cross-checked by an open detector, calibrated on pre-AI human writing. All raw outputs published — re-score them with anything."*

## 8. Rollout

1. **Pilot (days)**: 5 scenarios × 4 domains × 5 models × 5 samples (~500 outputs). Run the two pre-registered checks (spread, FPR), validate bundle mode, see what the data says. Flat/saturated → apply documented fallbacks before launch. Full results ship unedited.
2. **v1 (2–3 weeks)**: full run, site, repo, launch thread — strongest finding up top, methodology in replies, disclosure sentence one, charts in front of benchmark-amplifying accounts.
3. **Sustain**: 24–48h reruns per model release as thread replies; four domain crowns per rerun.
4. **Sequels**: Steerability/slop-elasticity → Spine Test → Context uptake → Voice fidelity → Fabrication → Fingerprint tree → Spot the Slop game → Inbox Zero Bench.

## 9. Known objections, pre-answered

- *"Vendor benchmark"* → Slashy isn't on the board; 3 of 4 domains aren't our product; open harness + held-out set; **no relationship with Pangram** (disclosed). Stated first.
- *"You outsourced the score to a black box"* → version-pinned + date-stamped; open-source detector cross-check published alongside; FPR calibration on pre-AI corpora published first; **all raw outputs public — re-score with any detector you trust**. The board is re-derivable.
- *"Detectability ≠ slop"* → position honestly: the Slop Score measures how unmistakably AI the writing reads — which is what recipients react to; conciseness, homogeneity, tell counters, and (phase 2) human votes cover the quality dimensions. The human-vs-detector gap is reported, not hidden.
- *"Won't every model just score ~100?"* → continuous AI-likelihood, not binary flags; pre-registered spread check in the pilot with documented fallbacks; if models genuinely don't differ, that's a publishable finding.
- *"Pangram could update and shuffle the board"* → pinned versions; transition runs report both; open cross-check provides continuity.
- *"LLM judges are unreliable"* → there are none, anywhere.
- *"Baseline contamination"* → nothing post-Oct-2022, ever (calibration corpora).
- *"n too small"* → ~280/model/domain, bootstrap CIs, ties reported as ties.
- *"Old tweets aren't modern X" / "Discord isn't Slack"* → vintages disclosed; norms structural; crowd votes = modern check.
- *"Prompts cherry-picked"* → 80% public, held-out rotation, community submissions post-launch.
