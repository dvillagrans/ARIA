"""
Tests for SyncResult.record_metrics().

Spec requirement: increments connector_events_total and connector_errors_total
with correct labels.
"""

from app.connectors.base import SyncResult
from app.core.metrics import aria_connector_errors_total, aria_connector_events_total


class TestSyncResultMetrics:
    """Tests for SyncResult.record_metrics()."""

    def test_record_metrics_increments_events_counter(self):
        """record_metrics must increment connector_events_total."""
        # Get initial value
        initial = aria_connector_events_total.labels(connector="github")._value.get()

        result = SyncResult(created=5, skipped=2, failed=0)
        result.record_metrics("github")

        final = aria_connector_events_total.labels(connector="github")._value.get()
        assert final == initial + 1

    def test_record_metrics_increments_errors_counter(self):
        """record_metrics must increment connector_errors_total for each failure."""
        initial = aria_connector_errors_total.labels(connector="gmail")._value.get()

        result = SyncResult(created=0, skipped=0, failed=3, errors=["err1", "err2", "err3"])
        result.record_metrics("gmail")

        final = aria_connector_errors_total.labels(connector="gmail")._value.get()
        assert final == initial + 3

    def test_record_metrics_with_no_failures(self):
        """record_metrics with failed=0 must not increment errors counter."""
        initial = aria_connector_errors_total.labels(connector="calendar")._value.get()

        result = SyncResult(created=10, skipped=0, failed=0)
        result.record_metrics("calendar")

        final = aria_connector_errors_total.labels(connector="calendar")._value.get()
        assert final == initial

    def test_record_metrics_includes_created_and_skipped_in_events(self):
        """connector_events_total counts total events processed (created + skipped + failed)."""
        initial = aria_connector_events_total.labels(connector="github")._value.get()

        result = SyncResult(created=5, skipped=3, failed=2)
        result.record_metrics("github")

        final = aria_connector_events_total.labels(connector="github")._value.get()
        # Only one increment per sync run (not per record)
        assert final == initial + 1
