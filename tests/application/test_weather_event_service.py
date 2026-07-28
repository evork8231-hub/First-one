"""Tests for app.application.services.weather_event_service.WeatherEventService."""

from __future__ import annotations

import asyncio

import pytest
from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.application.services.weather_event_service import WeatherEventService
from app.core.exceptions import CollectorError
from app.domain.enums import AuditEventType
from app.domain.weather import WeatherEvent
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.collection_unit_of_work import InMemoryCollectionUnitOfWork
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_weather_event


def _service(
    weather_repo: InMemoryWeatherEventRepository, audit_repo: InMemoryAuditLogRepository
) -> WeatherEventService:
    uow = InMemoryCollectionUnitOfWork(InMemorySignalRepository(), weather_repo, audit_repo)
    return WeatherEventService(audit_repo, uow)


class _FakeWeatherCollector(WeatherCollectorInterface):
    def __init__(self, events: list[WeatherEvent] | None = None, *, fail: bool = False) -> None:
        self._events = events or []
        self._fail = fail

    @property
    def name(self) -> str:
        return "fake_weather_collector"

    @property
    def source(self) -> str:
        return "fake_source"

    async def collect(self) -> list[WeatherEvent]:
        if self._fail:
            raise CollectorError("Simulated weather collector failure.")
        return self._events


def test_ingest_from_collector_persists_events_and_logs_audit() -> None:
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(weather_repo, audit_repo)
    collector = _FakeWeatherCollector([make_weather_event(), make_weather_event()])

    stored = asyncio.run(service.ingest_from_collector(collector))

    assert len(stored) == 2
    event_types = [entry.event_type for entry in audit_repo.list_all(limit=10)]
    assert AuditEventType.COLLECTOR_RUN_STARTED in event_types
    assert AuditEventType.COLLECTOR_RUN_COMPLETED in event_types


def test_ingest_from_collector_failure_is_audit_logged_and_reraised() -> None:
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(weather_repo, audit_repo)
    collector = _FakeWeatherCollector(fail=True)

    with pytest.raises(CollectorError):
        asyncio.run(service.ingest_from_collector(collector))

    event_types = [entry.event_type for entry in audit_repo.list_all(limit=10)]
    assert AuditEventType.COLLECTOR_RUN_FAILED in event_types


def test_ingest_from_collector_surfaces_retry_attempts() -> None:
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(weather_repo, audit_repo)
    collector = _FakeWeatherCollector([make_weather_event()])
    collector.retry_count = 4  # type: ignore[attr-defined]

    asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert entries[0].context["retry_attempts"] == 4


def test_ingest_from_collector_reports_zero_retries_when_untracked() -> None:
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(weather_repo, audit_repo)
    collector = _FakeWeatherCollector([make_weather_event()])

    asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert entries[0].context["retry_attempts"] == 0


def test_ingest_from_collector_records_execution_id_and_inserted_event_ids() -> None:
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(weather_repo, audit_repo)
    collector = _FakeWeatherCollector([make_weather_event(), make_weather_event()])

    stored = asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    context = entries[0].context
    assert "execution_id" in context
    assert set(context["inserted_event_ids"]) == {str(e.id) for e in stored}
