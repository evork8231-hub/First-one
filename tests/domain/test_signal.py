"""Tests for app.domain.signal.Signal."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from app.domain.enums import VerificationStatus
from app.domain.value_objects import Address
from pydantic import ValidationError

from tests.fixtures.factories import make_signal


def test_valid_signal_defaults_to_unverified() -> None:
    signal = make_signal(verified=VerificationStatus.UNVERIFIED)
    assert signal.verified == VerificationStatus.UNVERIFIED
    assert signal.id is not None


def test_naive_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_signal(timestamp=datetime.now())


def test_future_timestamp_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_signal(timestamp=datetime.now(UTC) + timedelta(days=1))


def test_confidence_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_signal(confidence=1.5)


def test_address_county_mismatch_is_rejected() -> None:
    with pytest.raises(ValidationError):
        make_signal(
            county="Harju",
            municipality="Tallinn",
            address=Address(county="Tartu", municipality="Tallinn"),
        )


def test_address_matching_county_is_accepted() -> None:
    signal = make_signal(
        county="Harju",
        municipality="Tallinn",
        address=Address(county="Harju", municipality="Tallinn", street="Pikk", house_number="1"),
    )
    assert signal.address is not None
    assert signal.address.street == "Pikk"


def test_with_verification_returns_a_new_instance() -> None:
    original = make_signal(verified=VerificationStatus.UNVERIFIED)
    verified = original.with_verification(VerificationStatus.VERIFIED)

    assert original.verified == VerificationStatus.UNVERIFIED
    assert verified.verified == VerificationStatus.VERIFIED
    assert verified.id == original.id


def test_signal_is_immutable() -> None:
    signal = make_signal()
    with pytest.raises((ValidationError, TypeError)):
        signal.confidence = 0.1  # type: ignore[misc]
