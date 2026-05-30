"""
TDD RED tests for ingest_service._ingest_one.

Phase 4 — these tests MUST fail until ingest_service.py is created (task 2.5).

Scenarios:
- Returns "skipped" when (source, external_id) already exists in DB.
- Returns "created" on happy path; calls record_writer.write with correct args.
- Returns "created" when external_id is None (no dedup check performed).
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.schemas.ingest import IngestRequest


def _make_req(**kwargs) -> IngestRequest:
    defaults = {
        "source": "github",
        "record_type": "task",
        "user_id": uuid4(),
        "title": "Review PR",
        "external_id": "github:notification:42",
    }
    defaults.update(kwargs)
    return IngestRequest(**defaults)


def _make_chainable_select(data: list) -> MagicMock:
    """Build a chainable select mock: .select().eq().eq().execute() → data."""
    execute = AsyncMock(return_value=MagicMock(data=data))
    # Each .eq() call returns something with another .eq() and .execute()
    inner = MagicMock()
    inner.execute = execute
    inner.eq = MagicMock(return_value=inner)
    outer = MagicMock()
    outer.execute = execute
    outer.eq = MagicMock(return_value=inner)
    select = MagicMock(return_value=outer)
    return select


def _make_db(existing_id: str | None = None):
    """Build a mock Supabase client.

    If existing_id is provided, SELECT returns a row simulating a duplicate.
    Otherwise SELECT returns empty list (no duplicate).
    """
    existing_data = [{"id": existing_id}] if existing_id else []
    insert_id = str(uuid4())

    # Insert chain: .insert(...).execute() → data=[{id, title}]
    insert_execute = AsyncMock(return_value=MagicMock(data=[{"id": insert_id, "title": "Review PR"}]))
    insert_mock = MagicMock(return_value=MagicMock(execute=insert_execute))

    # Dedup select (tasks table) — returns existing_data
    dedup_select = _make_chainable_select(existing_data)

    # Projects select — returns a dummy project list
    project_id = str(uuid4())
    projects_select = _make_chainable_select([{"id": project_id, "name": "Personal"}])

    # table_mock: first call (dedup) gets dedup_select, second call (projects) gets projects_select
    call_count = {"n": 0}

    def table_side_effect(name: str):
        tbl = MagicMock()
        if name == "projects":
            tbl.select = projects_select
        else:
            tbl.select = dedup_select
        tbl.insert = insert_mock
        return tbl

    db = MagicMock()
    db.table = MagicMock(side_effect=table_side_effect)
    return db, insert_id


def _make_settings(ingest_api_key: str = "test-key"):
    settings = MagicMock()
    settings.ingest_api_key = ingest_api_key
    return settings


def _make_embedder(vector: list[float] | None = None):
    embedder = MagicMock()
    embedder.embed = AsyncMock(return_value=vector or [0.1] * 1536)
    return embedder


# ---------------------------------------------------------------------------
# Dedup: returns "skipped" when row already exists
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_one_returns_duplicate_when_duplicate():
    """When SELECT finds existing (source, external_id) row → return ('duplicate', existing_id)."""
    from app.services.ingest_service import _ingest_one

    existing_id = str(uuid4())
    db, _ = _make_db(existing_id=existing_id)
    embedder = _make_embedder()
    settings = _make_settings()
    req = _make_req()

    result = await _ingest_one(req, db, embedder, settings)

    assert result == ("duplicate", existing_id)
    # embedder.embed should NOT be called
    embedder.embed.assert_not_called()


# ---------------------------------------------------------------------------
# Happy path: returns "created" and calls record_writer.write
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_one_returns_created_on_new_record():
    """When no duplicate found → embed, write, return 'created'."""
    from app.services.ingest_service import _ingest_one

    db, insert_id = _make_db()  # no existing row
    embedder = _make_embedder()
    settings = _make_settings()
    req = _make_req()

    with patch("app.services.ingest_service.record_writer") as mock_rw:
        mock_rw.write = AsyncMock(return_value=("tasks", insert_id, "Review PR"))

        result = await _ingest_one(req, db, embedder, settings)

    assert result[0] == "created"
    assert result[1] is not None  # record_id is returned
    embedder.embed.assert_called_once()


@pytest.mark.asyncio
async def test_ingest_one_calls_record_writer_with_correct_source():
    """record_writer.write is called with source=req.source."""
    from app.services.ingest_service import _ingest_one

    db, insert_id = _make_db()
    embedder = _make_embedder()
    settings = _make_settings()
    req = _make_req(source="github", external_id="github:notification:99")

    with patch("app.services.ingest_service.record_writer") as mock_rw:
        mock_rw.write = AsyncMock(return_value=("tasks", insert_id, "Review PR"))

        await _ingest_one(req, db, embedder, settings)

        call_kwargs = mock_rw.write.call_args
        assert call_kwargs.kwargs.get("source") == "github" or (
            len(call_kwargs.args) > 5 and call_kwargs.args[5] == "github"
        )


@pytest.mark.asyncio
async def test_ingest_one_calls_record_writer_with_correct_external_id():
    """record_writer.write is called with external_id=req.external_id."""
    from app.services.ingest_service import _ingest_one

    db, insert_id = _make_db()
    embedder = _make_embedder()
    settings = _make_settings()
    req = _make_req(external_id="github:notification:99")

    with patch("app.services.ingest_service.record_writer") as mock_rw:
        mock_rw.write = AsyncMock(return_value=("tasks", insert_id, "Review PR"))

        await _ingest_one(req, db, embedder, settings)

        call_kwargs = mock_rw.write.call_args
        assert call_kwargs.kwargs.get("external_id") == "github:notification:99" or (
            len(call_kwargs.args) > 6 and call_kwargs.args[6] == "github:notification:99"
        )


# ---------------------------------------------------------------------------
# No external_id: skip dedup check, always insert
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_ingest_one_skips_dedup_when_no_external_id():
    """When external_id is None, no SELECT is issued — always insert."""
    from app.services.ingest_service import _ingest_one

    db, insert_id = _make_db()
    embedder = _make_embedder()
    settings = _make_settings()
    req = _make_req(external_id=None)

    with patch("app.services.ingest_service.record_writer") as mock_rw:
        mock_rw.write = AsyncMock(return_value=("tasks", insert_id, "Review PR"))

        result = await _ingest_one(req, db, embedder, settings)

    assert result[0] == "created"
    # SELECT should NOT have been called (no external_id to dedup)
    db.table.return_value.select.assert_not_called()
