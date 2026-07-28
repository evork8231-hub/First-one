"""Tests for the SQLite/SQLAlchemy repository implementations."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from app.core.exceptions import EntityNotFoundError
from app.domain.audit import AuditLogEntry
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import AuditEventType, ServiceCategory, VerificationStatus
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.configuration_repository import SQLiteConfigurationRepository
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from app.utils.time import utc_now

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


def test_signal_repository_add_many_and_count(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    stored = repo.add_many(
        [
            make_signal(county="Harju", verified=VerificationStatus.VERIFIED),
            make_signal(county="Tartu", verified=VerificationStatus.UNVERIFIED),
        ]
    )

    assert len(stored) == 2
    assert repo.count() == 2
    assert repo.count(county="Harju") == 1
    assert repo.count(verified=VerificationStatus.VERIFIED) == 1
    assert repo.add_many([]) == []


def test_signal_repository_list_ids_by_source_matches_only_that_source(
    sqlite_session_factory,
) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    first = repo.add(make_signal(source="ehitisregister"))
    second = repo.add(make_signal(source="ehitisregister"))
    repo.add(make_signal(source="ilmateenistus"))

    ids = repo.list_ids_by_source("ehitisregister")

    assert set(ids) == {first.id, second.id}


def test_signal_repository_list_ids_by_source_respects_before(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    now = utc_now()
    old = repo.add(make_signal(source="ehitisregister", timestamp=now - timedelta(days=10)))
    recent = repo.add(make_signal(source="ehitisregister", timestamp=now - timedelta(minutes=1)))

    ids = repo.list_ids_by_source("ehitisregister", before=now - timedelta(days=1))

    assert ids == [old.id]
    assert recent.id not in ids


def test_signal_repository_list_ids_by_source_no_match_returns_empty(
    sqlite_session_factory,
) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    repo.add(make_signal(source="ehitisregister"))

    assert repo.list_ids_by_source("does_not_exist") == []


def test_signal_repository_delete_by_ids_deletes_only_the_given_ids(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    to_delete = repo.add(make_signal(source="ehitisregister"))
    kept = repo.add(make_signal(source="ehitisregister"))

    deleted = repo.delete_by_ids([to_delete.id])

    assert deleted == 1
    assert repo.get_by_id(to_delete.id) is None
    assert repo.get_by_id(kept.id) is not None


def test_signal_repository_delete_by_ids_empty_list_returns_zero(sqlite_session_factory) -> None:
    repo = SQLiteSignalRepository(sqlite_session_factory)
    repo.add(make_signal(source="ehitisregister"))

    assert repo.delete_by_ids([]) == 0
    assert repo.count() == 1


def test_lead_repository_crud_roundtrip(sqlite_session_factory) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    lead = repo.add(make_lead())

    fetched = repo.get_by_id(lead.id)
    assert fetched is not None
    assert fetched.supporting_signal_ids == lead.supporting_signal_ids

    updated = repo.update_verification_status(lead.id, VerificationStatus.VERIFIED)
    assert updated.verification_status == VerificationStatus.VERIFIED


def test_lead_repository_count_respects_filters(sqlite_session_factory) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    repo.add(make_lead(verification_status=VerificationStatus.VERIFIED))
    repo.add(make_lead(verification_status=VerificationStatus.UNVERIFIED))

    assert repo.count() == 2
    assert repo.count(verification_status=VerificationStatus.VERIFIED) == 1


def test_lead_repository_list_referencing_signal_ids_finds_matching_leads(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    cited = uuid4()
    uncited = uuid4()
    matching = repo.add(make_lead(supporting_signal_ids=[cited, uuid4()]))
    repo.add(make_lead(supporting_signal_ids=[uncited, uuid4()]))

    found = repo.list_referencing_signal_ids([cited])

    assert [lead.id for lead in found] == [matching.id]


def test_lead_repository_list_referencing_signal_ids_empty_input_returns_empty(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    repo.add(make_lead())

    assert repo.list_referencing_signal_ids([]) == []


def test_lead_repository_list_referencing_signal_ids_no_match_returns_empty(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    repo.add(make_lead())

    assert repo.list_referencing_signal_ids([uuid4()]) == []


def test_lead_repository_find_by_identity_matches_same_type_and_signal_set(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    signal_ids = [uuid4(), uuid4()]
    stored = repo.add(
        make_lead(lead_type=ServiceCategory.ROOFING, supporting_signal_ids=signal_ids)
    )

    # Order-independent: a re-run's candidate may list the same ids in a different order.
    found = repo.find_by_identity(ServiceCategory.ROOFING, list(reversed(signal_ids)))

    assert found is not None
    assert found.id == stored.id


def test_lead_repository_find_by_identity_returns_none_for_different_signal_set(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    repo.add(make_lead(lead_type=ServiceCategory.ROOFING, supporting_signal_ids=[uuid4(), uuid4()]))

    assert repo.find_by_identity(ServiceCategory.ROOFING, [uuid4(), uuid4()]) is None


def test_lead_repository_find_by_identity_returns_none_for_different_lead_type(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    signal_ids = [uuid4(), uuid4()]
    repo.add(make_lead(lead_type=ServiceCategory.ROOFING, supporting_signal_ids=signal_ids))

    assert repo.find_by_identity(ServiceCategory.KITCHEN_REMODELING, signal_ids) is None


def test_weather_repository_roundtrip(sqlite_session_factory) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    event = repo.add(make_weather_event())

    results = repo.list_by_region_and_time(
        county="Harju", since=event.started_at, until=event.ended_at
    )
    assert [e.id for e in results] == [event.id]


def test_weather_repository_add_many_and_count(sqlite_session_factory) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    stored = repo.add_many([make_weather_event(), make_weather_event()])

    assert len(stored) == 2
    assert repo.count() == 2
    assert repo.add_many([]) == []


def test_weather_repository_list_ids_by_source_matches_only_that_source(
    sqlite_session_factory,
) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    matching = repo.add(make_weather_event(source="ilmateenistus"))
    repo.add(make_weather_event(source="other_source"))

    ids = repo.list_ids_by_source("ilmateenistus")

    assert ids == [matching.id]


def test_weather_repository_list_ids_by_source_respects_before(sqlite_session_factory) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
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
            source="ilmateenistus", started_at=now - timedelta(minutes=1), ended_at=now
        )
    )

    ids = repo.list_ids_by_source("ilmateenistus", before=now - timedelta(days=1))

    assert ids == [old.id]
    assert recent.id not in ids


def test_weather_repository_delete_by_ids_deletes_only_the_given_ids(
    sqlite_session_factory,
) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    to_delete = repo.add(make_weather_event(source="ilmateenistus"))
    kept = repo.add(make_weather_event(source="ilmateenistus"))

    deleted = repo.delete_by_ids([to_delete.id])

    assert deleted == 1
    assert repo.get_by_id(to_delete.id) is None
    assert repo.get_by_id(kept.id) is not None


def test_weather_repository_delete_by_ids_empty_list_returns_zero(sqlite_session_factory) -> None:
    repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    repo.add(make_weather_event(source="ilmateenistus"))

    assert repo.delete_by_ids([]) == 0
    assert repo.count() == 1


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
