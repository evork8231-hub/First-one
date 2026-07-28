"""Tests for app.application.services.weather_signal_bridge_service.WeatherSignalBridgeService."""

from __future__ import annotations

from datetime import timedelta

from app.application.services.weather_signal_bridge_service import WeatherSignalBridgeService
from app.config.settings import WeatherSignalBridgeConfig
from app.domain.enums import AuditEventType, ServiceCategory, SignalType
from app.domain.value_objects import Coordinates
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.configuration_repository import InMemoryConfigurationRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_bridge_unit_of_work import (
    InMemoryWeatherBridgeUnitOfWork,
)
from app.utils.time import utc_now
from app.verification.weather_bridge_dedup import WeatherBridgeDeduplicator

from tests.fixtures.factories import make_weather_event


def _service(
    **config_overrides: object,
) -> tuple[
    WeatherSignalBridgeService,
    InMemorySignalRepository,
    InMemoryAuditLogRepository,
    InMemoryConfigurationRepository,
]:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    config_repo = InMemoryConfigurationRepository()
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    uow = InMemoryWeatherBridgeUnitOfWork(signal_repo, config_repo, audit_repo)
    config = WeatherSignalBridgeConfig(**config_overrides)  # type: ignore[arg-type]
    service = WeatherSignalBridgeService(config, deduplicator, uow)
    return service, signal_repo, audit_repo, config_repo


def test_bridge_with_no_events_returns_empty_and_touches_nothing() -> None:
    service, signal_repo, _, _ = _service()
    assert service.bridge([]) == []
    assert signal_repo.count() == 0


def test_bridge_persists_one_weather_event_signal_per_event() -> None:
    service, signal_repo, _, _ = _service()
    event = make_weather_event()

    stored = service.bridge([event])

    assert len(stored) == 1
    signal = stored[0]
    assert signal.signal_type == SignalType.WEATHER_EVENT
    assert signal_repo.get_by_id(signal.id) is not None


def test_bridged_signal_carries_over_the_events_own_location_and_source() -> None:
    service, _, _, _ = _service()
    event = make_weather_event(
        county="Tartu",
        municipality="Tartu",
        source="Ilmateenistus (Estonian Environment Agency Weather Service)",
        source_url="https://example.ee/feed.xml",
        coordinates=Coordinates(latitude=58.38, longitude=26.72),
    )

    [signal] = service.bridge([event])

    assert signal.county == "Tartu"
    assert signal.municipality == "Tartu"
    assert signal.source == event.source
    assert signal.source_url == event.source_url
    assert signal.coordinates == event.coordinates
    assert signal.raw_payload == event.raw_payload


def test_bridged_signal_confidence_and_category_come_from_config_not_the_event() -> None:
    service, _, _, _ = _service(
        service_category=ServiceCategory.SOLAR_INSTALLATION, signal_confidence=0.55
    )
    event = make_weather_event(severity=0.99)  # deliberately different from configured confidence

    [signal] = service.bridge([event])

    assert signal.service_category == ServiceCategory.SOLAR_INSTALLATION
    assert signal.confidence == 0.55  # not event.severity


def test_bridged_signal_timestamp_is_collection_time_not_the_forecast_period() -> None:
    """A future-dated forecast period must not make Signal's timestamp validator reject it."""
    from datetime import UTC, datetime, timedelta

    service, _, _, _ = _service()
    future_start = datetime.now(UTC) + timedelta(days=2)
    event = make_weather_event(started_at=future_start, ended_at=future_start + timedelta(hours=6))

    [signal] = service.bridge([event])  # must not raise

    assert signal.timestamp <= datetime.now(UTC)
    assert signal.metadata["started_at"] == future_start.isoformat()


def test_bridge_metadata_links_back_to_the_source_weather_event() -> None:
    service, _, _, _ = _service()
    event = make_weather_event()

    [signal] = service.bridge([event])

    assert signal.metadata["weather_event_id"] == str(event.id)
    assert signal.metadata["weather_event_type"] == event.event_type.value
    assert signal.metadata["severity"] == event.severity


def test_bridge_writes_one_audit_log_entry_per_event() -> None:
    service, _, audit_repo, _ = _service()
    # Distinct counties (not just distinct auto-generated ids) so the two events are
    # genuinely different real-world occurrences, never accidentally deduplicated.
    events = [make_weather_event(), make_weather_event(county="Pärnu", municipality="Pärnu")]

    service.bridge(events)

    entries = audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10)
    assert len(entries) == 2
    assert all(e.context["source"] == "weather_signal_bridge" for e in entries)


def test_bridge_multiple_events_produces_multiple_independent_signals() -> None:
    service, signal_repo, _, _ = _service()
    events = [make_weather_event(), make_weather_event(county="Pärnu", municipality="Pärnu")]

    stored = service.bridge(events)

    assert len(stored) == 2
    assert signal_repo.count() == 2
    assert {s.county for s in stored} == {"Harju", "Pärnu"}


def test_bridge_skips_the_same_real_event_re_collected_on_a_later_run() -> None:
    """Two separate collector runs reporting the identical occurrence must not double-bridge."""
    service, signal_repo, _, _ = _service()
    started = utc_now() - timedelta(days=1)
    ended = started + timedelta(hours=3)
    first_collection = make_weather_event(started_at=started, ended_at=ended)
    second_collection = make_weather_event(started_at=started, ended_at=ended)
    assert first_collection.id != second_collection.id  # distinct rows, same real event

    first_stored = service.bridge([first_collection])
    second_stored = service.bridge([second_collection])

    assert len(first_stored) == 1
    assert second_stored == []  # skipped as a duplicate, not re-bridged
    assert signal_repo.count() == 1


def test_bridge_skips_a_duplicate_within_the_same_batch() -> None:
    """If a source ever reports the same event twice in one run, only one Signal is created."""
    service, signal_repo, _, _ = _service()
    started = utc_now() - timedelta(days=1)
    ended = started + timedelta(hours=3)
    event_a = make_weather_event(started_at=started, ended_at=ended)
    event_b = make_weather_event(started_at=started, ended_at=ended)

    stored = service.bridge([event_a, event_b])

    assert len(stored) == 1
    assert signal_repo.count() == 1


def test_bridge_does_not_write_an_audit_entry_for_a_skipped_duplicate() -> None:
    service, _, audit_repo, _ = _service()
    started = utc_now() - timedelta(days=1)
    ended = started + timedelta(hours=3)

    service.bridge([make_weather_event(started_at=started, ended_at=ended)])
    service.bridge([make_weather_event(started_at=started, ended_at=ended)])

    entries = audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10)
    assert len(entries) == 1


def test_bridge_persists_dedup_bookkeeping_alongside_the_signal() -> None:
    """The dedup fingerprint entry must exist right after a successful bridge (Task 1, test 1)."""
    service, signal_repo, audit_repo, config_repo = _service()
    event = make_weather_event()

    [signal] = service.bridge([event])

    assert signal_repo.count() == 1
    assert len(audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10)) == 1
    fingerprint_entries = [
        entry
        for entry in config_repo.list_all()
        if entry.key.startswith("weather_bridge_fingerprint.")
    ]
    assert len(fingerprint_entries) == 1
    assert fingerprint_entries[0].value["signal_id"] == str(signal.id)
