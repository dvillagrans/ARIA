"""
TDD RED tests for context_note_service.

Written BEFORE implementation — all must fail until Phase 3 GREEN.

Spec: context-note-service requirements
ADR-3: pg_trgm similarity > 0.3 for task search
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task_row(title: str = "Deploy API") -> dict:
    return {
        "id": str(uuid4()),
        "title": title,
        "context_note": "Work in progress",
        "project_id": str(uuid4()),
    }


def _make_db_for_search(rows: list[dict]):
    """
    Mock db where db.rpc('search_tasks_by_similarity', ...).execute() returns rows.
    context_note_service uses raw SQL via db.rpc or db.postgrest.
    We mock db.rpc for the pg_trgm call.
    """
    mock_execute = AsyncMock(return_value=MagicMock(data=rows))
    mock_rpc = MagicMock()
    mock_rpc.execute = mock_execute
    mock_db = MagicMock()
    mock_db.rpc = MagicMock(return_value=mock_rpc)
    return mock_db


def _make_db_for_update(updated_row: dict):
    """
    Mock db where db.table('tasks').update(...).eq(...).execute() works.

    Supabase builder pattern: every method in the chain returns the builder
    itself until execute() is called. We simulate this with a simple class
    so that .eq(...) doesn't auto-generate a new MagicMock child.
    """
    class _Builder:
        def update(self, data):
            return self

        def eq(self, col, val):
            return self

        async def execute(self):
            return MagicMock(data=[updated_row])

    builder = _Builder()

    mock_db = MagicMock()
    mock_db.table = MagicMock(return_value=builder)
    return mock_db


# ---------------------------------------------------------------------------
# test_search_task_returns_none_when_not_found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_task_returns_none_when_not_found():
    """search_task() must return None when no row matches above threshold."""
    from app.services.context_note_service import search_task

    db = _make_db_for_search([])
    user_id = uuid4()

    result = await search_task(user_id, "zzzxxx", db)

    assert result is None


# ---------------------------------------------------------------------------
# test_search_task_returns_task_dict_when_found
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_search_task_returns_task_dict_when_found():
    """search_task() must return the task dict when similarity > 0.3."""
    from app.services.context_note_service import search_task

    task = _task_row("Deploy API")
    db = _make_db_for_search([task])
    user_id = uuid4()

    result = await search_task(user_id, "Deploy API", db)

    assert result is not None
    assert isinstance(result, dict)
    assert result["title"] == "Deploy API"


# ---------------------------------------------------------------------------
# test_update_context_note_calls_llm_reason
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_context_note_calls_llm_reason():
    """update_context_note() must call llm.reason() with current note + update_text."""
    from app.services.context_note_service import update_context_note

    task = _task_row()
    task["context_note"] = "Old note"
    new_note = "Updated note with new info"

    llm = AsyncMock()
    llm.reason = AsyncMock(return_value=new_note)

    db = _make_db_for_update({**task, "context_note": new_note})

    await update_context_note(task, "It is now blocked by infra", db, llm)

    llm.reason.assert_called_once()
    # The prompt must include the current note and the update text
    prompt_arg = llm.reason.call_args[0][0]
    assert "Old note" in prompt_arg or "Old note" in str(llm.reason.call_args)
    assert "blocked by infra" in prompt_arg or "blocked by infra" in str(llm.reason.call_args)


# ---------------------------------------------------------------------------
# test_update_context_note_returns_new_note_string
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_context_note_returns_new_note_string():
    """update_context_note() must return the string produced by llm.reason()."""
    from app.services.context_note_service import update_context_note

    task = _task_row()
    task["context_note"] = "Initial note"
    expected = "Merged and improved note."

    llm = AsyncMock()
    llm.reason = AsyncMock(return_value=expected)

    db = _make_db_for_update({**task, "context_note": expected})

    result = await update_context_note(task, "add new info", db, llm)

    assert result == expected


# ---------------------------------------------------------------------------
# test_update_context_note_handles_null_context_note
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_update_context_note_handles_null_context_note():
    """update_context_note() must pass empty string when context_note is None."""
    from app.services.context_note_service import update_context_note

    task = _task_row()
    task["context_note"] = None  # NULL in DB
    new_note = "Brand new note."

    llm = AsyncMock()
    llm.reason = AsyncMock(return_value=new_note)

    db = _make_db_for_update({**task, "context_note": new_note})

    result = await update_context_note(task, "Starting fresh", db, llm)

    # Reason must have been called (empty string for prior note must not crash)
    llm.reason.assert_called_once()
    # Empty string or "(empty)" in prompt (spec says empty-string prior note)
    prompt_arg = llm.reason.call_args[0][0]
    # Must NOT pass "None" literally — must be empty or "(empty)"
    assert "None" not in prompt_arg
    assert result == new_note
