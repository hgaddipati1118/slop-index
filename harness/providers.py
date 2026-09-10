"""Provider adapter: single entrypoint over LiteLLM's unified interface, with
cost tracking.

Requires `litellm` (see harness/.venv, `python3 -m venv .venv && .venv/bin/pip
install litellm`, or `pip3 install --user litellm` if you'd rather skip the
venv). Reads OPENAI_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY /
FIREWORKS_API_KEY (or FIREWORKS_AI_API_KEY) from the environment; LiteLLM
picks these up itself via its provider prefix convention.
"""
import os
import time

import litellm

litellm.suppress_debug_info = True
litellm.telemetry = False
litellm.drop_params = True  # some providers reject params others accept

TIMEOUT = 120

# Fireworks: LiteLLM wants FIREWORKS_AI_API_KEY; our .env may only set
# FIREWORKS_API_KEY. Bridge it so `fireworks_ai/...` model strings work
# without editing the shared .env.
if os.environ.get("FIREWORKS_API_KEY") and not os.environ.get("FIREWORKS_AI_API_KEY"):
    os.environ["FIREWORKS_AI_API_KEY"] = os.environ["FIREWORKS_API_KEY"]

# alias -> LiteLLM model string. Pilot-002 roster: latest generation, cheapest
# viable tier per family, plus a couple of flagships for the price-vs-slop
# chart. All seven were smoke-tested (1-token calls) against the live APIs
# and against litellm.completion_cost() before this file was used for a real
# run, see the deliverable report for the results.
MODELS = {
    "gpt-5.6-sol":            "gpt-5.6-sol",
    "gpt-5.4-mini":           "gpt-5.4-mini",
    "claude-sonnet-5":        "anthropic/claude-sonnet-5",
    "gemini-3.5-flash":       "gemini/gemini-3.5-flash",
    "gemini-3.1-pro-preview": "gemini/gemini-3.1-pro-preview",
    "deepseek-v4-pro":        "fireworks_ai/accounts/fireworks/models/deepseek-v4-pro",
    "kimi-k2p6":              "fireworks_ai/accounts/fireworks/models/kimi-k2p6",
    # Roster expansion (2026-07-14): the original roster benchmarked Anthropic's
    # WORKHORSE (sonnet-5) rather than its flagship, used a previous-generation
    # OpenAI cheap tier, and omitted GLM. Fixed here. Grok/Qwen still need an
    # OpenRouter or xAI key.
    "claude-fable-5":   "anthropic/claude-fable-5",      # Anthropic FLAGSHIP, #1 Arena creative writing
    "claude-haiku-4-5": "anthropic/claude-haiku-4-5",    # Anthropic cheap tier
    "gpt-5.6-luna":     "gpt-5.6-luna",                  # OpenAI cheap tier, SAME generation as sol
    "glm-5.2":          "fireworks_ai/accounts/fireworks/models/glm-5p2",  # best open model per community
    "claude-opus-4-8":  "anthropic/claude-opus-4-8",     # Anthropic Opus-tier default, completes the ladder
    "gpt-5.6-terra":    "gpt-5.6-terra",                 # OpenAI middle tier, completes sol/terra/luna
    "muse-spark-1.1":   "openai/muse-spark-1.1",         # Meta flagship (OpenAI-compatible custom endpoint)
    "grok-4.5":         "xai/grok-4.5",                  # xAI flagship
    "qwen3.7-max":      "openrouter/qwen/qwen3.7-max",    # Alibaba flagship (proprietary API, safe via OpenRouter)
    "mistral-large":    "openrouter/mistralai/mistral-large-2512",  # Mistral EU flank
    "minimax-m3":       "openrouter/minimax/minimax-m3",  # MiniMax
    # Roster refresh (2026-07-31): four launches since the 2026-07-14 freeze. Two are direct
    # successors to models in the board's top 4, which is the whole franchise argument (slop is
    # a model-VERSION property, not a lab property, so only per-release reruns catch it).
    "claude-opus-5":    "anthropic/claude-opus-5",             # Anthropic flagship, 2026-07-24
    "kimi-k3":          "openrouter/moonshotai/kimi-k3",       # 2026-07-16, succeeds board-cleanest k2.6
    "gemini-3.6-flash": "gemini/gemini-3.6-flash",             # 2026-07-21, succeeds 3.5-flash
    "qwen3.7-flash":    "openrouter/qwen/qwen3.7-flash",       # 2026-07-27, cheap sibling of the Elo leader
    # Roster refresh (2026-09-09): seven direct successors + three cheap refreshes shipped
    # since the 2026-07-31 freeze. Every earlier model STAYS on the board (per-version history
    # is the franchise). All ten smoke-tested with a 1-call probe before being added.
    "gpt-6-astra":          "gpt-6-astra",                                # OpenAI flagship, 2026-08-27 (needs max_completion_tokens)
    "claude-fable-5.1":     "anthropic/claude-fable-5-1",                 # 2026-08-28, succeeds Fable 5
    "gemini-3.8-flash":     "gemini/gemini-3.8-flash",                    # 2026-09-02, succeeds 3.6-flash
    "gemini-3.7-flash":     "gemini/gemini-3.7-flash",                    # 2026-08-13, fills the Google ladder
    "qwen3.8-max":          "openrouter/qwen/qwen3.8-max-0902",           # 2026-09-03, succeeds the Elo leader
    "qwen3.8-flash":        "openrouter/qwen/qwen3.8-flash",              # 2026-08-26
    "muse-spark-1.3":       "openai/muse-spark-1.3",                      # 2026-09-02, Meta direct endpoint (OpenRouter copy is 18+ gated)
    # grok-4.6 started on xai/ direct; the xAI team hit its monthly spend cap after 86 outputs
    # (full-007), so the remaining 1,034 were generated through OpenRouter's x-ai/ route, which
    # is served by xAI itself at the same list price. Same model, same default reasoning.
    "grok-4.6":             "openrouter/x-ai/grok-4.6",                   # 2026-08-12, succeeds Grok 4.5
    "glm-5.3":              "openrouter/z-ai/glm-5.3",                    # 2026-08-18, succeeds GLM-5.2 (not on Fireworks yet)
    "deepseek-v4-pro-0813": "openrouter/deepseek/deepseek-v4-pro-0813",   # 2026-08-12, dated refresh of V4 Pro
}

