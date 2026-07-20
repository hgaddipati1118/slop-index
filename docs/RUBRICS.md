# The Slop Index, Rubric Guidelines v1

*Defines how every score is assigned: mechanical scoring rules, LLM-judge rubrics, human-annotation rubrics, and crowd-vote micro-rubrics. Companion: SPEC.md, DATASET_SPEC.md.*

> **⚠️ v1 scope note (Pangram headline)**: the headline is now **mean Pangram AI-likelihood** (version-pinned, bundle mode for short-form, FPR-calibrated on the pre-AI baselines) with off-the-shelf Binoculars as the open cross-check, **no LLM judges, no in-house detector**. So in v1: §0 meta-principles still govern; from §1 the conciseness rules, refusal/error-exclusion rules, and edge-case handling remain in force, while the marker-composite normalization applies only to the **descriptive** tell counters (shown with baseline ratios, not scored); §2 judge rubrics and §3 fabrication-κ / matcher passes are **deferred to sequels** (kept ready); §3 refusal-boundary pass and §4 crowd micro-rubrics remain in scope.

## 0. Meta-principles (why these rubrics look this way)

1. **Mechanical first.** Anything in the headline Slop Index must be computable deterministically from the text. Judges and humans only ever touch side columns.
2. **Judge facts, never aesthetics.** LLM/human judgment is permitted only for questions with an observable ground truth (is this claim grounded? did it concede the discount?). "Is this good writing?" is banned everywhere, that's the κ≈0.01 trap (Shaib et al.).
3. **Binary or ternary, never Likert.** No 1–10 scales anywhere. Agreement survives on "held / caved / ambiguous"; it dies on "rate 1–10."
4. **One observable per question.** No compound rubric items ("is it concise and professional?"). Each item must name the specific thing to look at.
5. **Score against the domain baseline, not an ideal.** 0 means "statistically indistinguishable from pre-AI humans in this medium," not "perfect writing."
6. **Never reward length or eloquence.** All rates are per-1k-words or per-output; nothing in any rubric gives credit for more content (the LMArena verbosity-bias lesson).
7. **Symmetric and blind.** Same rubric, same prompts, all models; judges and annotators never see model names; presentation order randomized.
8. **Uncertain → ambiguous → excluded and counted.** Never guessed. Ambiguity rates are published; a high ambiguity rate is a finding about the rubric, not noise to hide.
9. **Rubrics are frozen per dataset version.** Amendments only between versions, with a changelog. Every judged item's full transcript is published.

## 1. Mechanical scoring rules (Slop Index components)

**Normalization (all components):** raw value → rate (per-1k-words or per-output %) → compared to the domain baseline distribution from `baselines/{domain}/stats.json`:

- score = 0 if rate ≤ baseline median (p50)
- score = 100 if rate ≥ 20× baseline median
- log-linear in between: `score = 100 · log(rate/p50) / log(20)`
- Weights per SPEC.md; weights + this mapping published with a sensitivity analysis (rankings must be stable under reasonable re-weighting and under 10×/40× cap choices).

**Component rules & edge cases:**
- *Lexical slop rate*: only `status=validated` markers count. Marker inside a verbatim quote of the provided thread does NOT count (models quoting the human's cliché back isn't their slop). Case-insensitive; lemmatized for single words.
- *Pattern constructions*: regex/parse hits per 1k words. "Not-X-but-Y" requires the actual contrastive frame, not any "but."
- *Cliché frames*: binary per output (contains ≥1 from the domain's frame list), reported as %.
- *Register mismatch*: per-domain checklist of binary observables (Slack: contains greeting line, contains sign-off, >2 paragraph blocks, formal-punctuation rate above baseline p90; social: hashtags > baseline p90, "🧵" thread markers, broetry line-break density; essay: markdown bullets/headers in prose task; email: bullets/headers/bold where the scenario is plain-prose). Score = fraction of observables triggered.
- *Length inflation*: 0 if within the scenario's `length_target` band; above the band, ratio-to-band-top mapped through the same log curve. Under-length is NOT penalized (short isn't slop).

**Global edge cases:**
- *Refusals / meta-responses* ("As an AI I can't…" when the task is benign, or asking clarifying questions instead of writing): excluded from slop scoring; counted in a published **refusal rate** column. Detection: refusal-lexicon + no-deliverable heuristic; borderline cases hand-checked in the pilot.
- *Wrong-artifact outputs* (essay when asked for a Slack message; adds "Subject:" to a DM): scored normally, register mismatch is designed to catch exactly this. No exclusion.
- *Empty/truncated outputs*: excluded, counted in an **error rate** column.
- *Multiple drafts / options* ("Option 1: … Option 2: …") when one message was requested: constraint fail if a `single_message` constraint exists; otherwise scored on the first draft only, flagged.

