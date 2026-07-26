"""Tests for the in-memory repository implementations."""

from __future__ import annotations

import pytest
from app.core.exceptions import EntityNotFoundError
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import VerificationStatus
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.configuration_repository import InMemoryConfigurationRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_lead, make_signal, make_weather_event


def test_signal_repository_crud_roundtrip() -> None:
    repo = InMemorySignalRepository()
    signal = repo.add(make_signal(verified=VerificationStatus.UNVERIFIED))

    assert repo.get_by_id(signal.id) == signal
    assert repo.list_by_ids([signal.id]) == [signal]
    assert repo.list_unverified(limit=10) == [signal]

    updated = repo.update_verification(signal.id, VerificationStatus.VERIFIED)
    assert updated.verified == VerificationStatus.VERIFIED
    assert repo.get_by_id(signal.id).verified == VerificationStatus.VERIFIED


def test_signal_repository_update_missing_raises() -> None:
    repo = InMemorySignalRepository()
    with pytest.raises(EntityNotFoundError):
        repo.update_verification(make_signal().id, VerificationStatus.VERIFIED)


def test_signal_repository_list_filters_by_county() -> None:
    repo = InMemorySignalRepository()
    repo.add(make_signal(county="Harju", municipality="Tallinn"))
    repo.add(make_signal(county="Tartu", municipality="Tartu"))

    results = repo.list_all(county="Tartu", limit=10)
    assert len(results) == 1
    assert results[0].county == "Tartu"


def test_lead_repository_crud_roundtrip() -> None:
    repo = InMemoryLeadRepository()
    lead = repo.add(make_lead())

    assert repo.get_by_id(lead.id) == lead
    updated = repo.update_verification_status(lead.id, VerificationStatus.VERIFIED)
    assert updated.verification_status == VerificationStatus.VERIFIED


def test_lead_repository_update_missing_raises() -> None:
    repo = InMemoryLeadRepository()
    with pytest.raises(EntityNotFoundError):
        repo.update_verification_status(make_lead().id, VerificationStatus.VERIFIED)


def test_weather_repository_list_by_region_and_time() -> None:
    repo = InMemoryWeatherEventRepository()
    event = repo.add(make_weather_event())

    results = repo.list_by_region_and_time(
        county="Harju", since=event.started_at, until=event.ended_at
    )
    assert results == [event]

    assert (
        repo.list_by_region_and_time(county="Tartu", since=event.started_at, until=event.ended_at)
        == []
    )


def test_audit_log_repository_add_and_list() -> None:
    from app.domain.audit import AuditLogEntry
    from app.domain.enums import AuditEventType

    repo = InMemoryAuditLogRepository()
    repo.add(AuditLogEntry(event_type=AuditEventType.ERROR, message="something happened"))

    entries = repo.list_all(event_type=AuditEventType.ERROR, limit=10)
    assert len(entries) == 1


def test_configuration_repository_set_and_get() -> None:
    repo = InMemoryConfigurationRepository()
    entry = ConfigurationEntry(key="rules.roofing_storm.enabled", value=True)
    repo.set(entry)

    fetched = repo.get("rules.roofing_storm.enabled")
    assert fetched is not None
    assert fetched.value is True
    assert repo.get("does.not.exist") is None
    assert [e.key for e in repo.list_all()] == ["rules.roofing_storm.enabled"]
