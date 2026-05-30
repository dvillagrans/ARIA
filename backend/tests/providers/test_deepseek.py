"""
TDD RED tests for DeepSeekProvider (Phase 1 real implementation).

Tests are written BEFORE implementation. They MUST fail until task 4.5 is done.

Spec §1:
- classify() calls OpenAI-compatible API in JSON mode, returns dict.
- Retries up to 2 additional times on JSONDecodeError from provider.
- reason() returns a non-empty string of ≤120 characters.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4


def _test_settings():
    from app.core.config import Settings
    return Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        deepseek_api_key="test-deepseek-key",
        deepinfra_api_key="test-deepinfra-key",
    )


def _make_chat_completion(content: str):
    """Build a mock ChatCompletion response with given content string."""
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# ---------------------------------------------------------------------------
# Test: classify — happy path returns dict
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deepseek_classify_returns_dict():
    from app.providers.deepseek import DeepSeekProvider

    raw_json = json.dumps({
        "intent": "capture",
        "record_type": "task",
        "title": "Schedule meeting",
    })
    mock_completion = _make_chat_completion(raw_json)

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        result = await provider.classify("Schedule a meeting tomorrow at 3pm")

    assert isinstance(result, dict)
    assert result["intent"] == "capture"
    assert result["record_type"] == "task"


@pytest.mark.asyncio
async def test_deepseek_classify_no_retry_on_success():
    from app.providers.deepseek import DeepSeekProvider

    raw_json = json.dumps({"intent": "query", "query_text": "What tasks do I have?"})
    mock_completion = _make_chat_completion(raw_json)

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        result = await provider.classify("What tasks do I have?")

    assert mock_client.chat.completions.create.call_count == 1


# ---------------------------------------------------------------------------
# Test: classify — malformed JSON on first attempt, valid on second
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deepseek_classify_retries_on_malformed_json():
    from app.providers.deepseek import DeepSeekProvider

    bad_completion = _make_chat_completion("this is not json {")
    good_json = json.dumps({"intent": "capture", "record_type": "task", "title": "Buy milk"})
    good_completion = _make_chat_completion(good_json)

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[bad_completion, good_completion]
        )

        provider = DeepSeekProvider(_test_settings())
        result = await provider.classify("Buy milk")

    assert result["intent"] == "capture"
    assert mock_client.chat.completions.create.call_count == 2


# ---------------------------------------------------------------------------
# Test: classify — all attempts return malformed JSON → raises ClassifierError
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deepseek_classify_raises_after_all_retries():
    from app.providers.deepseek import DeepSeekProvider
    from app.services.classifier_service import ClassifierError

    bad_completion = _make_chat_completion("not json at all")

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=bad_completion)

        provider = DeepSeekProvider(_test_settings())

        with pytest.raises((ClassifierError, json.JSONDecodeError, Exception)):
            await provider.classify("Buy milk")

    # 3 total attempts
    assert mock_client.chat.completions.create.call_count == 3


# ---------------------------------------------------------------------------
# Test: reason — returns string ≤120 chars
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_deepseek_reason_returns_short_string():
    from app.providers.deepseek import DeepSeekProvider

    confirmation = "Got it! I've added 'Buy milk' as a task."
    mock_completion = _make_chat_completion(confirmation)

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        result = await provider.reason("Confirm capture of task 'Buy milk'")

    assert isinstance(result, str)
    assert len(result) > 0
    assert len(result) <= 120


@pytest.mark.asyncio
async def test_deepseek_reason_not_empty():
    from app.providers.deepseek import DeepSeekProvider

    mock_completion = _make_chat_completion("Task added.")

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        result = await provider.reason("Confirm")

    assert result != ""
