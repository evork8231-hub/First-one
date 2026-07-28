"""SQLite-backed CollectionUnitOfWork: atomic signal/event + audit write for collection.

Fixes the same class of bug ``SQLiteRollbackUnitOfWork`` and
``SQLiteWeatherBridgeUnitOfWork`` fixed elsewhere (see those modules'
docstrings for the full argument): the records a collector run produces
and the ``COLLECTOR_RUN_COMPLETED`` audit entry describing that run now
share a single SQLAlchemy ``Session`` -- and therefore a single SQLite
transaction -- via one ``session_scope`` call. ``session_scope``'s
existing ``except Exception: session.rollback()`` (unchanged, reused as
-is) guarantees that a failure partway through leaves nothing committed:
either the run's records and its completion entry all persist, or none
of them do.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.collection_unit_of_work import (
    CollectedSignal,
    CollectionUnitOfWork,
)
from app.database.models.audit_log_model import AuditLogModel
from app.database.models.signal_model import SignalModel
from app.database.models.weather_model import WeatherEventModel
from app.database.session import session_scope
from app.domain.audit import AuditLogEntry
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent


class SQLiteCollectionUnitOfWork(CollectionUnitOfWork):
    """Persists a collector run's records and its completion audit entry in one transaction."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def record_signal_collection(
        self, collected: Sequence[CollectedSignal], completion_entry: AuditLogEntry
    ) -> list[Signal]:
        with session_scope(self._session_factory) as session:
            signal_models = [SignalModel.from_domain(item.signal) for item in collected]
            if signal_models:
                session.add_all(signal_models)
                session.add_all(
                    AuditLogModel.from_domain(item.ingested_entry) for item in collected
                )
            session.add(AuditLogModel.from_domain(completion_entry))
            session.flush()
            return [model.to_domain() for model in signal_models]

    def record_weather_collection(
        self, events: Sequence[WeatherEvent], completion_entry: AuditLogEntry
    ) -> list[WeatherEvent]:
        with session_scope(self._session_factory) as session:
            event_models = [WeatherEventModel.from_domain(event) for event in events]
            if event_models:
                session.add_all(event_models)
            session.add(AuditLogModel.from_domain(completion_entry))
            session.flush()
            return [model.to_domain() for model in event_models]
