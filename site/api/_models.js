// The valid model roster, votes for anything not on this list are rejected,
// which blocks fake-model injection into the leaderboard. Regenerated whenever
// the benchmark roster changes (kept in sync with public/pairs.json).
// Roster refresh 2026-07-31: +claude-opus-5, +kimi-k3, +gemini-3.6-flash,
// +qwen3.7-flash. Generate this block with `harness/build_pairs.py`, which
// prints it, and update it in the SAME commit as public/pairs.json. A model
// present in pairs.json but missing here has every vote silently dropped.
export const MODELS = new Set([
  "claude-fable-5", "claude-fable-5.1", "claude-haiku-4-5",
  "claude-opus-4-8", "claude-opus-5", "claude-sonnet-5", "deepseek-v4-pro",
  "deepseek-v4-pro-0813", "deepseek-v4.1-flash", "gemini-3.1-pro-preview",
  "gemini-3.5-flash", "gemini-3.6-flash", "gemini-3.7-flash",
  "gemini-3.8-flash", "glm-5.2", "glm-5.3", "gpt-5.4-mini", "gpt-5.6-luna",
  "gpt-5.6-sol", "gpt-5.6-terra", "gpt-6-astra", "gpt-6-astra-pro",
  "grok-4.5", "grok-4.6", "hy4-preview", "inkling-small", "kimi-k2p6",
  "kimi-k3", "mercury-2.5", "minimax-m3", "mistral-large", "muse-spark-1.1",
  "muse-spark-1.3", "nemotron-3.5-lightning", "qwen3.7-flash", "qwen3.7-max",
  "qwen3.8-flash", "qwen3.8-max", "seed-2.1-turbo" 
]);
