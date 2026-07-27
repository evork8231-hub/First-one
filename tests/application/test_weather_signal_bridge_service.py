"""Tests for app.application.services.weather_signal_bridge_service.WeatherSignalBridgeService."""

from __future__ import annotations

from app.application.services.weather_signal_bridge_service import WeatherSignalBridgeService
from app.config.settings import WeatherSignalBridgeConfig
from app.domain.enums import AuditEventType, ServiceCategory, SignalType
from app.domain.value_objects import Coordinates
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository

from tests.fixtures.factories import make_weather_event


def _service(
    **config_overrides: object,
) -> tuple[WeatherSignalBridgeService, InMemorySignalRepository]:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    config = WeatherSignalBridgeConfig(**config_overrides)  # type: ignore[arg-type]
    return WeatherSignalBridgeService(signal_repo, audit_repo, config), signal_repo


def test_bridge_with_no_events_returns_empty_and_touches_nothing() -> None:
    service, signal_repo = _service()
    assert service.bridge([]) == []
    assert signal_repo.count() == 0


def test_bridge_persists_one_weather_event_signal_per_event() -> None:
    service, signal_repo = _service()
    event = make_weather_event()

    stored = service.bridge([event])

    assert len(stored) == 1
    signal = stored[0]
    assert signal.signal_type == SignalType.WEATHER_EVENT
    assert signal_repo.get_by_id(signal.id) is not None


def test_bridged_signal_carries_over_the_events_own_location_and_source() -> None:
    service, _ = _service()
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
    service, _ = _service(
        service_category=ServiceCategory.SOLAR_INSTALLATION, signal_confidence=0.55
    )
    event = make_weather_event(severity=0.99)  # deliberately different from configured confidence

    [signal] = service.bridge([event])

    assert signal.service_category == ServiceCategory.SOLAR_INSTALLATION
    assert signal.confidence == 0.55  # not event.severity


def test_bridged_signal_timestamp_is_collection_time_not_the_forecast_period() -> None:
    """A future-dated forecast period must not make Signal's timestamp validator reject it."""
    from datetime import UTC, datetime, timedelta

    service, _ = _service()
    future_start = datetime.now(UTC) + timedelta(days=2)
    event = make_weather_event(started_at=future_start, ended_at=future_start + timedelta(hours=6))

    [signal] = service.bridge([event])  # must not raise

    assert signal.timestamp <= datetime.now(UTC)
    assert signal.metadata["started_at"] == future_start.isoformat()


def test_bridge_metadata_links_back_to_the_source_weather_event() -> None:
    service, _ = _service()
    event = make_weather_event()

    [signal] = service.bridge([event])

    assert signal.metadata["weather_event_id"] == str(event.id)
    assert signal.metadata["weather_event_type"] == event.event_type.value
    assert signal.metadata["severity"] == event.severity


def test_bridge_writes_one_audit_log_entry_per_event() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = WeatherSignalBridgeService(signal_repo, audit_repo, WeatherSignalBridgeConfig())

    service.bridge([make_weather_event(), make_weather_event()])

    entries = audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10)
    assert len(entries) == 2
    assert all(e.context["source"] == "weather_signal_bridge" for e in entries)


def test_bridge_multiple_events_produces_multiple_independent_signals() -> None:
    service, signal_repo = _service()
    events = [make_weather_event(), make_weather_event(county="Pärnu", municipality="Pärnu")]

    stored = service.bridge(events)

    assert len(stored) == 2
    assert signal_repo.count() == 2
    assert {s.county for s in stored} == {"Harju", "Pärnu"}
