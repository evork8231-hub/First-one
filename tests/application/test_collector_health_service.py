"""Tests for app.application.services.collector_health_service.CollectorHealthService."""

from __future__ import annotations

import asyncio

import pytest
from app.application.services.collector_health_service import CollectorHealthService
from app.application.services.signal_service import SignalService
from app.application.services.weather_event_service import WeatherEventService
from app.core.exceptions import CollectorError
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_signal, make_weather_event
from tests.fixtures.fakes import FakeCollector, FakeWeatherCollector


def test_get_health_with_no_run_history_returns_empty() -> None:
    service = CollectorHealthService(InMemoryAuditLogRepository())
    assert service.get_health() == []


def test_get_health_reports_a_successful_run() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = SignalService(InMemorySignalRepository(), audit_repo)
    collector = FakeCollector([make_signal()], name="ehitisregister")

    asyncio.run(signal_service.ingest_from_collector(collector))

    [report] = CollectorHealthService(audit_repo).get_health()
    assert report.collector_name == "ehitisregister"
    assert report.last_status == "succeeded"
    assert report.last_item_count == 1
    assert report.last_duration_seconds is not None
    assert report.last_duration_seconds >= 0.0
    assert report.consecutive_failures == 0
    assert report.last_error is None


def test_get_health_reports_a_failed_run() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = SignalService(InMemorySignalRepository(), audit_repo)
    collector = FakeCollector([], name="kv_ee", fail=True)

    with pytest.raises(CollectorError):
        asyncio.run(signal_service.ingest_from_collector(collector))

    [report] = CollectorHealthService(audit_repo).get_health()
    assert report.collector_name == "kv_ee"
    assert report.last_status == "failed"
    assert report.consecutive_failures == 1
    assert report.last_error is not None


def test_get_health_counts_consecutive_failures_since_the_last_success() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = SignalService(InMemorySignalRepository(), audit_repo)

    asyncio.run(signal_service.ingest_from_collector(FakeCollector([make_signal()], name="kv_ee")))
    for _ in range(3):
        with pytest.raises(CollectorError):
            asyncio.run(
                signal_service.ingest_from_collector(FakeCollector([], name="kv_ee", fail=True))
            )

    [report] = CollectorHealthService(audit_repo).get_health()
    assert report.last_status == "failed"
    assert report.consecutive_failures == 3


def test_get_health_tracks_multiple_collectors_independently() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = SignalService(InMemorySignalRepository(), audit_repo)
    weather_service = WeatherEventService(InMemoryWeatherEventRepository(), audit_repo)

    asyncio.run(
        signal_service.ingest_from_collector(FakeCollector([make_signal()], name="ehitisregister"))
    )
    asyncio.run(
        weather_service.ingest_from_collector(
            FakeWeatherCollector([make_weather_event()], name="ilmateenistus")
        )
    )

    reports = CollectorHealthService(audit_repo).get_health()
    names = {report.collector_name for report in reports}
    assert names == {"ehitisregister", "ilmateenistus"}
    weather_report = next(r for r in reports if r.collector_name == "ilmateenistus")
    assert weather_report.last_item_count == 1
