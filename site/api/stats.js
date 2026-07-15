// Public, read-only vote stats for the live dashboard (/stats.html).
// Aggregate counts + a recent-matchup feed. Strips all PII: the raw log's IP
// hash and fingerprint are NEVER returned — only model/outcome/time.
import { redis, configured } from './_redis.js';

export default async function handler(req, res) {
  if (!configured) return res.status(200).json({ store: false, total: 0 });
  const m = (req.query.mode || 'v1').replace(/[^a-z]/g, '') || 'v';
  try {
    const [tallyRaw, eloRaw, gamesRaw, len, recentRaw] = await redis([
      ['HGETALL', 'tally'],
      ['HGETALL', `elo:${m}`],
      ['HGETALL', `games:${m}`],
      ['LLEN', 'votes:log'],
      ['LRANGE', 'votes:log', -400, -1],
    ]);
    const toObj = (a) => { const o = {}; for (let i = 0; i < (a || []).length; i += 2) o[a[i]] = a[i + 1]; return o; };
    const tally = toObj(tallyRaw), elo = toObj(eloRaw), games = toObj(gamesRaw);
    const n = (k) => Number(tally[k] || 0);

    const decided = n(`${m}:counted`), ties = n(`${m}:both`);
    const rows = Object.entries(elo)
      .map(([model, r]) => ({ model, elo: Number(r), games: Number(games[model] || 0) }))
      .sort((a, b) => b.elo - a.elo);

    // parse the log tail once: real last-hour count + newest-first feed (PII stripped)
    const now = Date.now();
    const parsed = (recentRaw || []).map((s) => { try { return JSON.parse(s); } catch { return null; } }).filter(Boolean);
    const lastHour = parsed.filter((v) => v.t && v.t > now - 3600000).length;
    const recent = parsed.slice(-18).reverse()
      .map((v) => ({ t: v.t, w: v.w, l: v.l, o: v.o || 'win', c: v.c || null, s: v.s || null }));

    res.setHeader('Cache-Control', 's-maxage=5, stale-while-revalidate=15');
    return res.status(200).json({
      store: true,
      total: decided + ties, decided, ties, lastHour,
      logLen: Number(len || 0),
      rejected: {
        too_fast: n('rejected:dwell'), rate_limited: n('rejected:rate'),
        daily_cap: n('rejected:cap'), no_session: n('rejected:nosession'),
        bad_pair: n('rejected:badpair'),
      },
      seen: n(`${m}:seen`),
      models: rows,
      recent,
    });
  } catch (e) {
    return res.status(500).json({ error: String(e).slice(0, 200) });
  }
}
