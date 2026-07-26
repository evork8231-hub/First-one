"""SQLite-backed ConfigurationRepository implementation."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.repositories import ConfigurationRepository
from app.database.column_types import to_storage_utc
from app.database.models.configuration_model import ConfigurationModel
from app.database.session import session_scope
from app.domain.configuration import ConfigurationEntry


class SQLiteConfigurationRepository(ConfigurationRepository):
    """Persists runtime-adjustable ConfigurationEntry records."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def get(self, key: str) -> ConfigurationEntry | None:
        with session_scope(self._session_factory) as session:
            stmt = select(ConfigurationModel).where(ConfigurationModel.key == key)
            model = session.scalars(stmt).one_or_none()
            return model.to_domain() if model is not None else None

    def set(self, entry: ConfigurationEntry) -> ConfigurationEntry:
        with session_scope(self._session_factory) as session:
            stmt = select(ConfigurationModel).where(ConfigurationModel.key == entry.key)
            existing = session.scalars(stmt).one_or_none()
            if existing is not None:
                existing.value = entry.value
                existing.description = entry.description
                existing.updated_at = to_storage_utc(entry.updated_at)
                session.flush()
                return existing.to_domain()
            model = ConfigurationModel.from_domain(entry)
            session.add(model)
            session.flush()
            return model.to_domain()

    def list_all(self) -> list[ConfigurationEntry]:
        with session_scope(self._session_factory) as session:
            stmt = select(ConfigurationModel).order_by(ConfigurationModel.key)
            return [model.to_domain() for model in session.scalars(stmt)]
