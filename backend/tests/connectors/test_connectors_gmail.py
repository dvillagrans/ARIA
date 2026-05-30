"""
TDD tests for Gmail connector — Phase 4.

Tests:
- _classify_heuristic: action keywords → "task"
- _classify_heuristic: informational → "note"
- _classify_heuristic: ambiguous → None
- map_messages: action subject → task
- map_messages: informational subject → note
- sync: idempotent (second call → all skipped)
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.ingest import IngestRequest


# ---------------------------------------------------------------------------
# _classify_heuristic unit tests (pure function — no I/O)
# ---------------------------------------------------------------------------

def test_classify_heuristic_action_keyword():
    """Subject with action keyword → 'task'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Please review the PR", "Hey, can you take a look?")
    assert result == "task"


def test_classify_heuristic_action_keyword_todo():
    """Subject with 'TODO' → 'task'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("TODO: Update documentation", "We need to update the docs.")
    assert result == "task"


def test_classify_heuristic_action_keyword_follow_up():
    """Subject with 'Follow up' → 'task'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Follow up on Q3 report", "Just checking in on the status.")
    assert result == "task"


def test_classify_heuristic_action_keyword_review():
    """Subject with 'Review' → 'task'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Review requested: Design doc", "Please take a look at the attached.")
    assert result == "task"


def test_classify_heuristic_action_keyword_action_required():
    """Subject with 'Action required' → 'task'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Action required: Verify your email", "Click the link below.")
    assert result == "task"


def test_classify_heuristic_informational():
    """Informational sender pattern → 'note'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Your weekly digest", "noreply@example.com sent you a summary.")
    assert result == "note"


def test_classify_heuristic_informational_newsletter():
    """Newsletter pattern → 'note'."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Newsletter: May Edition", "Here are the top stories this week.")
    assert result == "note"


def test_classify_heuristic_ambiguous_returns_none():
    """Ambiguous subject → None (LLM fallback needed)."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("Quick update on the project", "Just wanted to share some progress.")
    assert result is None


def test_classify_heuristic_case_insensitive():
    """Keywords are matched case-insensitively."""
    from app.connectors.gmail import _classify_heuristic

    result = _classify_heuristic("PLEASE REVIEW this", "Can you look?")
    assert result == "task"


# ---------------------------------------------------------------------------
# map_messages unit tests (pure function — no I/O)
# ---------------------------------------------------------------------------

def _gmail_message(msg_id: str = "1", subject: str = "Test", snippet: str = "test") -> dict:
    return {
        "id": msg_id,
        "threadId": "thread-" + msg_id,
        "snippet": snippet,
        "payload": {
            "headers": [
                {"name": "Subject", "value": subject},
                {"name": "From", "value": "sender@example.com"},
            ],
            "mimeType": "text/plain",
            "parts": [
                {
                    "mimeType": "text/plain",
                    "body": {"data": "VGVzdCBib2R5"},  # "Test body" base64
                }
            ],
        },
    }


def test_map_messages_action_subject_becomes_task():
    """Email with action subject → record_type='task'."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(subject="Please review the PR")]
    reqs = map_messages(raw, user_id)

    assert len(reqs) == 1
    assert reqs[0].record_type == "task"
    assert reqs[0].source == "gmail"


def test_map_messages_informational_becomes_note():
    """Email with informational subject → record_type='note'."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(subject="Your weekly digest", snippet="noreply digest")]
    reqs = map_messages(raw, user_id)

    assert reqs[0].record_type == "note"


def test_map_messages_external_id_format():
    """external_id must be 'gmail:message:<id>'."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(msg_id="abc123")]
    reqs = map_messages(raw, user_id)

    assert reqs[0].external_id == "gmail:message:abc123"


def test_map_messages_title_is_subject():
    """title must be the email subject."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(subject="Important meeting tomorrow")]
    reqs = map_messages(raw, user_id)

    assert reqs[0].title == "Important meeting tomorrow"


def test_map_messages_body_is_included():
    """body field contains decoded plain-text body for embedding."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(msg_id="1", subject="Test", snippet="test")]
    reqs = map_messages(raw, user_id)

    assert reqs[0].body is not None
    assert len(reqs[0].body) > 0