# Per-alias extra kwargs for models on custom (non-standard) endpoints. The key
# is read from the environment at call time, NEVER hardcoded here (this file is
# committed). Set META_SPARK_API_KEY in the shell before running.
EXTRA = {
    "muse-spark-1.1": lambda: {
        "api_base": "https://api.meta.ai/v1",
        "api_key": os.environ.get("META_SPARK_API_KEY", ""),
    },
    "muse-spark-1.3": lambda: {
        "api_base": "https://api.meta.ai/v1",
        "api_key": os.environ.get("META_SPARK_API_KEY", ""),
    },
}

# Manual fallback prices, $ per 1M tokens (input, output). ONLY used when
# litellm.completion_cost() raises or comes back falsy (0/None) for a given
# response, brand-new model IDs sometimes aren't in LiteLLM's bundled price
# map yet. Values below are each provider's published list price as of
# 2026-07-13; verified they are NOT needed for pilot-002 (all seven model
# strings above resolved via LiteLLM's own price map in the pre-flight smoke
# test, this table exists as a safety net for whichever family drifts out
# of LiteLLM's map next, or a future roster swap).
PRICES = {
    "gpt-5.6-sol":            (5.00, 30.00),   # openai.com/api/pricing
    "gpt-5.4-mini":           (0.75, 4.50),    # openai.com/api/pricing
    "claude-sonnet-5":        (2.00, 10.00),   # anthropic.com/pricing, <=200k ctx tier
    "gemini-3.5-flash":       (1.50, 9.00),    # ai.google.dev/pricing/gemini-3
    "gemini-3.1-pro-preview": (2.00, 12.00),   # ai.google.dev/pricing, <=200k ctx tier
    "deepseek-v4-pro":        (1.74, 3.48),    # fireworks.ai serverless pricing
    "kimi-k2p6":              (0.95, 4.00),    # fireworks.ai serverless pricing
    # Roster additions 2026-07-14, prices verified online:
    "grok-4.5":               (2.00, 6.00),    # x.ai/api, verified 2026-07-14
    "muse-spark-1.1":         (1.25, 4.25),    # aiweekly.co, verified 2026-07-14; reasoning tokens billed at output rate
    "claude-fable-5":         (10.00, 50.00),  # anthropic.com/pricing
    "claude-opus-4-8":        (5.00, 25.00),   # anthropic.com/pricing
    "claude-haiku-4-5":       (1.00, 5.00),    # anthropic.com/pricing
    "gpt-5.6-luna":           (1.00, 6.00),    # openai.com/api/pricing
    "gpt-5.6-terra":          (2.50, 15.00),   # openai.com/api/pricing
    "glm-5.2":                (1.40, 4.40),    # z.ai / fireworks
    "qwen3.7-max":            (2.50, 7.50),    # alibaba list (promo 1.25/3.75); conservative list used
    "minimax-m3":             (0.30, 1.20),    # openrouter
    "mistral-large":          (2.00, 6.00),    # openrouter mistral-large-2512 (Mistral Large tier)
    # Roster additions 2026-07-31, prices read off the live provider/OpenRouter model endpoints:
    "claude-opus-5":          (5.00, 25.00),   # anthropic.com/pricing
    "kimi-k3":                (3.00, 15.00),   # openrouter moonshotai/kimi-k3
    "gemini-3.6-flash":       (1.50, 7.50),    # ai.google.dev/pricing
    "qwen3.7-flash":          (0.03, 0.13),    # openrouter qwen/qwen3.7-flash
    # Roster additions 2026-09-09, prices read off the live provider/OpenRouter endpoints:
    "gpt-6-astra":            (10.00, 50.00),  # openrouter openai/gpt-6-astra
    "claude-fable-5.1":       (10.00, 50.00),  # openrouter anthropic/claude-fable-5.1
    "gemini-3.8-flash":       (0.75, 3.75),    # openrouter google/gemini-3.8-flash
    "gemini-3.7-flash":       (0.75, 3.75),    # openrouter google/gemini-3.7-flash
    "qwen3.8-max":            (2.00, 6.00),    # openrouter qwen/qwen3.8-max-0902
    "qwen3.8-flash":          (0.15, 0.47),    # openrouter qwen/qwen3.8-flash
    "muse-spark-1.3":         (1.25, 4.25),    # openrouter meta/muse-spark-1.3
    "grok-4.6":               (2.00, 6.00),    # openrouter x-ai/grok-4.6
    "glm-5.3":                (1.40, 4.40),    # openrouter z-ai/glm-5.3
    "deepseek-v4-pro-0813":   (0.58, 1.74),    # openrouter deepseek/deepseek-v4-pro-0813
}


