"""
TDD tests for Calendar connector — Phase 4.

Tests:
- map_events: produces event record_type
- map_events: duration defaults to 60 when end is absent
- map_events: duration computed from start/end
- sync: idempotent (second call → all skipped)
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.ingest import IngestRequest


# ---------------------------------------------------------------------------
# map_events unit tests (pure function — no I/O)
# ---------------------------------------------------------------------------

def _gcal_event(
    event_id: str = "evt1",
    summary: str = "Team meeting",
    description: str | None = None,
    start: str = "2026-06-01T14:00:00Z",
    end: str | None = "2026-06-01T15:00:00Z",
) -> dict:
    event = {
        "id": event_id,
        "summary": summary,
        "start": {"dateTime": start},
    }
    if end:
        event["end"] = {"dateTime": end}
    if description:
        event["description"] = description
    return event


def test_map_events_produces_event_record_type():
    """Calendar events → record_type='event'."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event()]
    reqs = map_events(raw, user_id)

    assert len(reqs) == 1
    assert reqs[0].record_type == "event"
    assert reqs[0].source == "google_calendar"


def test_map_events_external_id_format():
    """external_id must be 'gcal:event:<id>'."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(event_id="abc123")]
    reqs = map_events(raw, user_id)

    assert reqs[0].external_id == "gcal:event:abc123"


def test_map_events_title_is_summary():
    """title must be the event summary."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(summary="Sprint planning")]
    reqs = map_events(raw, user_id)

    assert reqs[0].title == "Sprint planning"


def test_map_events_body_is_description():
    """body must be the event description."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(description="Discuss Q3 goals")]
    reqs = map_events(raw, user_id)

    assert reqs[0].body == "Discuss Q3 goals"


def test_map_events_body_none_when_no_description():
    """body is None when event has no description."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(description=None)]
    reqs = map_events(raw, user_id)

    assert reqs[0].body is None


def test_map_events_duration_defaults_to_60():
    """When event has no end, duration_min defaults to 60."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(end=None)]
    reqs = map_events(raw, user_id)

    assert reqs[0].duration_min == 60


def test_map_events_duration_computed_from_start_end():
    """duration_min computed from start/end difference."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(
        start="2026-06-01T14:00:00Z",
        end="2026-06-01T15:30:00Z",
    )]
    reqs = map_events(raw, user_id)

    assert reqs[0].duration_min == 90


def test_map_events_starts_at_from_event_start():
    """starts_at is set from event start dateTime."""
    from app.connectors.calendar import map_events

    user_id = uuid.uuid4()
    raw = [_gcal_event(start="2026-06-01T14:00:00Z")]
    reqs = map_events(raw, user_id)

    assert reqs[0].starts_at == "2026-06-01T14:00:00Z"


# ---------------------------------------------------------------------------
# sync integration tests (mock google client + _ingest_one)
# ---------------------------------------------------------------------------

def _make_settings():
    s = MagicMock()
    s.google_client_id = "test-client-id"
    s.google_client_secret = "test-client-secret"
    s.calendar_refresh_token = "test-refresh-token"
    return s


@pytest.mark.asyncio
async def test_calendar_sync_idempotent():
    """Second sync call: all items return 'skipped' → result.skipped = N."""
    from app.connectors.calendar import sync

    user_id = uuid.uuid4()
    db = MagicMock()
    upsert_execute = AsyncMock(return_value=MagicMock(data=[{}]))
    db.table = MagicMock(return_value=MagicMock(
        upsert=MagicMock(return_value=MagicMock(execute=upsert_execute))
    ))

    settings = _make_settings()

    with patch("app.connectors.calendar._ingest_one", new_callable=AsyncMock) as mock_ingest, \
         patch("app.connectors.calendar._build_calendar_service") as mock_build:

        mock_ingest.return_value = ("duplicate", None)

        # Mock the calendar service: service.events().list().execute()
        mock_list_execute = MagicMock(return_value={
            "items": [
                {"id": "1", "summary": "Event 1", "start": {"dateTime": "2026-06-01T10:00:00Z"}},
                {"id": "2", "summary": "Event 2", "start": {"dateTime": "2026-06-02T10:00:00Z"}},
                {"id": "3", "summary": "Event 3", "start": {"dateTime": "2026-06-03T10:00:00Z"}},
            ]
        })
        mock_list = MagicMock(return_value=MagicMock(execute=mock_list_execute))
        mock_events = MagicMock(return_value=MagicMock(list=mock_list))
        mock_service = MagicMock()
        mock_service.events = mock_events
        mock_build.return_value = mock_service

        result = await sync(db, MagicMock(), MagicMock(), settings, user_id=user_id)

    assert result.skipped == 3
    assert result.created == 0
