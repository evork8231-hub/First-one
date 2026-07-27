"""SQLite-backed SignalRepository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.repositories import SignalRepository
from app.core.exceptions import EntityNotFoundError
from app.database.column_types import to_storage_utc
from app.database.models.signal_model import SignalModel
from app.database.session import session_scope
from app.domain.enums import ServiceCategory, VerificationStatus
from app.domain.signal import Signal


class SQLiteSignalRepository(SignalRepository):
    """Persists Signals to a SQLite (or any SQLAlchemy-supported) database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, signal: Signal) -> Signal:
        with session_scope(self._session_factory) as session:
            model = SignalModel.from_domain(signal)
            session.add(model)
            session.flush()
            return model.to_domain()

    def add_many(self, signals: Sequence[Signal]) -> list[Signal]:
        if not signals:
            return []
        with session_scope(self._session_factory) as session:
            models = [SignalModel.from_domain(signal) for signal in signals]
            session.add_all(models)
            session.flush()
            return [model.to_domain() for model in models]

    def get_by_id(self, signal_id: UUID) -> Signal | None:
        with session_scope(self._session_factory) as session:
            model = session.get(SignalModel, signal_id)
            return model.to_domain() if model is not None else None

    def list_by_ids(self, signal_ids: Sequence[UUID]) -> list[Signal]:
        if not signal_ids:
            return []
        with session_scope(self._session_factory) as session:
            stmt = select(SignalModel).where(SignalModel.id.in_(signal_ids))
            return [model.to_domain() for model in session.scalars(stmt)]

    def list_all(
        self,
        *,
        service_category: ServiceCategory | None = None,
        verified: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Signal]:
        with session_scope(self._session_factory) as session:
            stmt = select(SignalModel)
            if service_category is not None:
                stmt = stmt.where(SignalModel.service_category == service_category)
            if verified is not None:
                stmt = stmt.where(SignalModel.verified == verified)
            if county is not None:
                stmt = stmt.where(SignalModel.county == county)
            if municipality is not None:
                stmt = stmt.where(SignalModel.municipality == municipality)
            stmt = stmt.order_by(SignalModel.timestamp.desc()).limit(limit).offset(offset)
            return [model.to_domain() for model in session.scalars(stmt)]

    def list_unverified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        return self.list_all(verified=VerificationStatus.UNVERIFIED, limit=limit, offset=offset)

    def update_verification(self, signal_id: UUID, status: VerificationStatus) -> Signal:
        with session_scope(self._session_factory) as session:
            model = session.get(SignalModel, signal_id)
            if model is None:
                raise EntityNotFoundError(f"No signal found with id {signal_id}.")
            model.verified = status
            session.flush()
            return model.to_domain()

    def count(
        self,
        *,
        service_category: ServiceCategory | None = None,
        verified: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
    ) -> int:
        with session_scope(self._session_factory) as session:
            stmt = select(func.count()).select_from(SignalModel)
            if service_category is not None:
                stmt = stmt.where(SignalModel.service_category == service_category)
            if verified is not None:
                stmt = stmt.where(SignalModel.verified == verified)
            if county is not None:
                stmt = stmt.where(SignalModel.county == county)
            if municipality is not None:
                stmt = stmt.where(SignalModel.municipality == municipality)
            return session.scalar(stmt) or 0

    def delete_by_source(
        self, source: str, *, before: datetime | None = None, dry_run: bool = False
    ) -> int:
        with session_scope(self._session_factory) as session:
            filters = [SignalModel.source == source]
            if before is not None:
                filters.append(SignalModel.timestamp < to_storage_utc(before))
            count_stmt = select(func.count()).select_from(SignalModel).where(*filters)
            matching = session.scalar(count_stmt) or 0
            if not dry_run and matching:
                session.execute(delete(SignalModel).where(*filters))
            return matching
