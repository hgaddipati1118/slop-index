# Pilot Findings (2026-07-14)

Two runs. **Pilot-001 is superseded, its roster was months stale (gpt-5.1, gemini-2.5). Do not publish its numbers.** Pilot-002 is the live result set.

| | pilot-001 | pilot-002 |
|---|---|---|
| Roster | gpt-5.1, gpt-5-mini, claude-sonnet-5, gemini-2.5-pro/flash, deepseek-v4-pro | **gpt-5.6-sol, gpt-5.4-mini, claude-sonnet-5, gemini-3.5-flash, gemini-3.1-pro, deepseek-v4-pro, kimi-k2p6** |
| Outputs | 598 | **696** (4 kimi rate-limit losses) |
| Cost | not tracked | **$4.61 → $6.63 per 1,000 outputs** |

## 1. THE GATE: Pangram headline is NO-GO (survives both runs)

18 texts (6 models, 65–544 words) scored via pangram.com: **100% AI Generated, Confidence High. All 18. Zero variance.**

Pangram's number is a *composition* score ("% of this text that is AI"), which pins at 100 for any fully-AI document by construction. Excellent detector, useless ranking axis. This conclusion is about the detector's scoring, not the roster, so the stale-model problem does not touch it.

→ **Headline = the mechanical composite.** Pangram becomes a corroborating column, and the null result becomes the launch line:

> *"We asked the most accurate AI detector in the world to tell frontier models apart. It said 100% AI, every time, for all of them. It cannot see any difference. So we built something that can."*

## 2. Axis status (pilot-002, bootstrap 95% CIs)

**9 of 10 axes separate the models with disjoint CIs:**
MTLD lexical diversity · sentence burstiness · paragraph-length variance · length inflation (overall **and** in all four domains separately) · opener repetition (within-scenario).

