"""
Connector base types — Phase 4.

SyncResult: aggregated outcome of a single connector sync run.
"""

from dataclasses import dataclass, field

from app.core.metrics import aria_connector_errors_total, aria_connector_events_total


@dataclass
class SyncResult:
    """Aggregated result from a connector sync run.

    Attributes:
        created: Number of new records inserted.
        skipped: Number of records skipped due to dedup (external_id already exists).
        failed: Number of records that raised an exception.
        errors: Human-readable error messages, one per failed item.
    """

    created: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list[str] = field(default_factory=list)

    def record_metrics(self, connector_name: str) -> None:
        """
        Increment connector metrics counters for this sync run.

        Increments:
        - connector_events_total{connector=<name>} by 1 (per sync run)
        - connector_errors_total{connector=<name>} by number of failures
        """
        if aria_connector_events_total is not None:
            aria_connector_events_total.labels(connector=connector_name).inc()

        if aria_connector_errors_total is not None and self.failed > 0:
            aria_connector_errors_total.labels(connector=connector_name).inc(self.failed)
