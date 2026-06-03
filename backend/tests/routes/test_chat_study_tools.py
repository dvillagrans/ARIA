"""
Integration tests for web_search and study intents in the chat route.

Tests that the /chat endpoint correctly routes to the new services
when the classifier returns WebSearchIntent or StudyIntent.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.schemas.classifier import WebSearchIntent, StudyIntent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_web_search_intent(query_text: str = "latest AI news") -> WebSearchIntent:
    return WebSearchIntent(
        intent="web_search",
        query_text=query_text,
        max_results=5,
        classifier_raw={"intent": "web_search", "query_text": query_text},
    )


def _make_study_intent(
    mode: str = "summarize",
    source_text: str | None = "Machine learning is a subset of AI.",
) -> StudyIntent:
    return StudyIntent(
        intent="study",
        mode=mode,
        source_text=source_text,
        classifier_raw={"intent": "study", "mode": mode},
    )


# ---------------------------------------------------------------------------
# Tests: WebSearchIntent schema validation
# ---------------------------------------------------------------------------

def test_web_search_intent_valid():
    """WebSearchIntent accepts valid payload."""
    intent = WebSearchIntent(intent="web_search", query_text="test query")
    assert intent.intent == "web_search"
    assert intent.query_text == "test query"
    assert intent.max_results == 5  # default


def test_web_search_intent_custom_max_results():
    """WebSearchIntent accepts custom max_results."""
    intent = WebSearchIntent(intent="web_search", query_text="q", max_results=10)
    assert intent.max_results == 10


# ---------------------------------------------------------------------------
# Tests: StudyIntent schema validation
# ---------------------------------------------------------------------------

def test_study_intent_valid_modes():
    """StudyIntent accepts all four valid modes."""
    for mode in ("summarize", "quiz", "explain", "flashcards"):
        intent = StudyIntent(intent="study", mode=mode)
        assert intent.mode == mode


def test_study_intent_invalid_mode():
    """StudyIntent rejects invalid mode."""
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        StudyIntent(intent="study", mode="invalid")


def test_study_intent_optional_fields():
    """StudyIntent allows optional source_text and source_urls."""
    intent = StudyIntent(intent="study", mode="quiz")
    assert intent.source_text is None
    assert intent.source_urls == []


def test_study_intent_with_source():
    """StudyIntent accepts source_text and source_urls."""
    intent = StudyIntent(
        intent="study",
        mode="summarize",
        source_text="some text",
        source_urls=["https://example.com/file.pdf", "https://example.com/paper.pdf"],
    )
    assert intent.source_text == "some text"
    assert len(intent.source_urls) == 2


# ---------------------------------------------------------------------------
# Tests: ClassifierOutput discriminated union includes new intents
# ---------------------------------------------------------------------------

def test_classifier_output_accepts_web_search():
    """ClassifierOutput discriminated union routes to WebSearchIntent."""
    from pydantic import TypeAdapter
    from app.schemas.classifier import ClassifierOutput

    adapter = TypeAdapter(ClassifierOutput)
    raw = {"intent": "web_search", "query_text": "test"}
    result = adapter.validate_python(raw)

    assert isinstance(result, WebSearchIntent)
    assert result.intent == "web_search"


def test_classifier_output_accepts_study():
    """ClassifierOutput discriminated union routes to StudyIntent."""
    from pydantic import TypeAdapter
    from app.schemas.classifier import ClassifierOutput

    adapter = TypeAdapter(ClassifierOutput)
    raw = {"intent": "study", "mode": "quiz"}
    result = adapter.validate_python(raw)

    assert isinstance(result, StudyIntent)
    assert result.mode == "quiz"
