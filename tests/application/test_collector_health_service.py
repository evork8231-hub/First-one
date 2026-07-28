"""Tests for app.application.services.collector_health_service.CollectorHealthService."""

from __future__ import annotations

import asyncio

import pytest
from app.application.services.collector_health_service import CollectorHealthService
from app.application.services.signal_service import SignalService
from app.application.services.weather_event_service import WeatherEventService
from app.core.exceptions import CollectorError
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.collection_unit_of_work import InMemoryCollectionUnitOfWork
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_signal, make_weather_event
from tests.fixtures.fakes import FakeCollector, FakeWeatherCollector


def _signal_service(audit_repo: InMemoryAuditLogRepository) -> SignalService:
    signal_repo = InMemorySignalRepository()
    uow = InMemoryCollectionUnitOfWork(signal_repo, InMemoryWeatherEventRepository(), audit_repo)
    return SignalService(signal_repo, audit_repo, uow)


def _weather_service(audit_repo: InMemoryAuditLogRepository) -> WeatherEventService:
    weather_repo = InMemoryWeatherEventRepository()
    uow = InMemoryCollectionUnitOfWork(InMemorySignalRepository(), weather_repo, audit_repo)
    return WeatherEventService(audit_repo, uow)


def test_get_health_with_no_run_history_returns_empty() -> None:
    service = CollectorHealthService(InMemoryAuditLogRepository())
    assert service.get_health() == []


def test_get_health_reports_a_successful_run() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = _signal_service(audit_repo)
    collector = FakeCollector([make_signal()], name="ehitisregister")

    asyncio.run(signal_service.ingest_from_collector(collector))

    [report] = CollectorHealthService(audit_repo).get_health()
    assert report.collector_name == "ehitisregister"
    assert report.last_status == "succeeded"
    assert report.last_item_count == 1
    assert report.last_duration_seconds is not None
    assert report.last_duration_seconds >= 0.0
    assert report.last_retry_attempts == 0
    assert report.consecutive_failures == 0
    assert report.last_error is None


def test_get_health_surfaces_retry_attempts() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = _signal_service(audit_repo)
    collector = FakeCollector([make_signal()], name="ehitisregister")
    collector.retry_count = 5

    asyncio.run(signal_service.ingest_from_collector(collector))

    [report] = CollectorHealthService(audit_repo).get_health()
    assert report.last_retry_attempts == 5


def test_get_health_reports_a_failed_run() -> None:
    audit_repo = InMemoryAuditLogRepository()
    signal_service = _signal_service(audit_repo)
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
    signal_service = _signal_service(audit_repo)

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
    signal_service = _signal_service(audit_repo)
    weather_service = _weather_service(audit_repo)

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
