// Proof-of-human: the client solves Cloudflare Turnstile once, posts the token
// here, we verify it with Cloudflare, and issue a signed session token (valid
// ~2h, bound to the caller's IP hash). Votes require this token, so a bot must
// solve Turnstile per IP every couple hours instead of voting freely.
// If TURNSTILE_SECRET isn't set, sessions are issued freely (graceful dev mode).
import { createHmac } from 'node:crypto';
import { makeToken } from './_sign.js';

const SALT = process.env.IP_SALT || 'slop-default-salt';
const TTL_MS = 2 * 60 * 60 * 1000;

function ipHash(req) {
  const xff = req.headers['x-forwarded-for'] || '';
  const ip = String(xff).split(',')[0].trim() || 'noip';
  return createHmac('sha256', SALT).update(ip).digest('base64url').slice(0, 22);
}

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const iph = ipHash(req);
  const secret = process.env.TURNSTILE_SECRET;

  if (secret) {
    const tok = (req.body || {}).turnstile;
    if (!tok) return res.status(400).json({ error: 'missing turnstile token' });
    try {
      const form = new URLSearchParams({ secret, response: tok });
      const xff = req.headers['x-forwarded-for'] || '';
      const ip = String(xff).split(',')[0].trim();
      if (ip) form.append('remoteip', ip);
      const r = await fetch('https://challenges.cloudflare.com/turnstile/v0/siteverify',
        { method: 'POST', body: form });
      const out = await r.json();
      if (!out.success) return res.status(403).json({ error: 'turnstile failed', codes: out['error-codes'] });
    } catch (e) {
      return res.status(502).json({ error: 'verify unreachable' });
    }
  }
  const token = makeToken({ k: 'sess', iph, exp: Date.now() + TTL_MS });
  return res.status(200).json({ ok: true, session: token });
}
