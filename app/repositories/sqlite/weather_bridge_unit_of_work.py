"""SQLite-backed WeatherBridgeUnitOfWork: atomic signal + dedup + audit write.

Fixes the same class of bug ``SQLiteRollbackUnitOfWork`` fixed for
rollback (see that module's docstring for the full argument): the
Signal a bridged WeatherEvent produces, the ``ConfigurationEntry`` that
marks the event as bridged (so a later re-collection of the same real
occurrence is recognized as a duplicate), and the ``AuditLogEntry``
recording the bridge all now share a single SQLAlchemy ``Session`` --
and therefore a single SQLite transaction -- via one ``session_scope``
call. ``session_scope``'s existing ``except Exception: session.rollback()``
(unchanged, reused as-is) guarantees that a failure partway through a
batch reverts every write already issued in that batch, not just the
ones that would otherwise have already committed under the old
per-repository-call transaction boundaries.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.weather_bridge_unit_of_work import (
    BridgedEvent,
    WeatherBridgeUnitOfWork,
)
from app.database.models.audit_log_model import AuditLogModel
from app.database.models.configuration_model import ConfigurationModel
from app.database.models.signal_model import SignalModel
from app.database.session import session_scope
from app.domain.signal import Signal


class SQLiteWeatherBridgeUnitOfWork(WeatherBridgeUnitOfWork):
    """Persists a batch of bridged weather events in one SQLite transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def bridge_events(self, bridged: Sequence[BridgedEvent]) -> list[Signal]:
        if not bridged:
            return []
        with session_scope(self._session_factory) as session:
            signal_models = [SignalModel.from_domain(item.signal) for item in bridged]
            session.add_all(signal_models)
            session.add_all(ConfigurationModel.from_domain(item.dedup_entry) for item in bridged)
            session.add_all(AuditLogModel.from_domain(item.audit_entry) for item in bridged)
            session.flush()
            return [model.to_domain() for model in signal_models]
