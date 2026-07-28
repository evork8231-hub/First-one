"""ORM mapping for the Lead entity."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base
from app.database.column_types import assume_utc, enum_column, to_storage_utc
from app.domain.enums import Country, LeadPriority, ServiceCategory, VerificationStatus
from app.domain.lead import Lead
from app.domain.value_objects import EstimatedLocation


class LeadModel(Base):
    """Persistence row for a generated Lead. Stored independently from signals."""

    __tablename__ = "leads"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    lead_type: Mapped[ServiceCategory] = mapped_column(
        enum_column(ServiceCategory, length=32), nullable=False, index=True
    )
    supporting_signal_ids: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    #: sha256(lead_type + sorted supporting_signal_ids) -- see
    #: app.domain.lead.compute_lead_identity_key. A real, database-level
    #: unique constraint (not just an application-level check) so two
    #: concurrent processes racing to persist a Lead for the exact same
    #: evidence can never both succeed -- the second insert raises
    #: IntegrityError, which SQLiteLeadRepository.add() catches and
    #: resolves by returning the Lead that won the race.
    identity_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    country: Mapped[Country] = mapped_column(enum_column(Country, length=2), nullable=False)
    county: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    municipality: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    estimated_location: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    estimated_confidence: Mapped[float] = mapped_column(Float, nullable=False)
    intent_score: Mapped[float] = mapped_column(Float, nullable=False)
    priority: Mapped[LeadPriority] = mapped_column(
        enum_column(LeadPriority, length=16), nullable=False, index=True
    )
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    verification_status: Mapped[VerificationStatus] = mapped_column(
        enum_column(VerificationStatus, length=16),
        nullable=False,
        default=VerificationStatus.UNVERIFIED,
        index=True,
    )

    @classmethod
    def from_domain(cls, lead: Lead) -> LeadModel:
        return cls(
            id=lead.id,
            lead_type=lead.lead_type,
            supporting_signal_ids=[str(signal_id) for signal_id in lead.supporting_signal_ids],
            identity_key=lead.identity_key,
            country=lead.country,
            county=lead.county,
            municipality=lead.municipality,
            estimated_location=lead.estimated_location.model_dump(mode="json"),
            estimated_confidence=lead.estimated_confidence,
            intent_score=lead.intent_score,
            priority=lead.priority,
            reasoning=lead.reasoning,
            created_at=to_storage_utc(lead.created_at),
            verification_status=lead.verification_status,
        )

    def to_domain(self) -> Lead:
        return Lead(
            id=self.id,
            lead_type=self.lead_type,
            supporting_signal_ids=[UUID(signal_id) for signal_id in self.supporting_signal_ids],
            country=self.country,
            county=self.county,
            municipality=self.municipality,
            estimated_location=EstimatedLocation.model_validate(self.estimated_location),
            estimated_confidence=self.estimated_confidence,
            intent_score=self.intent_score,
            priority=self.priority,
            reasoning=self.reasoning,
            created_at=assume_utc(self.created_at),
            verification_status=self.verification_status,
        )
