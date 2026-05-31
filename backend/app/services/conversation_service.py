"""
Conversation service.

Manages conversation turn persistence in the conversations table.
Each POST /chat produces two rows: one for the user turn and one for the
assistant turn.

Spec §2 — conversation turns saved.
"""

from __future__ import annotations

import logging
from uuid import UUID

logger = logging.getLogger(__name__)

ConversationTurn = dict  # type alias — JSON rows from conversations table


async def save(
    user_turn: dict,
    assistant_turn: dict,
    db,  # AsyncClient — typed loosely to avoid circular supabase import
) -> None:
    """
    Insert both conversation turns into the conversations table.

    Args:
        user_turn: Dict with at minimum user_id, role="user", content, metadata.
        assistant_turn: Dict with role="assistant", content, metadata.
        db: Supabase AsyncClient (service-role).
    """
    await db.table("conversations").insert(user_turn).execute()
    await db.table("conversations").insert(assistant_turn).execute()
    logger.debug("conversation_service: saved 2 turns for user=%s", user_turn.get("user_id"))


async def get_history(
    user_id: UUID,
    db,
    limit: int = 20,
    project_id: UUID | None = None,
) -> list[ConversationTurn]:
    """
    Fetch recent conversation turns for a user, ordered by created_at ascending.

    Args:
        user_id: The user's UUID.
        db: Supabase AsyncClient.
        limit: Maximum number of turns to return (default 20).
        project_id: If provided, return only turns for that project.
                    If None, return only general-chat turns (project_id IS NULL).

    Returns:
        List of conversation turn dicts with role + content, oldest first.
    """
    query = (
        db.table("conversations")
        .select("role, content")
        .eq("user_id", str(user_id))
        .order("created_at", desc=False)
        .limit(limit)
    )
    if project_id is not None:
        query = query.eq("project_id", str(project_id))
    else:
        query = query.is_("project_id", "null")
    response = await query.execute()
    return response.data or []


async def get_last_assistant_turn(
    user_id: UUID,
    db,
) -> ConversationTurn | None:
    """
    Return the most recent assistant turn for a user.

    Used by the correction flow to locate the record that needs replacing.

    Args:
        user_id: The user's UUID.
        db: Supabase AsyncClient.

    Returns:
        The latest assistant conversation turn dict, or None if not found.
    """
    response = (
        await db.table("conversations")
        .select("*")
        .eq("user_id", str(user_id))
        .eq("role", "assistant")
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = response.data or []
    return rows[0] if rows else None
