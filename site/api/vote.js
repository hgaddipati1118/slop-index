// Records one blind pairwise vote + updates the crowd Elo board.
// Storage: Upstash Redis REST (no npm dep).
//
// Anti-gaming layers (open voting can never be fully botproof, so this is
// defense-in-depth + a clean audit trail to filter bad actors AFTER the fact):
//   1. Roster allowlist   — reject fake/garbage model names (no leaderboard injection).
//   2. Field length caps   — no storage-bloat abuse.
//   3. Dwell check         — a vote < 1.2s after the pair was shown doesn't count.
//   4. Per-voter + per-IP floor (1.5s) and daily caps — rotating fingerprints
//      from one IP still hit the IP limit; rotating IPs is the residual hole.
//   5. Permanent raw log with a SALTED IP HASH — groupable for bot detection
//      (same IP -> same hash) but not reversible PII, so a flood can be excised
//      and the board recomputed (see harness/recompute_votes.py).
import { createHmac } from 'node:crypto';
import { redis, one, configured } from './_redis.js';
import { MODELS } from './_models.js';
import { readToken } from './_sign.js';

const REQUIRE_TOKENS = Boolean(process.env.TOKEN_SECRET);   // on once secrets are set
const MAX_PAIR_AGE_MS = 30 * 60 * 1000;

const K = 32;
const MIN_GAP_MS = 1500;
const MIN_DWELL_MS = 1200;
const DAILY_CAP_FP = 400;   // per fingerprint
const DAILY_CAP_IP = 800;   // per IP (higher — NAT/shared networks are legit)
const SALT = process.env.IP_SALT || 'slop-default-salt';

