<h1>The Slop Index</h1>

**Which AI writes the least like AI?** A benchmark that ranks 18 frontier LLMs by how much
recognizable *AI slop* their writing contains, across email, social posts, essays, and chat.

The published **Human Score** (0–100, where **100 = writes like a real person**) blends two
independent signals: **human preference (40%)**, a live crowd Elo from a blind pairwise game -
and **four mechanical axes (15% each)** measured against real human writing that provably predates
ChatGPT. No LLM judges scoring other LLMs; every mechanical number is a token statistic against a
pre-AI baseline.

- **The report:** https://slop-game.vercel.app/benchmark.html
- **The game (Spot the Slop):** https://slop-game.vercel.app, flag the sloppier of two blind
  samples (or "both are slop"); the vote feeds 40% of the score.

## How the score is calculated

The headline **Human Score** is a weighted blend of five axes. Each axis is first put on a 0–100
human-likeness scale (100 = the most human-like of the models tested), then blended:

| Axis | Weight | What it captures |
|---|---|---|
| **Human preference** | **40%** | Live crowd Elo. People flag the sloppier of two blind samples; least-flagged rises. This is the biggest single input. |
| Conciseness | 15% | Resisting length inflation vs a human doing the same task. |
| Templating | 15% | Avoiding reused openers & skeletons across different prompts (homogeneity). |
| Rhythm | 15% | Natural paragraph-length variance. |
| Tells | 15% | Avoiding over-used AI words & constructions, vs the human baseline's own rate. |

```
Human Score = 0.40·human + 0.15·(conciseness + templating + rhythm + tells)     # higher = more human
```

The **mechanical 60%** is fully reproducible offline (below); the **human 40%** is live and needs
real vote volume before it's meaningful, so the public board updates as votes arrive. `score.py`
computes the four mechanical axes as raw *slop distance* from the human baseline (0 = human-like);
the site inverts and blends them with the crowd Elo. A leading AI *detector* (Pangram) was tried
only as a control, it flags all 18 models at ~100% AI, which is exactly why a mechanical **and**
human measure is needed to tell them apart.

## The mechanical layer (reproducible offline)

The 60% mechanical component, ranked by raw Slop Index (0 = writes like a pre-AI human, higher =
more slop). This is what `score.py` reproduces exactly from the committed outputs:

| Rank | Model | Lab | Slop Index |
|---|---|---|---|
| 1 (sloppiest) | Mistral Large | Mistral | 40.6 |
| 2 | Fable 5 | Anthropic | 35.6 |
| 3 | GPT-5.6 Terra | OpenAI | 32.8 |
| … | … | … | … |
| 16 | MiniMax M3 | MiniMax | 23.1 |
| 17 | Muse Spark | Meta | 23.1 |
| 18 (cleanest) | Kimi K2.6 | Moonshot | 21.1 |

Full board, per-axis, per-domain splits, tie groups, and a price-vs-slop scatter are in
`runs/full-merged-score.log` and rendered at the report link. Headline finding beyond the ranking:
**slop does not track price**, the priciest model on the board is near the sloppy end, one of the
cheapest is near the clean end.

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
see `AGENTS.md`. The human baselines are shipped as **derived statistics only**, the raw corpora
(Enron, Blog Authorship, ASAP, Sentiment140, DISCO) are third-party licensed; `baselines/README.md`
tells you how to fetch and rebuild them.

## Repo layout

See `AGENTS.md` for the full map. In short: `harness/` (the pipeline), `scenarios/` (the 112
prompts), `baselines/` (derived human stats + rebuild scripts), `runs/full-merged/` (the raw
outputs + results), `site/` (the game and report), `docs/` (methodology).

## License

Code and derived statistics: MIT (see `LICENSE`). The raw human corpora are **not** redistributed
here and remain under their own licenses. Model outputs in `runs/` are published as research data.

Built by [Slashy](https://slashy.com), the email client that saves you time instead of generating
more AI slop.
