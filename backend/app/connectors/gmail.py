"""
Gmail connector — Phase 4.

Lists unread Gmail messages and ingests them as tasks or notes based on
a heuristic classifier (keyword-based) with LLM fallback for ambiguous cases.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from app.connectors.base import SyncResult
from app.schemas.ingest import IngestRequest
from app.services.ingest_service import _ingest_one

logger = logging.getLogger(__name__)

_MAX_MESSAGES = 50

ACTION_KEYWORDS = {
    "action required",
    "review requested",
    "approve",
    "todo",
    "please review",
    "follow up",
    "please",
    "review",
}

INFORMATIONAL_PATTERNS = {
    "noreply@",
    "notifications@",
    "newsletter",
    "digest",
}


def _classify_heuristic(subject: str, snippet: str) -> Literal["task", "note"] | None:
    """
    Classify an email using keyword heuristics.

    Returns:
        "task" — subject contains action keywords.
        "note" — appears informational (newsletter, digest, noreply).
        None   — ambiguous; caller should use LLM fallback.
    """
    s = subject.lower()
    sn = snippet.lower()

    if any(kw in s for kw in ACTION_KEYWORDS):
        return "task"

    # Check both subject and snippet for informational patterns
    combined = f"{s} {sn}"
    if any(pat in combined for pat in INFORMATIONAL_PATTERNS):
        return "note"

    return None


def _decode_body_part(parts: list[dict] | None) -> str:
    """Extract and decode the first text/plain body part."""
    if not parts:
        return ""
    for part in parts:
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            if data:
                # Gmail base64 uses - and _ instead of + and /
                data = data.replace("-", "+").replace("_", "/")
                try:
                    return base64.b64decode(data).decode("utf-8", errors="replace")
                except Exception:
                    return ""
    return ""


def _get_header(headers: list[dict], name: str) -> str:
    """Get a header value by name (case-insensitive)."""
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def map_messages(raw: list[dict], user_id: UUID, llm=None) -> list[IngestRequest]:
    """
    Map raw Gmail message dicts to IngestRequest objects.

    Uses _classify_heuristic to determine record_type. If ambiguous (heuristic
    returns None) and an llm provider is given, calls llm.classify(subject, snippet)
    to determine the type. Falls back to "note" when llm is not provided or fails.

    Args:
        raw: List of Gmail message detail dicts (from messages.get).
        user_id: Owner UUID for the ingested records.
        llm: Optional LLMProvider for ambiguous classification fallback.

    Returns:
        List of IngestRequest objects ready for _ingest_one.
    """
    requests = []
    for msg in raw:
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        subject = _get_header(headers, "Subject")
        snippet = msg.get("snippet", "")

        classification = _classify_heuristic(subject, snippet)

        if classification is None and llm is not None:
            # LLM fallback for ambiguous emails
            try:
                classification = llm.classify(subject, snippet)
            except Exception:
                logger.warning("gmail connector: LLM classify failed, defaulting to note")
                classification = "note"

        record_type = classification if classification else "note"

        body = _decode_body_part(payload.get("parts"))
        # Truncate body for embedding (first 500 chars)
        body = body[:500] if body else None

        msg_id = msg.get("id", "")

        requests.append(
            IngestRequest(
                source="gmail",
                record_type=record_type,
                user_id=user_id,
                title=subject or "No subject",
                body=body,
                external_id=f"gmail:message:{msg_id}",
            )
        )
    return requests


def _build_gmail_service(settings):
    """Build an authenticated Gmail API service client."""
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build

    creds = Credentials(
        token=None,
        refresh_token=settings.gmail_refresh_token,
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        token_uri="https://oauth2.googleapis.com/token",
    )
    creds.refresh(Request())
    return build("gmail", "v1", credentials=creds)


async def sync(
    db,
    llm,
    embedder,
    settings,
    user_id: UUID,
) -> SyncResult:
    """
    Sync unread Gmail messages for the given user.

    Fetches at most 50 unread messages, classifies each via heuristic
    (with LLM fallback for ambiguous), and ingests through _ingest_one.

    Args:
        db: Supabase AsyncClient (service-role).
        llm: LLMProvider (used for ambiguous classification fallback).
        embedder: EmbeddingProvider.
        settings: Settings instance with Google OAuth credentials.
        user_id: Owner UUID.

    Returns:
        SyncResult with created/skipped/failed counts.
    """
    result = SyncResult()

    try:
        service = _build_gmail_service(settings)
    except Exception as exc:
        result.failed += 1
        result.errors.append(f"Gmail auth failed: {exc}")
        logger.exception("gmail connector: auth error")
        return result

    # List unread messages (max 50)
    try:
        response = service.users().messages().list(
            userId="me",
            q="is:unread",
            maxResults=_MAX_MESSAGES,
        ).execute()
    except Exception as exc:
        result.failed += 1
        result.errors.append(f"Failed to list messages: {exc}")
        logger.exception("gmail connector: list error")
        return result

    message_ids = [m["id"] for m in response.get("messages", [])]

    # Fetch full message details for classification
    raw_messages = []
    for msg_id in message_ids:
        try:
            msg = service.users().messages().get(
                userId="me",
                id=msg_id,
                format="full",
            ).execute()
            raw_messages.append(msg)
        except Exception as exc:
            result.failed += 1
            result.errors.append(f"Failed to fetch message {msg_id}: {exc}")
            logger.warning("gmail connector: failed to fetch %s", msg_id)

    # Map to IngestRequest (with LLM fallback for ambiguous classification)
    reqs = map_messages(raw_messages, user_id, llm=llm)

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
            logger.exception("gmail connector: error on %s", req.external_id)

    # Upsert connector_state
    now_iso = datetime.now(timezone.utc).isoformat()
    try:
        await db.table("connector_state").upsert(
            {
                "user_id": str(user_id),
                "provider": "gmail",
                "state_json": {"last_sync_at": now_iso},
                "updated_at": now_iso,
            },
            on_conflict="user_id,provider",
        ).execute()
    except Exception as exc:
        logger.warning("gmail connector: failed to upsert connector_state: %s", exc)

    logger.info(
        "gmail sync complete: created=%d skipped=%d failed=%d",
        result.created,
        result.skipped,
        result.failed,
    )
    return result
