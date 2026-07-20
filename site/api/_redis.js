// Minimal Upstash Redis REST client, no npm dependency, no build step.
// Reads UPSTASH_REDIS_REST_URL/TOKEN (Upstash integration) or KV_REST_API_URL/
// TOKEN (Vercel KV). Returns a `configured` flag so the game degrades
// gracefully (still playable, votes just not persisted) before a store is added.
const URL = process.env.UPSTASH_REDIS_REST_URL || process.env.KV_REST_API_URL;
const TOKEN = process.env.UPSTASH_REDIS_REST_TOKEN || process.env.KV_REST_API_TOKEN;

export const configured = Boolean(URL && TOKEN);

// Pipeline of commands in one round-trip. cmds = [["INCR","k"], ...]
export async function redis(cmds) {
  if (!configured) return cmds.map(() => null);
  const r = await fetch(`${URL}/pipeline`, {
    method: 'POST',
    headers: { Authorization: `Bearer ${TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify(cmds),
  });
  if (!r.ok) throw new Error(`redis ${r.status}`);
  const out = await r.json();
  return out.map((x) => (x && 'result' in x ? x.result : x));
}

export async function one(cmd) {
  return (await redis([cmd]))[0];
}
