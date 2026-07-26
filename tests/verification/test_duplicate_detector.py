"""Tests for app.verification.duplicate_detector.DuplicateDetector."""

from __future__ import annotations

from app.config.settings import DuplicateDetectionConfig
from app.domain.value_objects import Address, Coordinates
from app.verification.duplicate_detector import DuplicateDetector, DuplicateStatus

from tests.fixtures.factories import make_signal


def _detector(**overrides: object) -> DuplicateDetector:
    return DuplicateDetector(DuplicateDetectionConfig(**overrides))  # type: ignore[arg-type]


def test_unique_when_no_candidates() -> None:
    signal = make_signal()
    result = _detector().check(signal, [])
    assert result.status == DuplicateStatus.UNIQUE


def test_unique_when_no_candidate_shares_anything() -> None:
    signal = make_signal(building_identifier="AAA")
    other = make_signal(building_identifier="BBB")
    result = _detector().check(signal, [other])
    assert result.status == DuplicateStatus.UNIQUE


def test_exact_building_identifier_match_is_duplicate() -> None:
    signal = make_signal(building_identifier="EHR-123")
    other = make_signal(building_identifier="EHR-123")
    result = _detector().check(signal, [other])
    assert result.status == DuplicateStatus.DUPLICATE
    assert result.matched_signal_id == other.id


def test_ignores_itself_in_the_candidate_pool() -> None:
    signal = make_signal(building_identifier="EHR-123")
    result = _detector().check(signal, [signal])
    assert result.status == DuplicateStatus.UNIQUE


def test_only_compares_within_the_same_signal_type() -> None:
    from app.domain.enums import SignalType

    signal = make_signal(signal_type=SignalType.BUILDING_RECORD, building_identifier="EHR-123")
    other = make_signal(signal_type=SignalType.ROOF_MENTION, building_identifier="EHR-123")
    result = _detector().check(signal, [other])
    assert result.status == DuplicateStatus.UNIQUE


def test_coordinates_within_radius_are_duplicate() -> None:
    detector = _detector(coordinate_duplicate_radius_meters=50.0)
    signal = make_signal(coordinates=Coordinates(latitude=59.4370, longitude=24.7536))
    # ~11 meters away.
    other = make_signal(coordinates=Coordinates(latitude=59.4371, longitude=24.7536))
    result = detector.check(signal, [other])
    assert result.status == DuplicateStatus.DUPLICATE
    assert result.matched_signal_id == other.id


def test_coordinates_outside_radius_are_not_duplicate_by_distance_alone() -> None:
    detector = _detector(coordinate_duplicate_radius_meters=5.0)
    signal = make_signal(
        county="Harju",
        municipality="Tallinn",
        coordinates=Coordinates(latitude=59.4370, longitude=24.7536),
    )
    # A different municipality entirely, so the fuzzy address fallback cannot
    # coincidentally match on identical default text -- isolates the distance check.
    other = make_signal(
        county="Tartu",
        municipality="Tartu",
        coordinates=Coordinates(latitude=59.5000, longitude=24.9000),
    )
    result = detector.check(signal, [other])
    assert result.status == DuplicateStatus.UNIQUE


def test_phone_number_exact_match_is_duplicate() -> None:
    signal = make_signal(metadata={"phone": "+372 5555 1234"})
    other = make_signal(metadata={"phone": "+372 5555 1234"})
    result = _detector().check(signal, [other])
    assert result.status == DuplicateStatus.DUPLICATE
    assert result.matched_signal_id == other.id


def test_never_fabricates_a_phone_match_when_absent() -> None:
    signal = make_signal(metadata={})
    other = make_signal(metadata={"phone": "+372 5555 1234"})
    result = _detector().check(signal, [other])
    assert result.status == DuplicateStatus.UNIQUE


def test_fuzzy_address_similarity_above_duplicate_threshold() -> None:
    detector = _detector(fuzzy_duplicate_threshold=90.0, fuzzy_possible_duplicate_threshold=70.0)
    address = Address(county="Harju", municipality="Tallinn", street="Pikk", house_number="5")
    signal = make_signal(address=address)
    other = make_signal(address=address)
    result = detector.check(signal, [other])
    assert result.status == DuplicateStatus.DUPLICATE
    assert result.similarity_score == 100.0


def test_fuzzy_address_similarity_between_thresholds_is_possible_duplicate() -> None:
    detector = _detector(fuzzy_duplicate_threshold=99.0, fuzzy_possible_duplicate_threshold=30.0)
    signal = make_signal(
        address=Address(county="Harju", municipality="Tallinn", street="Pikk", house_number="5")
    )
    other = make_signal(
        address=Address(county="Harju", municipality="Tallinn", street="Lai", house_number="5")
    )
    result = detector.check(signal, [other])
    assert result.status == DuplicateStatus.POSSIBLE_DUPLICATE


def test_configurable_thresholds_change_the_outcome() -> None:
    address = Address(county="Harju", municipality="Tallinn", street="Pikk", house_number="5")
    signal = make_signal(address=address)
    other = make_signal(
        address=Address(county="Harju", municipality="Tallinn", street="Lai", house_number="9")
    )

    strict = _detector(fuzzy_duplicate_threshold=99.9, fuzzy_possible_duplicate_threshold=99.0)
    lenient = _detector(fuzzy_duplicate_threshold=10.0, fuzzy_possible_duplicate_threshold=1.0)

    strict_result = strict.check(signal, [other])
    lenient_result = lenient.check(signal, [other])

    assert strict_result.status == DuplicateStatus.UNIQUE
    assert lenient_result.status == DuplicateStatus.DUPLICATE
