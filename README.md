<h1>The Slop Index</h1>

**Which AI writes the least like AI?** A benchmark that ranks 18 frontier LLMs by how much
recognizable *AI slop* their writing contains — measured mechanically against real human writing
that provably predates ChatGPT, across email, social posts, essays, and chat.

No LLM judges scoring other LLMs. Every number is a token statistic computed against a pre-AI
human baseline, so a model that writes like a person scores near **0** and a model that writes
like a chatbot scores high.

- **The report:** https://slop-game.vercel.app/benchmark.html
- **The game (Spot the Slop):** https://slop-game.vercel.app — flag the sloppier of two blind
  samples; a live human-preference Elo runs alongside the mechanical board.

## Results (overall Slop Index, 0 = writes like a pre-AI human)

| Rank | Model | Lab | Slop Index |
|---|---|---|---|
| 1 (sloppiest) | Mistral Large | Mistral | 40.6 |
| 2 | Fable 5 | Anthropic | 35.6 |
| 3 | GPT-5.6 Terra | OpenAI | 32.8 |
| … | … | … | … |
| 16 | MiniMax M3 | MiniMax | 23.1 |
| 17 | Muse Spark | Meta | 23.1 |
| 18 (cleanest) | Kimi K2.6 | Moonshot | 21.1 |

The full 18-model board, the four sub-axes, per-domain splits, tie groups, and a price-vs-slop
scatter are in `runs/full-merged-score.log` and rendered at the report link above. Headline
finding beyond the ranking: **slop does not track price** — the most expensive model on the board
is near the top of the slop ranking, one of the cheapest is near the clean end.

## What it measures

Four mechanical axes, each 0–100 (0 = human-like), computed purely from token statistics:

- **Conciseness** — length inflation vs a human doing the same task.
- **Templating** — reused openers and skeletons across different prompts (homogeneity).
- **Rhythm** — flattened paragraph-length variance.
- **Tells** — over-used AI words and constructions, relative to the human baseline's own rate.

Blended `0.35 / 0.30 / 0.20 / 0.15`. Because that blend is subjective, the ranking is published
with bootstrap **tie groups**, not as a false-precision leaderboard. A leading AI *detector*
(Pangram) is run only as a control: it flags all 18 models at ~100% AI, which is exactly why a
mechanical slop measure is needed to tell them apart.

## Reproduce it

Everything here regenerates from the committed data. Agents: read **`AGENTS.md`**. Humans, TL;DR:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python harness/score.py       --run-id full-merged   # recompute the Slop Index from raw outputs
python harness/rank_spread.py --run-id full-merged   # recompute rank ranges + tie groups
```

`runs/full-merged/outputs.jsonl` holds all 19,928 raw, unedited model generations. To generate
new outputs you'll need model API keys (`cp harness/.run-keys.env.example harness/.run-keys.env`);
see `AGENTS.md`. The human baselines are shipped as **derived statistics only** — the raw corpora
(Enron, Blog Authorship, ASAP, Sentiment140, DISCO) are third-party licensed; `baselines/README.md`
tells you how to fetch and rebuild them.

## Repo layout

See `AGENTS.md` for the full map. In short: `harness/` (the pipeline), `scenarios/` (the 112
prompts), `baselines/` (derived human stats + rebuild scripts), `runs/full-merged/` (the raw
outputs + results), `site/` (the game and report), `docs/` (methodology).

## License

Code and derived statistics: MIT (see `LICENSE`). The raw human corpora are **not** redistributed
here and remain under their own licenses. Model outputs in `runs/` are published as research data.

Built by [Slashy](https://slashy.com) — the email client that saves you time instead of generating
more AI slop.
