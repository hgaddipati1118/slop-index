// HMAC sign/verify for short-lived tokens (session + pair). No secrets ever
// reach the client; tokens are payload.signature, verified server-side.
import { createHmac, timingSafeEqual } from 'node:crypto';

const SECRET = process.env.TOKEN_SECRET || 'dev-token-secret';

function b64u(obj) {
  return Buffer.from(JSON.stringify(obj)).toString('base64url');
}
function sig(body) {
  return createHmac('sha256', SECRET).update(body).digest('base64url').slice(0, 32);
}

export function makeToken(payload) {
  const body = b64u(payload);
  return `${body}.${sig(body)}`;
}

export function readToken(token) {
  if (!token || typeof token !== 'string' || !token.includes('.')) return null;
  const [body, s] = token.split('.');
  const expect = sig(body);
  try {
    if (!timingSafeEqual(Buffer.from(s), Buffer.from(expect))) return null;
    return JSON.parse(Buffer.from(body, 'base64url').toString());
  } catch { return null; }
}
