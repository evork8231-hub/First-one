"""Tests for app.application.services.lead_generation_service.LeadGenerationService."""

from __future__ import annotations

from app.application.services.lead_generation_service import LeadGenerationService
from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository

from tests.fixtures.factories import make_lead
from tests.fixtures.fakes import FakeLeadGenerator


def test_generate_from_matches_persists_leads_and_logs_audit() -> None:
    lead_repo = InMemoryLeadRepository()
    audit_repo = InMemoryAuditLogRepository()
    generator = FakeLeadGenerator([make_lead(), make_lead()])
    service = LeadGenerationService(generator, lead_repo, audit_repo)

    persisted = service.generate_from_matches([])

    assert len(persisted) == 2
    assert len(lead_repo.list_all(limit=10)) == 2
    event_types = [entry.event_type for entry in audit_repo.list_all(limit=10)]
    assert event_types.count(AuditEventType.LEAD_GENERATED) == 2
