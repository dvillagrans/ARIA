"""
Central Prometheus metrics registry for ARIA.

All 10+ PRD §10 metrics are defined here as module-level instances.
Call init_metrics() once at app startup to register with the global registry.
The init function is idempotent — safe to call multiple times.
"""

from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# Single shared registry for all ARIA metrics.
REGISTRY = CollectorRegistry()

# Sentinel to track whether init_metrics() has already run.
_initialized = False


# ---------------------------------------------------------------------------
# HTTP metrics (auto-instrumented by MetricsMiddleware)
# ---------------------------------------------------------------------------

aria_http_request_duration_seconds: Histogram | None = None
aria_http_requests_total: Counter | None = None

# ---------------------------------------------------------------------------
# Chat hot-path metrics (manual instrumentation)
# ---------------------------------------------------------------------------

aria_chat_latency_seconds: Histogram | None = None
aria_classification_latency_seconds: Histogram | None = None
aria_embedding_latency_seconds: Histogram | None = None
aria_rag_latency_seconds: Histogram | None = None

# ---------------------------------------------------------------------------
# Counter metrics
# ---------------------------------------------------------------------------

aria_records_created_total: Counter | None = None
aria_briefing_cache_hits_total: Counter | None = None
aria_briefing_latency_seconds: Histogram | None = None
aria_context_note_updates_total: Counter | None = None

# ---------------------------------------------------------------------------
# Connector metrics
# ---------------------------------------------------------------------------

aria_connector_events_total: Counter | None = None
aria_connector_errors_total: Counter | None = None

# ---------------------------------------------------------------------------
# Offline queue gauge (deferred to Phase 6 — always 0 for now)
# ---------------------------------------------------------------------------

aria_offline_queue_depth: Gauge | None = None


def init_metrics() -> None:
    """
    Register all metrics with the global REGISTRY.

    Idempotent: safe to call multiple times without DuplicateRegistrationError.
    """
    global _initialized, aria_http_request_duration_seconds, aria_http_requests_total
    global aria_chat_latency_seconds, aria_classification_latency_seconds
    global aria_embedding_latency_seconds, aria_rag_latency_seconds
    global aria_records_created_total, aria_briefing_cache_hits_total
    global aria_briefing_latency_seconds, aria_context_note_updates_total
    global aria_connector_events_total, aria_connector_errors_total
    global aria_offline_queue_depth

    if _initialized:
        return

    # HTTP middleware metrics
    aria_http_request_duration_seconds = Histogram(
        "aria_http_request_duration_seconds",
        "HTTP request duration in seconds",
        ["method", "endpoint", "status"],
        registry=REGISTRY,
    )
    aria_http_requests_total = Counter(
        "aria_http_requests_total",
        "Total HTTP requests",
        ["method", "endpoint", "status"],
        registry=REGISTRY,
    )

    # Chat hot-path metrics
    aria_chat_latency_seconds = Histogram(
        "aria_chat_latency_seconds",
        "Full /chat endpoint latency",
        registry=REGISTRY,
    )
    aria_classification_latency_seconds = Histogram(
        "aria_classification_latency_seconds",
        "LLM classification latency",
        ["model"],
        registry=REGISTRY,
    )
    aria_embedding_latency_seconds = Histogram(
        "aria_embedding_latency_seconds",
        "Embedding API latency",
        ["model"],
        registry=REGISTRY,
    )
    aria_rag_latency_seconds = Histogram(
        "aria_rag_latency_seconds",
        "Full RAG pipeline latency (retrieve + reason)",
        ["model"],
        registry=REGISTRY,
    )

    # Counter metrics
    aria_records_created_total = Counter(
        "aria_records_created_total",
        "Records created via chat or ingest",
        ["record_type", "source"],
        registry=REGISTRY,
    )
    aria_briefing_cache_hits_total = Counter(
        "aria_briefing_cache_hits_total",
        "Briefing cache hits",
        ["result"],
        registry=REGISTRY,
    )
    aria_briefing_latency_seconds = Histogram(
        "aria_briefing_latency_seconds",
        "Briefing generation latency",
        registry=REGISTRY,
    )
    aria_context_note_updates_total = Counter(
        "aria_context_note_updates_total",
        "Context note updates",
        registry=REGISTRY,
    )

    # Connector metrics
    aria_connector_events_total = Counter(
        "aria_connector_events_total",
        "Events processed by connector",
        ["connector"],
        registry=REGISTRY,
    )
    aria_connector_errors_total = Counter(
        "aria_connector_errors_total",
        "Errors per connector",
        ["connector"],
        registry=REGISTRY,
    )

    # Offline queue gauge (Phase 6 deferred — always 0)
    aria_offline_queue_depth = Gauge(
        "aria_offline_queue_depth",
        "Pending offline captures in IndexedDB (deferred to Phase 6)",
        registry=REGISTRY,
    )
    aria_offline_queue_depth.set(0)

    _initialized = True


# Auto-initialize on import so metrics are always available.
init_metrics()
