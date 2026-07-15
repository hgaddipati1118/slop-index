// The valid model roster — votes for anything not on this list are rejected,
// which blocks fake-model injection into the leaderboard. Regenerated whenever
// the benchmark roster changes (kept in sync with public/pairs.json).
export const MODELS = new Set([
  "claude-fable-5", "claude-haiku-4-5", "claude-opus-4-8", "claude-sonnet-5",
  "deepseek-v4-pro", "gemini-3.1-pro-preview", "gemini-3.5-flash", "glm-5.2",
  "gpt-5.4-mini", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-5.6-terra",
  "grok-4.5", "kimi-k2p6", "muse-spark-1.1",
  "minimax-m3", "mistral-large", "qwen3.7-max",
]);
