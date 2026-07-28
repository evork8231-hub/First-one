"""The RollbackUnitOfWork interface: atomic "delete records + record the rollback" boundary.

``RollbackService`` needs exactly one guarantee that no single repository
can give it on its own: that deleting the records a collector run
inserted and writing the ``COLLECTOR_RUN_ROLLED_BACK`` audit entry either
both happen or neither does. ``SignalRepository``, ``WeatherEventRepository``,
and ``AuditLogRepository`` each manage their own, independent database
transaction (see ``app.database.session.session_scope``) -- calling two of
them in sequence, as the earlier implementation did, leaves a real window
where a crash between the two commits deletes data with no audit record
of it.

This interface is deliberately narrow (exactly the two operations
rollback needs, nothing more general) rather than a full generic
Unit-of-Work abstraction spanning every repository -- see
``app.repositories.sqlite.rollback_unit_of_work.SQLiteRollbackUnitOfWork``
for how the SQLite implementation achieves atomicity by reusing the
existing ``session_scope`` machinery for a single shared session, and
``app.repositories.in_memory.rollback_unit_of_work.InMemoryRollbackUnitOfWork``
for the test double.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.domain.audit import AuditLogEntry


class RollbackUnitOfWork(ABC):
    """Atomically deletes a collector run's records and records the rollback."""

    @abstractmethod
    def delete_signals_and_record_rollback(
        self, signal_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        """Delete ``signal_ids`` from storage and persist ``rollback_entry``, atomically.

        Returns how many signals were actually deleted (never more than
        ``len(signal_ids)`` -- some may already be gone, e.g. via a prior
        ``sigint purge``). Raises
        ``app.core.exceptions.RollbackConflictError`` instead of writing
        anything if another process already recorded a rollback for the
        same ``rollback_entry.context["execution_id"]`` first.
        """

    @abstractmethod
    def delete_weather_events_and_record_rollback(
        self, event_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        """Delete ``event_ids`` from storage and persist ``rollback_entry``, atomically.

        See :meth:`delete_signals_and_record_rollback` for the full contract.
        """
