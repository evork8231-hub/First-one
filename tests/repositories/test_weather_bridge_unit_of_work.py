"""Tests for app.repositories.sqlite.weather_bridge_unit_of_work.SQLiteWeatherBridgeUnitOfWork.

These specifically exercise real SQLite transaction/commit behavior --
``tests/application/test_weather_signal_bridge_service.py`` covers
``WeatherSignalBridgeService``'s own dedup/skip logic against the
in-memory unit of work, which cannot demonstrate atomicity at all (a
process-local dict has nothing to roll back).

Mandatory proof for the weather-bridge-atomicity fix: a Signal, its
dedup fingerprint entry, and its audit log entry must commit or fail
together, so an interrupted collection run can never leave a Signal
persisted with no matching dedup record -- which would otherwise let
the next run bridge the same real-world event a second time.
"""

from __future__ import annotations

import pytest
from app.application.interfaces.weather_bridge_unit_of_work import BridgedEvent
from app.application.services.weather_signal_bridge_service import WeatherSignalBridgeService
from app.config.settings import WeatherSignalBridgeConfig
from app.domain.enums import AuditEventType, SignalType
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.configuration_repository import SQLiteConfigurationRepository
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_bridge_unit_of_work import SQLiteWeatherBridgeUnitOfWork
from app.verification.weather_bridge_dedup import WeatherBridgeDeduplicator
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests.fixtures.factories import make_weather_event


def _build_bridged_event(
    deduplicator: WeatherBridgeDeduplicator, config: WeatherSignalBridgeConfig, event
) -> BridgedEvent:
    """Build a BridgedEvent the exact same way WeatherSignalBridgeService does, without
    going through its atomic persistence -- lets a test drive the UoW directly."""
    service = WeatherSignalBridgeService(
        config, deduplicator, weather_bridge_unit_of_work=_NullUnitOfWork()
    )
    return service._build_bridged_event(event)


class _NullUnitOfWork:
    """Never actually called; _build_bridged_event never touches the unit of work."""

    def bridge_events(self, bridged):  # pragma: no cover - not exercised
        raise AssertionError("bridge_events should not be called via _NullUnitOfWork")


def test_bridge_events_happy_path_persists_signal_dedup_and_audit_atomically(
    sqlite_session_factory,
) -> None:
    """Test 1 (Task 1): a successful bridge creates the signal, the dedup entry, and the
    audit log entry -- all visible immediately after one bridge_events() call."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    config_repo = SQLiteConfigurationRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    uow = SQLiteWeatherBridgeUnitOfWork(sqlite_session_factory)
    config = WeatherSignalBridgeConfig()
    event = make_weather_event()

    bridged = _build_bridged_event(deduplicator, config, event)
    [stored_signal] = uow.bridge_events([bridged])

    assert stored_signal.signal_type == SignalType.WEATHER_EVENT
    assert signal_repo.get_by_id(stored_signal.id) is not None
    assert deduplicator.is_duplicate(event) is True
    entries = audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10)
    assert len(entries) == 1
    assert entries[0].entity_id == stored_signal.id


def test_bridge_events_empty_batch_persists_nothing(sqlite_session_factory) -> None:
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    uow = SQLiteWeatherBridgeUnitOfWork(sqlite_session_factory)

    assert uow.bridge_events([]) == []
    assert signal_repo.count() == 0


def test_atomicity_a_failure_at_commit_leaves_no_partial_state(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 2 (Task 1): forces Session.commit to raise after the signal INSERT, the dedup
    entry INSERT, and the audit INSERT have all already been flushed to the connection --
    exactly mirroring a crash/disk-full/lock failure at the last moment. If the signal
    creation, dedup bookkeeping, and audit logging were still three separate transactions
    (the pre-fix design), the signal would already be irreversibly committed by this point,
    with no matching dedup record. With one shared transaction, session_scope's
    `except Exception: session.rollback()` must undo all three together.
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    config_repo = SQLiteConfigurationRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    uow = SQLiteWeatherBridgeUnitOfWork(sqlite_session_factory)
    config = WeatherSignalBridgeConfig()
    event = make_weather_event()
    bridged = _build_bridged_event(deduplicator, config, event)

    def _failing_commit(self: Session) -> None:
        raise OperationalError("simulated commit failure (disk full / locked)", None, Exception())

    monkeypatch.setattr(Session, "commit", _failing_commit)

    with pytest.raises(OperationalError):
        uow.bridge_events([bridged])

    monkeypatch.undo()  # restore Session.commit before using the repositories again to verify

    assert signal_repo.get_by_id(bridged.signal.id) is None, "the signal must not have persisted"
    assert deduplicator.is_duplicate(event) is False, "the dedup entry must not have persisted"
    assert (
        audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10) == []
    ), "the audit entry must not have persisted either"


def test_interrupted_collection_run_cannot_create_duplicate_weather_signals(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 3 (Task 1): a collection run that gets interrupted mid-bridge (commit fails)
    must leave the database in a state where the *same* real-world event can be bridged
    exactly once by a later, successful retry -- never twice.

    Before this fix, WeatherSignalBridgeService wrote the Signal, then marked the event as
    bridged, then wrote the audit entry, as three separate transactions. An interruption
    between the first and second write would leave a Signal committed with no dedup record,
    so a retry's `is_duplicate` check would find nothing and create a second, duplicate
    WEATHER_EVENT signal for the identical occurrence. With one atomic transaction, an
    interrupted attempt leaves nothing committed at all, so the retry starts clean.
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    config_repo = SQLiteConfigurationRepository(sqlite_session_factory)
    deduplicator = WeatherBridgeDeduplicator(config_repo)
    uow = SQLiteWeatherBridgeUnitOfWork(sqlite_session_factory)
    config = WeatherSignalBridgeConfig()
    service = WeatherSignalBridgeService(config, deduplicator, uow)
    event = make_weather_event()

    def _failing_commit(self: Session) -> None:
        raise OperationalError("simulated interrupted collection run", None, Exception())

    monkeypatch.setattr(Session, "commit", _failing_commit)
    with pytest.raises(OperationalError):
        service.bridge([event])
    monkeypatch.undo()

    assert signal_repo.count() == 0, "the interrupted run must not have left a partial signal"
    assert deduplicator.is_duplicate(event) is False

    # The collection run is retried (a fresh call with the identical real-world event).
    retried = service.bridge([event])

    assert len(retried) == 1
    assert signal_repo.count() == 1, "exactly one signal must exist after the successful retry"

    # A third call reporting the same real-world event again (e.g. the next scheduled
    # collection) must now be skipped as an already-bridged duplicate, not create a second.
    repeat_event = make_weather_event(started_at=event.started_at, ended_at=event.ended_at)
    again = service.bridge([repeat_event])
    assert again == []
    assert signal_repo.count() == 1, "no duplicate weather signal may ever be created"
