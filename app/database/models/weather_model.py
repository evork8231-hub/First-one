"""ORM mapping for the WeatherEvent entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.column_types import assume_utc, enum_column, to_storage_utc
from app.domain.enums import WeatherEventType
from app.domain.value_objects import Coordinates
from app.domain.weather import WeatherEvent


class WeatherEventModel(Base):
    """Persistence row for a WeatherEvent, stored independently from signals."""

    __tablename__ = "weather_events"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    event_type: Mapped[WeatherEventType] = mapped_column(
        enum_column(WeatherEventType, length=32), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    county: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    municipality: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    severity: Mapped[float] = mapped_column(Float, nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    @classmethod
    def from_domain(cls, event: WeatherEvent) -> WeatherEventModel:
        return cls(
            id=event.id,
            event_type=event.event_type,
            source=event.source,
            source_url=event.source_url,
            county=event.county,
            municipality=event.municipality,
            latitude=event.coordinates.latitude if event.coordinates else None,
            longitude=event.coordinates.longitude if event.coordinates else None,
            severity=event.severity,
            started_at=to_storage_utc(event.started_at),
            ended_at=to_storage_utc(event.ended_at),
            raw_payload=event.raw_payload,
            metadata_=event.metadata,
        )

    def to_domain(self) -> WeatherEvent:
        coordinates = (
            Coordinates(latitude=self.latitude, longitude=self.longitude)
            if self.latitude is not None and self.longitude is not None
            else None
        )
        return WeatherEvent(
            id=self.id,
            event_type=self.event_type,
            source=self.source,
            source_url=self.source_url,
            county=self.county,
            municipality=self.municipality,
            coordinates=coordinates,
            severity=self.severity,
            started_at=assume_utc(self.started_at),
            ended_at=assume_utc(self.ended_at),
            raw_payload=self.raw_payload,
            metadata=self.metadata_,
        )
