"""The WeatherBridgeUnitOfWork interface: atomic "signal + dedup + audit" boundary.

``WeatherSignalBridgeService`` needs the same guarantee ``RollbackService``
needed from ``RollbackUnitOfWork`` (see
``app.application.interfaces.rollback_unit_of_work``): that persisting a
bridged WeatherEvent's Signal, its dedup fingerprint bookkeeping (see
``app.verification.weather_bridge_dedup.WeatherBridgeDeduplicator``), and
its audit log entry either all happen or none do. ``SignalRepository``,
``ConfigurationRepository``, and ``AuditLogRepository`` each manage their
own independent database transaction -- calling them in sequence, as the
earlier implementation did, left a real window where a crash between the
signal insert and the dedup bookkeeping committed the Signal but never
recorded that the event had been bridged. On the next collection run
(a forecast source is typically polled repeatedly), the same real
occurrence would then be bridged *again*, producing a duplicate
WEATHER_EVENT signal that silently inflates a Lead's weather-confidence
boost.

This interface is deliberately narrow (exactly the one batch operation
the bridge needs), mirroring ``RollbackUnitOfWork`` -- see
``app.repositories.sqlite.weather_bridge_unit_of_work.SQLiteWeatherBridgeUnitOfWork``
for how the SQLite implementation achieves atomicity by reusing the
existing ``session_scope`` machinery for a single shared session, and
``app.repositories.in_memory.weather_bridge_unit_of_work.InMemoryWeatherBridgeUnitOfWork``
for the test double.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.audit import AuditLogEntry
from app.domain.configuration import ConfigurationEntry
from app.domain.signal import Signal


@dataclass(frozen=True)
class BridgedEvent:
    """One WeatherEvent's fully-built Signal, dedup fingerprint entry, and audit entry.

    Grouping the three as one value (rather than three parallel lists)
    makes a length mismatch between them structurally impossible --
    ``WeatherSignalBridgeService`` builds exactly one of these per
    WeatherEvent it decides to bridge.
    """

    signal: Signal
    dedup_entry: ConfigurationEntry
    audit_entry: AuditLogEntry


class WeatherBridgeUnitOfWork(ABC):
    """Atomically persists a batch of bridged weather events."""

    @abstractmethod
    def bridge_events(self, bridged: Sequence[BridgedEvent]) -> list[Signal]:
        """Persist every signal, dedup entry, and audit entry in ``bridged`` as one transaction.

        Either every write in the batch commits, or (on any failure) none
        of them do -- there is no partial state to observe afterward.
        Returns the persisted Signals, in the same order as ``bridged``.
        """
