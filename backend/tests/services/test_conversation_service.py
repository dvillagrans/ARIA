"""
TDD RED tests for conversation_service.

Tests are written BEFORE implementation. They MUST fail until task 4.4 is done.

Spec §2:
- save(user_turn, assistant_turn, db) inserts 2 rows to conversations table.
- get_history(user_id, db, limit=20) returns list of ConversationTurn.
- get_last_assistant_turn(user_id, db) returns the latest assistant row or None.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, call
from uuid import uuid4


def _make_mock_db_for_insert(inserted_data=None):
    """Mock db that returns data from insert().execute()."""
    data = inserted_data or [{"id": str(uuid4())}]
    execute_mock = AsyncMock(return_value=MagicMock(data=data))
    insert_mock = MagicMock(return_value=MagicMock(execute=execute_mock))
    table_mock = MagicMock(return_value=MagicMock(insert=insert_mock))
    db = MagicMock()
    db.table = table_mock
    return db


def _make_mock_db_for_select(rows=None):
    """Mock db that returns rows from select().eq()...order().limit().execute()."""
    data = rows or []
    execute_mock = AsyncMock(return_value=MagicMock(data=data))
    limit_mock = MagicMock(return_value=MagicMock(execute=execute_mock))
    order_mock = MagicMock(return_value=MagicMock(limit=limit_mock))

    # Support chained .eq() calls: each eq() returns an object with eq + order.
    eq_chain = MagicMock()
    eq_chain.order = order_mock
    eq_chain.eq = MagicMock(return_value=eq_chain)
    eq_chain.limit = limit_mock

    select_mock = MagicMock(return_value=MagicMock(eq=MagicMock(return_value=eq_chain)))
    table_mock = MagicMock(return_value=MagicMock(select=select_mock))
    db = MagicMock()
    db.table = table_mock
    return db


# ---------------------------------------------------------------------------
# Test: save — inserts 2 rows into conversations table
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_inserts_two_rows():
    from app.services.conversation_service import save

    user_id = uuid4()
    user_turn = {
        "user_id": str(user_id),
        "role": "user",
        "content": "Buy milk",
        "metadata": {},
    }
    assistant_turn = {
        "user_id": str(user_id),
        "role": "assistant",
        "content": "Got it, I've added 'Buy milk' as a task.",
        "metadata": {"created_record": {"table": "tasks", "id": str(uuid4()), "title": "Buy milk"}},
    }
    db = _make_mock_db_for_insert()

    await save(user_turn, assistant_turn, db)

    # table("conversations") called twice (once per turn)
    assert db.table.call_count == 2
    db.table.assert_called_with("conversations")


@pytest.mark.asyncio
async def test_save_user_turn_has_correct_role():
    from app.services.conversation_service import save

    user_id = uuid4()
    user_turn = {
        "user_id": str(user_id),
        "role": "user",
        "content": "Hello",
        "metadata": {},
    }
    assistant_turn = {
        "user_id": str(user_id),
        "role": "assistant",
        "content": "Hi!",
        "metadata": {},
    }
    db = _make_mock_db_for_insert()

    await save(user_turn, assistant_turn, db)

    # First insert call should have role=user
    first_insert_payload = db.table.return_value.insert.call_args_list[0][0][0]
    assert first_insert_payload["role"] == "user"


# ---------------------------------------------------------------------------
# Test: get_last_assistant_turn — returns latest assistant row
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_last_assistant_turn_returns_latest():
    from app.services.conversation_service import get_last_assistant_turn

    user_id = uuid4()
    row_id = str(uuid4())
    rows = [
        {
            "id": row_id,
            "user_id": str(user_id),
            "role": "assistant",
            "content": "Done",
            "metadata": {"created_record": {"table": "tasks", "id": str(uuid4()), "title": "Buy milk"}},
        }
    ]
    db = _make_mock_db_for_select(rows)

    result = await get_last_assistant_turn(user_id, db)

    assert result is not None
    assert result["id"] == row_id
    assert result["role"] == "assistant"


@pytest.mark.asyncio
async def test_get_last_assistant_turn_returns_none_when_no_rows():
    from app.services.conversation_service import get_last_assistant_turn

    user_id = uuid4()
    db = _make_mock_db_for_select([])

    result = await get_last_assistant_turn(user_id, db)

    assert result is None


# ---------------------------------------------------------------------------
# Test: get_history — returns list of conversation turns
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_history_returns_rows():
    from app.services.conversation_service import get_history

    user_id = uuid4()
    rows = [
        {"id": str(uuid4()), "role": "user", "content": "Hello", "metadata": {}},
        {"id": str(uuid4()), "role": "assistant", "content": "Hi!", "metadata": {}},
    ]
    db = _make_mock_db_for_select(rows)

    result = await get_history(user_id, db, limit=20)

    assert len(result) == 2


@pytest.mark.asyncio
async def test_get_history_returns_empty_list_when_none():
    from app.services.conversation_service import get_history

    user_id = uuid4()
    db = _make_mock_db_for_select([])

    result = await get_history(user_id, db)

    assert result == []
