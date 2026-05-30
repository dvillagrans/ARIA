"""
Ingest service — Phase 4.

_ingest_one: shared pipeline for POST /ingest and all connector sync routes.

Flow:
  1. If external_id provided → SELECT for existing row (dedup check).
  2. If duplicate found → return ("duplicate", existing_id) without embedding.
  3. Embed title + body (if present).
  4. Resolve project via project_resolver (uses project_hint or falls back to Personal).
  5. Build CaptureIntent from IngestRequest.
  6. Call record_writer.write(..., source, external_id).
  7. Return ("created", record_id) on success, ("error", None) on exception.
"""

from __future__ import annotations

import logging
from typing import Literal
from uuid import UUID

from app.schemas.classifier import CaptureIntent
from app.schemas.ingest import IngestRequest
from app.services import record_writer
from app.services.project_resolver import resolve as resolve_project

logger = logging.getLogger(__name__)

# Fallback project used when the user has no projects at all.
_FALLBACK_PROJECT_ID = "00000000-0000-0000-0000-000000000001"


async def _ingest_one(
    req: IngestRequest,
    db,
    embedder,
    settings,
) -> tuple[Literal["created", "duplicate", "error"], str | None]:
    """
    Execute the embed → dedup → write pipeline for a single IngestRequest.

    Args:
        req: Validated IngestRequest from HTTP body or connector mapper.
        db: Supabase AsyncClient (service-role).
        embedder: EmbeddingProvider instance.
        settings: Settings instance (for project resolution config, if needed).

    Returns:
        ("created", record_id) — new record inserted.
        ("duplicate", existing_id) — duplicate (source, external_id) already exists.
        ("error", None) — unexpected exception; caller should add to SyncResult.errors.
    """
    try:
        # Step 1: Dedup check — only when external_id is present
        if req.external_id is not None:
            table_name = _table_for(req.record_type)
            existing = (
                await db.table(table_name)
                .select("id")
                .eq("source", req.source)
                .eq("external_id", req.external_id)
                .execute()
            )
            if existing.data:
                existing_id = existing.data[0]["id"]
                logger.debug(
                    "ingest_service: duplicate found source=%s external_id=%s record_id=%s",
                    req.source,
                    req.external_id,
                    existing_id,
                )
                return ("duplicate", str(existing_id))

        # Step 2: Embed title (+ body if present)
        embed_text = req.title
        if req.body:
            embed_text = f"{req.title}\n\n{req.body}"
        embedding = await embedder.embed(embed_text)

        # Step 3: Resolve project
        projects_resp = await db.table("projects").select("id, name").eq("user_id", str(req.user_id)).execute()
        projects = projects_resp.data or []
        project = await resolve_project(req.project_hint, projects)
        project_id = UUID(project["id"]) if project else UUID(_FALLBACK_PROJECT_ID)

        # Step 4: Build CaptureIntent from IngestRequest
        intent = _build_capture_intent(req)

        # Step 5: Write record
        _table, record_id, _title = await record_writer.write(
            intent,
            embedding,
            req.user_id,
            project_id,
            db,
            source=req.source,
            external_id=req.external_id,
        )

        logger.info(
            "ingest_service: created %s source=%s external_id=%s record_id=%s",
            req.record_type,
            req.source,
            req.external_id,
            record_id,
        )
        return ("created", str(record_id))

    except Exception as exc:
        logger.exception(
            "ingest_service: error processing external_id=%s: %s",
            req.external_id,
            exc,
        )
        return ("error", None)


def _table_for(record_type: str) -> str:
    mapping = {
        "task": "tasks",
        "event": "events",
        "reminder": "reminders",
        "note": "notes",
    }
    return mapping[record_type]


def _build_capture_intent(req: IngestRequest) -> CaptureIntent:
    """Map IngestRequest fields to CaptureIntent (no LLM — record_type is pre-determined)."""
    return CaptureIntent(
        intent="capture",
        record_type=req.record_type,
        title=req.title,
        project_hint=req.project_hint,
        energy_level=req.energy_level,
        deadline=req.deadline,
        starts_at=req.starts_at,
        duration_min=req.duration_min,
        due_at=req.due_at,
        tags=req.tags,
    )
