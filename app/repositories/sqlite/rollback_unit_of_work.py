"""SQLite-backed RollbackUnitOfWork: atomic delete + audit-write, race-safe.

Two problems the earlier implementation had, both fixed here without any
change to ``SignalRepository``/``WeatherEventRepository``/``AuditLogRepository``
or the tables they own:

1. **Atomicity.** ``delete_by_ids`` and ``audit_log_repository.add`` used
   to run in two separate ``session_scope`` blocks (two separate
   transactions, two separate commits). A crash between them left records
   deleted with no audit trail of it. Here, both statements run inside
   *one* ``session_scope`` call, so they share one SQLAlchemy ``Session``
   and therefore one SQLite transaction: either both the ``DELETE`` and
   the ``INSERT`` commit, or (on any exception) ``session_scope`` calls
   ``session.rollback()`` and *neither* takes effect. There is no
   intermediate state to crash into.

2. **Concurrent rollback.** Two ``sigint rollback --yes`` processes could
   previously both read "not yet rolled back" before either wrote,
   producing two ``COLLECTOR_RUN_ROLLED_BACK`` entries for the same run.
   The fix relies on a real SQLite guarantee, not a heuristic: SQLite
   allows only one writer to hold the database's write lock at a time,
   and issuing a DML statement (INSERT/UPDATE/DELETE) is what causes a
   connection to acquire that lock. So this method inserts the rollback
   audit entry *first* -- before checking anything -- which forces this
   transaction to either acquire the lock immediately or block (via the
   engine's configured ``busy_timeout_seconds``) until any concurrent
   rollback transaction has fully committed or rolled back. Only *after*
   that INSERT has been flushed (lock held) does it re-check whether a
   rollback for this exact ``execution_id`` already exists. Because no
   other writer could have committed anything while this transaction
   holds the lock, that re-check is guaranteed accurate -- if it finds a
   conflict, the whole transaction (including the INSERT just issued) is
   rolled back by raising, and no duplicate is ever committed.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.rollback_unit_of_work import RollbackUnitOfWork
from app.core.exceptions import RollbackConflictError
from app.database.models.audit_log_model import AuditLogModel
from app.database.models.signal_model import SignalModel
from app.database.models.weather_model import WeatherEventModel
from app.database.session import session_scope
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType

#: How many of the most recent COLLECTOR_RUN_ROLLED_BACK entries (across
#: every collector) to scan for a conflicting execution_id. A genuine race
#: can only have been written moments earlier by a concurrently-running
#: rollback, so it is always among the most recent entries -- this bound
#: only exists to keep the scan bounded, not to limit correctness.
_CONFLICT_CHECK_LIMIT = 50

_ModelT = TypeVar("_ModelT", SignalModel, WeatherEventModel)


class SQLiteRollbackUnitOfWork(RollbackUnitOfWork):
    """Deletes records and records the rollback in one SQLite transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def delete_signals_and_record_rollback(
        self, signal_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        return self._delete_and_record(SignalModel, signal_ids, rollback_entry)

    def delete_weather_events_and_record_rollback(
        self, event_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        return self._delete_and_record(WeatherEventModel, event_ids, rollback_entry)

    def _delete_and_record(
        self, model_cls: type[_ModelT], record_ids: Sequence[UUID], rollback_entry: AuditLogEntry
    ) -> int:
        with session_scope(self._session_factory) as session:
            audit_model = AuditLogModel.from_domain(rollback_entry)
            session.add(audit_model)
            session.flush()  # forces the INSERT now, acquiring SQLite's write lock

            self._raise_if_already_rolled_back(
                session,
                execution_id=rollback_entry.context.get("execution_id"),
                collector=rollback_entry.context.get("collector"),
                own_entry_id=audit_model.id,
            )

            deleted = 0
            if record_ids:
                filters = [model_cls.id.in_(record_ids)]
                count_stmt = select(func.count()).select_from(model_cls).where(*filters)
                deleted = session.scalar(count_stmt) or 0
                if deleted:
                    session.execute(delete(model_cls).where(*filters))
            return deleted

    @staticmethod
    def _raise_if_already_rolled_back(
        session: Session, *, execution_id: object, collector: object, own_entry_id: UUID
    ) -> None:
        stmt = (
            select(AuditLogModel)
            .where(
                AuditLogModel.event_type == AuditEventType.COLLECTOR_RUN_ROLLED_BACK,
                AuditLogModel.id != own_entry_id,
            )
            .order_by(AuditLogModel.created_at.desc())
            .limit(_CONFLICT_CHECK_LIMIT)
        )
        for row in session.scalars(stmt):
            if (
                row.context.get("execution_id") == execution_id
                and row.context.get("collector") == collector
            ):
                raise RollbackConflictError(
                    f"Collector {collector!r} run {execution_id} was already rolled back "
                    f"by another process. Aborting this rollback to avoid a duplicate."
                )
