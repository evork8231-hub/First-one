"""Tests for app.verification.duplicate_signal_verifier.DuplicateSignalVerifier."""

from __future__ import annotations

import asyncio

from app.config.settings import DuplicateDetectionConfig
from app.domain.enums import VerificationStatus
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.verification.duplicate_detector import DuplicateDetector
from app.verification.duplicate_signal_verifier import DuplicateSignalVerifier

from tests.fixtures.factories import make_signal


def _verifier(
    repo: InMemorySignalRepository, **config_overrides: object
) -> DuplicateSignalVerifier:
    config = DuplicateDetectionConfig(**config_overrides)  # type: ignore[arg-type]
    return DuplicateSignalVerifier(repo, DuplicateDetector(config), config)


def test_verifies_a_signal_with_no_existing_duplicates() -> None:
    repo = InMemorySignalRepository()
    signal = repo.add(make_signal(building_identifier="EHR-1"))

    result = asyncio.run(_verifier(repo).verify(signal))

    assert result.status == VerificationStatus.VERIFIED
    assert result.evidence["duplicate_status"] == "unique"


def test_rejects_an_exact_duplicate() -> None:
    repo = InMemorySignalRepository()
    existing = repo.add(make_signal(building_identifier="EHR-1"))
    new_signal = repo.add(make_signal(building_identifier="EHR-1"))

    result = asyncio.run(_verifier(repo).verify(new_signal))

    assert result.status == VerificationStatus.REJECTED
    assert result.evidence["duplicate_status"] == "duplicate"
    assert result.evidence["matched_signal_id"] == str(existing.id)


def test_possible_duplicate_flagged_but_verified_by_default_policy() -> None:
    repo = InMemorySignalRepository()
    from app.domain.value_objects import Address

    repo.add(
        make_signal(
            building_identifier=None,
            address=Address(
                county="Harju", municipality="Tallinn", street="Pikk", house_number="5"
            ),
        )
    )
    new_signal = repo.add(
        make_signal(
            building_identifier=None,
            address=Address(county="Harju", municipality="Tallinn", street="Lai", house_number="5"),
        )
    )

    verifier = _verifier(
        repo,
        fuzzy_duplicate_threshold=99.0,
        fuzzy_possible_duplicate_threshold=30.0,
        possible_duplicate_policy="flag",
    )
    result = asyncio.run(verifier.verify(new_signal))

    assert result.status == VerificationStatus.VERIFIED
    assert result.evidence["duplicate_status"] == "possible_duplicate"


def test_possible_duplicate_rejected_when_policy_is_reject() -> None:
    repo = InMemorySignalRepository()
    from app.domain.value_objects import Address

    repo.add(
        make_signal(
            building_identifier=None,
            address=Address(
                county="Harju", municipality="Tallinn", street="Pikk", house_number="5"
            ),
        )
    )
    new_signal = repo.add(
        make_signal(
            building_identifier=None,
            address=Address(county="Harju", municipality="Tallinn", street="Lai", house_number="5"),
        )
    )

    verifier = _verifier(
        repo,
        fuzzy_duplicate_threshold=99.0,
        fuzzy_possible_duplicate_threshold=30.0,
        possible_duplicate_policy="reject",
    )
    result = asyncio.run(verifier.verify(new_signal))

    assert result.status == VerificationStatus.REJECTED


def test_disabled_duplicate_detection_always_verifies() -> None:
    repo = InMemorySignalRepository()
    existing = repo.add(make_signal(building_identifier="EHR-1"))
    new_signal = repo.add(make_signal(building_identifier="EHR-1"))

    verifier = _verifier(repo, enabled=False)
    result = asyncio.run(verifier.verify(new_signal))

    assert result.status == VerificationStatus.VERIFIED
    assert (
        existing.building_identifier == new_signal.building_identifier
    )  # sanity: would've matched


def test_verifier_name_is_stable() -> None:
    repo = InMemorySignalRepository()
    assert _verifier(repo).name == "duplicate_signal_verifier"
