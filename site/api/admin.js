// Admin recovery endpoint — token-protected. Lets you reset or rebuild the
// board in one call if the game gets botted. The raw vote log is the source of
// truth; the Elo board is a derived cache you can always recompute.
//
//   POST /api/admin  { token, action }
//     action "reset"     -> wipe the derived board (elo/games/tally), KEEP votes:log
//     action "wipe"      -> wipe everything including the raw log (fresh start)
//     action "recompute" -> rebuild elo/games from votes:log, capping each IP hash
//                           at `capPerIp` votes (default 50) to neutralize a flood
import { redis, one, configured } from './_redis.js';
import { MODELS } from './_models.js';

const K = 32;

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { token, action, mode, capPerIp } = req.body || {};
  if (!process.env.ADMIN_TOKEN || token !== process.env.ADMIN_TOKEN) {
    return res.status(403).json({ error: 'forbidden' });
  }
  if (!configured) return res.status(200).json({ ok: true, note: 'no store' });
  const m = (mode || 'reply').replace(/[^a-z]/g, '') || 'reply';
  try {
    if (action === 'reset') {
      await redis([['DEL', `elo:${m}`], ['DEL', `games:${m}`], ['DEL', 'tally'], ['DEL', 'scenario_votes']]);
      return res.status(200).json({ ok: true, did: 'reset board (raw log kept)' });
    }
    if (action === 'wipe') {
      await redis([['DEL', `elo:${m}`], ['DEL', `games:${m}`], ['DEL', 'tally'],
        ['DEL', 'scenario_votes'], ['DEL', 'votes:log']]);
      return res.status(200).json({ ok: true, did: 'wiped everything' });
    }
    if (action === 'recompute') {
      const cap = Number(capPerIp) || 50;
      const n = Number(await one(['LLEN', 'votes:log'])) || 0;
      const elo = {}, games = {}, ipCount = {};
      let used = 0, dropped = 0;
      for (let start = 0; start < n; start += 1000) {
        const chunk = await one(['LRANGE', 'votes:log', start, start + 999]);
        for (const s of chunk) {
          let v; try { v = JSON.parse(s); } catch { continue; }
          if (v.m !== m || !MODELS.has(v.w) || !MODELS.has(v.l)) { dropped++; continue; }
          ipCount[v.iph] = (ipCount[v.iph] || 0) + 1;
          if (ipCount[v.iph] > cap) { dropped++; continue; }   // flood control
          const ew = elo[v.w] ?? 1500, el = elo[v.l] ?? 1500;
          const ex = 1 / (1 + 10 ** ((el - ew) / 400));
          elo[v.w] = Math.round(ew + K * (1 - ex));
          elo[v.l] = Math.round(el - K * (1 - ex));
          games[v.w] = (games[v.w] || 0) + 1; games[v.l] = (games[v.l] || 0) + 1;
          used++;
        }
      }
      const cmds = [['DEL', `elo:${m}`], ['DEL', `games:${m}`]];
      for (const [k, val] of Object.entries(elo)) cmds.push(['HSET', `elo:${m}`, k, String(val)]);
      for (const [k, val] of Object.entries(games)) cmds.push(['HSET', `games:${m}`, k, String(val)]);
      await redis(cmds);
      return res.status(200).json({ ok: true, did: 'recomputed', used, dropped, capPerIp: cap });
    }
    return res.status(400).json({ error: 'action must be reset | wipe | recompute' });
  } catch (e) {
    return res.status(500).json({ error: String(e).slice(0, 200) });
  }
}
