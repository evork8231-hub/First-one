"""Tests for app.application.services.signal_service.SignalService."""

from __future__ import annotations

import asyncio

import pytest
from app.application.services.signal_service import SignalService
from app.core.exceptions import CollectorError
from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository

from tests.fixtures.factories import make_signal
from tests.fixtures.fakes import FakeCollector


def test_ingest_from_collector_persists_signals_and_logs_audit() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = SignalService(signal_repo, audit_repo)
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
    service = SignalService(signal_repo, audit_repo)
    collector = FakeCollector([], fail=True)

    with pytest.raises(CollectorError):
        asyncio.run(service.ingest_from_collector(collector))

    assert signal_repo.list_all(limit=10) == []
    event_types = [entry.event_type for entry in audit_repo.list_all(limit=10)]
    assert AuditEventType.COLLECTOR_RUN_FAILED in event_types


def test_ingest_from_collectors_runs_every_collector_and_persists_all_signals() -> None:
    signal_repo = InMemorySignalRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = SignalService(signal_repo, audit_repo)
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
    service = SignalService(signal_repo, audit_repo)
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
