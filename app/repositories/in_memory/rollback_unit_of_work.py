"""In-memory RollbackUnitOfWork, used primarily in tests.

Mirrors ``app.repositories.sqlite.rollback_unit_of_work.SQLiteRollbackUnitOfWork``'s
observable behavior -- the same conflict check, the same "record first,
then check" ordering -- so ``RollbackService`` unit tests can exercise the
concurrency guard without a real database. It cannot reproduce SQLite's
actual locking (there is nothing to lock in a process-local dict), so it
is not a substitute for the SQLite-backed atomicity/race tests; it exists
so ``RollbackService``'s own logic can be tested in isolation.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.interfaces.repositories import (
    AuditLogRepository,
    SignalRepository,
    WeatherEventRepository,
)
from app.application.interfaces.rollback_unit_of_work import RollbackUnitOfWork
from app.core.exceptions import RollbackConflictError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


class InMemoryRollbackUnitOfWork(RollbackUnitOfWork):
    """Deletes records and records the rollback against in-memory repositories."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        weather_event_repository: WeatherEventRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._audit_log_repository = audit_log_repository

    def delete_signals_and_record_rollback(
        self, signal_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        self._raise_if_already_rolled_back(rollback_entry)
        self._audit_log_repository.add(rollback_entry)
        return self._signal_repository.delete_by_ids(signal_ids) if signal_ids else 0

    def delete_weather_events_and_record_rollback(
        self, event_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        self._raise_if_already_rolled_back(rollback_entry)
        self._audit_log_repository.add(rollback_entry)
        return self._weather_event_repository.delete_by_ids(event_ids) if event_ids else 0

    def _raise_if_already_rolled_back(self, rollback_entry: AuditLogEntry) -> None:
        execution_id = rollback_entry.context.get("execution_id")
        collector = rollback_entry.context.get("collector")
        existing = self._audit_log_repository.list_all(
            event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=500
        )
        for entry in existing:
            if (
                entry.context.get("execution_id") == execution_id
                and entry.context.get("collector") == collector
            ):
                raise RollbackConflictError(
                    f"Collector {collector!r} run {execution_id} was already rolled back "
                    f"by another process. Aborting this rollback to avoid a duplicate."
                )
