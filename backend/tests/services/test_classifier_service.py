"""
TDD RED tests for classifier_service.

Tests are written BEFORE implementation. They MUST fail until task 4.1 is done.

Spec §1:
- classify() calls DeepSeekProvider.classify() to get a raw dict.
- Parses the dict into ClassifierOutput discriminated union.
- Retries once on JSONDecodeError / ValidationError from provider.
- Raises ClassifierError after exhausting 2 retries (3 total attempts).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.classifier import CaptureIntent, CorrectionIntent, ClassifierOutput
from pydantic import TypeAdapter


# ---------------------------------------------------------------------------
# Helper: valid raw dicts the mock provider returns
# ---------------------------------------------------------------------------

CAPTURE_RAW = {
    "intent": "capture",
    "record_type": "task",
    "title": "Buy groceries",
    "project_hint": None,
}

CORRECTION_RAW = {
    "intent": "correction",
    "new_type": "event",
}


# ---------------------------------------------------------------------------
# Test: build_system_prompt
# ---------------------------------------------------------------------------

def test_build_system_prompt_contains_datetime():
    from app.services.classifier_service import build_system_prompt

    projects = [{"id": "abc", "name": "Work"}, {"id": "def", "name": "Personal"}]
    prompt = build_system_prompt(projects, "2026-05-29T10:00:00", "America/Argentina/Buenos_Aires")

    assert "2026-05-29" in prompt
    assert "America/Argentina/Buenos_Aires" in prompt


def test_build_system_prompt_contains_energy_level_guidance():
    """TASK-2.5: build_system_prompt must include energy_level guidance for capture."""
    from app.services.classifier_service import build_system_prompt

    projects = [{"id": "abc", "name": "Work"}]
    prompt = build_system_prompt(projects, "2026-05-30T10:00:00", "UTC")

    assert "energy_level" in prompt


def test_build_system_prompt_lists_projects():
    from app.services.classifier_service import build_system_prompt

    projects = [{"id": "abc", "name": "Work"}, {"id": "def", "name": "Personal"}]
    prompt = build_system_prompt(projects, "2026-05-29T10:00:00", "UTC")

    assert "Work" in prompt
    assert "Personal" in prompt


# ---------------------------------------------------------------------------
# Test: classify — happy path (capture intent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_returns_capture_intent():
    from app.services.classifier_service import classify

    mock_provider = AsyncMock()
    mock_provider.classify.return_value = dict(CAPTURE_RAW)

    projects = [{"id": "abc", "name": "Personal"}]
    result = await classify("Buy groceries", projects, mock_provider)

    assert isinstance(result, CaptureIntent)
    assert result.intent == "capture"
    assert result.record_type == "task"
    assert result.title == "Buy groceries"
    mock_provider.classify.assert_called_once()


@pytest.mark.asyncio
async def test_classify_attaches_classifier_raw():
    from app.services.classifier_service import classify

    mock_provider = AsyncMock()
    mock_provider.classify.return_value = dict(CAPTURE_RAW)

    result = await classify("Buy groceries", [], mock_provider)

    assert isinstance(result, CaptureIntent)
    assert result.classifier_raw == CAPTURE_RAW


# ---------------------------------------------------------------------------
# Test: classify — correction intent
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_returns_correction_intent():
    from app.services.classifier_service import classify

    mock_provider = AsyncMock()
    mock_provider.classify.return_value = dict(CORRECTION_RAW)

    result = await classify("No, it was an event", [], mock_provider)

    assert isinstance(result, CorrectionIntent)
    assert result.intent == "correction"
    assert result.new_type == "event"


# ---------------------------------------------------------------------------
# Test: classify — retry on provider returning invalid dict (missing fields)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_retries_on_invalid_response():
    """Provider returns bad dict first, valid dict second — succeeds after 1 retry."""
    from app.services.classifier_service import classify

    mock_provider = AsyncMock()
    # First call: missing required 'record_type' and 'title' → ValidationError
    # Second call: valid
    mock_provider.classify.side_effect = [
        {"intent": "capture"},          # invalid — missing record_type/title
        dict(CAPTURE_RAW),              # valid
    ]

    result = await classify("Buy groceries", [], mock_provider)

    assert isinstance(result, CaptureIntent)
    assert mock_provider.classify.call_count == 2


# ---------------------------------------------------------------------------
# Test: classify — ClassifierError after exhausting retries
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_raises_classifier_error_after_exhausted_retries():
    """Provider always returns invalid dict — ClassifierError raised after 3 attempts."""
    from app.services.classifier_service import classify, ClassifierError

    mock_provider = AsyncMock()
    # Always invalid — missing record_type/title
    mock_provider.classify.return_value = {"intent": "capture"}

    with pytest.raises(ClassifierError):
        await classify("Buy groceries", [], mock_provider)

    # 3 total attempts (initial + 2 retries)
    assert mock_provider.classify.call_count == 3


@pytest.mark.asyncio
async def test_classify_raises_classifier_error_on_unknown_intent():
    """Provider returns unknown intent value — ClassifierError raised."""
    from app.services.classifier_service import classify, ClassifierError

    mock_provider = AsyncMock()
    mock_provider.classify.return_value = {"intent": "unknown_intent"}

    with pytest.raises(ClassifierError):
        await classify("???", [], mock_provider)
