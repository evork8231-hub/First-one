"""SQLite-backed LeadRepository implementation."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.application.interfaces.repositories import LeadRepository
from app.core.exceptions import EntityNotFoundError
from app.database.models.lead_model import LeadModel
from app.database.session import session_scope
from app.domain.enums import ServiceCategory, VerificationStatus
from app.domain.lead import Lead, compute_lead_identity_key


class SQLiteLeadRepository(LeadRepository):
    """Persists Leads to a SQLite (or any SQLAlchemy-supported) database."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def add(self, lead: Lead) -> Lead:
        """Persist ``lead``, or -- if another writer already persisted a Lead with the
        exact same identity (``lead_type`` + ``supporting_signal_ids``) first -- return
        that existing Lead instead.

        ``leads.identity_key`` carries a real, database-level unique index (see
        ``app.database.models.lead_model.LeadModel``), so this is safe even against a
        second, concurrent writer racing on the exact same insert: whichever commits
        first wins, and the loser's ``IntegrityError`` is caught here and resolved by
        re-reading the winner -- never by silently creating a duplicate, and never by
        raising a raw database error out to the caller for a condition that isn't
        actually a failure (the Lead this call wanted to exist now exists).
        """
        try:
            with session_scope(self._session_factory) as session:
                model = LeadModel.from_domain(lead)
                session.add(model)
                session.flush()
                return model.to_domain()
        except IntegrityError:
            existing = self.find_by_identity(lead.lead_type, lead.supporting_signal_ids)
            if existing is not None:
                return existing
            raise

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
        identity_key = compute_lead_identity_key(lead_type, supporting_signal_ids)
        with session_scope(self._session_factory) as session:
            # A single indexed equality lookup against the same identity_key
            # column the unique constraint enforces -- see LeadModel -- so
            # this check and the constraint that backs add() can never
            # disagree about what "the same identity" means.
            stmt = select(LeadModel).where(LeadModel.identity_key == identity_key)
            model = session.scalars(stmt).one_or_none()
            return model.to_domain() if model is not None else None
