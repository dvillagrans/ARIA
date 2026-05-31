"""
FastAPI application factory.

Call `create_app()` to obtain a configured FastAPI instance. The module-level
`app` singleton is what uvicorn targets: `uvicorn app.main:app`.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import Response

from app.core import metrics
from app.middleware.metrics import MetricsMiddleware
from app.routes import briefing, chat, connectors, health, ingest, reminders


def create_app() -> FastAPI:
    """
    Construct and configure the FastAPI application.

    Responsibilities:
    - Initialize Prometheus metrics registry.
    - Mount all route groups.
    - Add MetricsMiddleware (before CORS) for auto-instrumentation.
    - Add CORS middleware (permissive for localhost in Phase 0).
    - Expose GET /metrics endpoint for Prometheus scraping.
    """
    # Initialize metrics registry (idempotent).
    metrics.init_metrics()

    application = FastAPI(
        title="ARIA Backend",
        description="Personal AI assistant — provider-agnostic backend.",
        version="0.1.0",
    )

    # Metrics middleware: MUST be added before CORS so it sees every request.
    application.add_middleware(MetricsMiddleware)

    # CORS: allow the Next.js dev server (localhost + Tailscale dev access).
    # Set CORS_ORIGINS env var to override (comma-separated).
    # Tighten origins before any production deployment.
    _default_origins = "http://localhost:3000,http://chi:3000,http://100.124.11.63:3000"
    _cors_origins_raw = os.getenv("CORS_ORIGINS", _default_origins)
    _cors_origins = [o.strip() for o in _cors_origins_raw.split(",") if o.strip()]
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    application.include_router(health.router, tags=["ops"])
    application.include_router(chat.router, tags=["chat"])
    application.include_router(ingest.router, tags=["ingest"])
    application.include_router(briefing.router, tags=["briefing"])
    application.include_router(reminders.router, tags=["reminders"])
    application.include_router(connectors.router, prefix="/connectors", tags=["connectors"])

    # Prometheus metrics endpoint — publicly accessible for scraping.
    # NOTE: CONTENT_TYPE_LATEST from prometheus_client uses version=1.0.0
    # (current library default) rather than the spec's version=0.0.4.
    # This is expected behavior — the library's format is fully compatible
    # with Prometheus scraping and supersedes the older 0.0.4 format.
    @application.get("/metrics", include_in_schema=False)
    async def metrics_endpoint() -> Response:
        return Response(
            generate_latest(metrics.REGISTRY),
            media_type=CONTENT_TYPE_LATEST,
        )

    return application


app = create_app()
