"""
Classifier service.

Orchestrates prompt building and provider calls to produce a typed
ClassifierOutput from a raw user message. Owns the retry logic and
the Pydantic discriminated-union parse step.

ADR-02: DeepSeekProvider.classify() returns dict; this service wraps it
into ClassifierOutput. The provider has no knowledge of the schema.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import TypeAdapter, ValidationError

from app.providers.base import LLMProvider
from app.schemas.classifier import ClassifierOutput

logger = logging.getLogger(__name__)

_CLASSIFIER_ADAPTER = TypeAdapter(ClassifierOutput)

_MAX_ATTEMPTS = 3  # 1 initial + 2 retries


class ClassifierError(Exception):
    """Raised when the classifier fails to produce a valid ClassifierOutput."""


def build_system_prompt(
    projects: list[dict],
    current_datetime: str,
    timezone: str,
) -> str:
    """
    Build the system prompt for the classifier LLM call.

    Args:
        projects: List of active project dicts with at least a 'name' key.
        current_datetime: ISO-8601 datetime string for the current moment.
        timezone: IANA timezone string for the user (e.g. 'America/Argentina/Buenos_Aires').

    Returns:
        A system prompt string instructing the LLM to return JSON only.
    """
    project_names = ", ".join(p["name"] for p in projects) if projects else "Personal"

    return f"""You are ARIA, a personal assistant classifier. Your job is to analyze the user's message and return ONLY a valid JSON object (no markdown, no extra text).

Current date-time (UTC): {current_datetime}
User timezone: {timezone}
Active projects: {project_names}

Return a JSON object with one of these intent values:

1. "capture" — the user wants to add a task, event, reminder, or note.
   Required fields: intent, record_type (task|event|reminder|note), title
   Optional: project_hint, deadline, starts_at, duration_min, due_at, amount, currency, tags
   Optional for tasks: energy_level ("low" = administrative/quick, "medium" = default, "high" = complex/research/deep-work)

   IMPORTANT for reminders and tasks:
   - ALWAYS convert relative times to absolute ISO-8601 datetimes in UTC.
   - "en 15 min" → current_time + 15 minutes (e.g., if current is "2026-05-30T20:35:00Z", return "2026-05-30T20:50:00Z")
   - "mañana" → next day at 09:00 in user's timezone, converted to UTC
   - "en 2 horas" → current_time + 2 hours
   - "el viernes" → next Friday at 09:00 in user's timezone
   - "a las 3pm" → today at 15:00 in user's timezone (or tomorrow if already past)
   - If no time specified for a reminder, set due_at to 1 hour from now in UTC
   - Calculate the actual datetime value — do NOT return relative text like "en 15 min"

2. "correction" — the user is correcting a previous classification.
   Required fields: intent
   Optional: new_type (task|event|reminder|note), new_project_hint

3. "context_note_update" — the user is adding context to an existing task.
   Required fields: intent, task_reference, update_text

4. "query" — the user is asking a factual question that can be answered from general knowledge.
   Required fields: intent, query_text
   IMPORTANT: If the message contains URLs, documents, or references to specific material AND the user wants to learn/study/understand it, classify as "study" instead of "query". "query" is for simple factual questions like "what is the capital of France?", not for studying material.

5. "conversation" — the user is chatting casually, greeting, saying thanks, making small talk, or saying something trivial that is NOT a task, event, reminder, note, query, or correction.
   Required fields: intent
   IMPORTANT: Greetings ("hola", "hello"), thanks ("gracias", "thanks"), farewells ("chau", "bye"), and trivial small talk MUST be classified as "conversation", NOT as "capture" or "query".

6. "web_search" — the user wants to search the web for current or external information.
   Required fields: intent, query_text
   Optional: max_results (default 5)
   Triggers: "search for", "latest on", "what is X", "look up", "find information about", "google"
   IMPORTANT: Only classify as web_search when the user explicitly wants external/current information. General knowledge questions should be "query".

7. "study" — the user wants structured study help on a topic, document, or list of resources.
   Required fields: intent, mode ("summarize" | "quiz" | "explain" | "flashcards")
   Optional: source_text, source_url
   Triggers: "summarize this", "quiz me on", "explain like I'm 5", "make flashcards from", "study mode", "help me study", "ayudame a estudiar", "estudiar", "study this", "teach me about", "prep me for", "I need to learn", "quiero aprender", "necesito entender"
   The mode should be inferred from the user's request language. Default to "summarize" if unclear.
   IMPORTANT: If the user shares URLs or references to documents/videos and asks to study/learn/understand them, classify as "study" with mode "summarize" and include the URLs in source_url.
   IMPORTANT: If the user sends a list of topics to study (like a syllabus or curriculum), classify as "study" with mode "summarize" and include the full text in source_text.
   IMPORTANT: When in doubt between "query" and "study", prefer "study" if the message contains URLs, multiple topics, or asks for comprehensive understanding.

Respond ONLY with a valid JSON object. No explanation, no markdown.
"""


async def classify(
    message: str,
    projects: list[dict],
    llm_provider: LLMProvider,
    *,
    current_datetime: str = "",
    timezone: str = "UTC",
) -> ClassifierOutput:
    """
    Classify a user message into a typed ClassifierOutput.

    Calls llm_provider.classify() with a system prompt, then parses the
    returned dict into the discriminated union. Retries up to _MAX_ATTEMPTS
    times on ValidationError (bad provider output).

    Args:
        message: The raw user message.
        projects: List of active project dicts.
        llm_provider: An LLMProvider instance (e.g. DeepSeekProvider).
        current_datetime: ISO-8601 string for the current moment.
        timezone: IANA timezone string.

    Returns:
        A typed ClassifierOutput (CaptureIntent | CorrectionIntent | ...).

    Raises:
        ClassifierError: If all attempts fail to produce a valid output.
    """
    system_prompt = build_system_prompt(projects, current_datetime, timezone)
    last_error: Exception | None = None

    for attempt in range(1, _MAX_ATTEMPTS + 1):
        try:
            raw: dict[str, Any] = await llm_provider.classify(
                message, system=system_prompt
            )
            output = _CLASSIFIER_ADAPTER.validate_python(raw)
            # Attach the raw provider output to the model for metadata logging.
            # model_copy(update=...) is the Pydantic v2 way to produce a new
            # instance without modifying the original.
            output = output.model_copy(update={"classifier_raw": raw})
            if attempt > 1:
                logger.info(
                    "classifier_service: succeeded on attempt %d/%d",
                    attempt,
                    _MAX_ATTEMPTS,
                )
            return output
        except (ValidationError, json.JSONDecodeError, KeyError, TypeError) as exc:
            last_error = exc
            logger.warning(
                "classifier_service: attempt %d/%d failed: %s",
                attempt,
                _MAX_ATTEMPTS,
                exc,
            )

    raise ClassifierError(
        f"Classifier failed after {_MAX_ATTEMPTS} attempts. Last error: {last_error}"
    ) from last_error
