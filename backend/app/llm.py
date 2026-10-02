"""Small wrapper around the Google Gemini API."""
from google import genai
from google.genai import types

from .config import GEMINI_API_KEY, GEMINI_MODEL
from .logger import log

_client = None


class LLMError(Exception):
    """Raised when Gemini cannot answer (bad key, rate limit, network...)."""


def _get_client():
    global _client
    if _client is None:
        if not GEMINI_API_KEY or GEMINI_API_KEY.startswith("paste-"):
            raise LLMError("Gemini API key is missing. Add GEMINI_API_KEY to backend/.env.")
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def generate(prompt: str, system: str = "", temperature: float = 0.2) -> str:
    try:
        response = _get_client().models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system or None,
                                               temperature=temperature),
        )
        return (response.text or "").strip()
    except LLMError:
        raise
    except Exception as e:
        msg = str(e)
        log.error(f"Gemini error: {msg[:300]}")
        if "429" in msg or "RESOURCE_EXHAUSTED" in msg:
            raise LLMError("The AI service is busy (free limit reached). Please wait a minute and try again.")
        if "API key" in msg or "401" in msg or "403" in msg:
            raise LLMError("The Gemini API key is not valid. Please check backend/.env.")
        if "404" in msg or "NOT_FOUND" in msg:
            raise LLMError(f"Gemini model '{GEMINI_MODEL}' was not found. Change GEMINI_MODEL in backend/.env.")
        raise LLMError("The AI service is not available right now. Please try again.")
