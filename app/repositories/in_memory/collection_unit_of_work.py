"""In-memory CollectionUnitOfWork, used primarily in tests.

Mirrors ``app.repositories.in_memory.rollback_unit_of_work.InMemoryRollbackUnitOfWork``:
it cannot reproduce SQLite's real transaction/rollback behavior (there is
nothing to roll back in a process-local dict), so it is not a substitute
for the SQLite-backed atomicity tests -- it exists so
``SignalService``/``WeatherEventService``'s own logic can be tested in
isolation without a real database.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.interfaces.collection_unit_of_work import (
    CollectedSignal,
    CollectionUnitOfWork,
)
from app.application.interfaces.repositories import (
    AuditLogRepository,
    SignalRepository,
    WeatherEventRepository,
)
from app.domain.audit import AuditLogEntry
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent


class InMemoryCollectionUnitOfWork(CollectionUnitOfWork):
    """Persists a collector run's records and its completion audit entry against
    in-memory repositories."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        weather_event_repository: WeatherEventRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._weather_event_repository = weather_event_repository
        self._audit_log_repository = audit_log_repository

    def record_signal_collection(
        self, collected: Sequence[CollectedSignal], completion_entry: AuditLogEntry
    ) -> list[Signal]:
        stored = (
            self._signal_repository.add_many([item.signal for item in collected])
            if collected
            else []
        )
        for item in collected:
            self._audit_log_repository.add(item.ingested_entry)
        self._audit_log_repository.add(completion_entry)
        return stored

    def record_weather_collection(
        self, events: Sequence[WeatherEvent], completion_entry: AuditLogEntry
    ) -> list[WeatherEvent]:
        stored = self._weather_event_repository.add_many(events) if events else []
        self._audit_log_repository.add(completion_entry)
        return stored
