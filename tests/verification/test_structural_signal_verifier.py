"""Tests for app.verification.structural_signal_verifier.StructuralSignalVerifier."""

from __future__ import annotations

import asyncio

import pytest
from app.config.settings import CoordinateBounds
from app.domain.enums import VerificationStatus
from app.domain.value_objects import Address, Coordinates
from app.verification.structural_signal_verifier import StructuralSignalVerifier

from tests.fixtures.factories import make_signal

# A real point inside Estonia (Tallinn) and one clearly outside (Helsinki, Finland).
_TALLINN = Coordinates(latitude=59.437, longitude=24.7536)
_HELSINKI = Coordinates(latitude=60.1699, longitude=24.9384)


def test_accepts_a_well_formed_signal() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.5)
    result = asyncio.run(verifier.verify(make_signal(confidence=0.9)))
    assert result.status == VerificationStatus.VERIFIED


def test_rejects_confidence_below_floor() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.8)
    result = asyncio.run(verifier.verify(make_signal(confidence=0.5)))
    assert result.status == VerificationStatus.REJECTED
    assert "confidence" in result.reason


def test_rejects_empty_raw_payload() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(raw_payload={})
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.REJECTED
    assert "raw_payload" in result.reason


def test_rejects_malformed_source_url() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(source_url="ftp://not-http.example")
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.REJECTED
    assert "source_url" in result.reason


def test_rejects_coordinates_outside_estonia() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(coordinates=_HELSINKI)
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.REJECTED
    assert "outside Estonia" in result.reason


def test_accepts_coordinates_inside_estonia() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(coordinates=_TALLINN)
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.VERIFIED


def test_custom_coordinate_bounds_are_respected() -> None:
    # A tiny bounding box that excludes Tallinn.
    narrow_bounds = CoordinateBounds(
        min_latitude=58.0, max_latitude=58.5, min_longitude=25.0, max_longitude=25.5
    )
    verifier = StructuralSignalVerifier(min_confidence=0.0, coordinate_bounds=narrow_bounds)
    result = asyncio.run(verifier.verify(make_signal(coordinates=_TALLINN)))
    assert result.status == VerificationStatus.REJECTED


def test_require_coordinates_rejects_signal_without_any() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0, require_coordinates=True)
    result = asyncio.run(verifier.verify(make_signal(coordinates=None)))
    assert result.status == VerificationStatus.REJECTED
    assert "coordinates are required" in result.reason


def test_coordinates_not_required_by_default() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    result = asyncio.run(verifier.verify(make_signal(coordinates=None)))
    assert result.status == VerificationStatus.VERIFIED


def test_rejects_malformed_postal_code() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(
        address=Address(county="Harju", municipality="Tallinn", postal_code="ABCDE")
    )
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.REJECTED
    assert "postal_code" in result.reason


def test_accepts_well_formed_postal_code() -> None:
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(
        address=Address(county="Harju", municipality="Tallinn", postal_code="10111")
    )
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.VERIFIED


def test_never_repairs_or_guesses_missing_address_components() -> None:
    """An address with only county/municipality (no street) is not 'fixed up' -- it passes as-is."""
    verifier = StructuralSignalVerifier(min_confidence=0.0)
    signal = make_signal(address=Address(county="Harju", municipality="Tallinn"))
    result = asyncio.run(verifier.verify(signal))
    assert result.status == VerificationStatus.VERIFIED
    assert signal.address is not None
    assert signal.address.street is None  # untouched, not fabricated


def test_verifier_name_is_stable() -> None:
    assert StructuralSignalVerifier().name == "structural_signal_verifier"


def test_constructor_rejects_invalid_min_confidence() -> None:
    with pytest.raises(ValueError):
        StructuralSignalVerifier(min_confidence=1.5)
