"""SQLite-backed PurgeUnitOfWork: atomic delete + audit-write for ``sigint purge``.

Fixes the same class of bug ``SQLiteRollbackUnitOfWork`` fixed for
rollback (see that module's docstring for the full argument):
``delete_by_source``/``delete_by_ids`` and ``audit_log_repository.add``
used to run in two separate ``session_scope`` blocks (two separate
transactions, two separate commits) inside
``DataManagementService.purge_signals``/``purge_weather_events``. A crash
between them left records deleted with no audit trail of it -- the
deletion itself was correct and dependency-checked, but the platform's
evidence-based design lost its record of what happened and why. Here,
the ``DELETE`` and the audit ``INSERT`` run inside *one* ``session_scope``
call, so they share one SQLAlchemy ``Session`` and therefore one SQLite
transaction: either both commit, or (on any exception) ``session_scope``
calls ``session.rollback()`` and *neither* takes effect. There is no
intermediate state to crash into.

No changes were made to ``SignalRepository``, ``WeatherEventRepository``,
``AuditLogRepository``, or the tables they own -- this unit of work talks
to the same ORM models (``SignalModel``, ``WeatherEventModel``,
``AuditLogModel``) directly, exactly as ``SQLiteRollbackUnitOfWork`` does,
rather than composing the existing repository methods (which cannot be
composed into one transaction across separate ``session_scope`` calls).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TypeVar
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.purge_unit_of_work import PurgeUnitOfWork
from app.database.models.audit_log_model import AuditLogModel
from app.database.models.signal_model import SignalModel
from app.database.models.weather_model import WeatherEventModel
from app.database.session import session_scope
from app.domain.audit import AuditLogEntry

_ModelT = TypeVar("_ModelT", SignalModel, WeatherEventModel)


class SQLitePurgeUnitOfWork(PurgeUnitOfWork):
    """Deletes records and records the purge in one SQLite transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def purge_signals_and_record(
        self, signal_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        return self._delete_and_record(SignalModel, signal_ids, purge_entry)

    def purge_weather_events_and_record(
        self, event_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        return self._delete_and_record(WeatherEventModel, event_ids, purge_entry)

    def _delete_and_record(
        self, model_cls: type[_ModelT], record_ids: Sequence[UUID], purge_entry: AuditLogEntry
    ) -> int:
        with session_scope(self._session_factory) as session:
            deleted = 0
            if record_ids:
                filters = [model_cls.id.in_(record_ids)]
                count_stmt = select(func.count()).select_from(model_cls).where(*filters)
                deleted = session.scalar(count_stmt) or 0
                if deleted:
                    session.execute(delete(model_cls).where(*filters))
            session.add(AuditLogModel.from_domain(purge_entry))
            session.flush()
            return deleted
