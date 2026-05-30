"""
TDD RED tests for DeepSeekProvider.reason() — Phase 2 rewrite.

Written BEFORE implementation — must fail until task 3.1 / 3.2 are done.

Spec: deepseek-reason-impl requirements
ADR-1: _CLASSIFY_MODEL="deepseek-chat", _REASON_MODEL="deepseek-reasoner"
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


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
    message = MagicMock()
    message.content = content
    choice = MagicMock()
    choice.message = message
    completion = MagicMock()
    completion.choices = [choice]
    return completion


# ---------------------------------------------------------------------------
# test_reason_uses_deepseek_reasoner_model (ADR-1)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reason_uses_deepseek_reasoner_model():
    """reason() MUST call the API with model='deepseek-reasoner', NOT deepseek-chat."""
    from app.providers.deepseek import DeepSeekProvider

    mock_completion = _make_chat_completion("ARIA's detailed answer.")

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        await provider.reason("What tasks do I have?")

    call_kwargs = mock_client.chat.completions.create.call_args
    model_used = call_kwargs[1].get("model") or call_kwargs[0][0] if call_kwargs[0] else call_kwargs[1]["model"]
    assert model_used == "deepseek-reasoner", (
        f"Expected model='deepseek-reasoner' but got model='{model_used}'"
    )


# ---------------------------------------------------------------------------
# test_reason_includes_context_in_messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reason_includes_context_in_messages():
    """reason() must include context passages in the messages list."""
    from app.providers.deepseek import DeepSeekProvider

    context_passages = ["Passage A: task Deploy API", "Passage B: note about infra"]
    mock_completion = _make_chat_completion("Answer with context.")

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        await provider.reason("Tell me about deploy", context=context_passages)

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs[1].get("messages") or call_kwargs[0][0]

    # Flatten all message content for assertion
    all_content = " ".join(m["content"] for m in messages if m.get("content"))
    assert "Passage A" in all_content, "Context passage A must appear in messages"
    assert "Passage B" in all_content, "Context passage B must appear in messages"


# ---------------------------------------------------------------------------
# test_reason_includes_history_in_messages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reason_includes_history_in_messages():
    """reason() must include conversation history turns before the final prompt."""
    from app.providers.deepseek import DeepSeekProvider

    history = [
        {"role": "user", "content": "What is the status of Deploy?"},
        {"role": "assistant", "content": "Deploy is in progress."},
    ]
    mock_completion = _make_chat_completion("Here is more info.")

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        await provider.reason("Any updates?", history=history)

    call_kwargs = mock_client.chat.completions.create.call_args
    messages = call_kwargs[1].get("messages") or call_kwargs[0][0]

    all_content = " ".join(m["content"] for m in messages if m.get("content"))
    assert "What is the status of Deploy?" in all_content
    assert "Deploy is in progress." in all_content


# ---------------------------------------------------------------------------
# test_reason_with_no_context_or_history (backward compat)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_reason_with_no_context_or_history():
    """reason() must work without context or history (backward compat)."""
    from app.providers.deepseek import DeepSeekProvider

    mock_completion = _make_chat_completion("Simple answer.")

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        result = await provider.reason("Simple question?")

    assert isinstance(result, str)
    assert len(result) > 0
    mock_client.chat.completions.create.assert_called_once()

    call_kwargs = mock_client.chat.completions.create.call_args
    model_used = call_kwargs[1].get("model")
    assert model_used == "deepseek-reasoner"


# ---------------------------------------------------------------------------
# test_classify_still_uses_deepseek_chat (ADR-1 — no regression)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_classify_still_uses_deepseek_chat():
    """classify() must still use _CLASSIFY_MODEL ('deepseek-chat'), not deepseek-reasoner."""
    import json
    from app.providers.deepseek import DeepSeekProvider

    raw_json = json.dumps({"intent": "query", "query_text": "test"})
    mock_completion = _make_chat_completion(raw_json)

    with patch("app.providers.deepseek.AsyncOpenAI") as mock_openai_cls:
        mock_client = AsyncMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create = AsyncMock(return_value=mock_completion)

        provider = DeepSeekProvider(_test_settings())
        await provider.classify("test message")

    call_kwargs = mock_client.chat.completions.create.call_args
    model_used = call_kwargs[1].get("model")
    assert model_used == "deepseek-chat", (
        f"classify() must use deepseek-chat, got '{model_used}'"
    )
