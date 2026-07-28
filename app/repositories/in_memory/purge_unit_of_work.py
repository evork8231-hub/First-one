"""In-memory PurgeUnitOfWork, used primarily in tests.

Mirrors ``app.repositories.in_memory.rollback_unit_of_work.InMemoryRollbackUnitOfWork``:
it cannot reproduce SQLite's real transaction/rollback behavior (there is
nothing to roll back in a process-local dict), so it is not a substitute
for the SQLite-backed atomicity tests -- it exists so
``DataManagementService``'s own logic (dependency checks, dry-run
behavior) can be tested in isolation without a real database.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.interfaces.purge_unit_of_work import PurgeUnitOfWork
from app.application.interfaces.repositories import (
    AuditLogRepository,
    SignalRepository,
    WeatherEventRepository,
)
from app.domain.audit import AuditLogEntry


class InMemoryPurgeUnitOfWork(PurgeUnitOfWork):
    """Deletes records and records the purge against in-memory repositories."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        weather_event_repository: WeatherEventRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._audit_log_repository = audit_log_repository

    def purge_signals_and_record(
        self, signal_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        deleted = self._signal_repository.delete_by_ids(signal_ids) if signal_ids else 0
        self._audit_log_repository.add(purge_entry)
        return deleted

    def purge_weather_events_and_record(
        self, event_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        deleted = self._weather_event_repository.delete_by_ids(event_ids) if event_ids else 0
        self._audit_log_repository.add(purge_entry)
        return deleted
