"""
GitHub connector — Phase 4.

Polls the GitHub Notifications API and ingests relevant notifications
as tasks (assign/review_requested) or notes (mention/subscribed/other).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.connectors.base import SyncResult
from app.schemas.ingest import IngestRequest
from app.services.ingest_service import _ingest_one

logger = logging.getLogger(__name__)

_GITHUB_NOTIFICATIONS_URL = "https://api.github.com/notifications"
_MAX_NOTIFICATIONS = 50

_TASK_SUBJECT_TYPES = {"assign", "review_requested"}


def map_notifications(raw: list[dict], user_id: UUID) -> list[IngestRequest]:
    """
    Map raw GitHub notification dicts to IngestRequest objects.

    Args:
        raw: List of notification dicts from the GitHub API.
        user_id: Owner UUID for the ingested records.

    Returns:
        List of IngestRequest objects ready for _ingest_one.
    """
    requests = []
    for notification in raw:
        subject = notification.get("subject", {})
        subject_type = subject.get("type", "")
        title = subject.get("title", "GitHub notification")
        nid = str(notification.get("id", ""))
        repo = notification.get("repository", {}).get("full_name", "")

        record_type = "task" if subject_type in _TASK_SUBJECT_TYPES else "note"

        requests.append(
            IngestRequest(
                source="github",
                record_type=record_type,
                user_id=user_id,
                title=title,
                project_hint=repo or None,
                external_id=f"github:notification:{nid}",
            )
        )
    return requests


async def sync(
    db,
    llm,
    embedder,
    settings,
    user_id: UUID,
) -> SyncResult:
    """
    Sync GitHub notifications for the given user.

    Fetches at most 50 unread notifications and ingests each one through
    the shared _ingest_one pipeline. Errors are accumulated per-item —
    one failure does not abort the batch.

    Args:
        db: Supabase AsyncClient (service-role).
        llm: LLMProvider (unused by GitHub connector; passed for interface consistency).
        embedder: EmbeddingProvider.
        settings: Settings instance with github_token.
        user_id: Owner UUID.

    Returns:
        SyncResult with created/skipped/failed counts.
    """
    result = SyncResult()

    async with httpx.AsyncClient() as client:
        response = await client.get(
            _GITHUB_NOTIFICATIONS_URL,
            params={"per_page": _MAX_NOTIFICATIONS, "all": "false"},
            headers={
                "Authorization": f"token {settings.github_token}",
                "Accept": "application/vnd.github+json",
            },
        )
        response.raise_for_status()
        notifications = response.json()

    # Cap to 50 even if API returns more
    notifications = notifications[:_MAX_NOTIFICATIONS]

    reqs = map_notifications(notifications, user_id)

    for req in reqs:
        try:
            outcome, _record_id = await _ingest_one(req, db, embedder, settings)
            if outcome == "created":
                result.created += 1
            elif outcome == "duplicate":
                result.skipped += 1
            else:
                result.failed += 1
                result.errors.append(f"Error ingesting {req.external_id}")
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"{req.external_id}: {exc}")
            logger.exception("github connector: error on %s", req.external_id)

    # Upsert connector_state with last_sync_at
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db.table("connector_state").upsert(
            {
                "user_id": str(user_id),
                "provider": "github",
                "state_json": {"last_sync_at": now_iso},
                "updated_at": now_iso,
            },
            on_conflict="user_id,provider",
        ).execute()
    except Exception as exc:
        logger.warning("github connector: failed to upsert connector_state: %s", exc)

    logger.info(
        "github sync complete: created=%d skipped=%d failed=%d",
        result.created,
        result.skipped,
        result.failed,
    )
    return result
