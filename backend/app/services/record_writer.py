"""
Record writer service.

Routes a CaptureIntent to the correct Supabase domain table and inserts the
record. Returns (table_name, record_id, title) for use in ChatResponse and
conversation metadata.

Spec §2 — record written to correct domain table.
Phase 4 — source and external_id params added (backward compatible).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.schemas.classifier import CaptureIntent

logger = logging.getLogger(__name__)


async def write(
    intent: CaptureIntent,
    embedding: list[float] | None,
    user_id: UUID,
    project_id: UUID,
    db,  # AsyncClient — typed loosely to avoid circular supabase import
    source: str = "aria_chat",
    external_id: str | None = None,
) -> tuple[str, UUID, str]:
    """
    Insert a capture record into the correct domain table.

    Args:
        intent: A CaptureIntent with record_type and field data.
        embedding: Optional embedding vector; stored as NULL when None.
        user_id: The owner's user UUID.
        project_id: The resolved project UUID.
        db: Supabase AsyncClient (service-role).
        source: Origin of the record; defaults to 'aria_chat' for chat pipeline.
        external_id: Source-prefixed dedup key; None for manually-created records.

    Returns:
        Tuple of (table_name, record_id, title).
    """
    table_name = _table_for(intent.record_type)
    payload = _build_payload(intent, embedding, user_id, project_id, source=source, external_id=external_id)

    response = await db.table(table_name).insert(payload).execute()
    row = response.data[0]
    record_id = UUID(row["id"])
    title = row.get("title") or intent.title

    logger.info(
        "record_writer: inserted %s row id=%s title='%s'",
        table_name,
        record_id,
        title,
    )
    return table_name, record_id, title


def _table_for(record_type: str) -> str:
    mapping = {
        "task": "tasks",
        "event": "events",
        "reminder": "reminders",
        "note": "notes",
    }
    return mapping[record_type]


def _serialize_embedding(embedding: list[float] | None) -> str | None:
    """Convert a float list to pgvector string format expected by PostgREST."""
    if embedding is None:
        return None
    return "[" + ",".join(str(v) for v in embedding) + "]"


def _build_payload(
    intent: CaptureIntent,
    embedding: list[float] | None,
    user_id: UUID,
    project_id: UUID,
    source: str = "aria_chat",
    external_id: str | None = None,
) -> dict:
    """Build the INSERT payload appropriate for the record_type."""
    embedding_str = _serialize_embedding(embedding)
    base = {
        "title": intent.title,
        "embedding": embedding_str,
        "source": source,
        "external_id": external_id,
    }

    if intent.record_type == "task":
        payload = {
            **base,
            "project_id": str(project_id),
            "status": "pending",
            "priority": 3,
            "energy_level": intent.energy_level,
        }
        if intent.deadline:
            payload["deadline"] = intent.deadline

    elif intent.record_type == "event":
        payload = {
            **base,
            "user_id": str(user_id),
            "project_id": str(project_id),
            # starts_at is NOT NULL in schema — use provided value or raise
            "starts_at": intent.starts_at or _require_field("starts_at", intent),
            "duration_min": intent.duration_min or 60,
            "type": "other",
        }

    elif intent.record_type == "reminder":
        payload = {
            **base,
            "user_id": str(user_id),
            "project_id": str(project_id),
            "due_at": intent.due_at or (datetime.now(tz=timezone.utc) + timedelta(days=1)).isoformat(),
            "is_done": False,
        }
        if intent.amount is not None:
            payload["amount"] = intent.amount
        if intent.currency:
            payload["currency"] = intent.currency

    elif intent.record_type == "note":
        # notes use 'content' not 'title'
        payload = {
            "content": intent.title,
            "tags": intent.tags or [],
            "embedding": embedding_str,
            "source": source,
            "external_id": external_id,
            "user_id": str(user_id),
            "project_id": str(project_id),
        }

    else:
        raise ValueError(f"Unknown record_type: {intent.record_type}")

    return payload


def _require_field(field: str, intent: CaptureIntent):
    raise ValueError(
        f"record_writer: record_type='{intent.record_type}' requires field '{field}'"
    )
