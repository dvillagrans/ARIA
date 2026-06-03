"""
Study service — structured study assistance.

Provides four study modes (summarize, quiz, explain, flashcards) with
specialized prompt templates per mode. Each mode generates a prompt,
then calls the LLM reason() method to produce structured output.

Design: sdd/aria-study-tools/design §Interfaces
"""

from __future__ import annotations

import logging

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)


async def generate(
    mode: str,
    source_text: str,
    llm: LLMProvider,
    history: list[dict] | None = None,
) -> str:
    """
    Generate study material based on the selected mode.

    Args:
        mode: One of "summarize", "quiz", "explain", "flashcards".
        source_text: The source content to study from.
        llm: LLM provider for reasoning.
        history: Optional conversation history.

    Returns:
        Generated study content as a string.

    Raises:
        ValueError: If mode is not recognized.
    """
    prompt_builders = {
        "summarize": _build_summarize_prompt,
        "quiz": _build_quiz_prompt,
        "explain": _build_explain_prompt,
        "flashcards": _build_flashcards_prompt,
    }

    builder = prompt_builders.get(mode)
    if builder is None:
        raise ValueError(f"Unknown study mode: {mode}")

    prompt = builder(source_text)

    logger.info("study_service: generating '%s' content (%d chars source)", mode, len(source_text))

    result = await llm.reason(prompt, history=history or [])
    return result


def _build_summarize_prompt(source_text: str) -> str:
    """
    Build a prompt for summarization mode.

    Args:
        source_text: The content to summarize.

    Returns:
        Prompt string requesting a concise summary with key points.
    """
    return (
        "Summarize the following content concisely. "
        "Include the key points as a bulleted list after the summary.\n\n"
        f"Content:\n{source_text}"
    )


def _build_quiz_prompt(source_text: str) -> str:
    """
    Build a prompt for quiz mode.

    Args:
        source_text: The content to generate questions from.

    Returns:
        Prompt string requesting 5 Q&A questions.
    """
    return (
        "Based on the following content, create 5 quiz questions with answers. "
        "Format each as:\n"
        "Q1: [question]\nA1: [answer]\n\n"
        "Mix question types: recall, comprehension, and application.\n\n"
        f"Content:\n{source_text}"
    )


def _build_explain_prompt(source_text: str) -> str:
    """
    Build a prompt for explain (ELI5) mode.

    Args:
        source_text: The content to explain.

    Returns:
        Prompt string requesting an ELI5 explanation.
    """
    return (
        "Explain the following content as if teaching it to a beginner (ELI5). "
        "Use simple language, analogies where helpful, and avoid jargon. "
        "Break complex ideas into smaller steps.\n\n"
        f"Content:\n{source_text}"
    )


def _build_flashcards_prompt(source_text: str) -> str:
    """
    Build a prompt for flashcards mode.

    Args:
        source_text: The content to create flashcards from.

    Returns:
        Prompt string requesting Q&A flashcard pairs in JSON format.
    """
    return (
        "Create flashcards from the following content. "
        "Return them as a JSON array of objects with 'front' and 'back' keys. "
        "Create 8-12 flashcards covering the most important concepts.\n\n"
        "Example format:\n"
        '[{"front": "What is X?", "back": "X is..."}]\n\n'
        f"Content:\n{source_text}"
    )
