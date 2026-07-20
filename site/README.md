# Spot the Slop, the vote-collecting game

Blind pairwise game: two models wrote the same message, the crowd picks which
is worse. Votes feed a live Elo per model, per question ("would reply to",
"more human", "more cringe"). This Elo becomes the human-preference column of
The Slop Index.

## Deploy free on Vercel (5 minutes)
1. `cd slop-game && vercel` (or import the folder at vercel.com/new)
2. In the Vercel dashboard: **Storage -> Create -> KV** (Upstash Redis, free tier),
   connect it to this project. That auto-injects the KV_* env vars the API reads.
3. Redeploy. Done. `/` is the game, `/api/vote` records votes, `/api/leaderboard` serves the board.

No accounts, no PII. All message text is real unedited model output, baked into
`public/pairs.json` (regenerate from a newer run with the builder in the parent repo).

## Data
- `public/pairs.json`, blind matchups (scenario + two models' outputs)
- `public/prompts.json`, the task prompt shown as context
Regenerate both after a new benchmark run so the game reflects the latest models.

## Methodology notes (for the writeup)
- Sides randomized per view; model identity hidden until after the vote.
- Elo is per-mode (reply/human/cringe scored separately).
- `vote.js` reserves an `attention` field: attention-check pairs (obvious human
  vs obvious slop) are recorded but excluded from Elo, to filter low-quality voters.
- Crowd Elo is the ENGAGEMENT + volume signal; correlate it with the mechanical
  Slop Index. Agreement validates the metric; divergence is a finding.
