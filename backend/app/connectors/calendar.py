"""
Google Calendar connector — Phase 4.

Lists upcoming Google Calendar events and ingests them as event records.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from app.connectors.base import SyncResult
from app.schemas.ingest import IngestRequest
from app.services.ingest_service import _ingest_one

logger = logging.getLogger(__name__)

_MAX_EVENTS = 50
_DEFAULT_DURATION_MIN = 60


def _parse_datetime(dt_str: str | None) -> datetime | None:
    """Parse an ISO 8601 datetime string from the Calendar API."""
    if not dt_str:
        return None
    try:
        # Handle Z suffix
        if dt_str.endswith("Z"):
            dt_str = dt_str[:-1] + "+00:00"
        return datetime.fromisoformat(dt_str)
    except (ValueError, TypeError):
        return None


def map_events(raw: list[dict], user_id: UUID) -> list[IngestRequest]:
    """
    Map raw Google Calendar event dicts to IngestRequest objects.

    Args:
        raw: List of event dicts from the Google Calendar API.
        user_id: Owner UUID for the ingested records.

    Returns:
        List of IngestRequest objects ready for _ingest_one.
    """
    requests = []
    for event in raw:
        event_id = event.get("id", "")
        summary = event.get("summary", "Untitled event")
        description = event.get("description")

        start_str = event.get("start", {}).get("dateTime")
        end_str = event.get("end", {}).get("dateTime")

        # Compute duration
        start_dt = _parse_datetime(start_str)
        end_dt = _parse_datetime(end_str)
        if start_dt and end_dt:
            duration_min = int((end_dt - start_dt).total_seconds() / 60)
            if duration_min <= 0:
                duration_min = _DEFAULT_DURATION_MIN
        else:
            duration_min = _DEFAULT_DURATION_MIN

        requests.append(
            IngestRequest(
                source="google_calendar",
                record_type="event",
                user_id=user_id,
                title=summary,
                body=description,
                starts_at=start_str,
                duration_min=duration_min,
                external_id=f"gcal:event:{event_id}",
            )
        )
    return requests


def _build_calendar_service(settings):
    """Build an authenticated Google Calendar API service client."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=settings.calendar_refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return build("calendar", "v3", credentials=creds)


async def sync(
    db,
    llm,
    embedder,
    settings,
    user_id: UUID,
) -> SyncResult:
    """
    Sync upcoming Google Calendar events for the given user.

    Fetches events from now to now+30 days (max 50) and ingests each
    through the shared _ingest_one pipeline.

    Args:
        db: Supabase AsyncClient (service-role).
        llm: LLMProvider (unused by calendar connector; passed for interface consistency).
        embedder: EmbeddingProvider.
        settings: Settings instance with Google OAuth credentials.
        user_id: Owner UUID.

    Returns:
        SyncResult with created/skipped/failed counts.
    """
    result = SyncResult()

    try:
        service = _build_calendar_service(settings)
    except Exception as exc:
        result.failed += 1
        result.errors.append(f"Calendar auth failed: {exc}")
        logger.exception("calendar connector: auth error")
        return result

    now = datetime.now(timezone.utc)
    time_max = now + timedelta(days=30)

    try:
        response = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            maxResults=_MAX_EVENTS,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
    except Exception as exc:
        result.failed += 1
        result.errors.append(f"Failed to list events: {exc}")
        logger.exception("calendar connector: list error")
        return result

    events = response.get("items", [])

    reqs = map_events(events, user_id)

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
            logger.exception("calendar connector: error on %s", req.external_id)

    # Upsert connector_state
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db.table("connector_state").upsert(
            {
                "user_id": str(user_id),
                "provider": "google_calendar",
                "state_json": {"last_sync_at": now_iso},
                "updated_at": now_iso,
            },
            on_conflict="user_id,provider",
        ).execute()
    except Exception as exc:
        logger.warning("calendar connector: failed to upsert connector_state: %s", exc)

    logger.info(
        "calendar sync complete: created=%d skipped=%d failed=%d",
        result.created,
        result.skipped,
        result.failed,
    )
    return result
