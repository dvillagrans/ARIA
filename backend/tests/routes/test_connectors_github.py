"""
TDD RED tests for GitHub connector — Phase 4.

Tests:
- map_notifications: assign subject → record_type="task"
- map_notifications: mention subject → record_type="note"
- sync: capped at 50 notifications
- sync: idempotent (second call → all skipped)
"""

import pytest
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.schemas.ingest import IngestRequest


# ---------------------------------------------------------------------------
# map_notifications unit tests (pure function — no I/O)
# ---------------------------------------------------------------------------

def _notification(subject_type: str, subject_title: str = "Review PR", nid: str = "1") -> dict:
    return {
        "id": nid,
        "subject": {
            "type": subject_type,
            "title": subject_title,
        },
        "repository": {
            "full_name": "org/repo",
        },
    }


def test_map_notifications_assign_becomes_task():
    """subject.type='assign' → record_type='task'."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("assign")]
    reqs = map_notifications(raw, user_id)

    assert len(reqs) == 1
    assert reqs[0].record_type == "task"
    assert reqs[0].source == "github"


def test_map_notifications_review_requested_becomes_task():
    """subject.type='review_requested' → record_type='task'."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("review_requested")]
    reqs = map_notifications(raw, user_id)

    assert reqs[0].record_type == "task"


def test_map_notifications_mention_becomes_note():
    """subject.type='mention' → record_type='note'."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("mention")]
    reqs = map_notifications(raw, user_id)

    assert reqs[0].record_type == "note"


def test_map_notifications_subscribed_becomes_note():
    """subject.type='subscribed' → record_type='note'."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("subscribed")]
    reqs = map_notifications(raw, user_id)

    assert reqs[0].record_type == "note"


def test_map_notifications_unknown_type_becomes_note():
    """Unknown subject.type → defaults to record_type='note'."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("ci_activity")]
    reqs = map_notifications(raw, user_id)

    assert reqs[0].record_type == "note"


def test_map_notifications_external_id_format():
    """external_id must be 'github:notification:<id>'."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("mention", nid="99")]
    reqs = map_notifications(raw, user_id)

    assert reqs[0].external_id == "github:notification:99"


def test_map_notifications_project_hint_is_repo_name():
    """project_hint must be the repository full_name."""
    from app.connectors.github import map_notifications

    user_id = uuid.uuid4()
    raw = [_notification("mention")]
    reqs = map_notifications(raw, user_id)

    assert reqs[0].project_hint == "org/repo"


# ---------------------------------------------------------------------------
# sync integration tests (mock httpx + _ingest_one)
# ---------------------------------------------------------------------------

def _make_settings():
    s = MagicMock()
    s.github_token = "test-github-token"
    return s


def _make_fifty_notifications() -> list[dict]:
    return [_notification("mention", nid=str(i)) for i in range(80)]


@pytest.mark.asyncio
async def test_sync_capped_at_50():
    """sync() processes at most 50 notifications even if API returns more."""
    import httpx
    from app.connectors.github import sync

    # Build httpx mock transport that returns 80 notifications
    notifications = _make_fifty_notifications()
    transport = httpx.MockTransport(
        lambda req: httpx.Response(200, json=notifications)
    )

    db = MagicMock()
    # connector_state upsert
    upsert_execute = AsyncMock(return_value=MagicMock(data=[{}]))
    db.table = MagicMock(return_value=MagicMock(
        upsert=MagicMock(return_value=MagicMock(execute=upsert_execute))
    ))

    embedder = MagicMock()
    llm = MagicMock()
    settings = _make_settings()

    user_id = uuid.uuid4()

    with patch("app.connectors.github._ingest_one", new_callable=AsyncMock) as mock_ingest, \
         patch("app.connectors.github.httpx.AsyncClient") as mock_client_cls:

        mock_ingest.return_value = ("created", str(uuid.uuid4()))

        # Make AsyncClient a context manager mock
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value=notifications),
            raise_for_status=MagicMock(),
        ))
        mock_client_cls.return_value = mock_client

        result = await sync(db, llm, embedder, settings, user_id=user_id)

    # At most 50 items processed
    assert mock_ingest.call_count <= 50
    assert result.created <= 50


@pytest.mark.asyncio
async def test_sync_idempotent():
    """Second sync call: all items return 'skipped' → result.skipped = N."""
    from app.connectors.github import sync

    notifications = [_notification("mention", nid=str(i)) for i in range(3)]
    user_id = uuid.uuid4()

    db = MagicMock()
    upsert_execute = AsyncMock(return_value=MagicMock(data=[{}]))
    db.table = MagicMock(return_value=MagicMock(
        upsert=MagicMock(return_value=MagicMock(execute=upsert_execute))
    ))

    settings = _make_settings()

    with patch("app.connectors.github._ingest_one", new_callable=AsyncMock) as mock_ingest, \
         patch("app.connectors.github.httpx.AsyncClient") as mock_client_cls:

        mock_ingest.return_value = ("duplicate", None)

        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.get = AsyncMock(return_value=MagicMock(
            status_code=200,
            json=MagicMock(return_value=notifications),
            raise_for_status=MagicMock(),
        ))
        mock_client_cls.return_value = mock_client

        result = await sync(db, MagicMock(), MagicMock(), settings, user_id=user_id)

    assert result.skipped == 3
    assert result.created == 0
