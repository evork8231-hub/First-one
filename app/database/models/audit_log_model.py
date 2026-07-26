"""ORM mapping for the AuditLogEntry entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.column_types import assume_utc, enum_column, to_storage_utc
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


class AuditLogModel(Base):
    """Persistence row for a single AuditLogEntry. Append-only, never updated."""

    __tablename__ = "audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[AuditEventType] = mapped_column(
        enum_column(AuditEventType, length=32), nullable=False, index=True
    )
    entity_type: Mapped[str | None] = mapped_column(String(64))
    entity_id: Mapped[UUID | None] = mapped_column(index=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)

    @classmethod
    def from_domain(cls, entry: AuditLogEntry) -> AuditLogModel:
        return cls(
            id=entry.id,
            event_type=entry.event_type,
            entity_type=entry.entity_type,
            entity_id=entry.entity_id,
            message=entry.message,
            created_at=to_storage_utc(entry.created_at),
            context=entry.context,
        )

    def to_domain(self) -> AuditLogEntry:
        return AuditLogEntry(
            id=self.id,
            event_type=self.event_type,
            entity_type=self.entity_type,
            entity_id=self.entity_id,
            message=self.message,
            created_at=assume_utc(self.created_at),
            context=self.context,
        )
