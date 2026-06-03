"""
Classifier output schemas — Pydantic v2 discriminated union on intent field.

ADR-04: ClassifierOutput is resolved via Pydantic discriminated union on the
'intent' literal field. Providers return dict; classifier_service wraps it here.
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field


class CaptureIntent(BaseModel):
    intent: Literal["capture"]
    record_type: Literal["task", "event", "reminder", "note"]
    title: str
    project_hint: str | None = None
    energy_level: Literal["low", "medium", "high"] = "medium"
    # Type-specific optional fields
    deadline: str | None = None         # tasks / reminders
    starts_at: str | None = None        # events
    duration_min: int | None = None     # events
    due_at: str | None = None           # reminders
    amount: float | None = None         # reminders
    currency: str | None = None         # reminders
    tags: list[str] = []                # notes
    classifier_raw: dict = {}


class CorrectionIntent(BaseModel):
    intent: Literal["correction"]
    new_type: Literal["task", "event", "reminder", "note"] | None = None
    new_project_hint: str | None = None
    classifier_raw: dict = {}


class ContextNoteIntent(BaseModel):
    intent: Literal["context_note_update"]
    task_reference: str
    update_text: str
    classifier_raw: dict = {}


class QueryIntent(BaseModel):
    intent: Literal["query"]
    query_text: str
    classifier_raw: dict = {}


class ConversationIntent(BaseModel):
    """Casual / trivial message — no record created, no RAG query."""
    intent: Literal["conversation"]
    classifier_raw: dict = {}


class WebSearchIntent(BaseModel):
    """User wants to search the web for current/external information."""
    intent: Literal["web_search"]
    query_text: str
    max_results: int = 5
    classifier_raw: dict = {}


class StudyIntent(BaseModel):
    """User wants structured study assistance (summarize, quiz, explain, flashcards)."""
    intent: Literal["study"]
    mode: Literal["summarize", "quiz", "explain", "flashcards"]
    source_text: str | None = None
    source_url: str | None = None
    classifier_raw: dict = {}


ClassifierOutput = Annotated[
    Union[
        CaptureIntent,
        CorrectionIntent,
        ContextNoteIntent,
        QueryIntent,
        ConversationIntent,
        WebSearchIntent,
        StudyIntent,
    ],
    Field(discriminator="intent"),
]
