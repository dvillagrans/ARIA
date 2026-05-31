"""
Chat request/response schemas.

Spec §2: ChatRequest requires message + user_id (both fields mandatory).
ADR-05: user_id is injected by the Next.js API route server-side; the browser
never sends user_id directly. FastAPI trusts it as-is in Phase 1.
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, UUID4


class ChatRequest(BaseModel):
    message: str
    user_id: UUID4
    project_id: UUID4 | None = None


class ChatResponse(BaseModel):
    status: Literal["ok", "error"]
    intent: Literal["capture", "correction", "context_note_update", "query", "conversation"]
    record_type: Literal["task", "event", "reminder", "note"] | None = None
    record_id: UUID | None = None
    confirmation_text: str
    metadata: dict  # mirrors conversations row metadata for the assistant turn
