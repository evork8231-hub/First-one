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

Deleting the matched records and writing the ``DATA_PURGED`` audit entry
is delegated to ``PurgeUnitOfWork`` as one atomic operation -- mirroring
``RollbackService``'s use of ``RollbackUnitOfWork`` and
``WeatherSignalBridgeService``'s use of ``WeatherBridgeUnitOfWork``, this
service only reads (``list_ids_by_source``, for both the candidate-id
lookup and the Lead-dependency check) and builds *what* to persist; the
unit of work handles the actual delete-and-audit write atomically, so a
crash between deleting the data and recording that it was deleted can no
longer happen -- either both commit, or neither does.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from app.application.interfaces.purge_unit_of_work import PurgeUnitOfWork
from app.application.interfaces.repositories import (
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
        purge_unit_of_work: PurgeUnitOfWork,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._lead_repository = lead_repository
        self._purge_unit_of_work = purge_unit_of_work

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

        if dry_run:
            return len(candidate_ids)

        purge_entry = self._build_purge_entry(
            entity_type="Signal",
            label="signal",
            source=source,
            before=before,
            record_ids=candidate_ids,
        )
        return self._purge_unit_of_work.purge_signals_and_record(candidate_ids, purge_entry)

    def purge_weather_events(
        self, source: str, *, before: datetime | None = None, dry_run: bool = True
    ) -> int:
        """Delete (or, if ``dry_run``, just count) weather events from ``source``.

        Returns the number of weather events deleted (or that would be deleted).
        """
        candidate_ids = self._weather_event_repository.list_ids_by_source(source, before=before)

        if dry_run:
            return len(candidate_ids)

        purge_entry = self._build_purge_entry(
            entity_type="WeatherEvent",
            label="weather event",
            source=source,
            before=before,
            record_ids=candidate_ids,
        )
        return self._purge_unit_of_work.purge_weather_events_and_record(candidate_ids, purge_entry)

    @staticmethod
    def _build_purge_entry(
        *,
        entity_type: str,
        label: str,
        source: str,
        before: datetime | None,
        record_ids: list[UUID],
    ) -> AuditLogEntry:
        return AuditLogEntry(
            event_type=AuditEventType.DATA_PURGED,
            entity_type=entity_type,
            message=f"Purged {len(record_ids)} {label}(s) from source {source!r}.",
            context={
                "source": source,
                "before": before.isoformat() if before else None,
                "deleted_count": len(record_ids),
            },
        )
