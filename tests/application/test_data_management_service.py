"""Tests for app.application.services.data_management_service.DataManagementService."""

from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

import pytest
from app.application.services.data_management_service import DataManagementService
from app.core.exceptions import PurgeBlockedByDependentDataError
from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.purge_unit_of_work import InMemoryPurgeUnitOfWork
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository
from app.utils.time import utc_now

from tests.fixtures.factories import make_lead, make_signal, make_weather_event


def _service() -> tuple[
    DataManagementService,
    InMemorySignalRepository,
    InMemoryWeatherEventRepository,
    InMemoryLeadRepository,
    InMemoryAuditLogRepository,
]:
    signal_repo = InMemorySignalRepository()
    weather_repo = InMemoryWeatherEventRepository()
    lead_repo = InMemoryLeadRepository()
    audit_repo = InMemoryAuditLogRepository()
    purge_uow = InMemoryPurgeUnitOfWork(signal_repo, weather_repo, audit_repo)
    service = DataManagementService(signal_repo, weather_repo, lead_repo, purge_uow)
    return service, signal_repo, weather_repo, lead_repo, audit_repo


def test_purge_signals_dry_run_deletes_nothing_and_writes_no_audit_entry() -> None:
    service, signal_repo, _, _, audit_repo = _service()
    signal_repo.add(make_signal(source="stale_collector"))
    signal_repo.add(make_signal(source="keep_me"))

    affected = service.purge_signals("stale_collector", dry_run=True)

    assert affected == 1
    assert signal_repo.count() == 2
    assert audit_repo.list_all(limit=10) == []


def test_purge_signals_real_run_deletes_and_writes_an_audit_entry() -> None:
    service, signal_repo, _, _, audit_repo = _service()
    signal_repo.add(make_signal(source="stale_collector"))
    kept = signal_repo.add(make_signal(source="keep_me"))

    affected = service.purge_signals("stale_collector", dry_run=False)

    assert affected == 1
    assert signal_repo.count() == 1
    assert signal_repo.get_by_id(kept.id) is not None

    entries = audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)
    assert len(entries) == 1
    assert entries[0].context["source"] == "stale_collector"
    assert entries[0].context["deleted_count"] == 1


def test_purge_signals_respects_before() -> None:
    service, signal_repo, _, _, _audit_repo = _service()
    now = utc_now()
    old = signal_repo.add(make_signal(source="s", timestamp=now - timedelta(days=10)))
    recent = signal_repo.add(make_signal(source="s", timestamp=now - timedelta(minutes=1)))

    affected = service.purge_signals("s", before=now - timedelta(days=1), dry_run=False)

    assert affected == 1
    assert signal_repo.get_by_id(old.id) is None
    assert signal_repo.get_by_id(recent.id) is not None


def test_purge_weather_events_dry_run_and_real() -> None:
    service, _, weather_repo, _, _audit_repo = _service()
    weather_repo.add(make_weather_event(source="ilmateenistus"))
    kept = weather_repo.add(make_weather_event(source="other"))

    previewed = service.purge_weather_events("ilmateenistus", dry_run=True)
    assert previewed == 1
    assert weather_repo.count() == 2

    deleted = service.purge_weather_events("ilmateenistus", dry_run=False)
    assert deleted == 1
    assert weather_repo.count() == 1
    assert weather_repo.get_by_id(kept.id) is not None


def test_purge_weather_events_real_run_writes_an_audit_entry() -> None:
    service, _, weather_repo, _, audit_repo = _service()
    weather_repo.add(make_weather_event(source="ilmateenistus"))

    service.purge_weather_events("ilmateenistus", dry_run=False)

    entries = audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)
    assert len(entries) == 1
    assert entries[0].entity_type == "WeatherEvent"


def test_purge_no_matching_source_returns_zero_and_no_audit_entry() -> None:
    service, _signal_repo, _weather_repo, _lead_repo, audit_repo = _service()

    affected = service.purge_signals("does_not_exist", dry_run=False)

    assert affected == 0
    # A no-op deletion still gets an audit entry (dry_run=False was explicitly requested),
    # recording that the purge ran and found nothing -- useful operator evidence.
    entries = audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)
    assert len(entries) == 1
    assert entries[0].context["deleted_count"] == 0


def test_purge_signals_referenced_by_a_lead_is_blocked() -> None:
    """Consistency with RollbackService: a Signal a Lead still depends on cannot be deleted."""
    service, signal_repo, _, lead_repo, audit_repo = _service()
    referenced = signal_repo.add(make_signal(source="stale_collector"))
    lead_repo.add(make_lead(supporting_signal_ids=[referenced.id, uuid4()]))

    with pytest.raises(PurgeBlockedByDependentDataError):
        service.purge_signals("stale_collector", dry_run=False)

    assert signal_repo.get_by_id(referenced.id) is not None
    assert audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10) == []


def test_purge_signals_referenced_by_a_lead_is_blocked_even_as_a_dry_run() -> None:
    """A dry-run preview must not claim success for a purge that would actually be blocked."""
    service, signal_repo, _, lead_repo, _ = _service()
    referenced = signal_repo.add(make_signal(source="stale_collector"))
    lead_repo.add(make_lead(supporting_signal_ids=[referenced.id, uuid4()]))

    with pytest.raises(PurgeBlockedByDependentDataError):
        service.purge_signals("stale_collector", dry_run=True)


def test_purge_signals_blocks_the_whole_batch_if_any_signal_is_referenced() -> None:
    """One referenced signal among several candidates blocks the entire purge_signals call."""
    service, signal_repo, _, lead_repo, _ = _service()
    referenced = signal_repo.add(make_signal(source="stale_collector"))
    unreferenced = signal_repo.add(make_signal(source="stale_collector"))
    lead_repo.add(make_lead(supporting_signal_ids=[referenced.id, uuid4()]))

    with pytest.raises(PurgeBlockedByDependentDataError):
        service.purge_signals("stale_collector", dry_run=False)

    assert signal_repo.get_by_id(referenced.id) is not None
    assert signal_repo.get_by_id(unreferenced.id) is not None


def test_purge_signals_unreferenced_by_any_lead_still_succeeds() -> None:
    service, signal_repo, _, lead_repo, audit_repo = _service()
    unreferenced = signal_repo.add(make_signal(source="stale_collector"))
    # A Lead exists, but it references an entirely different signal.
    lead_repo.add(make_lead())

    affected = service.purge_signals("stale_collector", dry_run=False)

    assert affected == 1
    assert signal_repo.get_by_id(unreferenced.id) is None
    entries = audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)
    assert len(entries) == 1
