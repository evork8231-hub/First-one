"""SQLite-backed AuditLogRepository implementation."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.repositories import AuditLogRepository
from app.database.models.audit_log_model import AuditLogModel
from app.database.session import session_scope
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


class SQLiteAuditLogRepository(AuditLogRepository):
    """Persists AuditLogEntry records to a SQLite (or any SQLAlchemy-supported) database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        with session_scope(self._session_factory) as session:
            model = AuditLogModel.from_domain(entry)
            session.add(model)
            session.flush()
            return model.to_domain()

    def list_all(
        self,
        *,
        event_type: AuditEventType | None = None,
        entity_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        with session_scope(self._session_factory) as session:
            stmt = select(AuditLogModel)
            if event_type is not None:
                stmt = stmt.where(AuditLogModel.event_type == event_type)
            if entity_id is not None:
                stmt = stmt.where(AuditLogModel.entity_id == entity_id)
            stmt = stmt.order_by(AuditLogModel.created_at.desc()).limit(limit).offset(offset)
            return [model.to_domain() for model in session.scalars(stmt)]
