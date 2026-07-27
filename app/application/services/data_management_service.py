"""DataManagementService: safe, audited deletion of collected data by source.

Backs the ``sigint purge`` CLI command so operators never have to run
manual SQL against the database to remove data from a misconfigured or
retired collector. Every call previews its effect via ``dry_run`` by
default -- callers must pass ``dry_run=False`` explicitly to actually
delete anything, and every real deletion is audit logged.

Deliberately scoped to Signal and WeatherEvent only, not Lead: a Lead is
generated from signals across potentially several sources (see
``app.lead_generation.generator.LeadGenerator``), so it has no single
``source`` to purge by. Removing the signals that fed a Lead does not
retroactively delete the Lead itself -- that is a distinct, intentional
design choice, not an oversight.
"""

from __future__ import annotations

from datetime import datetime

from app.application.interfaces.repositories import (
    AuditLogRepository,
    SignalRepository,
    WeatherEventRepository,
)
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


class DataManagementService:
    """Previews and performs source-scoped deletion of Signals and WeatherEvents."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        weather_event_repository: WeatherEventRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._audit_log_repository = audit_log_repository

    def purge_signals(
        self, source: str, *, before: datetime | None = None, dry_run: bool = True
    ) -> int:
        """Delete (or, if ``dry_run``, just count) signals from ``source``.

        Returns the number of signals deleted (or that would be deleted).
        """
        affected = self._signal_repository.delete_by_source(source, before=before, dry_run=dry_run)
        if not dry_run:
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.DATA_PURGED,
                    entity_type="Signal",
                    message=f"Purged {affected} signal(s) from source {source!r}.",
                    context={
                        "source": source,
                        "before": before.isoformat() if before else None,
                        "deleted_count": affected,
                    },
                )
            )
        return affected

    def purge_weather_events(
        self, source: str, *, before: datetime | None = None, dry_run: bool = True
    ) -> int:
        """Delete (or, if ``dry_run``, just count) weather events from ``source``.

        Returns the number of weather events deleted (or that would be deleted).
        """
        affected = self._weather_event_repository.delete_by_source(
            source, before=before, dry_run=dry_run
        )
        if not dry_run:
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.DATA_PURGED,
                    entity_type="WeatherEvent",
                    message=f"Purged {affected} weather event(s) from source {source!r}.",
                    context={
                        "source": source,
                        "before": before.isoformat() if before else None,
                        "deleted_count": affected,
                    },
                )
            )
        return affected
