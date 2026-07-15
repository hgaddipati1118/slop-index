// Live Elo leaderboard, aggregated from stored votes. Public, read-only.
import { redis, configured } from './_redis.js';

function hashToObj(arr) {
  const o = {};
  for (let i = 0; i < (arr || []).length; i += 2) o[arr[i]] = arr[i + 1];
  return o;
}

export default async function handler(req, res) {
  try {
    const mode = (req.query.mode || 'reply').replace(/[^a-z]/g, '');
    if (!configured) {
      return res.status(200).json({ mode, rows: [], totalVotes: 0, store: false });
    }
    const [eloRaw, gamesRaw, tallyRaw] = await redis([
      ['HGETALL', `elo:${mode}`],
      ['HGETALL', `games:${mode}`],
      ['HGETALL', 'tally'],
    ]);
    const elo = hashToObj(eloRaw), games = hashToObj(gamesRaw), tally = hashToObj(tallyRaw);
    const rows = Object.entries(elo)
      .map(([model, rating]) => ({ model, elo: Number(rating), games: Number(games[model] || 0) }))
      .sort((a, b) => b.elo - a.elo);
    res.setHeader('Cache-Control', 's-maxage=10, stale-while-revalidate=30');
    return res.status(200).json({ mode, rows, totalVotes: Number(tally[`${mode}:counted`] || 0), store: true });
  } catch (e) {
    return res.status(500).json({ error: String(e).slice(0, 200) });
  }
}
