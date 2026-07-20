# AGENTS.md, reproduce The Slop Index end to end

> This file is the machine-readable playbook. An agent (Claude Code, Codex, etc.) should be
> able to rebuild every result in this repo from it. `CLAUDE.md` is a symlink to this file, so
> both tools read the same instructions. Humans want `README.md`.

The Slop Index ranks frontier LLMs by how much recognizable **"AI slop"** their writing contains,
measured mechanically against **pre-AI human baselines** (all text provably written before
Oct 2022) across four domains: **email, social, essay, chat**. A companion web app collects a
human-preference Elo. No LLM judges score other LLMs, every number is a token statistic.

## Repo layout

```
harness/           the pipeline (pure stdlib + LiteLLM). Run everything from repo root.
  providers.py       model roster (MODELS), prices, LiteLLM adapter. Reads keys from env.
  generate.py        stage 1: scenarios x models x samples -> runs/<id>/outputs.jsonl
  score.py           stage 3: mechanical Slop Index (conciseness/templating/rhythm/tells)
  rank_spread.py     bootstrap rank ranges + tie groups from a run
  detect.py          optional: Pangram AI-detector pass (needs PANGRAM_API_KEY). SATURATES.
  analyze.py         pilot go/no-go gate (works with or without detector scores)
  budget.py          hard $ cap ledger + kill switch (runs/BUDGET.json)
  export_votes.py    dump the live vote log from Redis to jsonl
scenarios/pilot/   the 112 hand-written scenarios (email/social/essay/slack) + per-scenario setups
baselines/         DERIVED human-baseline stats only (stats.json). Raw corpora are NOT shipped
                   (1.4GB, third-party licenses), see baselines/README.md to rebuild them.
runs/full-merged/  outputs.jsonl = the 19,928 real generations behind the published board
runs/full-merged-score.log  = the exact score.py + rank_spread.py output (the results)
site/              the deployed app (Vercel + Upstash Redis + Cloudflare Turnstile)
  public/            index.html (the game), benchmark.html (the report), *.json data
  api/               serverless vote/session/leaderboard/admin endpoints (read secrets from env)
  scripts/           gen_pairs.py, build_bench_data.py, norm_logos.py (rebuild the site data)
docs/              SPEC.md, RUBRICS.md, DATASETS.md, DATASET_SPEC.md, PILOT_FINDINGS.md
```

## 0. Environment

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt          # litellm + a couple of stats libs
cp harness/.run-keys.env.example harness/.run-keys.env   # then fill in real keys
set -a; source harness/.run-keys.env; set +a
```

Keys are read from the environment at call time, never hardcoded. Which providers you need
depends on which models you run (see `providers.py`): OpenAI, Anthropic, Google, xAI, Mistral,
Fireworks (DeepSeek/Kimi/GLM), OpenRouter (Qwen/MiniMax/Mistral), and a Meta Spark endpoint.

## 1. (Optional) rebuild the human baselines

`baselines/<domain>/stats.json` are already committed, so scoring works without this step.
To re-derive them from source, follow `baselines/README.md`: download each corpus (Enron/EnronSent,
Blog Authorship + ASAP essays, Sentiment140 + archived tweets, DISCO Discord), run the per-domain
`filter.py` (dedup + pre-Oct-2022 + register filters) to produce `clean.jsonl`, then
`python baselines/compute_stats.py` to emit the `stats.json` the scorer reads.

**Hard rules for baselines** (see PILOT_FINDINGS.md for why): only text provably written before
ChatGPT (Oct 2022); publish DERIVED STATS ONLY, never redistribute corpus text; do not use
`wordfreq` or any post-2022 frequency table as a reference (contamination).

## 2. Generate model outputs

```bash
# dry-run prints the projected cost and exits (respects the budget cap)
python harness/generate.py --models kimi-k2p6,claude-sonnet-5 --samples 5 --run-id myrun --dry-run
python harness/generate.py --models kimi-k2p6,claude-sonnet-5 --samples 5 --run-id myrun
```

112 scenarios x N models x 5 samples. Writes `runs/myrun/outputs.jsonl`. `budget.py` refuses to
start a run that would breach the cap and kills in-flight calls if it's crossed. The published
board used 18 models x 5 samples = 19,928 outputs, already merged into `runs/full-merged/`.

## 3. Score (the actual benchmark)

```bash
python harness/score.py       --run-id full-merged     # per-domain + overall Slop Index + per-axis
python harness/rank_spread.py --run-id full-merged     # 500-bootstrap rank ranges + tie groups
```

`runs/full-merged-score.log` is the committed output of exactly these two commands. This is the
**mechanical** layer: four axes of raw slop distance from the human baseline (0 = human-like).

**The published Human Score** (on the site) is a composite computed live in `site/public/benchmark.html`:
each axis is put on a 0–100 human-likeness scale (100 = writes like a human), then blended
**human vote 40% + conciseness/templating/rhythm/tells 15% each**. The human axis is the live crowd
Elo from the game, so the public board updates as votes arrive; `score.py` above is the frozen
mechanical 60%. Keep both, the mechanical scorer is fully reproducible offline; the human 40% needs
real vote volume before it's meaningful.

## 4. (Optional) detector cross-check

```bash
PANGRAM_API_KEY=... python harness/detect.py --run-id full-merged
```

Finding: Pangram flags **every** frontier model at ~100% AI / high confidence, it saturates and
cannot rank models. It's a control that motivates the mechanical index, never a ranking axis.
(The published site intentionally omits it.)

## 5. Rebuild + deploy the site

The app is static `public/` + serverless `api/` on Vercel, with **Upstash Redis** for the vote
store and **Cloudflare Turnstile** for proof-of-human. To regenerate the data it serves:

```bash
python site/scripts/gen_pairs.py         # runs/full-merged -> site/public/pairs.json (blind matchups)
python site/scripts/build_bench_data.py  # score log + providers prices -> site/public/bench.json
python site/scripts/norm_logos.py        # normalize brand SVGs -> site/public/logos.json
```

Deploy: `cd site && vercel --prod`. Required env vars (set in the Vercel project, never in git):
`TOKEN_SECRET`, `IP_SALT`, `ADMIN_TOKEN`, `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`,
`UPSTASH_REDIS_REST_URL`/`_TOKEN` (or `KV_REST_API_URL`/`_TOKEN`). See `site/README.md` and
`site/SECURITY.md`. Vote framing: players flag the **sloppier** of two blind samples; the flagged
model loses Elo, so least-slop rises to the top.

## Add a model

1. Add it to `MODELS` (and `PRICES`) in `harness/providers.py`.
2. `python harness/generate.py --models <alias> --samples 5 --run-id addN`
3. Merge into `runs/full-merged/outputs.jsonl`, re-run steps 3 and 5.
4. Add the alias to `site/api/_models.js` (the vote allowlist) and re-run `gen_pairs.py`.

## Gotchas we already hit (don't relearn them)

- **`id="turnstile"` collision**: never name a DOM element `turnstile`, it shadows the global
  Cloudflare installs and silently kills every vote. The container is `id="cfslot"`.
- **Never wipe the vote board** except on explicit request, `admin` wipe deletes real votes.
- **No em dashes in site copy**, the benchmark scores em-dash usage as a typography tell; the
  honest claim is "em dash = typography-era signal, not an AI signal" (pre-AI Discord humans
  who *could* type them still didn't).
- **Reasoning effort** is left at each model's default and disclosed per-model, not forced.
- **Detectors saturate** (see step 4), this is expected, not a bug.
