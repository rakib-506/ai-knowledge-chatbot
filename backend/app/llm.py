"""Smart multi-provider LLM wrapper with automatic fallback.

Tries models one by one until one works. Supports Google Gemini, xAI Grok,
and Hugging Face (free safety net). Each model gets 10 seconds to respond.
"""
import os
from .logger import log

GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GROK_KEY = os.getenv("GROK_API_KEY", "").strip()
HF_KEY = os.getenv("HF_API_KEY", "").strip()

if GEMINI_KEY.startswith("paste-"):
    GEMINI_KEY = ""
if GROK_KEY.startswith("paste-"):
    GROK_KEY = ""
if HF_KEY.startswith("paste-"):
    HF_KEY = ""


class LLMError(Exception):
    """Raised when no model could answer."""


FALLBACK_CHAIN = [
    ("Grok 3 Mini Fast", "grok", "grok-3-mini-fast"),
    ("Gemini 3.8 Flash", "gemini", "gemini-3.8-flash"),
    ("Gemini Flash Latest", "gemini", "gemini-flash-latest"),
    ("Grok 4.1 Fast", "grok", "grok-4.1-fast"),
    ("Gemini 1.5 Flash", "gemini", "gemini-1.5-flash"),
    ("Qwen 2.5 72B", "huggingface", "Qwen/Qwen2.5-72B-Instruct"),
    ("Mistral Small 24B", "huggingface", "mistralai/Mistral-Small-24B-Instruct-2501"),
]

_gemini_client = None
_grok_client = None
_hf_client = None


def _get_gemini():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=GEMINI_KEY)
    return _gemini_client


def _get_grok():
    global _grok_client
    if _grok_client is None:
        from openai import OpenAI
        _grok_client = OpenAI(
            api_key=GROK_KEY,
            base_url="https://api.x.ai/v1",
            timeout=10.0,
        )
    return _grok_client


def _get_hf():
    global _hf_client
    if _hf_client is None:
        from huggingface_hub import InferenceClient
        _hf_client = InferenceClient(token=HF_KEY, timeout=10)
    return _hf_client


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


def _call_grok(model_id, prompt, system, temperature):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = _get_grok().chat.completions.create(
        model=model_id, messages=messages, temperature=temperature,
    )
    return (response.choices[0].message.content or "").strip()


def _call_huggingface(model_id, prompt, system, temperature):
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    response = _get_hf().chat.completions.create(
        model=model_id, messages=messages,
        temperature=max(temperature, 0.01), max_tokens=1024,
    )
    return (response.choices[0].message.content or "").strip()


def _is_permanent(error_msg):
    keywords = ["api key", "api_key", "invalid key", "401", "403",
                "permission", "denied", "authentication", "unauthorized",
                "invalid token", "invalid credentials"]
    lower = error_msg.lower()
    return any(k in lower for k in keywords)


def _is_temporary(error_msg):
    keywords = ["429", "rate", "resource_exhausted", "overloaded",
                "503", "unavailable", "high demand", "capacity", "quota",
                "too many requests", "busy", "timeout", "timed out",
                "504", "gateway"]
    lower = error_msg.lower()
    return any(k in lower for k in keywords)


def _is_model_not_found(error_msg):
    keywords = ["404", "not_found", "not found", "does not exist",
                "no longer available", "model not found", "unknown model"]
    lower = error_msg.lower()
    return any(k in lower for k in keywords)


_last_model = None


def get_active_model():
    return _last_model or "not connected yet"


def generate(prompt, system="", temperature=0.2):
    global _last_model

    if not GEMINI_KEY and not GROK_KEY and not HF_KEY:
        raise LLMError(
            "No API keys found. Add at least one to backend/.env:\n"
            "  GEMINI_API_KEY  (from ai.google.dev)\n"
            "  GROK_API_KEY    (from console.x.ai)\n"
            "  HF_API_KEY      (from huggingface.co/settings/tokens — free!)"
        )

    models_to_try = []
    for name, provider, model_id in FALLBACK_CHAIN:
        if provider == "gemini" and GEMINI_KEY:
            models_to_try.append((name, provider, model_id))
        elif provider == "grok" and GROK_KEY:
            models_to_try.append((name, provider, model_id))
        elif provider == "huggingface" and HF_KEY:
            models_to_try.append((name, provider, model_id))

    if not models_to_try:
        raise LLMError(
            "No API keys found. Add at least one to backend/.env:\n"
            "  GEMINI_API_KEY  (from ai.google.dev)\n"
            "  GROK_API_KEY    (from console.x.ai)\n"
            "  HF_API_KEY      (from huggingface.co/settings/tokens — free!)"
        )

    blocked_providers = set()
    errors = []

    for name, provider, model_id in models_to_try:
        if provider in blocked_providers:
            continue
        try:
            log.info(f"Trying: {name} ({model_id})...")
            if provider == "gemini":
                result = _call_gemini(model_id, prompt, system, temperature)
            elif provider == "grok":
                result = _call_grok(model_id, prompt, system, temperature)
            else:
                result = _call_huggingface(model_id, prompt, system, temperature)

            if result:
                if _last_model != name:
                    log.info(f"Using model: {name} ({model_id})")
                    _last_model = name
                return result

        except Exception as e:
            error_msg = str(e)
            short_error = error_msg[:200]
            log.warning(f"{name} ({model_id}) failed: {short_error}")

            if _is_model_not_found(error_msg):
                log.warning(f"Model '{model_id}' not found — skipping it")
                errors.append(f"{name}: model not found")
            elif _is_permanent(error_msg):
                log.warning(f"Blocking provider '{provider}' (bad key)")
                blocked_providers.add(provider)
                errors.append(f"{name}: key error")
            elif _is_temporary(error_msg):
                errors.append(f"{name}: busy/timeout")
            else:
                errors.append(f"{name}: {short_error}")

    error_summary = " | ".join(errors)
    log.error(f"All models failed: {error_summary}")

    active_providers = {p for p in ["gemini", "grok", "huggingface"]
                        if (p == "gemini" and GEMINI_KEY) or
                           (p == "grok" and GROK_KEY) or
                           (p == "huggingface" and HF_KEY)}

    if blocked_providers >= active_providers:
        raise LLMError("All API keys are invalid. Check backend/.env.")

    raise LLMError(
        "All AI models are busy right now. Please wait a minute and try again. "
        f"(Tried: {error_summary})"
    )
