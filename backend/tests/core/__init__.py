"""
Tests for the central metrics registry.

Spec requirement: all 10 PRD metrics exist with correct names, types, and labels
after init_metrics() is called.
"""

import pytest
from prometheus_client import Counter, Gauge, Histogram

from app.core.metrics import (
    REGISTRY,
    init_metrics,
    aria_briefing_cache_hits_total,
    aria_briefing_latency_seconds,
    aria_chat_latency_seconds,
    aria_classification_latency_seconds,
    aria_connector_errors_total,
    aria_connector_events_total,
    aria_context_note_updates_total,
    aria_embedding_latency_seconds,
    aria_http_request_duration_seconds,
    aria_http_requests_total,
    aria_rag_latency_seconds,
    aria_records_created_total,
)


class TestMetricRegistry:
    """Tests for metric definitions and registry initialization."""

    def test_init_metrics_is_idempotent(self):
        """Calling init_metrics() twice must not raise DuplicateRegistrationError."""
        init_metrics()
        init_metrics()  # Should not raise

    def test_registry_is_collector_registry(self):
        """REGISTRY must be a CollectorRegistry instance."""
        from prometheus_client import CollectorRegistry

        assert isinstance(REGISTRY, CollectorRegistry)

    # --- HTTP middleware metrics ---

    def test_http_request_duration_is_histogram(self):
        assert isinstance(aria_http_request_duration_seconds, Histogram)
        assert aria_http_request_duration_seconds._name == "aria_http_request_duration_seconds"
        assert set(aria_http_request_duration_seconds._labelnames) == {"method", "endpoint", "status"}

    def test_http_requests_total_is_counter(self):
        assert isinstance(aria_http_requests_total, Counter)
        assert aria_http_requests_total._name == "aria_http_requests_total"
        assert set(aria_http_requests_total._labelnames) == {"method", "endpoint", "status"}

    # --- Chat hot-path metrics ---

    def test_chat_latency_is_histogram(self):
        assert isinstance(aria_chat_latency_seconds, Histogram)
        assert aria_chat_latency_seconds._name == "aria_chat_latency_seconds"

    def test_classification_latency_is_histogram(self):
        assert isinstance(aria_classification_latency_seconds, Histogram)
        assert aria_classification_latency_seconds._name == "aria_classification_latency_seconds"
        assert set(aria_classification_latency_seconds._labelnames) == {"model"}

    def test_embedding_latency_is_histogram(self):
        assert isinstance(aria_embedding_latency_seconds, Histogram)
        assert aria_embedding_latency_seconds._name == "aria_embedding_latency_seconds"
        assert set(aria_embedding_latency_seconds._labelnames) == {"model"}

    def test_rag_latency_is_histogram(self):
        assert isinstance(aria_rag_latency_seconds, Histogram)
        assert aria_rag_latency_seconds._name == "aria_rag_latency_seconds"
        assert set(aria_rag_latency_seconds._labelnames) == {"model"}

    # --- Counter metrics ---

    def test_records_created_total_is_counter(self):
        assert isinstance(aria_records_created_total, Counter)
        assert aria_records_created_total._name == "aria_records_created_total"
        assert set(aria_records_created_total._labelnames) == {"record_type", "source"}

    def test_briefing_cache_hits_total_is_counter(self):
        assert isinstance(aria_briefing_cache_hits_total, Counter)
        assert aria_briefing_cache_hits_total._name == "aria_briefing_cache_hits_total"
        assert set(aria_briefing_cache_hits_total._labelnames) == {"state"}

    def test_briefing_latency_is_histogram(self):
        assert isinstance(aria_briefing_latency_seconds, Histogram)
        assert aria_briefing_latency_seconds._name == "aria_briefing_latency_seconds"

    def test_context_note_updates_total_is_counter(self):
        assert isinstance(aria_context_note_updates_total, Counter)
        assert aria_context_note_updates_total._name == "aria_context_note_updates_total"

    # --- Connector metrics ---

    def test_connector_events_total_is_counter(self):
        assert isinstance(aria_connector_events_total, Counter)
        assert aria_connector_events_total._name == "aria_connector_events_total"
        assert set(aria_connector_events_total._labelnames) == {"connector"}

    def test_connector_errors_total_is_counter(self):
        assert isinstance(aria_connector_errors_total, Counter)
        assert aria_connector_errors_total._name == "aria_connector_errors_total"
        assert set(aria_connector_errors_total._labelnames) == {"connector"}

    # --- Offline queue gauge (deferred to Phase 6) ---

    def test_offline_queue_depth_is_gauge(self):
        """Gauge exists but returns 0 until Phase 6."""
        from app.core.metrics import aria_offline_queue_depth

        assert isinstance(aria_offline_queue_depth, Gauge)
        assert aria_offline_queue_depth._name == "aria_offline_queue_depth"
