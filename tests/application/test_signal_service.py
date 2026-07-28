"""Tests for app.application.services.signal_service.SignalService."""

from __future__ import annotations

import asyncio

import pytest
from app.application.services.signal_service import SignalService
from app.core.exceptions import CollectorError
from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.collection_unit_of_work import InMemoryCollectionUnitOfWork
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_signal
from tests.fixtures.fakes import FakeCollector


def _service(
    signal_repo: InMemorySignalRepository, audit_repo: InMemoryAuditLogRepository
) -> SignalService:
    uow = InMemoryCollectionUnitOfWork(signal_repo, InMemoryWeatherEventRepository(), audit_repo)
    return SignalService(signal_repo, audit_repo, uow)


def test_ingest_from_collector_persists_signals_and_logs_audit() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collector = FakeCollector([make_signal(), make_signal()])

    stored = asyncio.run(service.ingest_from_collector(collector))

    assert len(stored) == 2
    assert len(signal_repo.list_all(limit=10)) == 2
    event_types = [entry.event_type for entry in audit_repo.list_all(limit=10)]
    assert AuditEventType.COLLECTOR_RUN_STARTED in event_types
    assert AuditEventType.COLLECTOR_RUN_COMPLETED in event_types
    assert event_types.count(AuditEventType.SIGNAL_INGESTED) == 2


def test_ingest_from_collector_failure_is_audit_logged_and_reraised() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collector = FakeCollector([], fail=True)

    with pytest.raises(CollectorError):
        asyncio.run(service.ingest_from_collector(collector))

    assert signal_repo.list_all(limit=10) == []
    event_types = [entry.event_type for entry in audit_repo.list_all(limit=10)]
    assert AuditEventType.COLLECTOR_RUN_FAILED in event_types


def test_ingest_from_collector_reports_zero_retries_when_untracked() -> None:
    """A collector that never tracks retry_count reports 0, honestly, not a guess."""
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collector = FakeCollector([make_signal()])

    asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert entries[0].context["retry_attempts"] == 0


def test_ingest_from_collector_surfaces_the_collectors_retry_count() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collector = FakeCollector([make_signal()])
    collector.retry_count = 3  # simulates a BaseCollector subclass that hit retries

    asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert entries[0].context["retry_attempts"] == 3


def test_ingest_from_collector_failure_still_reports_retry_attempts() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collector = FakeCollector([], fail=True)
    collector.retry_count = 2

    with pytest.raises(CollectorError):
        asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_FAILED, limit=10)
    assert entries[0].context["retry_attempts"] == 2


def test_ingest_from_collector_records_execution_id_and_inserted_signal_ids() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collector = FakeCollector([make_signal(), make_signal()])

    stored = asyncio.run(service.ingest_from_collector(collector))

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    context = entries[0].context
    assert "execution_id" in context
    assert set(context["inserted_signal_ids"]) == {str(s.id) for s in stored}


def test_ingest_from_collectors_runs_every_collector_and_persists_all_signals() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collectors = [
        FakeCollector([make_signal()], name="a"),
        FakeCollector([make_signal(), make_signal()], name="b"),
    ]

    results = asyncio.run(service.ingest_from_collectors(collectors, max_concurrency=2))

    assert {r.collector_name for r in results} == {"a", "b"}
    assert all(r.succeeded for r in results)
    assert len(signal_repo.list_all(limit=10)) == 3


def test_ingest_from_collectors_one_failure_does_not_abort_the_batch() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = _service(signal_repo, audit_repo)
    collectors = [
        FakeCollector([make_signal()], name="good"),
        FakeCollector([], name="bad", fail=True),
    ]

    results = asyncio.run(service.ingest_from_collectors(collectors, max_concurrency=2))

    by_name = {r.collector_name: r for r in results}
    assert by_name["good"].succeeded
    assert not by_name["bad"].succeeded
    assert by_name["bad"].error is not None
    assert len(signal_repo.list_all(limit=10)) == 1
