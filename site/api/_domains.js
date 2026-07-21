// Scenario ids are "<domain>.<type>.<nnn>" (e.g. "email.cold.002"); the domain is the
// first dot-segment. Derived SERVER-side from the signed scenario so a client can't
// stuff votes into a different domain's board than the pair it was actually shown.
export const VOTE_DOMAINS = ['email', 'social', 'essay', 'slack'];
const SET = new Set(VOTE_DOMAINS);
export const domainOf = (s) => {
  const d = String(s || '').split('.')[0];
  return SET.has(d) ? d : null;
};
