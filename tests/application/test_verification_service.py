"""Tests for app.application.services.verification_service.VerificationService."""

from __future__ import annotations

import asyncio

import pytest
from app.application.services.verification_service import VerificationService
from app.core.exceptions import EntityNotFoundError, VerificationError
from app.domain.enums import VerificationStatus
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository

from tests.fixtures.factories import make_lead, make_signal
from tests.fixtures.fakes import FakeLeadVerifier, FakeSignalVerifier


def _build_service(signal_verifiers, lead_verifiers):
    signal_repo = InMemorySignalRepository()
    lead_repo = InMemoryLeadRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = VerificationService(
        signal_repo, lead_repo, audit_repo, signal_verifiers, lead_verifiers
    )
    return service, signal_repo, lead_repo, audit_repo


def test_verify_signal_verified_when_all_verifiers_agree() -> None:
    service, signal_repo, _, _ = _build_service(
        [FakeSignalVerifier(VerificationStatus.VERIFIED)], []
    )
    signal = signal_repo.add(make_signal(verified=VerificationStatus.UNVERIFIED))

    result = asyncio.run(service.verify_signal(signal.id))

    assert result.verified == VerificationStatus.VERIFIED
    assert signal_repo.get_by_id(signal.id).verified == VerificationStatus.VERIFIED


def test_verify_signal_rejected_if_any_verifier_rejects() -> None:
    service, signal_repo, _, _ = _build_service(
        [
            FakeSignalVerifier(VerificationStatus.VERIFIED),
            FakeSignalVerifier(VerificationStatus.REJECTED),
        ],
        [],
    )
    signal = signal_repo.add(make_signal(verified=VerificationStatus.UNVERIFIED))

    result = asyncio.run(service.verify_signal(signal.id))

    assert result.verified == VerificationStatus.REJECTED


def test_verify_signal_missing_raises_not_found() -> None:
    service, _, _, _ = _build_service([FakeSignalVerifier(VerificationStatus.VERIFIED)], [])
    with pytest.raises(EntityNotFoundError):
        asyncio.run(service.verify_signal(make_signal().id))


def test_verify_signal_with_no_verifiers_raises() -> None:
    service, signal_repo, _, _ = _build_service([], [])
    signal = signal_repo.add(make_signal())
    with pytest.raises(VerificationError):
        asyncio.run(service.verify_signal(signal.id))


def test_verify_lead_verified_when_all_verifiers_agree() -> None:
    service, _, lead_repo, _ = _build_service([], [FakeLeadVerifier(VerificationStatus.VERIFIED)])
    lead = lead_repo.add(make_lead())

    result = asyncio.run(service.verify_lead(lead.id))

    assert result.verification_status == VerificationStatus.VERIFIED
