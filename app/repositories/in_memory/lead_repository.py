"""In-memory LeadRepository implementation, used primarily in tests."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.interfaces.repositories import LeadRepository
from app.core.exceptions import EntityNotFoundError
from app.domain.enums import ServiceCategory, VerificationStatus
from app.domain.lead import Lead


class InMemoryLeadRepository(LeadRepository):
    """Stores Leads in a process-local dict. Not safe across processes."""

    def __init__(self) -> None:
        self._leads: dict[UUID, Lead] = {}

    def add(self, lead: Lead) -> Lead:
        self._leads[lead.id] = lead
        return lead

    def get_by_id(self, lead_id: UUID) -> Lead | None:
        return self._leads.get(lead_id)

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
        results = list(self._leads.values())
        if lead_type is not None:
            results = [lead for lead in results if lead.lead_type == lead_type]
        if verification_status is not None:
            results = [lead for lead in results if lead.verification_status == verification_status]
        if county is not None:
            results = [lead for lead in results if lead.county == county]
        if municipality is not None:
            results = [lead for lead in results if lead.municipality == municipality]
        results.sort(key=lambda lead: lead.created_at, reverse=True)
        return results[offset : offset + limit]

    def update_verification_status(self, lead_id: UUID, status: VerificationStatus) -> Lead:
        existing = self._leads.get(lead_id)
        if existing is None:
            raise EntityNotFoundError(f"No lead found with id {lead_id}.")
        updated = existing.with_verification(status)
        self._leads[lead_id] = updated
        return updated

    def count(
        self,
        *,
        lead_type: ServiceCategory | None = None,
        verification_status: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
    ) -> int:
        results = list(self._leads.values())
        if lead_type is not None:
            results = [lead for lead in results if lead.lead_type == lead_type]
        if verification_status is not None:
            results = [lead for lead in results if lead.verification_status == verification_status]
        if county is not None:
            results = [lead for lead in results if lead.county == county]
        if municipality is not None:
            results = [lead for lead in results if lead.municipality == municipality]
        return len(results)

    def list_referencing_signal_ids(self, signal_ids: Sequence[UUID]) -> list[Lead]:
        wanted = set(signal_ids)
        if not wanted:
            return []
        return [
            lead for lead in self._leads.values() if wanted.intersection(lead.supporting_signal_ids)
        ]
