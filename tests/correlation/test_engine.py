"""Tests for app.correlation.engine.CorrelationEngine."""

from __future__ import annotations

import pytest
from app.core.exceptions import CorrelationError
from app.correlation.engine import CorrelationEngine
from app.domain.enums import VerificationStatus
from app.domain.value_objects import Address

from tests.fixtures.factories import make_signal


def test_signals_sharing_building_identifier_are_clustered_together() -> None:
    a = make_signal(building_identifier="EHR-123")
    b = make_signal(building_identifier="EHR-123")
    clusters = CorrelationEngine().correlate([a, b])

    assert len(clusters) == 1
    assert {s.id for s in clusters[0].signals} == {a.id, b.id}
    assert clusters[0].building_identifier == "EHR-123"


def test_signals_sharing_street_address_are_clustered_together() -> None:
    address = Address(county="Harju", municipality="Tallinn", street="Pikk", house_number="5")
    a = make_signal(address=address)
    b = make_signal(address=address)
    clusters = CorrelationEngine().correlate([a, b])

    assert len(clusters) == 1
    assert {s.id for s in clusters[0].signals} == {a.id, b.id}


def test_signals_without_finer_detail_fall_back_to_region_clustering() -> None:
    a = make_signal(county="Harju", municipality="Tallinn")
    b = make_signal(county="Harju", municipality="Tallinn")
    c = make_signal(county="Tartu", municipality="Tartu")

    clusters = CorrelationEngine().correlate([a, b, c])

    assert len(clusters) == 2


def test_unverified_signal_raises_correlation_error() -> None:
    unverified = make_signal(verified=VerificationStatus.UNVERIFIED)
    with pytest.raises(CorrelationError):
        CorrelationEngine().correlate([unverified])