def _manual_cost(alias, prompt_tokens, completion_tokens):
    """Fallback $ cost from the PRICES table. Returns None (never a guess) if
    the alias isn't in the table."""
    prices = PRICES.get(alias)
    if not prices or prompt_tokens is None or completion_tokens is None:
        return None
    in_price, out_price = prices
    return (prompt_tokens * in_price + completion_tokens * out_price) / 1_000_000


def generate(alias, system, user, max_tokens=4000):
    """Call `alias` via LiteLLM. Returns (text, usage_dict) where usage_dict has:
    prompt_tokens, completion_tokens, reasoning_tokens (None if not reported),
    cost_usd (None if genuinely unknown), cost_estimated (bool, True if
    cost_usd came from the manual PRICES fallback rather than LiteLLM's own
    price map), model_id, latency_s, retried_8k (bool).
    """
    model_id = MODELS[alias]
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    extra = EXTRA[alias]() if alias in EXTRA else {}

    def call(mt):
        t0 = time.time()
        # gpt-6 rejects `max_tokens` outright (400: use max_completion_tokens) and
        # LiteLLM does not auto-map it for that family yet.
        tok = {"max_completion_tokens": mt} if model_id.startswith("gpt-6") else {"max_tokens": mt}
        resp = litellm.completion(
            model=model_id, messages=messages, timeout=TIMEOUT, **tok, **extra,
        )
        return resp, time.time() - t0

    resp, latency_s = call(max_tokens)
    text = resp.choices[0].message.content or ""
    retried_8k = False

    # Reasoning models (gpt-5.x, gemini-3.x) can burn the whole max_tokens
    # budget on hidden reasoning tokens and return empty visible text. One
    # retry at double the budget before giving up.
    if not text.strip() and max_tokens < 8000:
        resp2, latency2 = call(8000)
        text2 = resp2.choices[0].message.content or ""
        retried_8k = True
        resp, latency_s, text = resp2, latency_s + latency2, text2

    usage = resp.usage
    prompt_tokens = getattr(usage, "prompt_tokens", None)
    completion_tokens = getattr(usage, "completion_tokens", None)
    reasoning_tokens = None
    ctd = getattr(usage, "completion_tokens_details", None)
    if ctd is not None:
        reasoning_tokens = getattr(ctd, "reasoning_tokens", None)

    cost_usd, cost_estimated = None, False
    try:
        c = litellm.completion_cost(completion_response=resp)
        if c:
            cost_usd = float(c)
        else:
            raise ValueError("litellm.completion_cost returned falsy (0/None)")
    except Exception:
        manual = _manual_cost(alias, prompt_tokens, completion_tokens)
        if manual is not None:
            cost_usd, cost_estimated = manual, True
        # else: cost stays None. Never silently report a wrong number.

    usage_dict = {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "reasoning_tokens": reasoning_tokens,
        "cost_usd": cost_usd,
        "cost_estimated": cost_estimated,
        "model_id": model_id,
        "latency_s": round(latency_s, 3),
        "retried_8k": retried_8k,
    }
    return text.strip(), usage_dict
