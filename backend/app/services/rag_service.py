"""
RAG service — Phase 2: Memory & RAG.

Provides vector-similarity retrieval over all user domain records, and a
higher-level answer() function that composes retrieval + conversation history
+ LLM reasoning.

ADR-2: Zero imports from the chat route module. retrieve() is a pure,
       chat-free function usable from any layer (Phase 3 briefing service etc.).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import UUID

from app.core.metrics import aria_rag_latency_seconds
from app.providers.base import EmbeddingProvider, LLMProvider
from app.services import conversation_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Passage:
    """A single retrieval result from match_all_embeddings."""

    id: UUID
    source_table: str        # "tasks" | "notes" | "events" | "reminders" | "conversations"
    content: str
    similarity: float
    project_id: UUID | None
    project_name: str | None


async def retrieve(
    user_id: UUID,
    query_text: str,
    db,
    embedder: EmbeddingProvider,
    match_threshold: float,
    match_count: int,
) -> list[Passage]:
    """
    Embed query_text and call match_all_embeddings RPC.

    Returns a list of Passage objects ranked by cosine similarity descending.
    Returns an empty list (without raising) if no records match.

    ADR-2: No chat-route imports — this function is reusable from any layer.

    Args:
        user_id: The owner's UUID (used for future row-level filtering).
        query_text: Natural language query to embed.
        db: Supabase AsyncClient (service-role).
        embedder: Embedding provider.
        match_threshold: Minimum similarity (0.0–1.0) for a result to qualify.
        match_count: Maximum number of results to return.

    Returns:
        List of Passage dataclasses, most similar first.
    """
    query_vector = await embedder.embed(query_text)

    response = await db.rpc(
        "match_all_embeddings",
        {
            "query_embedding": query_vector,
            "match_threshold": match_threshold,
            "match_count": match_count,
        },
    ).execute()

    rows = response.data or []
    passages: list[Passage] = []

    for row in rows:
        raw_project_id = row.get("project_id")
        raw_project_name = row.get("project_name")

        passages.append(
            Passage(
                id=UUID(str(row["id"])),
                source_table=row["source_table"],
                content=row.get("content") or "",
                similarity=float(row["similarity"]),
                project_id=UUID(str(raw_project_id)) if raw_project_id else None,
                project_name=raw_project_name,
            )
        )

    return passages


async def answer(
    user_id: UUID,
    question: str,
    db,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    settings,
    history: list[dict] | None = None,
) -> tuple[str, list[Passage]]:
    """
    Full RAG pipeline: retrieve → fetch history → reason → return.

    Steps:
      1. retrieve() to get relevant Passage objects
      2. Get last 20 conversation turns for user_id
      3. Format passages as labeled context strings
      4. Call llm.reason(question, context=..., history=...)
      5. Return (answer_text, passages)

    Args:
        user_id: The owner's UUID.
        question: The user's question.
        db: Supabase AsyncClient.
        llm: LLM provider (must support reason() with context + history).
        embedder: Embedding provider.
        settings: Settings instance (supplies RAG_MATCH_THRESHOLD/COUNT).

    Returns:
        Tuple of (answer string, list of Passage objects used as context).
    """
    if aria_rag_latency_seconds is None:
        return await _answer_impl(user_id, question, db, llm, embedder, settings, history)

    with aria_rag_latency_seconds.labels(model="deepseek-reasoner").time():
        return await _answer_impl(user_id, question, db, llm, embedder, settings, history)


async def _answer_impl(
    user_id: UUID,
    question: str,
    db,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    settings,
    history: list[dict] | None = None,
) -> tuple[str, list[Passage]]:
    """Internal RAG implementation (called with or without timing)."""
    passages = await retrieve(
        user_id,
        question,
        db,
        embedder,
        settings.RAG_MATCH_THRESHOLD,
        settings.RAG_MATCH_COUNT,
    )

    effective_history = (
        history if history is not None
        else await conversation_service.get_history(user_id, db, limit=10)
    )

    context_texts: list[str] = []
    for p in passages:
        label = f"From {p.source_table}"
        if p.project_name:
            label += f" ({p.project_name})"
        context_texts.append(f"{label}: {p.content}")

    answer_text = await llm.reason(question, context=context_texts, history=effective_history)

    logger.info(
        "rag_service.answer: user=%s passages=%d answer_len=%d",
        user_id,
        len(passages),
        len(answer_text),
    )

    return answer_text, passages
