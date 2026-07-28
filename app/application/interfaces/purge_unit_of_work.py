"""The PurgeUnitOfWork interface: atomic "delete records + record the purge" boundary.

``DataManagementService`` needs exactly the same guarantee ``RollbackService``
needed from ``RollbackUnitOfWork`` (see
``app.application.interfaces.rollback_unit_of_work`` for the full argument):
that deleting the Signals/WeatherEvents a purge targets and writing the
``DATA_PURGED`` audit entry either both happen or neither does.
``SignalRepository``, ``WeatherEventRepository``, and ``AuditLogRepository``
each manage their own, independent database transaction -- calling
``delete_by_source`` and then ``audit_log_repository.add`` in sequence, as
the earlier implementation did, leaves a real window where a crash
between the two commits deletes data with no audit record of it, which
is exactly the fail-closed, evidence-based guarantee this platform's
destructive operations are supposed to uphold (see
``app.application.services.rollback_service`` and
``app.application.services.weather_signal_bridge_service`` for the same
class of bug, fixed the same way, in the two other destructive/derived
write paths this platform has).

This interface is deliberately narrow (exactly the two operations purge
needs, nothing more general) rather than a full generic Unit-of-Work
abstraction spanning every repository -- mirroring
``app.application.interfaces.rollback_unit_of_work.RollbackUnitOfWork``
both in shape and in taking an explicit, already-known id set rather than
a filter: ``DataManagementService`` resolves the exact ids to delete via
``SignalRepository.list_ids_by_source``/``WeatherEventRepository.list_ids_by_source``
*before* calling this interface (the same read it already needed to run
the Lead-dependency check), so the unit of work never has to re-derive
"which rows does this purge mean" itself -- it only has to delete exactly
the ids it is given and record that it did.

Unlike ``RollbackUnitOfWork``, there is no concurrent-conflict check here:
rollback guards against two processes racing to roll back the same
``execution_id`` a second time, but a purge has no equivalent replayable
identifier to collide on -- each call targets an explicit, caller-supplied
id set, and deleting an id that is already gone is simply a no-op (see
:meth:`PurgeUnitOfWork.purge_signals_and_record`).

See ``app.repositories.sqlite.purge_unit_of_work.SQLitePurgeUnitOfWork``
for how the SQLite implementation achieves atomicity by reusing the
existing ``session_scope`` machinery for a single shared session, and
``app.repositories.in_memory.purge_unit_of_work.InMemoryPurgeUnitOfWork``
for the test double.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from app.domain.audit import AuditLogEntry


class PurgeUnitOfWork(ABC):
    """Atomically deletes purge-targeted records and records the purge."""

    @abstractmethod
    def purge_signals_and_record(
        self, signal_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        """Delete ``signal_ids`` from storage and persist ``purge_entry``, atomically.

        Returns how many signals were actually deleted (never more than
        ``len(signal_ids)`` -- some may already be gone, e.g. via a
        concurrent rollback). ``purge_entry`` is persisted even when
        ``signal_ids`` is empty, so a real (non-dry-run) purge that
        matched nothing still leaves an audit record that it ran.
        """

    @abstractmethod
    def purge_weather_events_and_record(
        self, event_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        """Delete ``event_ids`` from storage and persist ``purge_entry``, atomically.

        See :meth:`purge_signals_and_record` for the full contract.
        """
