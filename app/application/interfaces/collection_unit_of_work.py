"""The CollectionUnitOfWork interface: atomic "persist a collection run" boundary.

``SignalService``/``WeatherEventService`` needed the same guarantee
``RollbackUnitOfWork``/``WeatherBridgeUnitOfWork``/``PurgeUnitOfWork``
already provide elsewhere: that persisting the records a successful
collector run produced and recording that run's completion (the
``COLLECTOR_RUN_COMPLETED`` audit entry, which carries the ``execution_id``
and ``inserted_signal_ids``/``inserted_event_ids`` that
``app.application.services.rollback_service.RollbackService`` depends on
to find and undo that exact run later) either both happen or neither
does. ``SignalRepository``/``WeatherEventRepository`` and
``AuditLogRepository`` each manage their own independent database
transaction -- calling ``add_many`` and then ``audit_log_repository.add``
in sequence, as the earlier implementation did, leaves a real window
where a crash between the two commits leaves signals or weather events
durably persisted with no ``COLLECTOR_RUN_COMPLETED`` entry recording
them. Because ``RollbackService`` can only discover a run through that
entry's ``inserted_signal_ids``/``inserted_event_ids``, such an
interruption leaves the newly-collected records permanently invisible to
``sigint rollback`` -- exactly the manual-SQL scenario this platform's
destructive-operation tooling exists to eliminate.

This interface is deliberately narrow (exactly the two operations
collection needs, nothing more general) rather than a full generic
Unit-of-Work abstraction spanning every repository -- mirroring
``app.application.interfaces.rollback_unit_of_work.RollbackUnitOfWork``
and
``app.application.interfaces.weather_bridge_unit_of_work.WeatherBridgeUnitOfWork``
both in shape and in taking already-built domain objects (pure, no I/O)
rather than doing any collection/business logic itself.

Deliberately NOT covered by this unit of work -- and left as direct,
independent ``AuditLogRepository.add`` calls in the service, exactly as
before:

* ``COLLECTOR_RUN_STARTED`` -- written *before* ``collector.collect()``
  runs, so an operator or ``sigint health`` can see a collection is in
  progress even if the collector itself hangs or crashes during network
  I/O. It cannot be part of the same transaction as the eventual
  completion write, because the whole point is that it is durable
  independently of whether collection ever finishes.
* ``COLLECTOR_RUN_FAILED`` -- written when ``collector.collect()`` itself
  raises. Nothing was collected in that case, so there is nothing for
  this unit of work to be atomic *with*; it is its own independent fact,
  the same way a zero-match ``sigint purge`` run still gets its own
  standalone audit entry.

See ``app.repositories.sqlite.collection_unit_of_work.SQLiteCollectionUnitOfWork``
for how the SQLite implementation achieves atomicity by reusing the
existing ``session_scope`` machinery for a single shared session, and
``app.repositories.in_memory.collection_unit_of_work.InMemoryCollectionUnitOfWork``
for the test double.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass

from app.domain.audit import AuditLogEntry
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent


@dataclass(frozen=True)
class CollectedSignal:
    """One collected Signal paired with its own SIGNAL_INGESTED audit entry.

    Grouping the two as one value (rather than two parallel lists) makes
    a length mismatch between them structurally impossible -- mirrors
    ``app.application.interfaces.weather_bridge_unit_of_work.BridgedEvent``.
    """

    signal: Signal
    ingested_entry: AuditLogEntry


class CollectionUnitOfWork(ABC):
    """Atomically persists a collector run's records and its completion audit entry."""

    @abstractmethod
    def record_signal_collection(
        self, collected: Sequence[CollectedSignal], completion_entry: AuditLogEntry
    ) -> list[Signal]:
        """Persist every signal, its own audit entry, and ``completion_entry`` as one transaction.

        ``completion_entry`` is persisted even when ``collected`` is
        empty (a run that legitimately produced no new signals still
        gets a ``COLLECTOR_RUN_COMPLETED`` record), matching the
        pre-existing behavior this replaces. Returns the persisted
        Signals, in the same order as ``collected``.
        """

    @abstractmethod
    def record_weather_collection(
        self, events: Sequence[WeatherEvent], completion_entry: AuditLogEntry
    ) -> list[WeatherEvent]:
        """Persist every weather event and ``completion_entry`` as one transaction.

        See :meth:`record_signal_collection` for the full contract.
        Weather collection writes no per-event audit entry -- this
        matches the pre-existing behavior, which never had one either.
        """
