"""Tests for app.verification.weather_bridge_dedup."""

from __future__ import annotations

from datetime import timedelta

from app.repositories.in_memory.configuration_repository import InMemoryConfigurationRepository
from app.utils.time import utc_now
from app.verification.weather_bridge_dedup import WeatherBridgeDeduplicator, compute_fingerprint

from tests.fixtures.factories import make_weather_event


def test_compute_fingerprint_is_stable_for_identical_fields() -> None:
    started = utc_now() - timedelta(days=1)
    ended = started + timedelta(hours=3)
    event_a = make_weather_event(started_at=started, ended_at=ended)
    event_b = make_weather_event(started_at=started, ended_at=ended)

    assert event_a.id != event_b.id  # distinct rows...
    assert compute_fingerprint(event_a) == compute_fingerprint(event_b)  # ...same real event


def test_compute_fingerprint_differs_by_county() -> None:
    event_a = make_weather_event(county="Harju", municipality="Tallinn")
    event_b = make_weather_event(county="Tartu", municipality="Tartu")
    assert compute_fingerprint(event_a) != compute_fingerprint(event_b)


def test_compute_fingerprint_differs_by_event_type() -> None:
    from app.domain.enums import WeatherEventType

    event_a = make_weather_event(event_type=WeatherEventType.HAILSTORM)
    event_b = make_weather_event(event_type=WeatherEventType.HIGH_WIND)
    assert compute_fingerprint(event_a) != compute_fingerprint(event_b)


def test_compute_fingerprint_differs_by_severity() -> None:
    event_a = make_weather_event(severity=0.5)
    event_b = make_weather_event(severity=0.9)
    assert compute_fingerprint(event_a) != compute_fingerprint(event_b)


def test_compute_fingerprint_differs_by_source() -> None:
    event_a = make_weather_event(source="source_a")
    event_b = make_weather_event(source="source_b")
    assert compute_fingerprint(event_a) != compute_fingerprint(event_b)


def test_compute_fingerprint_differs_by_timestamps() -> None:
    now = utc_now()
    event_a = make_weather_event(started_at=now - timedelta(days=1), ended_at=now)
    event_b = make_weather_event(
        started_at=now - timedelta(days=2), ended_at=now - timedelta(days=1)
    )
    assert compute_fingerprint(event_a) != compute_fingerprint(event_b)


def test_deduplicator_reports_not_a_duplicate_before_first_mark() -> None:
    deduplicator = WeatherBridgeDeduplicator(InMemoryConfigurationRepository())
    event = make_weather_event()

    assert deduplicator.is_duplicate(event) is False


def test_deduplicator_reports_a_duplicate_after_marking() -> None:
    config_repo = InMemoryConfigurationRepository()
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    event = make_weather_event()

    deduplicator.mark_bridged(event, signal_id="11111111-1111-1111-1111-111111111111")

    assert deduplicator.is_duplicate(event) is True


def test_deduplicator_treats_a_re_collected_identical_event_as_a_duplicate() -> None:
    """The core scenario: the same real event, collected again with a fresh WeatherEvent.id."""
    config_repo = InMemoryConfigurationRepository()
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    started = utc_now() - timedelta(days=1)
    ended = started + timedelta(hours=3)
    first_collection = make_weather_event(started_at=started, ended_at=ended)
    second_collection = make_weather_event(started_at=started, ended_at=ended)
    assert first_collection.id != second_collection.id

    deduplicator.mark_bridged(first_collection, signal_id="11111111-1111-1111-1111-111111111111")

    assert deduplicator.is_duplicate(second_collection) is True


def test_deduplicator_does_not_flag_genuinely_different_events() -> None:
    config_repo = InMemoryConfigurationRepository()
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    event_a = make_weather_event(county="Harju", municipality="Tallinn")
    event_b = make_weather_event(county="Tartu", municipality="Tartu")

    deduplicator.mark_bridged(event_a, signal_id="11111111-1111-1111-1111-111111111111")

    assert deduplicator.is_duplicate(event_b) is False


def test_deduplicator_stores_fingerprint_under_a_unique_constrained_key() -> None:
    """ConfigurationModel.key carries a real DB-level unique constraint; verify the key shape."""
    config_repo = InMemoryConfigurationRepository()
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    event = make_weather_event()

    deduplicator.mark_bridged(event, signal_id="11111111-1111-1111-1111-111111111111")

    [entry] = config_repo.list_all()
    assert entry.key.startswith("weather_bridge_fingerprint.")
    assert entry.value["weather_event_id"] == str(event.id)
    assert entry.value["signal_id"] == "11111111-1111-1111-1111-111111111111"
