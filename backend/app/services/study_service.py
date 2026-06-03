"""
Study service — structured study assistance.

Provides study modes (study_plan, summarize, quiz, explain, flashcards) with
specialized prompt templates per mode. Each mode generates a prompt,
then calls the LLM reason() method to produce structured output.

Design: sdd/aria-study-tools/design §Interfaces
"""

from __future__ import annotations

import logging
import re

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TOTAL = 72_000
_STUDY_PLAN_MAX_TOTAL = 64_000
_MIN_PER_SOURCE = 400


def _parse_source_blocks(source_text: str) -> list[tuple[str, str]]:
    """Split combined source text into (header, body) pairs."""
    blocks: list[tuple[str, str]] = []
    raw_blocks = re.split(r"(?=\n--- Source:)", source_text.strip())
    if source_text.strip().startswith("--- Source:"):
        raw_blocks = re.split(r"(?=--- Source:)", source_text.strip())

    for block in raw_blocks:
        block = block.strip()
        if not block:
            continue
        if not block.startswith("--- Source:"):
            block = "--- Source:" + block.lstrip("-")
        header_end = block.find("\n")
        if header_end == -1:
            continue
        blocks.append((block[:header_end], block[header_end + 1 :]))
    return blocks


def _excerpt_body(body: str, limit: int) -> str:
    """Keep head + tail excerpt when body exceeds per-source budget."""
    if len(body) <= limit:
        return body
    if limit < 120:
        return body[:limit]
    marker = "\n\n[... sección omitida ...]\n\n"
    head = int((limit - len(marker)) * 0.75)
    tail = limit - len(marker) - head
    return body[:head] + marker + body[-tail:]


def _truncate_sources(source_text: str, *, mode: str = "summarize") -> str:
    """
    Fit extracted sources into the LLM context window.

    Uses equal budget per source so multi-resource study requests keep every
    URL/topic instead of dropping later sources after early ones consume the cap.
    """
    max_total = _STUDY_PLAN_MAX_TOTAL if mode == "study_plan" else _DEFAULT_MAX_TOTAL

    if "--- Source:" not in source_text:
        return source_text[:max_total]

    parsed = _parse_source_blocks(source_text)
    if not parsed:
        return source_text[:max_total]

    per_source = max(_MIN_PER_SOURCE, max_total // len(parsed))
    parts = [f"{header}\n{_excerpt_body(body, per_source)}" for header, body in parsed]
    return "\n\n".join(parts)


def _language_instruction(user_message: str) -> str:
    return (
        "Responde SIEMPRE en el mismo idioma que usó el estudiante en su mensaje. "
        f"Mensaje del estudiante (referencia de idioma): {user_message[:200]}\n\n"
        if user_message.strip()
        else "Responde en el idioma del material o del estudiante si se infiere del contexto.\n\n"
    )


async def generate(
    mode: str,
    source_text: str,
    llm: LLMProvider,
    history: list[dict] | None = None,
    *,
    user_message: str = "",
) -> str:
    """
    Generate study material based on the selected mode.

    Args:
        mode: One of "study_plan", "summarize", "quiz", "explain", "flashcards".
        source_text: The source content to study from.
        llm: LLM provider for reasoning.
        history: Optional conversation history.
        user_message: Original user request (for language + context).

    Returns:
        Generated study content as a string.

    Raises:
        ValueError: If mode is not recognized.
    """
    prompt_builders = {
        "study_plan": _build_study_plan_prompt,
        "summarize": _build_summarize_prompt,
        "quiz": _build_quiz_prompt,
        "explain": _build_explain_prompt,
        "flashcards": _build_flashcards_prompt,
    }

    builder = prompt_builders.get(mode)
    if builder is None:
        raise ValueError(f"Unknown study mode: {mode}")

    truncated = _truncate_sources(source_text, mode=mode)
    prompt = builder(truncated, user_message=user_message)

    logger.info(
        "study_service: generating '%s' content (%d → %d chars source)",
        mode,
        len(source_text),
        len(truncated),
    )

    result = await llm.reason(prompt, history=history or [])
    return result


def _build_study_plan_prompt(source_text: str, user_message: str = "") -> str:
    """Build a tutor-style study guide for multi-topic curriculum requests."""
    return (
        "Eres ARIA, un tutor de estudio personal. El estudiante pidió ayuda para estudiar.\n\n"
        f"{_language_instruction(user_message)}"
        "Crea una guía de estudio práctica. NO entregues un resumen académico seco en inglés.\n\n"
        "Estructura obligatoria:\n"
        "## Plan de estudio\n"
        "- Orden sugerido de temas y tiempo estimado por tema\n\n"
        "## Por cada tema\n"
        "Para cada tema detectado en el material:\n"
        "### [Nombre del tema]\n"
        "- **Conceptos clave** (3-5 bullets en lenguaje claro)\n"
        "- **Qué revisar** (video, paper, secciones clave)\n"
        "- **Autoevaluación** (1-2 preguntas cortas)\n\n"
        "## Próximos pasos\n"
        "- Qué estudiar primero antes de la próxima sesión\n"
        "- Invita al estudiante a pedir quiz, flashcards o profundizar en un tema\n\n"
        "Reglas:\n"
        "- Si un recurso es solo un enlace (YouTube, Drive) con poco texto extraído, "
        "indica que debe abrirlo y qué buscar en él.\n"
        "- Prioriza comprensión de conceptos sobre citar papers.\n\n"
        f"Solicitud del estudiante:\n{user_message}\n\n"
        f"Material de referencia extraído:\n{source_text}"
    )


def _build_summarize_prompt(source_text: str, user_message: str = "") -> str:
    """Build a prompt for summarization mode."""
    return (
        f"{_language_instruction(user_message)}"
        "Resume el siguiente contenido de forma concisa y útil para estudiar. "
        "Incluye los puntos clave como lista después del resumen.\n\n"
        f"Contenido:\n{source_text}"
    )


def _build_quiz_prompt(source_text: str, user_message: str = "") -> str:
    """Build a prompt for quiz mode."""
    return (
        f"{_language_instruction(user_message)}"
        "Basándote en el siguiente contenido, crea 5 preguntas de quiz con respuestas. "
        "Formato:\n"
        "P1: [pregunta]\nR1: [respuesta]\n\n"
        "Mezcla tipos: recuerdo, comprensión y aplicación.\n\n"
        f"Contenido:\n{source_text}"
    )


def _build_explain_prompt(source_text: str, user_message: str = "") -> str:
    """Build a prompt for explain (ELI5) mode."""
    return (
        f"{_language_instruction(user_message)}"
        "Explica el siguiente contenido como si enseñaras a alguien principiante (ELI5). "
        "Usa lenguaje simple, analogías y evita jerga. "
        "Divide ideas complejas en pasos pequeños.\n\n"
        f"Contenido:\n{source_text}"
    )


def _build_flashcards_prompt(source_text: str, user_message: str = "") -> str:
    """Build a prompt for flashcards mode."""
    return (
        f"{_language_instruction(user_message)}"
        "Crea flashcards del siguiente contenido. "
        "Devuélvelas como arreglo JSON con claves 'front' y 'back'. "
        "Crea 8-12 tarjetas con los conceptos más importantes.\n\n"
        "Formato ejemplo:\n"
        '[{"front": "¿Qué es X?", "back": "X es..."}]\n\n'
        f"Contenido:\n{source_text}"
    )
