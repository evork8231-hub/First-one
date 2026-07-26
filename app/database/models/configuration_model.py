"""ORM mapping for the ConfigurationEntry entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.column_types import assume_utc, to_storage_utc
from app.domain.configuration import ConfigurationEntry


class ConfigurationModel(Base):
    """Persistence row for a single runtime-adjustable ConfigurationEntry."""

    __tablename__ = "configuration"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    value: Mapped[Any] = mapped_column(JSON, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    @classmethod
    def from_domain(cls, entry: ConfigurationEntry) -> ConfigurationModel:
        return cls(
            id=entry.id,
            key=entry.key,
            value=entry.value,
            description=entry.description,
            updated_at=to_storage_utc(entry.updated_at),
        )

    def to_domain(self) -> ConfigurationEntry:
        return ConfigurationEntry(
            id=self.id,
            key=self.key,
            value=self.value,
            description=self.description,
            updated_at=assume_utc(self.updated_at),
        )
