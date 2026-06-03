"""
TDD RED tests for rag_service.

Written BEFORE implementation — all must fail until Phase 3 GREEN.

Spec: rag-service requirements
ADR-2: retrieve() has ZERO imports from chat.py (contract test)
"""

from __future__ import annotations

import importlib
import inspect
import sys
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_rpc_response(rows: list[dict]):
    """Return a mock db where db.rpc(...).execute() returns rows."""
    mock_execute = AsyncMock(return_value=MagicMock(data=rows))
    mock_rpc = MagicMock()
    mock_rpc.execute = mock_execute
    mock_db = MagicMock()
    mock_db.rpc = MagicMock(return_value=mock_rpc)
    return mock_db


def _make_embedder(vector: list[float] | None = None):
    vector = vector or [0.1] * 1536
    embedder = AsyncMock()
    embedder.embed = AsyncMock(return_value=vector)
    return embedder


def _make_llm(answer: str = "Here is your answer."):
    llm = AsyncMock()
    llm.reason = AsyncMock(return_value=answer)
    return llm


def _sample_row(source_table: str = "tasks") -> dict:
    return {
        "id": str(uuid4()),
        "source_table": source_table,
        "content": "Sample content",
        "similarity": 0.85,
        "project_id": str(uuid4()),
        "project_name": "My Project",
    }


# ---------------------------------------------------------------------------
# test_passage_fields — Passage dataclass has expected fields
# ---------------------------------------------------------------------------

def test_passage_fields():
    """Passage dataclass must expose id, source_table, content, similarity,
    project_id, project_name."""
    from app.services.rag_service import Passage  # noqa: F401

    row = _sample_row()
    p = Passage(
        id=UUID(row["id"]),
        source_table=row["source_table"],
        content=row["content"],
        similarity=row["similarity"],
        project_id=UUID(row["project_id"]),
        project_name=row["project_name"],
    )
    assert p.id == UUID(row["id"])
    assert p.source_table == "tasks"
    assert p.content == "Sample content"
    assert p.similarity == 0.85
    assert p.project_name == "My Project"


# ---------------------------------------------------------------------------
# test_retrieve_calls_match_all_embeddings
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_calls_match_all_embeddings():
    """retrieve() must call db.rpc('match_all_embeddings', ...) exactly once."""
    from app.services.rag_service import retrieve

    row = _sample_row()
    db = _make_db_rpc_response([row])
    embedder = _make_embedder()
    user_id = uuid4()

    await retrieve(user_id, "What tasks do I have?", db, embedder, 0.5, 10)

    db.rpc.assert_called_once()
    call_args = db.rpc.call_args
    assert call_args[0][0] == "match_all_embeddings"


# ---------------------------------------------------------------------------
# test_retrieve_returns_passage_dataclass_list
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_returns_passage_dataclass_list():
    """retrieve() must return a list of Passage instances with correct fields."""
    from app.services.rag_service import Passage, retrieve

    row = _sample_row("notes")
    db = _make_db_rpc_response([row])
    embedder = _make_embedder()
    user_id = uuid4()

    result = await retrieve(user_id, "notes query", db, embedder, 0.5, 10)

    assert isinstance(result, list)
    assert len(result) == 1
    assert isinstance(result[0], Passage)
    assert result[0].source_table == "notes"
    assert result[0].content == "Sample content"


# ---------------------------------------------------------------------------
# test_retrieve_empty_result
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_returns_empty_list_when_no_embeddings():
    """retrieve() must return [] (not raise) when no rows come back."""
    from app.services.rag_service import retrieve

    db = _make_db_rpc_response([])
    embedder = _make_embedder()
    user_id = uuid4()

    result = await retrieve(user_id, "anything", db, embedder, 0.5, 10)

    assert result == []


# ---------------------------------------------------------------------------
# test_retrieve_respects_match_count (result count contract)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retrieve_passes_match_count_to_rpc():
    """retrieve() must pass match_threshold and match_count to the RPC call."""
    from app.services.rag_service import retrieve

    db = _make_db_rpc_response([])
    embedder = _make_embedder()
    user_id = uuid4()

    await retrieve(user_id, "query", db, embedder, 0.7, 5)

    call_params = db.rpc.call_args[0][1]
    assert call_params.get("match_threshold") == 0.7
    assert call_params.get("match_count") == 5


# ---------------------------------------------------------------------------
# test_answer_returns_string_and_passages
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_returns_string_and_passages():
    """answer() must return (str, list[Passage])."""
    from app.services.rag_service import Passage, answer

    row = _sample_row("tasks")
    db = _make_db_rpc_response([row])

    embedder = _make_embedder()
    llm = _make_llm("ARIA's answer here.")

    from app.core.config import Settings
    settings = Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        deepseek_api_key="key",
        deepinfra_api_key="key2",
    )

    user_id = uuid4()
    answer_text, passages = await answer(user_id, "My question?", db, llm, embedder, settings, history=[])

    assert isinstance(answer_text, str)
    assert len(answer_text) > 0
    assert isinstance(passages, list)
    # All items are Passage instances
    for p in passages:
        assert isinstance(p, Passage)


# ---------------------------------------------------------------------------
# test_answer_calls_llm_reason_with_history
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_answer_calls_llm_reason():
    """answer() must call llm.reason() exactly once."""
    from app.services.rag_service import answer

    row = _sample_row("tasks")
    db = _make_db_rpc_response([row])

    embedder = _make_embedder()
    llm = _make_llm()

    from app.core.config import Settings
    settings = Settings(
        supabase_url="http://localhost:54321",
        supabase_anon_key="anon",
        supabase_service_role_key="service",
        deepseek_api_key="key",
        deepinfra_api_key="key2",
    )

    user_id = uuid4()
    await answer(user_id, "question?", db, llm, embedder, settings, history=[])

    llm.reason.assert_called_once()


# ---------------------------------------------------------------------------
# ADR-2 contract test: rag_service MUST NOT import from chat.py
# ---------------------------------------------------------------------------

def test_rag_service_has_no_chat_import():
    """rag_service must have zero imports from app.routes.chat (ADR-2)."""
    # Force a fresh import so we can inspect source
    if "app.services.rag_service" in sys.modules:
        del sys.modules["app.services.rag_service"]

    import app.services.rag_service as rag_module

    source = inspect.getsource(rag_module)
    # Must not import chat module
    assert "from app.routes.chat" not in source
    assert "import chat" not in source
    # Also verify the module file does not reference routes.chat
    assert "routes.chat" not in source
