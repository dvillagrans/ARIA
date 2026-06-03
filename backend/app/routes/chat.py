"""
POST /chat — full orchestration route.

Phase 1: classifies the user message, embeds it, resolves the project,
writes the domain record, generates a confirmation, saves conversation
turns, and returns ChatResponse.

Design data-flow: spec §2 + design data-flow diagram.
ADR-01: AsyncClient per-request via Depends.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.core.deps import get_async_supabase, get_embedder, get_llm
from app.core.metrics import (
    aria_chat_latency_seconds,
    aria_context_note_updates_total,
    aria_records_created_total,
)
from app.providers.base import EmbeddingProvider, LLMProvider
from app.providers.qwen import EmbeddingError
from app.schemas.chat import ChatRequest, ChatResponse
from app.schemas.classifier import CaptureIntent, ContextNoteIntent, ConversationIntent, CorrectionIntent, QueryIntent, StudyIntent, WebSearchIntent
from app.services import (
    briefing_service,
    calendar_sync,
    classifier_service,
    context_note_service,
    conversation_service,
    pdf_service,
    project_resolver,
    rag_service,
    record_writer,
    study_service,
    web_search_service,
)
from app.services.classifier_service import ClassifierError

logger = logging.getLogger(__name__)

router = APIRouter()


def _turns(
    request: ChatRequest,
    *,
    assistant_content: str,
    metadata: dict,
) -> tuple[dict, dict]:
    """Build user + assistant conversation turn dicts, optionally tagging project_id."""
    base: dict = {"user_id": str(request.user_id)}
    if request.project_id:
        base["project_id"] = str(request.project_id)
    user_turn = {**base, "role": "user", "content": request.message, "metadata": {}}
    assistant_turn = {**base, "role": "assistant", "content": assistant_content, "metadata": metadata}
    return user_turn, assistant_turn


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    llm: LLMProvider = Depends(get_llm),
    embedder: EmbeddingProvider = Depends(get_embedder),
    db=Depends(get_async_supabase),
    settings: Settings = Depends(get_settings),
) -> ChatResponse:
    """
    Main chat endpoint.

    Orchestrates: classify + embed → project_resolve → record_write →
    reason → save turns → return ChatResponse.
    """
    if aria_chat_latency_seconds is not None:
        with aria_chat_latency_seconds.time():
            return await _chat_impl(request, llm, embedder, db, settings)
    return await _chat_impl(request, llm, embedder, db, settings)


async def _chat_impl(
    request: ChatRequest,
    llm: LLMProvider,
    embedder: EmbeddingProvider,
    db,
    settings: Settings,
) -> ChatResponse:
    """Internal chat implementation (called with or without timing)."""
    now = datetime.now(tz=timezone.utc).isoformat()

    # Fetch user timezone for relative time calculations.
    user_tz = "UTC"
    try:
        user_resp = await db.table("users").select("timezone").eq(
            "id", str(request.user_id)
        ).single().execute()
        if user_resp.data and user_resp.data.get("timezone"):
            user_tz = user_resp.data["timezone"]
    except Exception as exc:
        logger.warning("chat: user timezone fetch failed (using UTC): %s", exc)

    # Fetch active projects for this user.
    try:
        projects_resp = await db.table("projects").select("id, name").eq(
            "user_id", str(request.user_id)
        ).eq("is_active", True).execute()
        projects: list[dict] = projects_resp.data or []
    except Exception as exc:
        logger.error("chat: projects fetch failed: %s", exc)
        raise HTTPException(status_code=500, detail="Database unavailable")

    # Fetch recent conversation history (project-scoped or general).
    try:
        history = await conversation_service.get_history(
            request.user_id, db, limit=10, project_id=request.project_id
        )
    except Exception as exc:
        logger.warning("chat: history fetch failed (using empty): %s", exc)
        history = []

    # Parallel classify + embed.
    classify_coro = classifier_service.classify(
        request.message,
        projects,
        llm,
        current_datetime=now,
        timezone=user_tz,
    )
    embed_coro = embedder.embed(request.message)

    results = await asyncio.gather(classify_coro, embed_coro, return_exceptions=True)
    classifier_result, embed_result = results

    # Classify failure is fatal.
    if isinstance(classifier_result, Exception):
        logger.error("chat: classify failed: %s", classifier_result)
        raise HTTPException(status_code=500, detail="Classification failed")

    # Embed failure is non-fatal — graceful degradation.
    embedding: list[float] | None = None
    if isinstance(embed_result, Exception):
        logger.warning("chat: embed failed (graceful degradation): %s", embed_result)
    else:
        embedding = embed_result

    intent_obj = classifier_result

    # Log classifier output for debugging.
    logger.info(
        "chat: classified intent=%s for user=%s",
        getattr(intent_obj, "intent", "unknown"),
        request.user_id,
    )
    if hasattr(intent_obj, "source_urls"):
        logger.info("chat: study source_urls=%s", intent_obj.source_urls)
    if hasattr(intent_obj, "source_text") and intent_obj.source_text:
        logger.info("chat: study source_text_len=%d", len(intent_obj.source_text))

    # --- CAPTURE intent ---
    if isinstance(intent_obj, CaptureIntent):
        # If the request already carries a project_id (project-scoped chat), use it
        # directly and skip the fuzzy resolver entirely.
        if request.project_id:
            project_id: UUID | None = request.project_id
        else:
            project = await project_resolver.resolve(intent_obj.project_hint, projects)
            project_id = UUID(project["id"]) if project else None

        if project_id is None:
            logger.error("chat: no project resolved for user %s", request.user_id)
            raise HTTPException(status_code=500, detail="No project available")

        try:
            table_name, record_id, record_title = await record_writer.write(
                intent_obj, embedding, request.user_id, project_id, db
            )
        except Exception as exc:
            logger.error("chat: record_writer.write() failed: %s", exc)
            raise HTTPException(status_code=500, detail="Failed to save record")

        # Increment records_created_total counter.
        if aria_records_created_total is not None:
            aria_records_created_total.labels(
                record_type=intent_obj.record_type,
                source="manual",
            ).inc()

        # Invalidate today's briefing so next open regenerates with the new task.
        # ADR-4: synchronous await (not fire-and-forget); non-fatal on error.
        try:
            await briefing_service.invalidate(request.user_id, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: briefing invalidate failed (non-fatal): %s", exc)

        # Sync reminders to Google Calendar.
        if intent_obj.record_type == "reminder" and intent_obj.due_at:
            try:
                cal_id = await calendar_sync.sync_reminder_to_calendar(
                    reminder_id=str(record_id),
                    title=record_title,
                    due_at_iso=intent_obj.due_at,
                    calendar_event_id=None,
                    settings=settings,
                )
                if cal_id:
                    await (
                        db.table("reminders")
                        .update({"calendar_event_id": cal_id})
                        .eq("id", str(record_id))
                        .execute()
                    )
            except Exception as exc:  # noqa: BLE001
                logger.warning("chat: calendar sync failed (non-fatal): %s", exc)

        # Generate short confirmation.
        try:
            confirm_prompt = (
                f"Confirm you captured a {intent_obj.record_type} "
                f"titled '{record_title}' for the user."
            )
            confirmation_text = await llm.reason(confirm_prompt)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: reason() failed: %s", exc)
            confirmation_text = f"Captured: {record_title}"

        metadata = {
            "created_record": {
                "table": table_name,
                "id": str(record_id),
                "title": record_title,
            },
            "intent": "capture",
            "classifier_raw": intent_obj.classifier_raw,
        }

        user_turn, assistant_turn = _turns(request, assistant_content=confirmation_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="capture",
            record_type=intent_obj.record_type,
            record_id=record_id,
            confirmation_text=confirmation_text,
            metadata=metadata,
        )

    # --- CORRECTION intent ---
    elif isinstance(intent_obj, CorrectionIntent):
        prior_turn = await conversation_service.get_last_assistant_turn(
            request.user_id, db
        )
        if prior_turn is None:
            raise HTTPException(
                status_code=422,
                detail="No previous record to correct.",
            )

        prior_meta = prior_turn.get("metadata", {})
        created = prior_meta.get("created_record")
        if not created:
            raise HTTPException(
                status_code=422,
                detail="Previous assistant turn has no record to correct.",
            )

        old_table = created["table"]
        old_id = created["id"]
        new_type = intent_obj.new_type or created.get("table", "tasks").rstrip("s")
        new_table = {
            "task": "tasks",
            "event": "events",
            "reminder": "reminders",
            "note": "notes",
        }.get(new_type, "tasks")

        # Build payload from prior classifier_raw.
        payload = dict(prior_meta.get("classifier_raw", {}))
        payload["user_id"] = str(request.user_id)
        payload.pop("id", None)  # remove old id if present

        new_record_id_resp = await db.rpc(
            "correct_record",
            {
                "old_table": old_table,
                "old_id": old_id,
                "new_table": new_table,
                "payload": payload,
            },
        ).execute()
        new_record_id = UUID(new_record_id_resp.data)

        try:
            confirmation_text = await llm.reason(
                f"Confirm you corrected the record from {old_table} to {new_table}."
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: reason() failed: %s", exc)
            confirmation_text = f"Corrected: moved record to {new_table}"

        metadata = {
            "created_record": {
                "table": new_table,
                "id": str(new_record_id),
                "title": created.get("title", ""),
            },
            "correction_of": prior_turn["id"],
            "intent": "correction",
            "classifier_raw": intent_obj.classifier_raw,
        }

        user_turn, assistant_turn = _turns(request, assistant_content=confirmation_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="correction",
            record_type=new_type if new_type in ("task", "event", "reminder", "note") else None,  # type: ignore[arg-type]
            record_id=new_record_id,
            confirmation_text=confirmation_text,
            metadata=metadata,
        )

    # --- QUERY intent — RAG answer ---
    elif isinstance(intent_obj, QueryIntent):
        try:
            answer_text, passages = await rag_service.answer(
                request.user_id, request.message, db, llm, embedder, settings, history
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: rag_service.answer() failed: %s", exc)
            answer_text = "I could not retrieve an answer right now."
            passages = []

        metadata = {
            "intent": "query",
            "passages": [
                {
                    "source_table": p.source_table,
                    "id": str(p.id),
                    "project": p.project_name,
                }
                for p in passages
            ],
            "classifier_raw": intent_obj.classifier_raw,
        }

        user_turn, assistant_turn = _turns(request, assistant_content=answer_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="query",
            record_type=None,
            record_id=None,
            confirmation_text=answer_text,
            metadata=metadata,
        )

    # --- CONTEXT NOTE intent — fuzzy task lookup + LLM update ---
    elif isinstance(intent_obj, ContextNoteIntent):
        task = await context_note_service.search_task(
            request.user_id, intent_obj.task_reference, db
        )

        if task is None:
            confirmation_text = (
                f"No encontré ninguna tarea llamada '{intent_obj.task_reference}'."
            )
            metadata = {
                "intent": "context_note_update",
                "task_found": False,
                "classifier_raw": intent_obj.classifier_raw,
            }
        else:
            try:
                new_note = await context_note_service.update_context_note(
                    task, intent_obj.update_text, db, llm
                )
                # Increment context_note_updates_total on successful update.
                if aria_context_note_updates_total is not None:
                    aria_context_note_updates_total.inc()
                confirmation_text = f"Actualicé el contexto de '{task['title']}'."
                metadata = {
                    "intent": "context_note_update",
                    "task_id": str(task["id"]),
                    "task_found": True,
                    "classifier_raw": intent_obj.classifier_raw,
                }
            except Exception as exc:  # noqa: BLE001
                logger.warning("chat: update_context_note() failed: %s", exc)
                confirmation_text = "No pude actualizar el contexto de la tarea."
                metadata = {
                    "intent": "context_note_update",
                    "task_found": True,
                    "error": str(exc),
                    "classifier_raw": intent_obj.classifier_raw,
                }

        user_turn, assistant_turn = _turns(request, assistant_content=confirmation_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="context_note_update",
            record_type=None,
            record_id=None,
            confirmation_text=confirmation_text,
            metadata=metadata,
        )

    # --- CONVERSATION intent — casual/trivial, no record, no vectorize ---
    elif isinstance(intent_obj, ConversationIntent):
        try:
            reply_text = await llm.reason(
                "The user sent a casual message. Respond briefly and naturally "
                f"in the same language. User message: {request.message}",
                history=history,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation reason() failed: %s", exc)
            reply_text = "¡Hola! ¿En qué te puedo ayudar?"

        metadata = {
            "intent": "conversation",
            "classifier_raw": intent_obj.classifier_raw,
        }
        user_turn, assistant_turn = _turns(request, assistant_content=reply_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="conversation",
            record_type=None,
            record_id=None,
            confirmation_text=reply_text,
            metadata=metadata,
        )

    # --- WEB SEARCH intent — external knowledge retrieval ---
    elif isinstance(intent_obj, WebSearchIntent):
        try:
            search_results = await web_search_service.search(
                intent_obj.query_text, settings, max_results=intent_obj.max_results
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: web_search_service.search() failed: %s", exc)
            search_results = []

        # Build context from search results for the reasoner.
        context_texts: list[str] = []
        for r in search_results:
            context_texts.append(f"Source: {r['title']} ({r['url']}): {r['snippet']}")

        try:
            answer_text = await llm.reason(
                f"Answer based on these web search results:\n\n"
                + "\n".join(context_texts)
                + f"\n\nUser question: {intent_obj.query_text}",
                history=history,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: web search reason() failed: %s", exc)
            if search_results:
                answer_text = "Here are the search results I found:\n" + "\n".join(
                    f"- {r['title']}: {r['snippet']}" for r in search_results
                )
            else:
                answer_text = "I couldn't search the web right now."

        metadata = {
            "intent": "web_search",
            "search_results": [
                {"title": r["title"], "url": r["url"], "snippet": r["snippet"][:200]}
                for r in search_results
            ],
            "classifier_raw": intent_obj.classifier_raw,
        }

        user_turn, assistant_turn = _turns(request, assistant_content=answer_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="web_search",
            record_type=None,
            record_id=None,
            confirmation_text=answer_text,
            metadata=metadata,
        )

    # --- STUDY intent — structured study assistance ---
    elif isinstance(intent_obj, StudyIntent):
        source_text = intent_obj.source_text or ""

        # If source_urls provided, download and extract text from each.
        if intent_obj.source_urls and not source_text:
            extracted_parts = []
            for url in intent_obj.source_urls:
                try:
                    text = await pdf_service.download_and_extract(url)
                    if text:
                        extracted_parts.append(f"--- Source: {url} ---\n{text}")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("chat: pdf_service.download_and_extract() failed for %s: %s", url, exc)

            if extracted_parts:
                source_text = "\n\n".join(extracted_parts)

        if not source_text:
            answer_text = (
                "I need source content to study from. "
                "Please provide text or PDF URLs."
            )
        else:
            try:
                answer_text = await study_service.generate(
                    mode=intent_obj.mode,
                    source_text=source_text,
                    llm=llm,
                    history=history,
                )
            except Exception as exc:  # noqa: BLE001
                logger.warning("chat: study_service.generate() failed: %s", exc)
                answer_text = f"Study mode '{intent_obj.mode}' encountered an error."

        metadata = {
            "intent": "study",
            "mode": intent_obj.mode,
            "source_urls": intent_obj.source_urls,
            "classifier_raw": intent_obj.classifier_raw,
        }

        user_turn, assistant_turn = _turns(request, assistant_content=answer_text, metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent="study",
            record_type=None,
            record_id=None,
            confirmation_text=answer_text,
            metadata=metadata,
        )

    # --- Fallback (should not be reached for any classified intent) ---
    else:
        logger.warning(
            "chat: unhandled intent type %s for user %s",
            type(intent_obj).__name__,
            request.user_id,
        )
        metadata = {
            "intent": getattr(intent_obj, "intent", "unknown"),
            "classifier_raw": getattr(intent_obj, "classifier_raw", {}),
        }
        user_turn, assistant_turn = _turns(request, assistant_content="Got it.", metadata=metadata)
        try:
            await conversation_service.save(user_turn, assistant_turn, db)
        except Exception as exc:  # noqa: BLE001
            logger.warning("chat: conversation_service.save() failed (non-fatal): %s", exc)

        return ChatResponse(
            status="ok",
            intent=getattr(intent_obj, "intent", "unknown"),  # type: ignore[arg-type]
            record_type=None,
            record_id=None,
            confirmation_text="Got it.",
            metadata=metadata,
        )
