"""In-memory WeatherBridgeUnitOfWork, used primarily in tests.

Mirrors ``app.repositories.in_memory.rollback_unit_of_work.InMemoryRollbackUnitOfWork``:
it cannot reproduce SQLite's real transaction/rollback behavior (there is
nothing to roll back in a process-local dict), so it is not a substitute
for the SQLite-backed atomicity tests -- it exists so
``WeatherSignalBridgeService``'s own logic can be tested in isolation
without a real database.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.interfaces.repositories import (
    AuditLogRepository,
    ConfigurationRepository,
    SignalRepository,
)
from app.application.interfaces.weather_bridge_unit_of_work import (
    BridgedEvent,
    WeatherBridgeUnitOfWork,
)
from app.domain.signal import Signal


class InMemoryWeatherBridgeUnitOfWork(WeatherBridgeUnitOfWork):
    """Persists a batch of bridged weather events against in-memory repositories."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        configuration_repository: ConfigurationRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._configuration_repository = configuration_repository
        self._audit_log_repository = audit_log_repository

    def bridge_events(self, bridged: Sequence[BridgedEvent]) -> list[Signal]:
        if not bridged:
            return []
        stored = self._signal_repository.add_many([item.signal for item in bridged])
        for item in bridged:
            self._configuration_repository.set(item.dedup_entry)
        for item in bridged:
            self._audit_log_repository.add(item.audit_entry)
        return stored
