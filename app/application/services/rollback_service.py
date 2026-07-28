"""RollbackService: reverse the most recent completed run of a single collector.

Backs the ``sigint rollback`` CLI command. Every collector run that
finishes successfully already records its ``execution_id`` and the ids of
every record it inserted in its ``COLLECTOR_RUN_COMPLETED`` audit entry --
see ``SignalService.ingest_from_collector`` and
``WeatherEventService.ingest_from_collector``. This service uses exactly
that trail to delete precisely those records, never guessing which rows
belong to a run the way ``DataManagementService`` (source + optional
cutoff date) has to.

Rollback is dry-run by default, like every other destructive operation in
this platform. A real rollback deletes the records and writes a new
``COLLECTOR_RUN_ROLLED_BACK`` entry as a single atomic operation via
``RollbackUnitOfWork`` (see that module for why two separate commits were
not safe) -- it never edits or deletes the audit entries it reads, so the
audit history stays complete and the same run can never be rolled back
twice (the lookup skips any completed run whose execution id already has
a matching rolled-back entry; ``RollbackUnitOfWork`` re-checks this again,
authoritatively, immediately before committing, closing the race window
between two concurrent rollback attempts).

Before touching anything, this service validates that the audit entry's
rollback metadata (``execution_id``, ``inserted_signal_ids``/
``inserted_event_ids``) actually parses as UUIDs -- a corrupted or
hand-edited entry raises ``CorruptedRollbackMetadataError`` instead of an
uncaught ``ValueError``. For a Signal rollback, it also refuses to delete
any Signal still cited by an existing Lead's ``supporting_signal_ids``
(raising ``RollbackBlockedByDependentDataError``) rather than leaving that
Lead pointing at a record that no longer exists, or silently rewriting
the Lead itself -- see ``app.core.exceptions`` for the full rationale
behind that choice.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from app.application.interfaces.repositories import AuditLogRepository, LeadRepository
from app.application.interfaces.rollback_unit_of_work import RollbackUnitOfWork
from app.core.exceptions import (
    CorruptedRollbackMetadataError,
    EntityNotFoundError,
    RollbackBlockedByDependentDataError,
)
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType

_LOOKBACK_LIMIT = 500


@dataclass(frozen=True)
class RollbackResult:
    """The outcome of rolling back (or previewing the rollback of) a collector run."""

    collector: str
    execution_id: str
    record_count: int
    dry_run: bool


class RollbackService:
    """Reverses the most recent not-yet-rolled-back run of a named collector."""

    def __init__(
        self,
        audit_log_repository: AuditLogRepository,
        lead_repository: LeadRepository,
        rollback_unit_of_work: RollbackUnitOfWork,
    ) -> None:
        self._audit_log_repository = audit_log_repository
        self._lead_repository = lead_repository
        self._rollback_unit_of_work = rollback_unit_of_work

    def rollback_last_signal_run(
        self, collector_name: str, *, dry_run: bool = True
    ) -> RollbackResult:
        """Roll back (or preview rolling back) the last completed run of a Signal collector.

        Raises:
            EntityNotFoundError: No un-rolled-back completed run exists.
            CorruptedRollbackMetadataError: The run's audit metadata is invalid.
            RollbackBlockedByDependentDataError: A Lead still cites one of these signals.
            RollbackConflictError: Another process rolled back this exact run first
                (real rollback only; never raised in a dry run).
        """
        entry = self._find_last_rollable_run(collector_name, entity_type="Collector")
        if entry is None:
            raise EntityNotFoundError(
                f"No un-rolled-back completed run found for collector {collector_name!r}."
            )
        execution_id, record_ids = self._parse_metadata(
            entry, ids_key="inserted_signal_ids", collector_name=collector_name
        )

        if record_ids:
            blocking_leads = self._lead_repository.list_referencing_signal_ids(record_ids)
            if blocking_leads:
                raise RollbackBlockedByDependentDataError(
                    f"Cannot roll back collector {collector_name!r} run {execution_id}: "
                    f"{len(blocking_leads)} lead(s) still reference signals from this run. "
                    f"Reject or otherwise resolve those leads before rolling back."
                )

        if dry_run:
            return RollbackResult(
                collector=collector_name,
                execution_id=execution_id,
                record_count=len(record_ids),
                dry_run=True,
            )

        rollback_entry = self._build_rollback_entry(
            collector_name,
            entity_type="Collector",
            execution_id=execution_id,
            record_ids=record_ids,
        )
        deleted = self._rollback_unit_of_work.delete_signals_and_record_rollback(
            record_ids, rollback_entry
        )
        return RollbackResult(
            collector=collector_name, execution_id=execution_id, record_count=deleted, dry_run=False
        )

    def rollback_last_weather_run(
        self, collector_name: str, *, dry_run: bool = True
    ) -> RollbackResult:
        """Roll back (or preview rolling back) the last completed run of a weather collector.

        See :meth:`rollback_last_signal_run` for the full contract. WeatherEvents
        are never cited by a Lead directly (only the WEATHER_EVENT Signal the
        bridge derives from one is), so no dependent-data check applies here.
        """
        entry = self._find_last_rollable_run(collector_name, entity_type="WeatherCollector")
        if entry is None:
            raise EntityNotFoundError(
                f"No un-rolled-back completed run found for collector {collector_name!r}."
            )
        execution_id, record_ids = self._parse_metadata(
            entry, ids_key="inserted_event_ids", collector_name=collector_name
        )

        if dry_run:
            return RollbackResult(
                collector=collector_name,
                execution_id=execution_id,
                record_count=len(record_ids),
                dry_run=True,
            )

        rollback_entry = self._build_rollback_entry(
            collector_name,
            entity_type="WeatherCollector",
            execution_id=execution_id,
            record_ids=record_ids,
        )
        deleted = self._rollback_unit_of_work.delete_weather_events_and_record_rollback(
            record_ids, rollback_entry
        )
        return RollbackResult(
            collector=collector_name, execution_id=execution_id, record_count=deleted, dry_run=False
        )

    @staticmethod
    def _build_rollback_entry(
        collector_name: str, *, entity_type: str, execution_id: str, record_ids: Sequence[UUID]
    ) -> AuditLogEntry:
        return AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK,
            entity_type=entity_type,
            message=(
                f"Rolled back collector {collector_name!r} run {execution_id} "
                f"({len(record_ids)} record(s))."
            ),
            context={
                "collector": collector_name,
                "execution_id": execution_id,
                "rolled_back_count": len(record_ids),
            },
        )

    @staticmethod
    def _parse_metadata(
        entry: AuditLogEntry, *, ids_key: str, collector_name: str
    ) -> tuple[str, list[UUID]]:
        """Validate and parse an audit entry's rollback metadata.

        Never trusts ``context`` to already be well-formed -- a hand-edited
        row, a future schema change, or a bug elsewhere writing malformed
        data must never crash rollback with a raw Python traceback. Any
        validation failure here is fail-closed: it raises rather than
        guessing, coercing, or skipping the offending id.
        """
        raw_execution_id = entry.context.get("execution_id")
        try:
            execution_id = str(UUID(str(raw_execution_id)))
        except (TypeError, ValueError) as exc:
            raise CorruptedRollbackMetadataError(
                f"Rollback metadata for collector {collector_name!r} is corrupted "
                f"(execution_id={raw_execution_id!r} is not a valid UUID). "
                f"Rollback cannot continue safely."
            ) from exc

        raw_ids: Any = entry.context.get(ids_key, [])
        if not isinstance(raw_ids, list):
            raise CorruptedRollbackMetadataError(
                f"Rollback metadata for collector {collector_name!r} run {execution_id} is "
                f"corrupted ({ids_key!r} is not a list). Rollback cannot continue safely."
            )
        try:
            record_ids = [UUID(str(raw_id)) for raw_id in raw_ids]
        except (TypeError, ValueError) as exc:
            raise CorruptedRollbackMetadataError(
                f"Rollback metadata for collector {collector_name!r} run {execution_id} is "
                f"corrupted (one or more entries in {ids_key!r} is not a valid UUID). "
                f"Rollback cannot continue safely."
            ) from exc

        return execution_id, record_ids

    def _find_last_rollable_run(
        self, collector_name: str, *, entity_type: str
    ) -> AuditLogEntry | None:
        rolled_back_execution_ids = {
            str(entry.context.get("execution_id"))
            for entry in self._audit_log_repository.list_all(
                event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=_LOOKBACK_LIMIT
            )
            if entry.context.get("collector") == collector_name
        }
        completed_runs = self._audit_log_repository.list_all(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=_LOOKBACK_LIMIT
        )
        for entry in completed_runs:
            if entry.entity_type != entity_type:
                continue
            if entry.context.get("collector") != collector_name:
                continue
            if "execution_id" not in entry.context:
                continue
            if str(entry.context["execution_id"]) in rolled_back_execution_ids:
                continue
            return entry
        return None
