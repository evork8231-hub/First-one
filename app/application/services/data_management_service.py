"""DataManagementService: safe, audited deletion of collected data by source.

Backs the ``sigint purge`` CLI command so operators never have to run
manual SQL against the database to remove data from a misconfigured or
retired collector. Every call previews its effect via ``dry_run`` by
default -- callers must pass ``dry_run=False`` explicitly to actually
delete anything, and every real deletion is audit logged.

Deliberately scoped to Signal and WeatherEvent only, not Lead: a Lead is
generated from signals across potentially several sources (see
``app.lead_generation.generator.LeadGenerator``), so it has no single
``source`` to purge by.

``purge_signals`` refuses the whole operation -- deleting nothing -- if
any signal it would delete is still cited by an existing Lead's
``supporting_signal_ids``, mirroring the same check
``app.application.services.rollback_service.RollbackService`` makes
before a rollback. Earlier, purge had no such check while rollback did;
that inconsistency between two similar destructive operations is exactly
what this guards against now -- see
``app.core.exceptions.PurgeBlockedByDependentDataError``. WeatherEvents
are never cited by a Lead directly (only the WEATHER_EVENT Signal a
weather event is bridged into can be), so ``purge_weather_events`` has no
analogous check to make.
"""

from __future__ import annotations

from datetime import datetime

from app.application.interfaces.repositories import (
    AuditLogRepository,
    LeadRepository,
    SignalRepository,
    WeatherEventRepository,
)
from app.core.exceptions import PurgeBlockedByDependentDataError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


class DataManagementService:
    """Previews and performs source-scoped deletion of Signals and WeatherEvents."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        weather_event_repository: WeatherEventRepository,
        lead_repository: LeadRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._lead_repository = lead_repository
        self._audit_log_repository = audit_log_repository

    def purge_signals(
        self, source: str, *, before: datetime | None = None, dry_run: bool = True
    ) -> int:
        """Delete (or, if ``dry_run``, just count) signals from ``source``.

        Returns the number of signals deleted (or that would be deleted).

        Raises:
            PurgeBlockedByDependentDataError: Any signal that would be
                deleted is still cited by an existing Lead's
                ``supporting_signal_ids`` -- checked (and can raise) even
                when ``dry_run`` is ``True``, so a preview accurately
                reports that the real run would fail rather than silently
                claiming success.
        """
        candidate_ids = self._signal_repository.list_ids_by_source(source, before=before)
        if candidate_ids:
            blocking_leads = self._lead_repository.list_referencing_signal_ids(candidate_ids)
            if blocking_leads:
                raise PurgeBlockedByDependentDataError(
                    f"Cannot purge signals from {source!r}: {len(blocking_leads)} lead(s) "
                    f"still reference {len(candidate_ids)} candidate signal(s). Resolve or "
                    f"reject those leads before purging."
                )

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
