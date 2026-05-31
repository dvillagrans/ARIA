"""
POST /documents/process

Called by the Next.js API after a file is uploaded to Supabase Storage.
Downloads the file, extracts text, ingests into RAG, marks the document done.
"""

from __future__ import annotations

import io
import logging
from uuid import UUID

from fastapi import APIRouter, Depends
from supabase._async.client import AsyncClient

from app.core.deps import get_async_supabase, get_embedder, get_settings
from app.core.config import Settings
from app.providers.base import EmbeddingProvider
from app.schemas.ingest import IngestRequest
from app.services.ingest_service import _ingest_one

logger = logging.getLogger(__name__)

router = APIRouter()


def _extract_text(content: bytes, mime_type: str | None) -> str:
    if mime_type == "application/pdf":
        try:
            from pypdf import PdfReader  # type: ignore[import-untyped]

            reader = PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            return "\n\n".join(p for p in pages if p.strip())
        except Exception as exc:
            logger.warning("pdf extraction failed: %s", exc)
            return ""
    # plain text / markdown
    return content.decode("utf-8", errors="replace")


@router.post("/documents/process")
async def process_document(
    document_id: UUID,
    user_id: UUID,
    db: AsyncClient = Depends(get_async_supabase),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> dict[str, str]:
    # 1. Fetch document record
    doc_res = await (
        db.table("documents")
        .select("id, name, storage_path, mime_type, project_id")
        .eq("id", str(document_id))
        .eq("user_id", str(user_id))
        .single()
        .execute()
    )
    if not doc_res.data:
        return {"status": "error", "detail": "document not found"}

    doc = doc_res.data

    # Mark as processing
    await (
        db.table("documents")
        .update({"status": "processing"})
        .eq("id", str(document_id))
        .execute()
    )

    # 2. Fetch project name for project_hint
    project_name: str | None = None
    try:
        proj_res = await (
            db.table("projects")
            .select("name")
            .eq("id", doc["project_id"])
            .single()
            .execute()
        )
        project_name = proj_res.data.get("name") if proj_res.data else None
    except Exception:
        pass

    # 3. Download from Storage
    try:
        file_bytes: bytes = await db.storage.from_("project-documents").download(
            doc["storage_path"]
        )
    except Exception as exc:
        logger.error("failed to download document %s: %s", document_id, exc)
        await (
            db.table("documents")
            .update({"status": "error"})
            .eq("id", str(document_id))
            .execute()
        )
        return {"status": "error", "detail": "download failed"}

    # 4. Extract text
    text = _extract_text(file_bytes, doc.get("mime_type"))
    if not text.strip():
        await (
            db.table("documents")
            .update({"status": "error"})
            .eq("id", str(document_id))
            .execute()
        )
        return {"status": "error", "detail": "no text extracted"}

    # 5. Ingest as note
    req = IngestRequest(
        source="document",
        record_type="note",
        user_id=user_id,
        title=doc["name"],
        body=text[:8000],
        external_id=f"document:{document_id}",
        project_hint=project_name,
    )
    try:
        outcome, _ = await _ingest_one(req, db, embedder, settings)
    except Exception as exc:
        logger.error("ingest failed for document %s: %s", document_id, exc)
        await (
            db.table("documents")
            .update({"status": "error"})
            .eq("id", str(document_id))
            .execute()
        )
        return {"status": "error", "detail": "ingest failed"}

    # 6. Mark done
    await (
        db.table("documents")
        .update({"status": "done"})
        .eq("id", str(document_id))
        .execute()
    )

    logger.info(
        "document processed: %s (%s) outcome=%s", doc["name"], document_id, outcome
    )
    return {"status": outcome}
