"""
agents/llm_provider.py -- Thin LLM abstraction layer.

Wraps google-generativeai (Gemini) behind a single call:

    response = LLMProvider().call(prompt)

Behaviour
---------
- If GEMINI_API_KEY is set in .env, uses Gemini 1.5 Flash (one call, no loops).
- If the key is missing or the call fails, falls back to a lightweight stub
  that does keyword-based action selection -- fully offline and deterministic.

The stub keeps the hackathon runnable without any API key, while the real
path gives polished natural-language responses when the key is present.

No agent should call this more than once per user request.
"""

from __future__ import annotations

import warnings
from typing import Any

from backend.config import settings

# Suppress the deprecation warning printed to stderr by google-generativeai.
warnings.filterwarnings("ignore", category=FutureWarning, module="google")

_GEMINI_AVAILABLE = False
_genai: Any = None

if settings.GEMINI_API_KEY:
    try:
        import google.generativeai as _genai_module  # type: ignore[import]
        _genai_module.configure(api_key=settings.GEMINI_API_KEY)
        _genai = _genai_module
        _GEMINI_AVAILABLE = True
    except Exception:
        _GEMINI_AVAILABLE = False


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------

class LLMProvider:
    """
    Single-call LLM wrapper used by all specialist agents.

    Usage::

        llm = LLMProvider()
        text = llm.call("Summarise this tool result: ...")
    """

    def __init__(self, model: str = "gemini-1.5-flash") -> None:
        self._model_name = model
        self._available = _GEMINI_AVAILABLE

    @property
    def is_live(self) -> bool:
        """True when a real LLM is configured and reachable."""
        return self._available

    def call(self, prompt: str) -> str:
        """
        Send a single prompt to the LLM and return the text response.

        Falls back to the stub if the LLM is unavailable or raises.
        """
        if self._available and _genai is not None:
            try:
                model = _genai.GenerativeModel(self._model_name)
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as exc:
                return f"[LLM unavailable: {exc}] (deterministic tool result returned above)"
        return "[LLM not configured -- add GEMINI_API_KEY to .env for AI-generated responses]"
