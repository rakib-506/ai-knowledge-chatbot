"""Smart multi-provider LLM wrapper with automatic fallback.

Tries models one by one until one works. Supports 4 providers:
  - Google Gemini (free tier)
  - xAI Grok (free tier)
  - Groq (free, no credit card, very fast)
  - OpenRouter (free models, no credit card)

Set your keys in .env. You need at least one key. The more keys you add,
the more backup models you have.

Settings in .env:
    GEMINI_API_KEY=your-gemini-key           (optional, from ai.google.dev)
    GROK_API_KEY=your-grok-key               (optional, from console.x.ai)
    GROQ_API_KEY=your-groq-key               (optional, free at console.groq.com)
    OPENROUTER_API_KEY=your-openrouter-key   (optional, free at openrouter.ai)

The system tries models in this order and stops at the first one that answers.
Each model gets 10 seconds max — if it is slow, we move to the next one.
"""
import os
from .logger import log

# ---------- keys (read from .env) ----------
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROK_KEY = os.getenv("GROK_API_KEY", "").strip()
GROQ_KEY = os.getenv("GROQ_API_KEY", "").strip()
OPENROUTER_KEY = os.getenv("OPENROUTER_API_KEY", "").strip()

# Remove placeholder values (simple and reliable)
if GEMINI_KEY.startswith(("paste-", "your-")):
    GEMINI_KEY = ""
if GROK_KEY.startswith(("paste-", "your-")):
    GROK_KEY = ""
if GROQ_KEY.startswith(("paste-", "your-")):
    GROQ_KEY = ""
if OPENROUTER_KEY.startswith(("paste-", "your-")):
    OPENROUTER_KEY = ""


class LLMError(Exception):
    """Raised when no model could answer."""


# ---------- model definitions ----------
# Each entry: (display_name, provider, model_id)
# The system skips any entry whose provider has no key.
# More models = more chances at least one answers.
FALLBACK_CHAIN = [
    # --- Gemini (free tier from Google) ---
    ("Gemini Flash Latest", "gemini", "gemini-flash-latest"),
    ("Gemini 2.5 Flash", "gemini", "gemini-2.5-flash-preview-05-20"),

    # --- Groq (free, very fast, no credit card needed) ---
    ("Groq Llama 3.3 70B", "groq", "llama-3.3-70b-versatile"),
    ("Groq Llama 3.1 8B", "groq", "llama-3.1-8b-instant"),
    ("Groq GPT-OSS 20B", "groq", "openai/gpt-oss-20b"),

    # --- xAI Grok (if you have a key) ---
    ("Grok 3 Mini Fast", "grok", "grok-3-mini-fast"),

    # --- OpenRouter free models (no credit card needed) ---
    ("OR Gemma 4 27B", "openrouter", "google/gemma-4-27b-it:free"),
    ("OR Gemma 4 31B", "openrouter", "google/gemma-4-31b-it:free"),
    ("OR Nemotron Lightning", "openrouter", "nvidia/nemotron-3.5-lightning:free"),
    ("OR Nemotron Super", "openrouter", "nvidia/nemotron-3-super-120b-a12b:free"),
    ("OR Qwen 3.8 27B", "openrouter", "qwen/qwen3.8-27b:free"),
]

# ---------- clients (created once, on first use) ----------
_clients = {}


def _get_client(provider):
    """Get or create an OpenAI-compatible client for the given provider."""
    if provider not in _clients:
        from openai import OpenAI

        if provider == "grok":
            _clients[provider] = OpenAI(
                api_key=GROK_KEY,
                base_url="https://api.x.ai/v1",
                timeout=10.0,
            )
        elif provider == "groq":
            _clients[provider] = OpenAI(
                api_key=GROQ_KEY,
                base_url="https://api.groq.com/openai/v1",
                timeout=10.0,
            )
        elif provider == "openrouter":
            _clients[provider] = OpenAI(
                api_key=OPENROUTER_KEY,
                base_url="https://openrouter.ai/api/v1",
                timeout=10.0,
            )
    return _clients[provider]


_gemini_client = None


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_KEY)
    return _gemini_client


# ---------- provider-specific calls ----------
def _call_gemini(model_id, prompt, system, temperature):
    from google.genai import types
    response = _get_gemini().models.generate_content(
        model=model_id,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=system or None,
            temperature=temperature,
            http_options={"timeout": 10000},
        ),
    )
    return (response.text or "").strip()


