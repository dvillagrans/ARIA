"""
Context note service — Phase 2: Memory & RAG.

Provides fuzzy task search via pg_trgm and LLM-powered context_note updates.

ADR-3: pg_trgm similarity() > 0.3 for task lookup (enforced in SQL).
"""

from __future__ import annotations

import logging
from uuid import UUID

from app.providers.base import LLMProvider

logger = logging.getLogger(__name__)

# pg_trgm similarity threshold for task title matching (ADR-3)
_TRGM_THRESHOLD = 0.3


async def search_task(
    user_id: UUID,
    task_reference: str,
    db,
) -> dict | None:
    """
    Find the best-matching task for a user using pg_trgm trigram similarity.

    Executes a raw RPC call that runs:
        SELECT * FROM tasks
        WHERE user_id (via project) = <user_id>
          AND similarity(title, <task_reference>) > 0.3
        ORDER BY similarity(title, <task_reference>) DESC
        LIMIT 1

    Args:
        user_id: The owner's UUID.
        task_reference: Natural language task name/reference from the user.
        db: Supabase AsyncClient.

    Returns:
        Task row dict if found, None otherwise.
    """
    response = await db.rpc(
        "search_tasks_by_similarity",
        {
            "p_user_id": str(user_id),
            "p_reference": task_reference,
            "p_threshold": _TRGM_THRESHOLD,
        },
    ).execute()

    rows = response.data or []
    if not rows:
        return None

    return rows[0]


async def update_context_note(
    task: dict,
    update_text: str,
    db,
    llm: LLMProvider,
) -> str:
    """
    Use LLM reasoning to merge update_text into the task's existing context_note,
    then persist the result.

    The prior note is passed as empty string when NULL (spec: null context_note handled).

    Args:
        task: Task row dict with at minimum 'id' and 'context_note'.
        update_text: New information to incorporate into the note.
        db: Supabase AsyncClient.
        llm: LLM provider.

    Returns:
        The updated context_note string as persisted.
    """
    prior_note = task.get("context_note") or ""
    task_id = task["id"]

    prompt = (
        f"Current note: {prior_note}. "
        f"Update: {update_text}. "
        "Return updated note only, max 300 chars."
    )

    new_note = await llm.reason(prompt)

    await db.table("tasks").update({"context_note": new_note}).eq("id", task_id).execute()

    logger.info(
        "context_note_service: updated context_note for task_id=%s len=%d",
        task_id,
        len(new_note),
    )

    return new_note
