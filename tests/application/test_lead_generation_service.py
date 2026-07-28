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


def test_generate_from_matches_is_idempotent_for_identical_evidence() -> None:
    """Production Blocker 1: re-running generation over the exact same evidence (the same
    RuleMatches, correlated the exact same way -- what a scheduled 'sigint pipeline' re-run
    with no new Signals does, since CorrelationService.run() has no incremental filter) must
    not create a second Lead. The pre-fix LeadGenerationService persisted every candidate
    LeadGenerator.generate() returned unconditionally, so calling this twice with the same
    FakeLeadGenerator output would have produced 4 leads, not 2 -- this is exactly the
    scenario that would fail against the old implementation.
    """
    lead_repo = InMemoryLeadRepository()
    audit_repo = InMemoryAuditLogRepository()
    candidate = make_lead()
    # Same LeadGenerator output every call -- simulates correlation re-finding the identical
    # rule match because the underlying verified Signals have not changed between runs.
    generator = FakeLeadGenerator([candidate])
    service = LeadGenerationService(generator, lead_repo, audit_repo)

    first_run = service.generate_from_matches([])
    second_run = service.generate_from_matches([])

    assert len(first_run) == 1
    assert second_run == [], "the second run must persist nothing new"
    assert lead_repo.count() == 1, "exactly one Lead must exist, not a duplicate"
    assert len(audit_repo.list_all(event_type=AuditEventType.LEAD_GENERATED, limit=10)) == 1


def test_generate_from_matches_remains_idempotent_across_many_consecutive_runs() -> None:
    lead_repo = InMemoryLeadRepository()
    audit_repo = InMemoryAuditLogRepository()
    generator = FakeLeadGenerator([make_lead()])
    service = LeadGenerationService(generator, lead_repo, audit_repo)

    for _ in range(10):
        service.generate_from_matches([])

    assert lead_repo.count() == 1
    assert len(audit_repo.list_all(event_type=AuditEventType.LEAD_GENERATED, limit=10)) == 1


def test_generate_from_matches_creates_a_new_lead_for_genuinely_new_evidence() -> None:
    """A different supporting_signal_ids set (new Signals became part of the evidence)
    is a different real-world identity and must still be generated normally."""
    lead_repo = InMemoryLeadRepository()
    audit_repo = InMemoryAuditLogRepository()
    first_candidate = make_lead()
    service = LeadGenerationService(FakeLeadGenerator([first_candidate]), lead_repo, audit_repo)
    service.generate_from_matches([])
    assert lead_repo.count() == 1

    second_candidate = make_lead()  # make_lead() defaults to a fresh random signal-id pair
    assert second_candidate.supporting_signal_ids != first_candidate.supporting_signal_ids
    service_for_new_evidence = LeadGenerationService(
        FakeLeadGenerator([second_candidate]), lead_repo, audit_repo
    )
    persisted = service_for_new_evidence.generate_from_matches([])

    assert len(persisted) == 1
    assert lead_repo.count() == 2, "new evidence must still produce a new Lead"
    assert len(audit_repo.list_all(event_type=AuditEventType.LEAD_GENERATED, limit=10)) == 2


def test_repository_level_add_enforces_uniqueness_even_without_a_pre_check() -> None:
    """LeadRepository.add() itself now enforces identity uniqueness (a real unique
    database constraint in SQLiteLeadRepository, mirrored here for the in-memory double)
    -- calling add() twice with two distinct Lead records (different ids) that share the
    same lead_type/supporting_signal_ids returns the SAME (first) Lead both times, rather
    than creating a duplicate. This is what closes the concurrency race
    LeadGenerationService's find_by_identity pre-check alone could not: two callers can
    both pass that check before either calls add(), but add() itself is now the actual
    safety net.
    """
    lead_repo = InMemoryLeadRepository()
    shared_signal_ids = make_lead().supporting_signal_ids
    first = make_lead(supporting_signal_ids=shared_signal_ids)
    second = make_lead(supporting_signal_ids=shared_signal_ids)
    assert first.id != second.id  # two distinct records, identical business content

    stored_first = lead_repo.add(first)
    stored_second = lead_repo.add(second)

    assert lead_repo.count() == 1, "add() must not create a second Lead for the same identity"
    assert stored_second.id == stored_first.id, "the losing add() must return the existing Lead"