function clientIp(req) {
  const xff = req.headers['x-forwarded-for'] || '';
  return String(xff).split(',')[0].trim() || req.socket?.remoteAddress || 'noip';
}
function ipHash(ip) {
  // HMAC-SHA256 with a server-only salt: groupable, not brute-forceable without the salt.
  return createHmac('sha256', SALT).update(ip).digest('base64url').slice(0, 22);
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  try {
    const { winner, loser, scenario, mode, attention, fingerprint, dwell,
            session, pair, outcome } = req.body || {};
    const tie = outcome === 'both';   // "both are slop" = a draw, no Elo movement
    if (!winner || !loser || winner === loser) {
      return res.status(400).json({ error: 'need distinct winner and loser' });
    }
    if (!MODELS.has(winner) || !MODELS.has(loser)) {
      return res.status(400).json({ error: 'unknown model' });
    }

    // Verification gate. Only verified votes count, but we return a CLEAR reason
    // so the client can tell the user (honest UX) instead of silently dropping it.
    //  session = proof-of-human (issued after Turnstile), bound to IP + not expired.
    //  pair    = proof this exact matchup was served by us; dwell measured server-side.
    let serverDwell = dwell;
    if (REQUIRE_TOKENS && !attention) {
      const s = readToken(session);
      if (!s || s.k !== 'sess' || (s.exp || 0) < Date.now()) {
        await one(['HINCRBY', 'tally', 'rejected:nosession', 1]);
        return res.status(200).json({ ok: true, counted: false, reason: 'verifying' });
      }
      const p = readToken(pair);
      const [pm1, pm2] = [winner, loser].sort();
      if (!p || p.k !== 'pair' || p.a !== pm1 || p.b !== pm2 ||
          (Date.now() - (p.t || 0)) > MAX_PAIR_AGE_MS) {
        await one(['HINCRBY', 'tally', 'rejected:badpair', 1]);
        return res.status(200).json({ ok: true, counted: false, reason: 'stale' });
      }
      serverDwell = Date.now() - p.t;   // trust the server clock, not the client
    }
    if ((fingerprint && String(fingerprint).length > 80) ||
        (scenario && String(scenario).length > 60)) {
      return res.status(400).json({ error: 'oversized field' });
    }
    if (!configured) {
      return res.status(200).json({ ok: true, counted: false, reason: 'no_store' });
    }

    const m = (mode || 'reply').replace(/[^a-z]/g, '') || 'reply';
    const ip = clientIp(req);
    const iph = ipHash(ip);
    const fp = (fingerprint || 'nofp').slice(0, 80);
    const now = Date.now();
    const day = new Date(now).toISOString().slice(0, 10);

    await one(['HINCRBY', 'tally', `${m}:seen`, 1]);

    if (attention) {
      await redis([['HINCRBY', 'tally', 'attention:seen', 1],
        ...(attention === 'passed' ? [['HINCRBY', 'tally', 'attention:passed', 1]] : [])]);
      return res.status(200).json({ ok: true, counted: false, reason: 'attention' });
    }
    if (typeof serverDwell === 'number' && serverDwell < MIN_DWELL_MS) {
      await one(['HINCRBY', 'tally', 'rejected:dwell', 1]);
      return res.status(200).json({ ok: true, counted: false, reason: 'too_fast' });
    }

    // rate floors: both the fingerprint AND the IP must be past the 1.5s gap
    const [lastFp, lastIp] = await redis([['GET', `last:${iph}:${fp}`], ['GET', `lastip:${iph}`]]);
    if ((now - (Number(lastFp) || 0) < MIN_GAP_MS) || (now - (Number(lastIp) || 0) < MIN_GAP_MS)) {
      await one(['HINCRBY', 'tally', 'rejected:rate', 1]);
      return res.status(429).json({ ok: true, counted: false, reason: 'slow_down' });
    }
    // daily caps: fingerprint and IP
    const [cFp, cIp] = await redis([['INCR', `cnt:${iph}:${fp}:${day}`], ['INCR', `cntip:${iph}:${day}`]]);
    if (Number(cFp) === 1) await one(['EXPIRE', `cnt:${iph}:${fp}:${day}`, 86400]);
    if (Number(cIp) === 1) await one(['EXPIRE', `cntip:${iph}:${day}`, 86400]);
    if (Number(cFp) > DAILY_CAP_FP || Number(cIp) > DAILY_CAP_IP) {
      await one(['HINCRBY', 'tally', 'rejected:cap', 1]);
      return res.status(429).json({ ok: true, counted: false, reason: 'daily_cap' });
    }

    await redis([['SET', `last:${iph}:${fp}`, String(now), 'EX', 3600],
                 ['SET', `lastip:${iph}`, String(now), 'EX', 3600]]);

    const board = `elo:${m}`;
    const [rw, rl] = await redis([['HGET', board, winner], ['HGET', board, loser]]);
    const ew = rw != null ? Number(rw) : 1500, el = rl != null ? Number(rl) : 1500;
    const expW = 1 / (1 + 10 ** ((el - ew) / 400));

    // permanent raw record: includes the salted IP hash + fingerprint so a flood
    // can be identified and excised at recompute time. `o` = outcome ('win' | 'both').
    const raw = JSON.stringify({
      t: now, m, w: winner, l: loser, o: tie ? 'both' : 'win', s: scenario || null,
      fp, iph, d: serverDwell || null,
    });

    // "both are slop" is a tie: log + count it, keep both on the board, but move no Elo.
    const eloOps = tie ? [
      ['HSET', board, winner, String(Math.round(ew))],
      ['HSET', board, loser, String(Math.round(el))],
    ] : [
      ['HSET', board, winner, String(Math.round(ew + K * (1 - expW)))],
      ['HSET', board, loser, String(Math.round(el - K * (1 - expW)))],
    ];
    await redis([
      ['RPUSH', 'votes:log', raw],
      ...eloOps,
      ['HINCRBY', `games:${m}`, winner, 1],
      ['HINCRBY', `games:${m}`, loser, 1],
      ['HINCRBY', 'tally', tie ? `${m}:both` : `${m}:counted`, 1],
      ...(scenario ? [['HINCRBY', 'scenario_votes', scenario, 1]] : []),
    ]);
    return res.status(200).json({ ok: true, counted: true, tie });
  } catch (e) {
    return res.status(500).json({ error: String(e).slice(0, 200) });
  }
}
