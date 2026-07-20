// Issues a signed pair token when the client is shown a matchup. The token
// binds (scenario, the two models, a server timestamp). The vote must return
// it, which proves: (a) the voter was actually served THIS pair by our server,
// and (b) how long they looked at it, the dwell is measured server-side from
// the token timestamp, so the client can't forge a fast/slow read.
import { makeToken } from './_sign.js';
import { MODELS } from './_models.js';

export default async function handler(req, res) {
  if (req.method !== 'POST') return res.status(405).json({ error: 'POST only' });
  const { scenario, a, b } = req.body || {};
  if (!MODELS.has(a) || !MODELS.has(b) || a === b) {
    return res.status(400).json({ error: 'bad pair' });
  }
  // sort models so the token is order-independent (client randomizes sides)
  const [m1, m2] = [a, b].sort();
  const token = makeToken({ k: 'pair', s: String(scenario || '').slice(0, 60), a: m1, b: m2, t: Date.now() });
  return res.status(200).json({ ok: true, pair: token });
}
