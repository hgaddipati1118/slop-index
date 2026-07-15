# Spot the Slop — Security & Anti-Bot Posture

Honest assessment. Open crowd voting can never be fully botproof; the strategy is
defense-in-depth + a clean audit trail so a flood can be **excised and the board
recomputed**, plus keeping crowd Elo a *companion* signal, never the headline.

## What's protected (deployed)

| Layer | Stops |
|---|---|
| **Roster allowlist** (`_models.js`) | Fake/garbage models being injected onto the board. Verified: `{"error":"unknown model"}`. |
| **Field length caps** | Storage-bloat abuse (huge winner/fingerprint strings). |
| **Dwell check** (>1.2s) | Votes fired faster than a human could read the pair. |
| **Per-fingerprint floor + daily cap** (1.5s / 400/day) | Casual spam-clicking. |
| **Per-IP floor + daily cap** (1.5s / 800/day) | **Rotating fingerprints from one IP** (the common bypass). |
| **Salted IP HMAC in the raw log** | Bot detection without storing raw-IP PII. Same IP → same `iph`, not reversible without `IP_SALT`. |
| **Permanent raw vote log** | Recovery: rebuild a clean board excluding bad actors. |
| **No model API keys in the deployment** | The game holds only the public outputs + Redis creds (server-side env). Verified none present. |
| **XSS-safe rendering** | Card text is HTML-escaped before markdown render. |

## Residual risks (be honest about these)

1. **Rotating IPs + fingerprints (proxy botnet)** — the fundamental open-voting hole. A determined attacker with many IPs defeats rate limits. LMArena has this too; their answer is post-hoc statistical anomaly detection. Ours is the raw log + per-IP recompute cap.
2. **Client-supplied `dwell`/`fingerprint`** — a bot can forge both. The IP hash (server-derived) is the trustworthy signal; treat fp/dwell as soft.
3. **No proof the voter saw the pair** — the API accepts winner/loser directly. Optional hardening below.

## Recovery — "easy to fix if it happens" (`/api/admin`, token-protected)

```
POST /api/admin { token: <ADMIN_TOKEN>, action, mode:"v1" }
  action "reset"     -> wipe derived board, KEEP raw log
  action "wipe"      -> fresh start (board + raw log)
  action "recompute" -> rebuild board from raw log, capping each IP hash at
                        capPerIp votes (default 50) to neutralize a flood
```
Token is in `slop-game/.admin-secrets` (gitignored). `harness/export_votes.py`
snapshots the raw log to JSONL for offline analysis / archival.

**Playbook if botted:** export the log → inspect vote counts per `iph` →
`recompute` with a sane `capPerIp` → the flood is gone, legit votes remain.

## Hardening — NOW DEPLOYED (both)

- **Cloudflare Turnstile** (invisible/interaction-only). The client solves it once
  on load; `/api/session` verifies with Cloudflare and issues a signed session
  token (HMAC, ~2h, IP-bound). Votes require it. A bot must solve Turnstile per
  IP every couple hours instead of voting freely. Widget created via the CF API
  (sitekey public; secret in `TURNSTILE_SECRET`).
- **Signed pair tokens** (`/api/sign`). When a matchup is shown, the server issues
  an HMAC token binding (scenario, both models, server timestamp). The vote must
  return it, which proves the voter was actually served THIS pair and lets the
  server measure dwell from its own clock — the client can't forge fast/slow reads.

**Vote-gate behavior (honest UX, not silent drops).** An unverified vote is NOT
counted, but `/api/vote` returns `{counted:false, reason}` and the client TELLS
the user (`verifying` / `stale` / `too_fast` / `slow_down` / `daily_cap`). The
personal "you judged N" counter only increments on `counted:true`, so it can
never drift ahead of the real board again.

**Verified end-to-end in a real browser (2026-07-14):** Turnstile mints a session,
a pair token is issued, and a vote reaches the board (`counted:true`). Before this,
the widget was silently dead — see the regression note below.

⚠️ **Regression that hit us once:** the Turnstile container `<div>` had
`id="turnstile"`, which made `window.turnstile` resolve to that DOM element
(named-element global) and blocked Cloudflare's API from installing. The widget
never rendered, no session was ever minted, and EVERY vote was rejected while the
client's local counter kept climbing — board looked "reset on refresh." Fix:
renamed the container to `id="cfslot"`. Never name an element `turnstile`.

Secrets (Vercel env): `TURNSTILE_SITE_KEY`, `TURNSTILE_SECRET`, `TOKEN_SECRET`,
`IP_SALT`, `ADMIN_TOKEN` — all also in `slop-game/.admin-secrets` (gitignored).

**Tradeoff to know:** Turnstile is *required*, so a user who blocks Cloudflare
challenges can't vote (they'll now SEE "still verifying you're human" rather than
silently failing). interaction-only mode makes this rare, but if it ever blocks
legit voters, relaxing it is a one-line change (make session optional).

Keep the mechanical Slop Index as the published headline (it can't be voted on);
present crowd Elo as a corroborating signal with these caveats stated.

## Note on API keys

Model API keys live only in `harness/.run-keys.env` (local, gitignored) and the
shared `slashy-backend/.env`. They are NOT in the deployed game. Keys pasted into
any chat/transcript (Meta Spark, xAI, OpenRouter) should be rotated if that
transcript is shared or logged.