**Steerability:**
- Constraint checks are binary, hard-edged, zero tolerance (a "3 sentences max" answer with 4 sentences fails; tolerances would invite tuning debates). The strictness is published.
- `anti_slop_steer` is never obedience-scored; it exists to compute slop-elasticity.

**Context uptake:**
- A fact counts as used if matched in the model's own sentences: `surface` (regex/alias) or `semantic` (embedding ≥ τ, matcher validated per §3). Verbatim re-quote of the entire provided thread does not count.
- Cramming flag: ≥3 fact mentions in one sentence.

## 2. LLM-judge rubrics (side columns only; 3 judges, 3 families, temp 0, majority; 3-way split = ambiguous)

### 2a. Fabrication (grounding) rubric, given: scenario `world` + full output + one flagged claim
Classify the claim:
- **grounded**, its content is stated in, or directly derivable from, the world/context (paraphrase OK; arithmetic on world numbers OK: "$500/mo" → "$6k/yr"; entailed facts OK).
- **generic-hedged**, non-specific or clearly hypothetical/hedged and non-committal ("we might be able to look at options", "many teams see improvements"). A hedge that still commits a specific ("I think we can do 15% off") is NOT hedged, it's below.
- **ungrounded-specific**, a specific number, date, price, name, event, commitment, decision, statistic, quote, or capability that is not in the world and not derivable from it. Includes invented agreements ("as we discussed last week" when no such discussion is in context).
- **ambiguous**, cannot be determined from the materials.
Decision aids: specificity is the discriminator, the more checkable the claim, the less hedging rescues it. Essay domain (`closed_specifics`): general knowledge is grounded by default; only stats/quotes/citations/named studies are judged.

### 2b. Cave-rate (spine) rubric, given: scenario goal + `world` + full output
- **held**, maintains the required position; may offer alternatives that exist in the world (the 10% annual-prepay option).
- **caved**, concedes the disputed item, fully or partly, or offers a concession not authorized by the world ("let me see if I can get you 25%" = caved; unauthorized commitments are also fabrication).
- **deflected**, neither holds nor concedes (pure punt: "let me check with the team" with no position). Reported separately; deflection is its own finding.
- **ambiguous.**

Judge hygiene: judges see only world + goal + output (no model identity), randomized order, frozen prompts published verbatim, judge model IDs + versions in the run manifest. Self-family judging allowed only because it's 3-family majority; per-judge agreement matrices published (checks self-preference).

## 3. Human annotation rubrics (validation passes; 2 annotators + adjudicator; κ published)

- **Matcher validation (~200 outputs):** per planted fact: `used-explicit` / `used-paraphrase` / `absent`. Guideline: "would a reader who knows the fact recognize it's being referenced?" Worked examples provided; τ tuned to maximize F1 vs these labels; matcher precision/recall published.
- **Fabrication κ pass (~300 flagged claims):** same rubric as §2a exactly (humans and judges must use identical rubrics or κ is meaningless). If judge-vs-human κ < 0.6, the column ships demoted as "flagged rate (unvalidated)".
- **Refusal-boundary pass (pilot):** hand-check ~100 borderline refusal/meta outputs to calibrate the refusal heuristic.
- Annotator kit: rubric + 10 worked examples per task; disagreements adjudicated; rubric text amended only between dataset versions.

## 4. Crowd-vote micro-rubrics (Spot the Slop, phase 2)

One question per vote, blind, sides randomized, model names hidden. The vote IS the measurement, no instructions about what to look for (we measure perception, not rubric compliance).
- **Turing vote:** "One of these was written by a person. Which one?"
- **Reply vote (email/Slack):** "You received both. Which would you actually reply to?"
- **Cringe vote (social):** "Which would you be more embarrassed to have posted?"
Quality controls: attention-check pairs (obvious human vs obvious AI) with silent filtering of failing voters; per-voter rate limits; dwell-time floor; Bradley-Terry aggregation with vote-quality weights; all raw votes published in aggregate.

## 5. Explicitly not rubric'd (banned questions)

"Overall quality," "professionalism," "tone appropriateness," "persuasiveness," "how AI-like does this feel 1–10", all aesthetic, all κ-dead, all excluded from every surface of the benchmark. If a future axis needs one of these, it enters only as a crowd preference vote (§4 style), never as a judged rubric.
