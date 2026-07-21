// Live Elo leaderboard, aggregated from stored votes. Public, read-only.
// ?domain=all additionally returns the four per-domain Elo boards in one round trip.
import { redis, configured } from './_redis.js';
import { VOTE_DOMAINS } from './_domains.js';

function hashToObj(arr) {
  const o = {};
  for (let i = 0; i < (arr || []).length; i += 2) o[arr[i]] = arr[i + 1];
  return o;
}
const toRows = (eloRaw, gamesRaw) => {
  const elo = hashToObj(eloRaw), games = hashToObj(gamesRaw);
  return Object.entries(elo)
    .map(([model, rating]) => ({ model, elo: Number(rating), games: Number(games[model] || 0) }))
    .sort((a, b) => b.elo - a.elo);
};

export default async function handler(req, res) {
  try {
    const mode = (req.query.mode || 'reply').replace(/[^a-z]/g, '');
    const wantDomains = req.query.domain === 'all';
    if (!configured) {
      return res.status(200).json({ mode, rows: [], totalVotes: 0, store: false });
    }
    const cmds = [
      ['HGETALL', `elo:${mode}`],
      ['HGETALL', `games:${mode}`],
      ['HGETALL', 'tally'],
    ];
    if (wantDomains) for (const d of VOTE_DOMAINS) {
      cmds.push(['HGETALL', `elo:${mode}:d:${d}`], ['HGETALL', `games:${mode}:d:${d}`]);
    }
    const out = await redis(cmds);
    const rows = toRows(out[0], out[1]);
    const tally = hashToObj(out[2]);
    const counted = Number(tally[`${mode}:counted`] || 0), ties = Number(tally[`${mode}:both`] || 0);
    const body = { mode, rows, totalVotes: counted + ties, decided: counted, ties, store: true };
    if (wantDomains) {
      body.domains = {};
      VOTE_DOMAINS.forEach((d, i) => { body.domains[d] = { rows: toRows(out[3 + i * 2], out[4 + i * 2]) }; });
    }
    res.setHeader('Cache-Control', 's-maxage=10, stale-while-revalidate=30');
    return res.status(200).json(body);
  } catch (e) {
    return res.status(500).json({ error: String(e).slice(0, 200) });
  }
}
