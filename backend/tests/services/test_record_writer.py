"""
TDD RED tests for record_writer.

Tests are written BEFORE implementation. They MUST fail until task 4.3 is done.

Spec §2:
- Routes CaptureIntent.record_type to the correct Supabase table.
- Returns (table: str, id: UUID, title: str).
- Passes embedding when provided; inserts with embedding=NULL when None.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch, call
from uuid import uuid4, UUID

from app.schemas.classifier import CaptureIntent


def _make_capture(record_type: str, title: str = "Test record") -> CaptureIntent:
    return CaptureIntent(
        intent="capture",
        record_type=record_type,
        title=title,
    )


def _make_mock_db(inserted_id: str | None = None, title: str = "Buy milk"):
    """Build a mock AsyncClient with a chainable .table().insert().execute() chain."""
    _id = inserted_id or str(uuid4())
    execute_mock = AsyncMock(return_value=MagicMock(data=[{"id": _id, "title": title}]))
    insert_mock = MagicMock(return_value=MagicMock(execute=execute_mock))
    table_mock = MagicMock(return_value=MagicMock(insert=insert_mock))
    db = MagicMock()
    db.table = table_mock
    return db, _id


# ---------------------------------------------------------------------------
# Test: task capture → inserts into tasks table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_task_inserts_into_tasks():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = _make_capture("task", "Buy milk")

    table, record_id, title = await write(intent, None, user_id, project_id, db)

    assert table == "tasks"
    db.table.assert_called_with("tasks")


@pytest.mark.asyncio
async def test_write_task_returns_correct_tuple():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = _make_capture("task", "Buy milk")

    table, record_id, title = await write(intent, None, user_id, project_id, db)

    assert table == "tasks"
    assert isinstance(record_id, UUID)
    assert title == "Buy milk"


# ---------------------------------------------------------------------------
# Test: event capture → inserts into events table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_event_inserts_into_events():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = CaptureIntent(
        intent="capture",
        record_type="event",
        title="Team meeting",
        starts_at="2026-05-30T14:00:00",
    )

    table, record_id, title = await write(intent, None, user_id, project_id, db)

    assert table == "events"
    db.table.assert_called_with("events")


# ---------------------------------------------------------------------------
# Test: reminder capture → inserts into reminders table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_reminder_inserts_into_reminders():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = CaptureIntent(
        intent="capture",
        record_type="reminder",
        title="Pay rent",
        due_at="2026-06-01T09:00:00",
    )

    table, record_id, title = await write(intent, None, user_id, project_id, db)

    assert table == "reminders"
    db.table.assert_called_with("reminders")


# ---------------------------------------------------------------------------
# Test: note capture → inserts into notes table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_note_inserts_into_notes():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = CaptureIntent(
        intent="capture",
        record_type="note",
        title="Interesting idea",
        tags=["idea", "work"],
    )

    table, record_id, title = await write(intent, None, user_id, project_id, db)

    assert table == "notes"
    db.table.assert_called_with("notes")


# ---------------------------------------------------------------------------
# Test: embedding passed to insert payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_write_includes_embedding_when_provided():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = _make_capture("task", "Task with embedding")
    embedding = [0.1] * 4096

    await write(intent, embedding, user_id, project_id, db)

    # The insert call should have received an embedding field (serialized as string for Postgres)
    insert_call_args = db.table.return_value.insert.call_args
    payload = insert_call_args[0][0]
    assert "embedding" in payload
    # Embedding is serialized to "[0.1,0.1,...]" string format for pgvector
    assert isinstance(payload["embedding"], str)
    assert payload["embedding"].startswith("[")
    assert payload["embedding"].endswith("]")


@pytest.mark.asyncio
async def test_write_embedding_none_when_not_provided():
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = _make_capture("task", "Task without embedding")

    await write(intent, None, user_id, project_id, db)

    insert_call_args = db.table.return_value.insert.call_args
    payload = insert_call_args[0][0]
    assert payload.get("embedding") is None


# ---------------------------------------------------------------------------
# TASK-2.6: energy_level is persisted from intent (not hardcoded)
# ---------------------------------------------------------------------------

def test_build_payload_task_uses_intent_energy_level_high():
    """CaptureIntent(energy_level='high') → payload has energy_level='high'."""
    from app.services.record_writer import _build_payload
    from app.schemas.classifier import CaptureIntent

    intent = CaptureIntent(
        intent="capture",
        record_type="task",
        title="Deep research",
        energy_level="high",
    )
    payload = _build_payload(intent, None, uuid4(), uuid4())
    assert payload["energy_level"] == "high"


def test_build_payload_task_uses_intent_energy_level_low():
    """CaptureIntent(energy_level='low') → payload has energy_level='low'."""
    from app.services.record_writer import _build_payload
    from app.schemas.classifier import CaptureIntent

    intent = CaptureIntent(
        intent="capture",
        record_type="task",
        title="Quick note review",
        energy_level="low",
    )
    payload = _build_payload(intent, None, uuid4(), uuid4())
    assert payload["energy_level"] == "low"


def test_build_payload_task_defaults_to_medium_energy():
    """CaptureIntent() with default energy_level → payload has energy_level='medium'."""
    from app.services.record_writer import _build_payload
    from app.schemas.classifier import CaptureIntent

    intent = CaptureIntent(
        intent="capture",
        record_type="task",
        title="Team meeting",
    )
    payload = _build_payload(intent, None, uuid4(), uuid4())
    assert payload["energy_level"] == "medium"


# ---------------------------------------------------------------------------
# TASK-2.1: source and external_id stored in payload (Phase 4)
# ---------------------------------------------------------------------------

def test_build_payload_uses_explicit_source():
    """_build_payload with source='github' → payload has source='github'."""
    from app.services.record_writer import _build_payload

    intent = CaptureIntent(intent="capture", record_type="task", title="Review PR")
    payload = _build_payload(intent, None, uuid4(), uuid4(), source="github")
    assert payload["source"] == "github"


def test_build_payload_defaults_source_to_aria_chat():
    """_build_payload without source kwarg → payload has source='aria_chat'."""
    from app.services.record_writer import _build_payload

    intent = CaptureIntent(intent="capture", record_type="task", title="Buy groceries")
    payload = _build_payload(intent, None, uuid4(), uuid4())
    assert payload["source"] == "aria_chat"


def test_build_payload_stores_external_id():
    """_build_payload with external_id → payload has external_id key."""
    from app.services.record_writer import _build_payload

    intent = CaptureIntent(intent="capture", record_type="task", title="Review PR")
    payload = _build_payload(intent, None, uuid4(), uuid4(), external_id="github:notification:99")
    assert payload["external_id"] == "github:notification:99"


def test_build_payload_external_id_none_by_default():
    """_build_payload without external_id → payload has external_id=None."""
    from app.services.record_writer import _build_payload

    intent = CaptureIntent(intent="capture", record_type="task", title="Stretch goal")
    payload = _build_payload(intent, None, uuid4(), uuid4())
    assert payload.get("external_id") is None


def test_build_payload_note_uses_explicit_source():
    """Note type also respects explicit source param."""
    from app.services.record_writer import _build_payload

    intent = CaptureIntent(intent="capture", record_type="note", title="Meeting notes")
    payload = _build_payload(intent, None, uuid4(), uuid4(), source="gmail")
    assert payload["source"] == "gmail"


@pytest.mark.asyncio
async def test_write_passes_source_to_payload():
    """write(..., source='github') → inserted payload has source='github'."""
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = _make_capture("task", "Review PR")

    await write(intent, None, user_id, project_id, db, source="github")

    insert_call_args = db.table.return_value.insert.call_args
    payload = insert_call_args[0][0]
    assert payload["source"] == "github"


@pytest.mark.asyncio
async def test_write_passes_external_id_to_payload():
    """write(..., external_id='github:notification:42') → payload has external_id."""
    from app.services.record_writer import write

    db, _id = _make_mock_db()
    user_id = uuid4()
    project_id = uuid4()
    intent = _make_capture("task", "Review PR")

    await write(intent, None, user_id, project_id, db, external_id="github:notification:42")

    insert_call_args = db.table.return_value.insert.call_args
    payload = insert_call_args[0][0]
    assert payload["external_id"] == "github:notification:42"
