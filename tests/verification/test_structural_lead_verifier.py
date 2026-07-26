"""Tests for app.verification.structural_lead_verifier.StructuralLeadVerifier.

Covers the phase's lead-verification requirements: supporting signals
exist, are themselves verified, and the lead's confidence exceeds a
configured threshold. ("Correlation rule succeeded" is guaranteed by
construction -- app.lead_generation.generator.LeadGenerator is the only
code path that builds a Lead, and it only does so from a matched Rule.)
"""

from __future__ import annotations

import asyncio

from app.domain.enums import VerificationStatus
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.verification.structural_lead_verifier import StructuralLeadVerifier

from tests.fixtures.factories import make_lead, make_signal


def test_verifies_a_lead_backed_by_verified_signals() -> None:
    repo = InMemorySignalRepository()
    s1 = repo.add(make_signal(verified=VerificationStatus.VERIFIED))
    s2 = repo.add(make_signal(verified=VerificationStatus.VERIFIED))
    lead = make_lead(supporting_signal_ids=[s1.id, s2.id], estimated_confidence=0.8)

    result = asyncio.run(StructuralLeadVerifier(repo, min_confidence=0.5).verify(lead))

    assert result.status == VerificationStatus.VERIFIED


def test_rejects_when_a_supporting_signal_is_missing_from_storage() -> None:
    repo = InMemorySignalRepository()
    s1 = repo.add(make_signal(verified=VerificationStatus.VERIFIED))
    from uuid import uuid4

    lead = make_lead(supporting_signal_ids=[s1.id, uuid4()], estimated_confidence=0.8)

    result = asyncio.run(StructuralLeadVerifier(repo, min_confidence=0.0).verify(lead))

    assert result.status == VerificationStatus.REJECTED
    assert "do not exist" in result.reason


def test_rejects_when_a_supporting_signal_is_not_itself_verified() -> None:
    repo = InMemorySignalRepository()
    s1 = repo.add(make_signal(verified=VerificationStatus.VERIFIED))
    s2 = repo.add(make_signal(verified=VerificationStatus.UNVERIFIED))
    lead = make_lead(supporting_signal_ids=[s1.id, s2.id], estimated_confidence=0.8)

    result = asyncio.run(StructuralLeadVerifier(repo, min_confidence=0.0).verify(lead))

    assert result.status == VerificationStatus.REJECTED
    assert "not themselves VERIFIED" in result.reason


def test_rejects_when_confidence_is_below_configured_threshold() -> None:
    repo = InMemorySignalRepository()
    s1 = repo.add(make_signal(verified=VerificationStatus.VERIFIED))
    s2 = repo.add(make_signal(verified=VerificationStatus.VERIFIED))
    lead = make_lead(supporting_signal_ids=[s1.id, s2.id], estimated_confidence=0.2)

    result = asyncio.run(StructuralLeadVerifier(repo, min_confidence=0.5).verify(lead))

    assert result.status == VerificationStatus.REJECTED
    assert "estimated_confidence" in result.reason


def test_verifier_name_is_stable() -> None:
    repo = InMemorySignalRepository()
    assert StructuralLeadVerifier(repo).name == "structural_lead_verifier"
