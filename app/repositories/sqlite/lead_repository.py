"""SQLite-backed LeadRepository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.repositories import LeadRepository
from app.core.exceptions import EntityNotFoundError
from app.database.models.lead_model import LeadModel
from app.database.session import session_scope
from app.domain.enums import ServiceCategory, VerificationStatus
from app.domain.lead import Lead


class SQLiteLeadRepository(LeadRepository):
    """Persists Leads to a SQLite (or any SQLAlchemy-supported) database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, lead: Lead) -> Lead:
        with session_scope(self._session_factory) as session:
            model = LeadModel.from_domain(lead)
            session.add(model)
            session.flush()
            return model.to_domain()

    def get_by_id(self, lead_id: UUID) -> Lead | None:
        with session_scope(self._session_factory) as session:
            model = session.get(LeadModel, lead_id)
            return model.to_domain() if model is not None else None

    def list_all(
        self,
        *,
        lead_type: ServiceCategory | None = None,
        verification_status: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Lead]:
        with session_scope(self._session_factory) as session:
            stmt = select(LeadModel)
            if lead_type is not None:
                stmt = stmt.where(LeadModel.lead_type == lead_type)
            if verification_status is not None:
                stmt = stmt.where(LeadModel.verification_status == verification_status)
            if county is not None:
                stmt = stmt.where(LeadModel.county == county)
            if municipality is not None:
                stmt = stmt.where(LeadModel.municipality == municipality)
            stmt = stmt.order_by(LeadModel.created_at.desc()).limit(limit).offset(offset)
            return [model.to_domain() for model in session.scalars(stmt)]

    def update_verification_status(self, lead_id: UUID, status: VerificationStatus) -> Lead:
        with session_scope(self._session_factory) as session:
            model = session.get(LeadModel, lead_id)
            if model is None:
                raise EntityNotFoundError(f"No lead found with id {lead_id}.")
            model.verification_status = status
            session.flush()
            return model.to_domain()

    def count(
        self,
        *,
        lead_type: ServiceCategory | None = None,
        verification_status: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
    ) -> int:
        with session_scope(self._session_factory) as session:
            stmt = select(func.count()).select_from(LeadModel)
            if lead_type is not None:
                stmt = stmt.where(LeadModel.lead_type == lead_type)
            if verification_status is not None:
                stmt = stmt.where(LeadModel.verification_status == verification_status)
            if county is not None:
                stmt = stmt.where(LeadModel.county == county)
            if municipality is not None:
                stmt = stmt.where(LeadModel.municipality == municipality)
            return session.scalar(stmt) or 0

    def list_referencing_signal_ids(self, signal_ids: Sequence[UUID]) -> list[Lead]:
        if not signal_ids:
            return []
        wanted = {str(signal_id) for signal_id in signal_ids}
        with session_scope(self._session_factory) as session:
            stmt = select(LeadModel)
            # supporting_signal_ids is a JSON list column (see LeadModel) with
            # no per-element index -- Leads are a small, curated output (never
            # a high-volume table like Signals), so an in-Python intersection
            # over every stored Lead is simple, portable across SQLAlchemy
            # dialects, and avoids depending on SQLite's JSON1 extension.
            # Revisit with a real query if Lead volume ever makes this slow.
            return [
                model.to_domain()
                for model in session.scalars(stmt)
                if wanted.intersection(model.supporting_signal_ids)
            ]

    def find_by_identity(
        self, lead_type: ServiceCategory, supporting_signal_ids: Sequence[UUID]
    ) -> Lead | None:
        wanted = {str(signal_id) for signal_id in supporting_signal_ids}
        with session_scope(self._session_factory) as session:
            # Scoped by lead_type (indexed) at the SQL layer; the exact-set
            # comparison itself is done in Python for the same reason
            # list_referencing_signal_ids does -- see that method's comment.
            stmt = select(LeadModel).where(LeadModel.lead_type == lead_type)
            for model in session.scalars(stmt):
                if set(model.supporting_signal_ids) == wanted:
                    return model.to_domain()
            return None
