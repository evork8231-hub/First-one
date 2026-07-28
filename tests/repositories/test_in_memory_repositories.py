"""Tests for the in-memory repository implementations."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from app.core.exceptions import EntityNotFoundError
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import ServiceCategory, VerificationStatus
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.configuration_repository import InMemoryConfigurationRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository
from app.utils.time import utc_now

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


def test_signal_repository_add_many_persists_every_signal() -> None:
    repo = InMemorySignalRepository()
    signals = [make_signal(), make_signal()]

    stored = repo.add_many(signals)

    assert len(stored) == 2
    assert repo.count() == 2


def test_signal_repository_add_many_empty_is_a_noop() -> None:
    repo = InMemorySignalRepository()
    assert repo.add_many([]) == []
    assert repo.count() == 0


def test_signal_repository_count_respects_filters() -> None:
    repo = InMemorySignalRepository()
    repo.add(make_signal(county="Harju", verified=VerificationStatus.VERIFIED))
    repo.add(make_signal(county="Tartu", verified=VerificationStatus.UNVERIFIED))

    assert repo.count() == 2
    assert repo.count(county="Harju") == 1
    assert repo.count(verified=VerificationStatus.VERIFIED) == 1
    assert repo.count(county="Saare") == 0


def test_signal_repository_list_ids_by_source_matches_only_that_source() -> None:
    repo = InMemorySignalRepository()
    first = repo.add(make_signal(source="ehitisregister"))
    second = repo.add(make_signal(source="ehitisregister"))
    repo.add(make_signal(source="ilmateenistus"))

    ids = repo.list_ids_by_source("ehitisregister")

    assert set(ids) == {first.id, second.id}


def test_signal_repository_list_ids_by_source_respects_before() -> None:
    repo = InMemorySignalRepository()
    now = utc_now()
    old = repo.add(make_signal(source="ehitisregister", timestamp=now - timedelta(days=10)))
    recent = repo.add(make_signal(source="ehitisregister", timestamp=now - timedelta(minutes=1)))

    ids = repo.list_ids_by_source("ehitisregister", before=now - timedelta(days=1))

    assert ids == [old.id]
    assert recent.id not in ids


def test_signal_repository_list_ids_by_source_no_match_returns_empty() -> None:
    repo = InMemorySignalRepository()
    repo.add(make_signal(source="ehitisregister"))

    assert repo.list_ids_by_source("does_not_exist") == []


def test_signal_repository_delete_by_ids_deletes_only_the_given_ids() -> None:
    repo = InMemorySignalRepository()
    to_delete = repo.add(make_signal(source="ehitisregister"))
    kept = repo.add(make_signal(source="ehitisregister"))

    deleted = repo.delete_by_ids([to_delete.id])

    assert deleted == 1
    assert repo.get_by_id(to_delete.id) is None
    assert repo.get_by_id(kept.id) is not None


def test_signal_repository_delete_by_ids_unknown_id_is_not_counted() -> None:
    repo = InMemorySignalRepository()
    kept = repo.add(make_signal(source="ehitisregister"))

    assert repo.delete_by_ids([kept.id, uuid4()]) == 1
    assert repo.count() == 0


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


def test_lead_repository_count_respects_filters() -> None:
    repo = InMemoryLeadRepository()
    repo.add(make_lead(verification_status=VerificationStatus.VERIFIED))
    repo.add(make_lead(verification_status=VerificationStatus.UNVERIFIED))

    assert repo.count() == 2
    assert repo.count(verification_status=VerificationStatus.VERIFIED) == 1


def test_lead_repository_list_referencing_signal_ids_finds_matching_leads() -> None:
    repo = InMemoryLeadRepository()
    cited = uuid4()
    uncited = uuid4()
    matching = repo.add(make_lead(supporting_signal_ids=[cited, uuid4()]))
    repo.add(make_lead(supporting_signal_ids=[uncited, uuid4()]))

    found = repo.list_referencing_signal_ids([cited])

    assert [lead.id for lead in found] == [matching.id]


def test_lead_repository_list_referencing_signal_ids_empty_input_returns_empty() -> None:
    repo = InMemoryLeadRepository()
    repo.add(make_lead())

    assert repo.list_referencing_signal_ids([]) == []


def test_lead_repository_find_by_identity_matches_same_type_and_signal_set() -> None:
    repo = InMemoryLeadRepository()
    signal_ids = [uuid4(), uuid4()]
    stored = repo.add(
        make_lead(lead_type=ServiceCategory.ROOFING, supporting_signal_ids=signal_ids)
    )

    found = repo.find_by_identity(ServiceCategory.ROOFING, list(reversed(signal_ids)))

    assert found is not None
    assert found.id == stored.id


def test_lead_repository_find_by_identity_returns_none_for_different_signal_set() -> None:
    repo = InMemoryLeadRepository()
    repo.add(make_lead(lead_type=ServiceCategory.ROOFING, supporting_signal_ids=[uuid4(), uuid4()]))

    assert repo.find_by_identity(ServiceCategory.ROOFING, [uuid4(), uuid4()]) is None


def test_weather_repository_add_many_and_count() -> None:
    repo = InMemoryWeatherEventRepository()
    stored = repo.add_many([make_weather_event(), make_weather_event()])

    assert len(stored) == 2
    assert repo.count() == 2


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


def test_weather_repository_list_ids_by_source_matches_only_that_source() -> None:
    repo = InMemoryWeatherEventRepository()
    matching = repo.add(make_weather_event(source="ilmateenistus"))
    repo.add(make_weather_event(source="other_source"))

    ids = repo.list_ids_by_source("ilmateenistus")

    assert ids == [matching.id]


def test_weather_repository_list_ids_by_source_respects_before() -> None:
    repo = InMemoryWeatherEventRepository()
    now = utc_now()
    old = repo.add(
        make_weather_event(
            source="ilmateenistus",
            started_at=now - timedelta(days=10),
            ended_at=now - timedelta(days=10) + timedelta(hours=3),
        )
    )
    recent = repo.add(
        make_weather_event(
            source="ilmateenistus",
            started_at=now - timedelta(minutes=1),
            ended_at=now,
        )
    )

    ids = repo.list_ids_by_source("ilmateenistus", before=now - timedelta(days=1))

    assert ids == [old.id]
    assert recent.id not in ids


def test_weather_repository_delete_by_ids_deletes_only_the_given_ids() -> None:
    repo = InMemoryWeatherEventRepository()
    to_delete = repo.add(make_weather_event(source="ilmateenistus"))
    kept = repo.add(make_weather_event(source="ilmateenistus"))

    deleted = repo.delete_by_ids([to_delete.id])

    assert deleted == 1
    assert repo.get_by_id(to_delete.id) is None
    assert repo.get_by_id(kept.id) is not None


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
