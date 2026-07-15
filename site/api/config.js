// Public client config: the Turnstile SITE key (public by design) and whether
// the token gate is active. No secrets here.
export default function handler(req, res) {
  res.setHeader('Cache-Control', 's-maxage=300');
  return res.status(200).json({
    turnstileSiteKey: process.env.TURNSTILE_SITE_KEY || null,
    tokensRequired: Boolean(process.env.TOKEN_SECRET),
  });
}
