"""Tests for the SQLite/SQLAlchemy repository implementations."""

from __future__ import annotations

import pytest
from app.core.exceptions import EntityNotFoundError
from app.domain.audit import AuditLogEntry
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import AuditEventType, VerificationStatus
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.configuration_repository import SQLiteConfigurationRepository
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository

from tests.fixtures.factories import make_lead, make_signal, make_weather_event


def test_signal_repository_crud_roundtrip(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    signal = repo.add(make_signal(verified=VerificationStatus.UNVERIFIED))

    fetched = repo.get_by_id(signal.id)
    assert fetched is not None
    assert fetched.id == signal.id
    assert fetched.raw_payload == signal.raw_payload

    updated = repo.update_verification(signal.id, VerificationStatus.VERIFIED)
    assert updated.verified == VerificationStatus.VERIFIED
    assert repo.list_unverified(limit=10) == []


def test_signal_repository_update_missing_raises(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    with pytest.raises(EntityNotFoundError):
        repo.update_verification(make_signal().id, VerificationStatus.VERIFIED)


def test_signal_repository_list_by_ids(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    a = repo.add(make_signal())
    repo.add(make_signal())

    results = repo.list_by_ids([a.id])
    assert [s.id for s in results] == [a.id]


def test_lead_repository_crud_roundtrip(sqlite_session_factory) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    lead = repo.add(make_lead())

    fetched = repo.get_by_id(lead.id)
    assert fetched is not None
    assert fetched.supporting_signal_ids == lead.supporting_signal_ids

    updated = repo.update_verification_status(lead.id, VerificationStatus.VERIFIED)
    assert updated.verification_status == VerificationStatus.VERIFIED


def test_weather_repository_roundtrip(sqlite_session_factory) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    event = repo.add(make_weather_event())

    results = repo.list_by_region_and_time(
        county="Harju", since=event.started_at, until=event.ended_at
    )
    assert [e.id for e in results] == [event.id]


def test_audit_log_repository_roundtrip(sqlite_session_factory) -> None:
    repo = SQLiteAuditLogRepository(sqlite_session_factory)
    repo.add(AuditLogEntry(event_type=AuditEventType.ERROR, message="something happened"))

    entries = repo.list_all(event_type=AuditEventType.ERROR, limit=10)
    assert len(entries) == 1


def test_configuration_repository_set_is_idempotent_per_key(sqlite_session_factory) -> None:
    repo = SQLiteConfigurationRepository(sqlite_session_factory)
    repo.set(ConfigurationEntry(key="scoring.weight", value=1.0))
    repo.set(ConfigurationEntry(key="scoring.weight", value=2.0))

    entries = repo.list_all()
    assert len(entries) == 1
    assert entries[0].value == 2.0
