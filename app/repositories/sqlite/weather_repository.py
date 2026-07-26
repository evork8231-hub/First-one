"""SQLite-backed WeatherEventRepository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.repositories import WeatherEventRepository
from app.database.models.weather_model import WeatherEventModel
from app.database.session import session_scope
from app.domain.weather import WeatherEvent


class SQLiteWeatherEventRepository(WeatherEventRepository):
    """Persists WeatherEvents to a SQLite (or any SQLAlchemy-supported) database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, event: WeatherEvent) -> WeatherEvent:
        with session_scope(self._session_factory) as session:
            model = WeatherEventModel.from_domain(event)
            session.add(model)
            session.flush()
            return model.to_domain()

    def add_many(self, events: Sequence[WeatherEvent]) -> list[WeatherEvent]:
        if not events:
            return []
        with session_scope(self._session_factory) as session:
            models = [WeatherEventModel.from_domain(event) for event in events]
            session.add_all(models)
            session.flush()
            return [model.to_domain() for model in models]

    def get_by_id(self, event_id: UUID) -> WeatherEvent | None:
        with session_scope(self._session_factory) as session:
            model = session.get(WeatherEventModel, event_id)
            return model.to_domain() if model is not None else None

    def list_by_region_and_time(
        self,
        *,
        county: str,
        municipality: str | None = None,
        since: datetime,
        until: datetime,
    ) -> list[WeatherEvent]:
        with session_scope(self._session_factory) as session:
            stmt = select(WeatherEventModel).where(
                WeatherEventModel.county == county,
                WeatherEventModel.started_at <= until,
                WeatherEventModel.ended_at >= since,
            )
            if municipality is not None:
                stmt = stmt.where(WeatherEventModel.municipality == municipality)
            stmt = stmt.order_by(WeatherEventModel.started_at.desc())
            return [model.to_domain() for model in session.scalars(stmt)]

    def count(self) -> int:
        with session_scope(self._session_factory) as session:
            return session.scalar(select(func.count()).select_from(WeatherEventModel)) or 0
