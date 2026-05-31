"""
GitHub connector — Phase 5.

Polls the GitHub Notifications API and ingests relevant notifications as
tasks (assign/review_requested) or notes (mention/subscribed/other).

Additionally fetches open issues, open pull requests, and the README for
each repo linked to the user's projects, and ingests them as context.

The user's PAT is read from connector_state.state_json["token"] with a
fallback to settings.github_token for backwards compatibility.
"""

from __future__ import annotations

import base64
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx

from app.connectors.base import SyncResult
from app.schemas.ingest import IngestRequest
from app.services.ingest_service import _ingest_one

logger = logging.getLogger(__name__)

_GITHUB_API_BASE = "https://api.github.com"
_GITHUB_NOTIFICATIONS_URL = f"{_GITHUB_API_BASE}/notifications"
_MAX_NOTIFICATIONS = 50
_MAX_PER_PAGE = 50

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


async def _ingest_requests(
    reqs: list[IngestRequest],
    db,
    embedder,
    settings,
    result: SyncResult,
) -> None:
    """Ingest a list of IngestRequests, accumulating results in-place."""
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


async def sync(
    db,
    llm,
    embedder,
    settings,
    user_id: UUID,
) -> SyncResult:
    """
    Sync GitHub data for the given user.

    1. Fetches the user's PAT from connector_state (falls back to settings).
    2. Fetches unread notifications.
    3. For each repo linked to the user's projects, fetches open issues,
       open PRs, and the README.

    Per-repo errors are caught individually and do not abort the batch.

    Args:
        db: Supabase AsyncClient (service-role).
        llm: LLMProvider (unused by GitHub connector; passed for interface consistency).
        embedder: EmbeddingProvider.
        settings: Settings instance with github_token fallback.
        user_id: Owner UUID.

    Returns:
        SyncResult with created/skipped/failed counts.
    """
    result = SyncResult()

    # --- 1. Resolve token --------------------------------------------------
    state_res = await db.table("connector_state").select("state_json").eq(
        "user_id", str(user_id)
    ).eq("provider", "github").execute()
    state_data = state_res.data[0] if state_res.data else None
    token = (
        state_data["state_json"].get("token", "")
        if state_data
        else settings.github_token
    )

    if not token:
        logger.warning(
            "github connector: no token configured for user %s — skipping sync",
            user_id,
        )
        return result

    auth_headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
    }

    # --- 2. Linked repos ---------------------------------------------------
    proj_res = await db.table("projects").select("name, github_repo").eq(
        "user_id", str(user_id)
    ).execute()

    def _normalize_repo(raw: str) -> str:
        raw = raw.strip().rstrip("/")
        if raw.startswith("https://github.com/"):
            raw = raw[len("https://github.com/"):]
        elif raw.startswith("github.com/"):
            raw = raw[len("github.com/"):]
        return raw

    # Map normalized repo slug → ARIA project name so project_hint matches
    # what the fuzzy resolver expects (project name, not the repo slug).
    repo_to_project_name: dict[str, str] = {
        _normalize_repo(p["github_repo"]): p["name"]
        for p in (proj_res.data or [])
        if p.get("github_repo") and p.get("name")
    }
    linked_repos: set[str] = set(repo_to_project_name.keys())

    async with httpx.AsyncClient() as client:
        # --- 3. Notifications ----------------------------------------------
        try:
            notif_resp = await client.get(
                _GITHUB_NOTIFICATIONS_URL,
                params={"per_page": _MAX_NOTIFICATIONS, "all": "false"},
                headers=auth_headers,
            )
            notif_resp.raise_for_status()
            notifications = notif_resp.json()[:_MAX_NOTIFICATIONS]
            notification_reqs = map_notifications(notifications, user_id)
            await _ingest_requests(notification_reqs, db, embedder, settings, result)
        except Exception as exc:
            logger.warning("github connector: failed to fetch notifications: %s", exc)

        # --- 4. Issues, PRs, README per linked repo ------------------------
        for repo in linked_repos:
            project_name = repo_to_project_name.get(repo, repo)

            # Issues
            try:
                issues_resp = await client.get(
                    f"{_GITHUB_API_BASE}/repos/{repo}/issues",
                    params={"state": "open", "per_page": _MAX_PER_PAGE},
                    headers=auth_headers,
                )
                issues_resp.raise_for_status()
                issue_reqs = [
                    IngestRequest(
                        source="github",
                        record_type="task",
                        user_id=user_id,
                        title=issue["title"],
                        body=(issue.get("body") or "")[:2000],
                        external_id=f"github:issue:{repo}:{issue['number']}",
                        project_hint=project_name,
                    )
                    for issue in issues_resp.json()
                ]
                await _ingest_requests(issue_reqs, db, embedder, settings, result)
            except Exception as exc:
                logger.warning(
                    "github connector: failed to fetch issues for %s: %s", repo, exc
                )

            # Pull requests
            try:
                prs_resp = await client.get(
                    f"{_GITHUB_API_BASE}/repos/{repo}/pulls",
                    params={"state": "open", "per_page": _MAX_PER_PAGE},
                    headers=auth_headers,
                )
                prs_resp.raise_for_status()
                pr_reqs = [
                    IngestRequest(
                        source="github",
                        record_type="task",
                        user_id=user_id,
                        title=f"PR: {pr['title']}",
                        body=(pr.get("body") or "")[:2000],
                        external_id=f"github:pr:{repo}:{pr['number']}",
                        project_hint=project_name,
                    )
                    for pr in prs_resp.json()
                ]
                await _ingest_requests(pr_reqs, db, embedder, settings, result)
            except Exception as exc:
                logger.warning(
                    "github connector: failed to fetch PRs for %s: %s", repo, exc
                )

            # README
            try:
                readme_resp = await client.get(
                    f"{_GITHUB_API_BASE}/repos/{repo}/readme",
                    headers=auth_headers,
                )
                if readme_resp.status_code == 404:
                    continue
                readme_resp.raise_for_status()
                readme_data = readme_resp.json()
                raw_content = readme_data.get("content", "")
                decoded = base64.b64decode(raw_content).decode("utf-8", errors="replace")
                readme_req = IngestRequest(
                    source="github",
                    record_type="note",
                    user_id=user_id,
                    title=f"README: {repo}",
                    body=decoded[:4000],
                    external_id=f"github:readme:{repo}",
                    project_hint=project_name,
                )
                await _ingest_requests([readme_req], db, embedder, settings, result)
            except Exception as exc:
                logger.warning(
                    "github connector: failed to fetch README for %s: %s", repo, exc
                )

    # --- 5. Upsert connector_state, preserving token -----------------------
    now_iso = datetime.now(timezone.utc).isoformat()
    current_state = state_data["state_json"] if state_data else {}
    updated_state = {**current_state, "last_sync_at": now_iso}
    try:
        await db.table("connector_state").upsert(
            {
                "user_id": str(user_id),
                "provider": "github",
                "state_json": updated_state,
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