def test_map_messages_ambiguous_uses_llm_fallback():
    """When heuristic returns None and llm is provided, llm.classify is called."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    # Ambiguous subject — heuristic returns None
    raw = [_gmail_message(subject="Quick update on the project", snippet="Just sharing progress.")]

    # Mock LLM that returns "task"
    mock_llm = MagicMock()
    mock_llm.classify.return_value = "task"

    reqs = map_messages(raw, user_id, llm=mock_llm)

    assert len(reqs) == 1
    assert reqs[0].record_type == "task"
    mock_llm.classify.assert_called_once_with("Quick update on the project", "Just sharing progress.")


def test_map_messages_ambiguous_defaults_to_note_without_llm():
    """When heuristic returns None and no llm provided, defaults to 'note'."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(subject="Quick update on the project", snippet="Just sharing progress.")]

    reqs = map_messages(raw, user_id)

    assert len(reqs) == 1
    assert reqs[0].record_type == "note"


def test_map_messages_ambiguous_llm_fails_falls_back_to_note():
    """When LLM classify raises an exception, falls back to 'note'."""
    from app.connectors.gmail import map_messages

    user_id = uuid.uuid4()
    raw = [_gmail_message(subject="Quick update on the project", snippet="Just sharing progress.")]

    mock_llm = MagicMock()
    mock_llm.classify.side_effect = Exception("LLM unavailable")

    reqs = map_messages(raw, user_id, llm=mock_llm)

    assert len(reqs) == 1
    assert reqs[0].record_type == "note"


# ---------------------------------------------------------------------------
# sync integration tests (mock google client + _ingest_one)
# ---------------------------------------------------------------------------

def _make_settings():
    s = MagicMock()
    s.google_client_id = "test-client-id"
    s.google_client_secret = "test-client-secret"
    s.gmail_refresh_token = "test-refresh-token"
    return s


@pytest.mark.asyncio
async def test_gmail_sync_idempotent():
    """Second sync call: all items return 'skipped' → result.skipped = N."""
    from app.connectors.gmail import sync

    user_id = uuid.uuid4()
    db = MagicMock()
    upsert_execute = AsyncMock(return_value=MagicMock(data=[{}]))
    db.table = MagicMock(return_value=MagicMock(
        upsert=MagicMock(return_value=MagicMock(execute=upsert_execute))
    ))

    settings = _make_settings()

    with patch("app.connectors.gmail._ingest_one", new_callable=AsyncMock) as mock_ingest, \
         patch("app.connectors.gmail._build_gmail_service") as mock_build:

        mock_ingest.return_value = ("duplicate", None)

        # Mock the gmail service: service.users().messages().list().execute()
        mock_list_execute = MagicMock(return_value={
            "messages": [
                {"id": "1", "threadId": "t1"},
                {"id": "2", "threadId": "t2"},
                {"id": "3", "threadId": "t3"},
            ]
        })
        mock_list = MagicMock(return_value=MagicMock(execute=mock_list_execute))
        mock_messages = MagicMock(return_value=MagicMock(list=mock_list))
        mock_users = MagicMock(return_value=MagicMock(messages=mock_messages))

        # For message.get calls
        mock_get_execute = MagicMock(return_value={
            "id": "1",
            "snippet": "test",
            "payload": {"headers": [{"name": "Subject", "value": "Test"}], "parts": []},
        })
        mock_get = MagicMock(return_value=MagicMock(execute=mock_get_execute))
        mock_messages.return_value.get = mock_get

        mock_service = MagicMock()
        mock_service.users = mock_users
        mock_build.return_value = mock_service

        # Configure the llm mock to return a valid classification for ambiguous emails
        mock_llm = MagicMock()
        mock_llm.classify.return_value = "note"

        result = await sync(db, mock_llm, MagicMock(), settings, user_id=user_id)

    assert result.skipped == 3
    assert result.created == 0
