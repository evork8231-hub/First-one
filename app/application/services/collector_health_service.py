"""CollectorHealthService: read-only collector run health derived from the audit log.

Backs the ``sigint health`` CLI command. Every field reported here comes
directly from ``COLLECTOR_RUN_COMPLETED`` / ``COLLECTOR_RUN_FAILED`` audit
entries already written by ``SignalService``/``WeatherEventService`` --
this service performs no collection itself and invents nothing: a
collector with no audit history simply has no report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.application.interfaces.repositories import AuditLogRepository
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


@dataclass(frozen=True)
class CollectorHealthReport:
    """The most recent known health of a single collector, by name."""

    collector_name: str
    last_status: str
    last_run_at: datetime
    last_duration_seconds: float | None
    last_item_count: int | None
    consecutive_failures: int
    last_error: str | None


class CollectorHealthService:
    """Aggregates collector run history from the audit log into per-collector reports."""

    def __init__(self, audit_log_repository: AuditLogRepository) -> None:
        self._audit_log_repository = audit_log_repository

    def get_health(self, *, sample_limit: int = 500) -> list[CollectorHealthReport]:
        """Return one report per collector with at least one COMPLETED/FAILED run.

        ``sample_limit`` bounds how many of the most recent entries of each
        event type are scanned per call, so this stays cheap even on a
        long-lived audit log; a collector whose last run falls outside the
        sample is simply omitted rather than misreported.
        """
        completed = self._audit_log_repository.list_all(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=sample_limit
        )
        failed = self._audit_log_repository.list_all(
            event_type=AuditEventType.COLLECTOR_RUN_FAILED, limit=sample_limit
        )

        by_collector: dict[str, list[tuple[AuditLogEntry, bool]]] = {}
        for entry in completed:
            name = entry.context.get("collector")
            if name:
                by_collector.setdefault(name, []).append((entry, True))
        for entry in failed:
            name = entry.context.get("collector")
            if name:
                by_collector.setdefault(name, []).append((entry, False))

        reports = []
        for name, runs in by_collector.items():
            runs.sort(key=lambda pair: pair[0].created_at, reverse=True)
            latest_entry, latest_succeeded = runs[0]

            consecutive_failures = 0
            for _entry, succeeded in runs:
                if succeeded:
                    break
                consecutive_failures += 1

            reports.append(
                CollectorHealthReport(
                    collector_name=name,
                    last_status="succeeded" if latest_succeeded else "failed",
                    last_run_at=latest_entry.created_at,
                    last_duration_seconds=latest_entry.context.get("duration_seconds"),
                    last_item_count=(
                        latest_entry.context.get("signal_count")
                        if "signal_count" in latest_entry.context
                        else latest_entry.context.get("event_count")
                    ),
                    consecutive_failures=consecutive_failures,
                    last_error=None if latest_succeeded else latest_entry.message,
                )
            )

        reports.sort(key=lambda report: report.collector_name)
        return reports