**Dropped:** compression ratio (overlapped in 001), raw word count (separated in 001, **overlaps in 002**, models now differ less in absolute length than in how they respond to each task's band; length-inflation-over-band is the correct metric and still separates).

## 3. THE BIG ONE: findings are model-VERSION properties, not lab properties

**"GPT is the windbag" fully reversed in four months.**

| | pilot-001 (gpt-5.1) | pilot-002 (gpt-5.6-sol) |
|---|---|---|
| Length inflation overall | **+35% (worst on the board)** | **+2% (best on the board)** |
| Email | +48% | **+0%** |
| Words per task | 296 | 162 |

Verified not an artifact: no truncation, no empty retries, median 72 words, well-formed outputs. OpenAI evidently tuned verbosity down between 5.1 and 5.6.

**This is the benchmark's identity argument.** Slop is a property of a *model version*, not of a lab, and only a benchmark that re-runs on every release can see that. It is the strongest possible case for the recurring-franchise design.

### Current verbosity crown: length inflation over the human band

| model | email | essay | slack | social | overall |
|---|---|---|---|---|---|
| gemini-3.5-flash | **+34%** | +4% | +6% | **+17%** | +15% |
| gemini-3.1-pro | +22% | +0% | +1% | +13% | +9% |
| deepseek-v4-pro | +19% | **+34%** | +5% | +10% | **+17%** |
| claude-sonnet-5 | +14% | +3% | +0% | +11% | +7% |
| kimi-k2p6 | +6% | +23% | +1% | +8% | +10% |
| gpt-5.4-mini | +5% | +16% | +0% | +3% | +6% |
| gpt-5.6-sol | **+0%** | +8% | +0% | **+0%** | **+2%** |

Email remains the domain where models inflate most.

## 4. Em-dash fingerprint: holds directionally, spread COLLAPSED

| | pilot-001 | pilot-002 |
|---|---|---|
| highest | gpt-5-mini 19.2 /1k words | deepseek 12.9 |
| lowest | gemini-2.5-flash **0.07** | gemini-3.1-pro **1.69** |
| ratio | **279x** | **7.6x** |

Gemini is still the low outlier (real, replicates, disjoint CIs). But gemini-2.5-flash's near-total abstinence (97% of outputs with zero em-dashes) is gone: gemini-3.5-flash now runs 5.05/1k, only 46% zero. **Do not ship the "190x/279x" line.** The honest 2026 claim: *"~8x spread, and Gemini-pro is the only real abstainer."* Convergence across generations is itself the story.

## 5. Homogeneity: the most stable axis

Same prompt, 5 samples, share sharing the identical 5-word opener (1/n = 0.20 floor):

**gpt-5.6-sol 0.67 · claude-sonnet-5 0.65 · gpt-5.4-mini 0.65 · gemini-3.1-pro 0.52 · gemini-3.5-flash 0.48 · kimi-k2p6 0.45 · deepseek-v4-pro 0.40**

Claude-high and DeepSeek-low replicate across both pilots. New: **gpt-5.6-sol is simultaneously the most concise AND the most templated**, it stopped padding but converged harder on one opening. "Terse and identical" is a distinct slop mode worth naming.

## 6. Hidden reasoning is a cost axis nobody sees

Gemini-3.1-pro burned **90,020 hidden reasoning tokens** to produce 112k total output tokens across 100 short writing tasks. You pay **$13.80/1k tasks** for prose no longer than Claude's, which costs **$3.84/1k**.

Note the two cost views rank models *differently*: gpt-5.6-sol is the priciest per *token* ($0.033/1k) but only 3rd per *task*, because it writes so little. That divergence is the price-vs-slop scatter chart.

| model | $/1k tasks | $/1k output tokens | hidden reasoning tokens (n=100) |
|---|---|---|---|
| gemini-3.1-pro | $13.80 | $0.0123 | 90,020 |
| gemini-3.5-flash | $10.48 | $0.0092 | 88,266 |
| gpt-5.6-sol | $7.76 | $0.0333 | 3,181 |
| kimi-k2p6 | $6.43 | $0.0041 | not reported |
| claude-sonnet-5 | $3.84 | $0.0113 | 0 |
| deepseek-v4-pro | $2.95 | $0.0038 | not reported |
| gpt-5.4-mini | $1.12 | $0.0050 | 0 |

## 7. FALSIFIED: "every model Slacks like a cover letter"

Our intended launch banger. **0% formal sign-offs across all models**, lengths inside the human band (+0–6%), 1–2 paragraphs. Models handle chat register fine. Publish as busted folklore; do not build on it.

(Gemini-flash's preamble ritual survives as a real, funny artifact: *"Hope you're having a good day... still getting my bearings"* even when the prompt says "no long windup.")

## 8. Full-run economics

**$6.63 per 1,000 outputs.** Full publishable run (~110 scenarios × 10 samples × 7 models ≈ 7,700 outputs) ≈ **$51**. Cheap enough to re-run within 24–48h of every model release, the franchise premise holds.

## 9. DESIGN DECISION: publish a scorecard, not a ranking

The composite Slop Index ranking is **not robust to its own weights.** Under 500 random reweightings of the four axes (each 0.10-0.45, all defensible), the exact leaderboard order survives in only **6% of trials** (email, pilot-002 data).

Stable across reweightings:
- **sloppiest** = gpt-5.4-mini (78% of trials)
- **cleanest** = deepseek-v4-pro (62% of trials)

The extremes are the data's. The middle order is the weights'. Shipping a single "model X is #3" number would let any critic reproduce our harness with equally reasonable weights and get a different board, a self-inflicted credibility hit.

**Therefore:**
1. The board is a **four-column scorecard** (conciseness · templating · rhythm · tells), each anchored on the human baseline, each defensible alone, each its own chart.
2. The composite ships only as a rough summary **with the sensitivity number printed beside it**.
3. Ranking claims are made **only about the extremes**, which are stable.

This is also better content: four axis-charts start four conversations; one leaderboard starts one argument about weights.

`harness/score.py --run-id X` prints the scorecard, the composite, and the sensitivity analysis together. Re-run on full-001 before concluding: 30 email scenarios (vs the pilot's 5) may separate the axes enough to improve stability.

## 9b. Reasoning effort: DEFAULT settings, disclosed (decision 2026-07-14)

**We never set a reasoning-effort parameter. Every model ran at its API out-of-box default.** That default is NOT uniform across models, and we disclose the actual per-output reasoning-token counts rather than pretend it is:

| Model group | Reasoning tokens / output (measured) | Their default |
|---|---|---|
| Gemini 3.1-pro / 3.5-flash | ~800–840 | heavy (thinks > half its visible output) |
| Grok 4.5 | ~1,750 | always-on high |
| Muse Spark 1.1 | ~1,140 | reasoning model, on |
| GPT-5.6 sol/terra/luna | 13–39 | light (scales to task; short writing needs little) |
| Claude Fable/Opus/Sonnet/Haiku | **0** | extended thinking OFF by default |
| GPT-5.4-mini | 0 | non-reasoning tier |
| DeepSeek / GLM / Kimi | not reported by Fireworks | likely minimal for writing |

**Why default, not forced-uniform:**
1. It is what real users experience out of the box (the benchmark's whole premise is everyday use).
2. **Reasoning cannot be fully disabled on several 2026 models** (measured): Gemini 3.x retains ~400 tokens even with "disable"; Grok 4.5 has no off, only "low" (floors ~168); Muse ignores the param entirely (thought *more* when asked to stop). True zero-reasoning parity is impossible, so "reasoning off for everyone" is not an achievable board.
3. Forcing max effort ≈ 2x cost on OpenAI, 3–5x on Claude (enabling thinking from zero at $50/M), ~$170–210 for a full re-run, not worth it to move a board that's already sound.

**This sharpens the headline, it doesn't weaken it:** Claude Fable 5 is the sloppiest model in the field (rank 1, isolated CI) *with zero reasoning tokens*, it didn't think at all and still produced the most slop. Gemini, despite thinking harder than any model, lands mid-pack. So "think harder" is not obviously the fix for slop, which is itself a finding.

**Companion experiment (optional, ~$12):** run 3–4 models on the pilot at default vs max effort to measure whether more reasoning reduces slop. Not required for v1; a good follow-up post.

## 10. Next actions

1. Expand 20 pilot scenarios → the full ~110 suite (scenario coverage is now the credibility bottleneck, not the machinery).
2. Ingest a pre-AI human baseline (EnronSent first) to convert length bands and tell-rates from hand-set to data-derived.
3. Re-run at n=10 samples for tighter CIs; use `--workers 8` (kimi hit Fireworks 429s at higher concurrency).
4. Kill the stale narratives everywhere: "GPT is the windbag" and "190x em-dash" are dead.