def _call_openai_compatible(provider, model_id, prompt, system, temperature):
    """Works for Grok, Groq, and OpenRouter — all use the OpenAI format."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = _get_client(provider).chat.completions.create(
        model=model_id,
        messages=messages,
        temperature=temperature,
        max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()


# ---------- error classification ----------
def _is_permanent(error_msg):
    keywords = ["api key", "api_key", "invalid key", "401", "403",
                "permission", "denied", "authentication", "unauthorized",
                "invalid token", "invalid credentials"]
    lower = error_msg.lower()
    return any(k in lower for k in keywords)


def _is_temporary(error_msg):
    keywords = ["429", "rate", "resource_exhausted", "overloaded",
                "503", "504", "unavailable", "high demand", "capacity",
                "quota", "too many requests", "busy", "timeout", "timed out",
                "gateway", "connection", "reset", "refused"]
    lower = error_msg.lower()
    return any(k in lower for k in keywords)


def _is_model_not_found(error_msg):
    keywords = ["404", "not_found", "not found", "does not exist",
                "no longer available", "model not found", "unknown model",
                "not a chat model", "is not a", "unsupported model",
                "payment required", "402"]
    lower = error_msg.lower()
    return any(k in lower for k in keywords)


# ---------- main function ----------
_last_model = None


def get_active_model():
    """Return the name of the model that answered last, for display."""
    return _last_model or "not connected yet"


def _provider_has_key(provider):
    """Check if a provider has a valid API key."""
    return (
        (provider == "gemini" and bool(GEMINI_KEY)) or
        (provider == "grok" and bool(GROK_KEY)) or
        (provider == "groq" and bool(GROQ_KEY)) or
        (provider == "openrouter" and bool(OPENROUTER_KEY))
    )


def generate(prompt, system="", temperature=0.2):
    """Try each model in the fallback chain. Stop at the first success."""
    global _last_model

    # Check if we have at least one key
    if not any([GEMINI_KEY, GROK_KEY, GROQ_KEY, OPENROUTER_KEY]):
        raise LLMError(
            "No API keys found. Add at least one to backend/.env:\n"
            "  GEMINI_API_KEY      (from ai.google.dev)\n"
            "  GROQ_API_KEY        (from console.groq.com — free, no card!)\n"
            "  OPENROUTER_API_KEY  (from openrouter.ai — free, no card!)\n"
            "  GROK_API_KEY        (from console.x.ai)"
        )

    # Build the list of models to try (skip providers with no key)
    models_to_try = [
        (name, provider, model_id)
        for name, provider, model_id in FALLBACK_CHAIN
        if _provider_has_key(provider)
    ]

    if not models_to_try:
        raise LLMError("No valid API keys. Check backend/.env.")

    blocked_providers = set()
    errors = []

    for name, provider, model_id in models_to_try:
        if provider in blocked_providers:
            continue

        try:
            log.info(f"Trying: {name} ...")

            if provider == "gemini":
                result = _call_gemini(model_id, prompt, system, temperature)
            else:
                result = _call_openai_compatible(provider, model_id, prompt,
                                                  system, temperature)

            if result:
                if _last_model != name:
                    log.info(f"Using model: {name} ({model_id})")
                    _last_model = name
                return result

        except Exception as e:
            error_msg = str(e)
            short_error = error_msg[:150]
            log.warning(f"{name} failed: {short_error}")

            if _is_model_not_found(error_msg):
                log.warning(f"Model '{model_id}' not available — skipping")
                errors.append(f"{name}: not available")
            elif _is_permanent(error_msg):
                log.warning(f"Blocking provider '{provider}' (bad key)")
                blocked_providers.add(provider)
                errors.append(f"{name}: key error")
            elif _is_temporary(error_msg):
                errors.append(f"{name}: busy/timeout")
            else:
                errors.append(f"{name}: {short_error}")

    # All models failed
    error_summary = " | ".join(errors)
    log.error(f"All models failed: {error_summary}")

    active = {p for p in ["gemini", "grok", "groq", "openrouter"]
              if _provider_has_key(p)}

    if blocked_providers >= active:
        raise LLMError("All API keys are invalid. Check backend/.env.")

    raise LLMError(
        "All AI models are busy right now. Please wait a minute and try again. "
        f"(Tried: {error_summary})"
    )
