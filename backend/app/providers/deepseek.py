"""
DeepSeek LLM provider — Phase 1 real implementation.

Uses the openai SDK in JSON mode against the DeepSeek OpenAI-compatible
Chat Completions endpoint. Retry logic for malformed JSON lives here
at the provider level (raw JSON parse), while schema-level retry lives
in classifier_service.

ADR-02: classify() returns dict (raw parsed JSON). The schema discriminated
union parse is the responsibility of classifier_service.
"""

from __future__ import annotations

import json
import logging

from openai import AsyncOpenAI

from app.core.config import Settings
from app.core.metrics import aria_classification_latency_seconds
from app.providers.base import LLMProvider
from app.services.classifier_service import ClassifierError

logger = logging.getLogger(__name__)

_DEEPSEEK_BASE_URL = "https://api.deepseek.com"
_CLASSIFY_MODEL = "deepseek-chat"    # ADR-1: classification model
_REASON_MODEL = "deepseek-reasoner"  # ADR-1: reasoning / RAG model
_MAX_ATTEMPTS = 3  # 1 initial + 2 retries

_ARIA_REASON_SYSTEM = (
    "You are ARIA, a thoughtful personal assistant. "
    "Answer clearly and concisely based on the provided context and conversation history. "
    "If context passages are provided, reference them in your answer. "
    "No markdown formatting unless necessary."
)


class DeepSeekProvider(LLMProvider):
    """Real LLM provider backed by DeepSeek (OpenAI-compatible API)."""

    def __init__(self, settings: Settings) -> None:
        self._client = AsyncOpenAI(
            api_key=settings.deepseek_api_key,
            base_url=_DEEPSEEK_BASE_URL,
        )

    async def classify(
        self,
        message: str,
        *,
        system: str | None = None,
    ) -> dict:
        """
        Call DeepSeek in JSON mode and return the parsed dict.

        Retries up to _MAX_ATTEMPTS times on JSONDecodeError.

        Args:
            message: The raw user message to classify.
            system: System prompt (built by classifier_service.build_system_prompt).

        Returns:
            Parsed dict with at minimum an 'intent' key.

        Raises:
            ClassifierError: If all attempts produce unparseable JSON.
        """
        if aria_classification_latency_seconds is None:
            return await self._classify_impl(message, system=system)

        with aria_classification_latency_seconds.labels(model=_CLASSIFY_MODEL).time():
            return await self._classify_impl(message, system=system)

    async def _classify_impl(
        self,
        message: str,
        *,
        system: str | None = None,
    ) -> dict:
        """Internal classification implementation (called with or without timing)."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": message})

        last_error: Exception | None = None

        for attempt in range(1, _MAX_ATTEMPTS + 1):
            completion = await self._client.chat.completions.create(
                model=_CLASSIFY_MODEL,
                messages=messages,  # type: ignore[arg-type]
                response_format={"type": "json_object"},
                temperature=0,
                max_tokens=512,
            )
            raw_content = completion.choices[0].message.content or ""

            try:
                parsed = json.loads(raw_content)
                if attempt > 1:
                    logger.info(
                        "deepseek_provider: classify succeeded on attempt %d/%d",
                        attempt,
                        _MAX_ATTEMPTS,
                    )
                return parsed
            except json.JSONDecodeError as exc:
                last_error = exc
                logger.warning(
                    "deepseek_provider: classify attempt %d/%d: JSONDecodeError: %s",
                    attempt,
                    _MAX_ATTEMPTS,
                    exc,
                )

        raise ClassifierError(
            f"DeepSeek returned unparseable JSON after {_MAX_ATTEMPTS} attempts. "
            f"Last error: {last_error}"
        ) from last_error

    async def reason(
        self,
        prompt: str,
        *,
        context: list[str] | None = None,
        history: list[dict] | None = None,
    ) -> str:
        """
        Generate a reasoned natural-language response using deepseek-reasoner.

        Builds a messages list in order:
          1. System message (ARIA identity)
          2. One system-role block per context passage (labeled)
          3. History turns (role/content dicts from conversation_service)
          4. Final user prompt

        Args:
            prompt: The question or instruction to reason about.
            context: Optional list of RAG passage strings.
            history: Optional list of conversation turn dicts (role + content).

        Returns:
            The model's text response as a non-empty string.
        """
        messages: list[dict] = [
            {"role": "system", "content": _ARIA_REASON_SYSTEM},
        ]

        # Inject context passages as system-role blocks (labeled)
        for passage_text in (context or []):
            messages.append({
                "role": "system",
                "content": passage_text,
            })

        # Inject conversation history turns before the final user prompt
        for turn in (history or []):
            role = turn.get("role", "user")
            content = turn.get("content", "")
            messages.append({"role": role, "content": content})

        # The actual user question / instruction
        messages.append({"role": "user", "content": prompt})

        completion = await self._client.chat.completions.create(
            model=_REASON_MODEL,
            messages=messages,  # type: ignore[arg-type]
            temperature=0.3,
            max_tokens=1024,
        )

        return (completion.choices[0].message.content or "").strip()
