"""ORM mapping for the Signal entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.column_types import assume_utc, enum_column, to_storage_utc
from app.domain.enums import Country, ServiceCategory, SignalType, VerificationStatus
from app.domain.signal import Signal
from app.domain.value_objects import Address, Coordinates


class SignalModel(Base):
    """Persistence row for a Signal. Kept independent from the leads table."""

    __tablename__ = "signals"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    signal_type: Mapped[SignalType] = mapped_column(
        enum_column(SignalType, length=32), nullable=False, index=True
    )
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048))
    service_category: Mapped[ServiceCategory] = mapped_column(
        enum_column(ServiceCategory, length=32), nullable=False, index=True
    )
    country: Mapped[Country] = mapped_column(enum_column(Country, length=2), nullable=False)
    county: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    municipality: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    address_json: Mapped[dict[str, Any] | None] = mapped_column("address", JSON)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    building_identifier: Mapped[str | None] = mapped_column(String(64), index=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    raw_payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    verified: Mapped[VerificationStatus] = mapped_column(
        enum_column(VerificationStatus, length=16),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        index=True,
    )
    metadata_: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSON, nullable=False, default=dict
    )

    @classmethod
    def from_domain(cls, signal: Signal) -> SignalModel:
        return cls(
            id=signal.id,
            signal_type=signal.signal_type,
            source=signal.source,
            source_url=signal.source_url,
            service_category=signal.service_category,
            country=signal.country,
            county=signal.county,
            municipality=signal.municipality,
            address_json=signal.address.model_dump(mode="json") if signal.address else None,
            latitude=signal.coordinates.latitude if signal.coordinates else None,
            longitude=signal.coordinates.longitude if signal.coordinates else None,
            building_identifier=signal.building_identifier,
            timestamp=to_storage_utc(signal.timestamp),
            raw_payload=signal.raw_payload,
            confidence=signal.confidence,
            verified=signal.verified,
            metadata_=signal.metadata,
        )

    def to_domain(self) -> Signal:
        coordinates = (
            Coordinates(latitude=self.latitude, longitude=self.longitude)
            if self.latitude is not None and self.longitude is not None
            else None
        )
        return Signal(
            id=self.id,
            signal_type=self.signal_type,
            source=self.source,
            source_url=self.source_url,
            service_category=self.service_category,
            country=self.country,
            county=self.county,
            municipality=self.municipality,
            address=Address.model_validate(self.address_json) if self.address_json else None,
            coordinates=coordinates,
            building_identifier=self.building_identifier,
            timestamp=assume_utc(self.timestamp),
            raw_payload=self.raw_payload,
            confidence=self.confidence,
            verified=self.verified,
            metadata=self.metadata_,
        )
