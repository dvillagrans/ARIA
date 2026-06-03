"""
Unit tests for study_service.

Tests prompt generation and mode routing for all four study modes.
"""

import pytest
from unittest.mock import AsyncMock

from app.services.study_service import (
    generate,
    _build_study_plan_prompt,
    _build_summarize_prompt,
    _build_quiz_prompt,
    _build_explain_prompt,
    _build_flashcards_prompt,
    _truncate_sources,
)


# ---------------------------------------------------------------------------
# Tests: prompt builders
# ---------------------------------------------------------------------------

def test_build_summarize_prompt_contains_source():
    """Summarize prompt includes the source text."""
    prompt = _build_summarize_prompt("Machine learning is a subset of AI.")
    assert "Machine learning is a subset of AI." in prompt
    assert "resume" in prompt.lower() or "resumen" in prompt.lower()


def test_build_study_plan_prompt_contains_structure():
    """Study plan prompt requests structured tutor output."""
    prompt = _build_study_plan_prompt("NLP content", user_message="Ayudame a estudiar esto")
    assert "Plan de estudio" in prompt
    assert "Ayudame a estudiar esto" in prompt
    assert "NLP content" in prompt


def test_truncate_sources_caps_total_size():
    """Large multi-source input is truncated to fit context."""
    block = "--- Source: https://example.com/a ---\n" + ("x" * 20_000)
    truncated = _truncate_sources(block + "\n\n" + block)
    assert len(truncated) <= 72_500


def test_truncate_sources_includes_all_sources_for_study_plan():
    """study_plan keeps every source with equal budget instead of dropping later ones."""
    blocks = [
        f"--- Source: https://example.com/{i} ---\n" + ("x" * 50_000)
        for i in range(8)
    ]
    source = "\n\n".join(blocks)
    truncated = _truncate_sources(source, mode="study_plan")
    for i in range(8):
        assert f"https://example.com/{i}" in truncated
    assert truncated.count("--- Source:") == 8


def test_build_quiz_prompt_contains_source():
    """Quiz prompt includes the source text and requests questions."""
    prompt = _build_quiz_prompt("Deep learning uses neural networks.")
    assert "Deep learning uses neural networks." in prompt
    assert "P1" in prompt or "pregunta" in prompt.lower()


def test_build_explain_prompt_contains_source():
    """Explain prompt includes the source text and ELI5 instruction."""
    prompt = _build_explain_prompt("Neural networks are layers of neurons.")
    assert "Neural networks are layers of neurons." in prompt
    assert "beginner" in prompt.lower() or "eli5" in prompt.lower() or "simple" in prompt.lower()


def test_build_flashcards_prompt_contains_source():
    """Flashcards prompt includes the source text and JSON format."""
    prompt = _build_flashcards_prompt("Python is a programming language.")
    assert "Python is a programming language." in prompt
    assert "front" in prompt
    assert "back" in prompt
    assert "json" in prompt.lower() or "JSON" in prompt


# ---------------------------------------------------------------------------
# Tests: generate (mode routing)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_generate_routes_to_study_plan():
    """generate() calls llm.reason() with study plan prompt."""
    mock_llm = AsyncMock()
    mock_llm.reason.return_value = "## Plan de estudio\n..."

    result = await generate("study_plan", "test content", mock_llm, user_message="Ayudame a estudiar")

    assert "Plan de estudio" in result
    call_args = mock_llm.reason.call_args
    assert "Plan de estudio" in call_args[0][0]


@pytest.mark.asyncio
async def test_generate_routes_to_summarize():
    """generate() calls llm.reason() with summarize prompt."""
    mock_llm = AsyncMock()
    mock_llm.reason.return_value = "Here is a summary."

    result = await generate("summarize", "test content", mock_llm)

    assert result == "Here is a summary."
    mock_llm.reason.assert_called_once()
    call_args = mock_llm.reason.call_args
    assert "resume" in call_args[0][0].lower() or "resumen" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_generate_routes_to_quiz():
    """generate() calls llm.reason() with quiz prompt."""
    mock_llm = AsyncMock()
    mock_llm.reason.return_value = "Q1: What is AI?"

    result = await generate("quiz", "AI content", mock_llm)

    assert result == "Q1: What is AI?"
    call_args = mock_llm.reason.call_args
    assert "pregunta" in call_args[0][0].lower() or "P1" in call_args[0][0]


@pytest.mark.asyncio
async def test_generate_routes_to_explain():
    """generate() calls llm.reason() with explain prompt."""
    mock_llm = AsyncMock()
    mock_llm.reason.return_value = "Let me explain simply..."

    result = await generate("explain", "complex topic", mock_llm)

    assert result == "Let me explain simply..."
    call_args = mock_llm.reason.call_args
    assert "beginner" in call_args[0][0].lower() or "eli5" in call_args[0][0].lower()


@pytest.mark.asyncio
async def test_generate_routes_to_flashcards():
    """generate() calls llm.reason() with flashcards prompt."""
    mock_llm = AsyncMock()
    mock_llm.reason.return_value = '[{"front": "Q", "back": "A"}]'

    result = await generate("flashcards", "study material", mock_llm)

    assert "front" in result
    call_args = mock_llm.reason.call_args
    assert "front" in call_args[0][0]


@pytest.mark.asyncio
async def test_generate_raises_on_unknown_mode():
    """generate() raises ValueError for unrecognized mode."""
    mock_llm = AsyncMock()

    with pytest.raises(ValueError, match="Unknown study mode"):
        await generate("invalid_mode", "content", mock_llm)


@pytest.mark.asyncio
async def test_generate_passes_history_to_llm():
    """generate() forwards conversation history to llm.reason()."""
    mock_llm = AsyncMock()
    mock_llm.reason.return_value = "response"
    history = [{"role": "user", "content": "prev message"}]

    await generate("summarize", "content", mock_llm, history=history)

    call_kwargs = mock_llm.reason.call_args.kwargs
    assert call_kwargs.get("history") == history
