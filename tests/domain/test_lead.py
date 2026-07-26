"""Tests for app.domain.lead.Lead."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

import pytest
from app.domain.enums import VerificationStatus
from app.domain.value_objects import EstimatedLocation
from pydantic import ValidationError

from tests.fixtures.factories import make_lead


def test_valid_lead_defaults_to_unverified() -> None:
    lead = make_lead()
    assert lead.verification_status == VerificationStatus.UNVERIFIED
    assert len(lead.supporting_signal_ids) >= 2


def test_single_supporting_signal_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_lead(supporting_signal_ids=[uuid4()])


def test_duplicate_supporting_signal_ids_are_rejected() -> None:
    shared_id = uuid4()
    with pytest.raises(ValidationError):
        make_lead(supporting_signal_ids=[shared_id, shared_id])


def test_estimated_location_municipality_mismatch_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_lead(
            county="Harju",
            municipality="Tallinn",
            estimated_location=EstimatedLocation(county="Harju", municipality="Tartu"),
        )


def test_naive_created_at_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_lead(created_at=datetime.now())


def test_empty_reasoning_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_lead(reasoning="short")


def test_with_verification_returns_a_new_instance() -> None:
    original = make_lead()
    verified = original.with_verification(VerificationStatus.VERIFIED)

    assert original.verification_status == VerificationStatus.UNVERIFIED
    assert verified.verification_status == VerificationStatus.VERIFIED
    assert verified.id == original.id
