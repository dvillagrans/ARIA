from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.core import metrics

router = APIRouter()

APP_VERSION = "0.1.0"


@router.get("/health")
async def health_check():
    """
    Health probe endpoint.

    Returns 200 with service identification and metrics readiness.
    Returns 503 when metrics registry is unavailable.
    Used by load balancers, compose healthchecks, and CI smoke tests.
    """
    metrics_ready = metrics._initialized and metrics.REGISTRY is not None

    if not metrics_ready:
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "metrics": "unavailable",
                "version": APP_VERSION,
            },
        )

    return {
        "status": "ok",
        "metrics": "ready",
        "version": APP_VERSION,
    }
