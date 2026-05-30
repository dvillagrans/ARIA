"""
POST /ingest route — Phase 4.

Replaces the Phase 0 501 stub with a real implementation.

Auth: X-API-Key header validated against settings.ingest_api_key via
      verify_ingest_key dependency (raises 401 on mismatch).

Flow: Validates IngestRequest → calls _ingest_one → returns IngestResponse.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from supabase._async.client import AsyncClient

from app.core.deps import get_async_supabase, get_embedder, get_settings, verify_ingest_key
from app.core.config import Settings
from app.core.metrics import aria_records_created_total
from app.providers.base import EmbeddingProvider
from app.schemas.ingest import IngestRequest, IngestResponse
from app.services.ingest_service import _ingest_one

router = APIRouter()


@router.post("/ingest", response_model=IngestResponse)
async def ingest(
    request: IngestRequest,
    _: None = Depends(verify_ingest_key),
    db: AsyncClient = Depends(get_async_supabase),
    embedder: EmbeddingProvider = Depends(get_embedder),
    settings: Settings = Depends(get_settings),
) -> IngestResponse:
    """
    Ingest a single record from an external source or manual caller.

    Returns:
        IngestResponse with status="created" on new insert,
        status="duplicate" when external_id already exists (with record_id),
        status="error" on unexpected failure.
    """
    status, record_id = await _ingest_one(request, db, embedder, settings)

    if status == "duplicate":
        return IngestResponse(
            status="duplicate",
            record_id=UUID(record_id) if record_id else None,
            record_type=request.record_type,
            detail="Duplicate external_id — record already exists",
        )
    elif status == "created":
        # Increment records_created_total counter.
        if aria_records_created_total is not None:
            aria_records_created_total.labels(
                record_type=request.record_type,
                source="ingest",
            ).inc()
        return IngestResponse(
            status="created",
            record_id=UUID(record_id) if record_id else None,
            record_type=request.record_type,
        )
    else:
        return IngestResponse(
            status="error",
            record_type=request.record_type,
            detail="Internal error during ingest",
        )
