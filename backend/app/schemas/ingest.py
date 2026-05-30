"""
Ingest endpoint schemas — Phase 4.

IngestRequest: typed payload submitted by connectors or external callers.
IngestResponse: result returned after record creation or dedup.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class IngestRequest(BaseModel):
    source: Literal["github", "gmail", "google_calendar", "manual"]
    record_type: Literal["task", "note", "event", "reminder"]
    user_id: UUID
    title: str
    body: str | None = None               # email/issue/event body — embedded with title
    project_hint: str | None = None
    external_id: str | None = None        # source-prefixed, e.g. "github:notification:99"
    deadline: str | None = None           # ISO 8601
    starts_at: str | None = None          # ISO 8601; required when record_type == "event"
    duration_min: int | None = None
    due_at: str | None = None             # ISO 8601; required when record_type == "reminder"
    tags: list[str] = []
    energy_level: Literal["low", "medium", "high"] = "medium"


class IngestResponse(BaseModel):
    status: Literal["created", "duplicate", "error"]
    record_id: UUID | None = None
    record_type: str | None = None
    detail: str | None = None             # error message or "duplicate" reason
