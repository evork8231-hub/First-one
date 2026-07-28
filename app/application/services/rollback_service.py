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
this platform, and it never edits or deletes the audit entries it reads --
a real rollback appends a new ``COLLECTOR_RUN_ROLLED_BACK`` entry instead,
so the audit history stays complete and the same run can never be rolled
back twice (the lookup skips any completed run whose execution id already
has a matching rolled-back entry).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from uuid import UUID

from app.application.interfaces.repositories import (
    AuditLogRepository,
    SignalRepository,
    WeatherEventRepository,
)
from app.core.exceptions import EntityNotFoundError
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
        signal_repository: SignalRepository,
        weather_event_repository: WeatherEventRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._audit_log_repository = audit_log_repository

    def rollback_last_signal_run(
        self, collector_name: str, *, dry_run: bool = True
    ) -> RollbackResult:
        """Roll back (or preview rolling back) the last completed run of a Signal collector."""
        return self._rollback(
            collector_name,
            entity_type="Collector",
            ids_key="inserted_signal_ids",
            delete_by_ids=self._signal_repository.delete_by_ids,
            dry_run=dry_run,
        )

    def rollback_last_weather_run(
        self, collector_name: str, *, dry_run: bool = True
    ) -> RollbackResult:
        """Roll back (or preview rolling back) the last completed run of a weather collector."""
        return self._rollback(
            collector_name,
            entity_type="WeatherCollector",
            ids_key="inserted_event_ids",
            delete_by_ids=self._weather_event_repository.delete_by_ids,
            dry_run=dry_run,
        )

    def _rollback(
        self,
        collector_name: str,
        *,
        entity_type: str,
        ids_key: str,
        delete_by_ids: Callable[[Sequence[UUID]], int],
        dry_run: bool,
    ) -> RollbackResult:
        entry = self._find_last_rollable_run(collector_name, entity_type=entity_type)
        if entry is None:
            raise EntityNotFoundError(
                f"No un-rolled-back completed run found for collector {collector_name!r}."
            )
        execution_id = str(entry.context["execution_id"])
        record_ids = [UUID(raw_id) for raw_id in entry.context.get(ids_key, [])]

        if not dry_run:
            if record_ids:
                delete_by_ids(record_ids)
            self._audit_log_repository.add(
                AuditLogEntry(
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
            )

        return RollbackResult(
            collector=collector_name,
            execution_id=execution_id,
            record_count=len(record_ids),
            dry_run=dry_run,
        )

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
