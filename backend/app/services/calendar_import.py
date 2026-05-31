"""
Google Calendar → ARIA sync service.

Fetches events from Google Calendar and creates/updates them in ARIA's events table.
One-way sync: Google Calendar is the source of truth.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from app.core.config import Settings

logger = logging.getLogger(__name__)


def _get_calendar_creds(settings: Settings) -> Credentials:
    """Build Google OAuth2 credentials from settings."""
    return Credentials(
        token=None,
        refresh_token=settings.calendar_refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
    )


def _get_calendar_service(settings: Settings):
    """Get a Google Calendar API service."""
    creds = _get_calendar_creds(settings)
    return build("calendar", "v3", credentials=creds)


def _parse_event(gcal_event: dict) -> dict | None:
    """Convert a Google Calendar event to an ARIA event dict."""
    start = gcal_event.get("start", {})
    end = gcal_event.get("end", {})

    # Skip all-day events (date only, no dateTime)
    if "date" in start and "dateTime" not in start:
        return None

    starts_at_str = start.get("dateTime")
    ends_at_str = end.get("dateTime")

    if not starts_at_str:
        return None

    try:
        starts_at = datetime.fromisoformat(starts_at_str.replace("Z", "+00:00"))
        ends_at = datetime.fromisoformat(ends_at_str.replace("Z", "+00:00")) if ends_at_str else None
    except (ValueError, TypeError):
        return None

    duration_min = 60
    if ends_at:
        duration_min = max(1, int((ends_at - starts_at).total_seconds() / 60))

    summary = gcal_event.get("summary", "(No title)")
    gcal_id = gcal_event.get("id", "")

    # Determine event type from summary/description
    event_type = "other"
    summary_lower = summary.lower()
    if any(kw in summary_lower for kw in ["meeting", "reunión", "junta", "call", "standup"]):
        event_type = "meeting"
    elif any(kw in summary_lower for kw in ["class", "clase", "lecture", "materia"]):
        event_type = "class"
    elif any(kw in summary_lower for kw in ["appointment", "cita", "médico", "doctor"]):
        event_type = "appointment"

    return {
        "title": summary,
        "starts_at": starts_at.isoformat(),
        "duration_min": duration_min,
        "type": event_type,
        "source": "google_calendar",
        "external_id": f"gcal:{gcal_id}",
    }


async def sync_calendar_events(
    user_id: str,
    settings,
    db,
    days_ahead: int = 30,
) -> dict:
    """
    Sync Google Calendar events to ARIA.

    Fetches events from now to now + days_ahead.
    Creates new events, updates existing ones (matched by external_id).
    Returns {imported, updated, skipped}.
    """
    if not settings.calendar_refresh_token:
        return {"imported": 0, "updated": 0, "skipped": 0, "error": "no_token"}

    try:
        service = _get_calendar_service(settings)
        now = datetime.now(tz=timezone.utc)
        time_max = now + timedelta(days=days_ahead)

        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=100,
        ).execute()

        gcal_events = result.get("items", [])
    except Exception as exc:
        logger.error("calendar sync: fetch failed: %s", exc)
        return {"imported": 0, "updated": 0, "skipped": 0, "error": str(exc)}

    imported = 0
    updated = 0
    skipped = 0

    for gcal_event in gcal_events:
        parsed = _parse_event(gcal_event)
        if not parsed:
            skipped += 1
            continue

        external_id = parsed["external_id"]

        # Check if event already exists
        try:
            existing = await (
                db.table("events")
                .select("id")
                .eq("user_id", user_id)
                .eq("external_id", external_id)
                .limit(1)
                .execute()
            )
        except Exception:
            existing = None

        if existing and existing.data:
            # Update existing
            try:
                await (
                    db.table("events")
                    .update({
                        "title": parsed["title"],
                        "starts_at": parsed["starts_at"],
                        "duration_min": parsed["duration_min"],
                        "type": parsed["type"],
                    })
                    .eq("id", existing.data[0]["id"])
                    .execute()
                )
                updated += 1
            except Exception as exc:
                logger.warning("calendar sync: update failed for %s: %s", external_id, exc)
                skipped += 1
        else:
            # Create new — need a project_id. Use null for synced events.
            try:
                await (
                    db.table("events")
                    .insert({
                        "user_id": user_id,
                        "title": parsed["title"],
                        "starts_at": parsed["starts_at"],
                        "duration_min": parsed["duration_min"],
                        "type": parsed["type"],
                        "source": parsed["source"],
                        "external_id": parsed["external_id"],
                        "project_id": None,
                    })
                    .execute()
                )
                imported += 1
            except Exception as exc:
                logger.warning("calendar sync: insert failed for %s: %s", external_id, exc)
                skipped += 1

    logger.info("calendar sync: imported=%d, updated=%d, skipped=%d", imported, updated, skipped)
    return {"imported": imported, "updated": updated, "skipped": skipped}
