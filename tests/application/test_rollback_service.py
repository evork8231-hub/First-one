"""Tests for app.application.services.rollback_service.RollbackService."""

from __future__ import annotations

from uuid import uuid4

import pytest
from app.application.services.rollback_service import RollbackService
from app.core.exceptions import (
    CorruptedRollbackMetadataError,
    EntityNotFoundError,
    RollbackBlockedByDependentDataError,
    RollbackConflictError,
)
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.rollback_unit_of_work import InMemoryRollbackUnitOfWork
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_lead, make_signal, make_weather_event


def _service() -> tuple[
    RollbackService,
    InMemorySignalRepository,
    InMemoryWeatherEventRepository,
    InMemoryAuditLogRepository,
    InMemoryLeadRepository,
]:
    signal_repo = InMemorySignalRepository()
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    lead_repo = InMemoryLeadRepository()
    uow = InMemoryRollbackUnitOfWork(signal_repo, weather_repo, audit_repo)
    service = RollbackService(audit_repo, lead_repo, uow)
    return service, signal_repo, weather_repo, audit_repo, lead_repo


def _seed_completed_signal_run(
    audit_repo: InMemoryAuditLogRepository,
    signal_repo: InMemorySignalRepository,
    *,
    collector: str,
    execution_id: str | None = None,
    inserted_signal_ids: list[str] | None = None,
) -> tuple[str, list]:
    stored = [
        signal_repo.add(make_signal(source=collector)),
        signal_repo.add(make_signal(source=collector)),
    ]
    resolved_execution_id = execution_id or str(uuid4())
    audit_repo.add(
        AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
            entity_type="Collector",
            message=f"Collector {collector!r} produced {len(stored)} signal(s).",
            context={
                "collector": collector,
                "execution_id": resolved_execution_id,
                "inserted_signal_ids": (
                    inserted_signal_ids
                    if inserted_signal_ids is not None
                    else [str(s.id) for s in stored]
                ),
            },
        )
    )
    return resolved_execution_id, stored


def _seed_completed_weather_run(
    audit_repo: InMemoryAuditLogRepository,
    weather_repo: InMemoryWeatherEventRepository,
    *,
    collector: str,
) -> tuple[str, list]:
    stored = [weather_repo.add(make_weather_event(source=collector))]
    execution_id = str(uuid4())
    audit_repo.add(
        AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
            entity_type="WeatherCollector",
            message=f"Weather collector {collector!r} produced {len(stored)} event(s).",
            context={
                "collector": collector,
                "execution_id": execution_id,
                "inserted_event_ids": [str(e.id) for e in stored],
            },
        )
    )
    return execution_id, stored


def test_rollback_last_signal_run_dry_run_deletes_nothing_and_writes_no_audit_entry() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    result = service.rollback_last_signal_run("ehitisregister", dry_run=True)

    assert result.record_count == 2
    assert result.dry_run is True
    assert signal_repo.count() == 2
    assert audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10) == []


def test_rollback_last_signal_run_real_run_deletes_exactly_the_inserted_signals() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _, stored = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")
    kept = signal_repo.add(make_signal(source="other_collector"))

    result = service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 2
    assert signal_repo.count() == 1
    assert signal_repo.get_by_id(kept.id) is not None
    for signal in stored:
        assert signal_repo.get_by_id(signal.id) is None

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(entries) == 1
    assert entries[0].context["collector"] == "ehitisregister"
    assert entries[0].context["rolled_back_count"] == 2


def test_rollback_last_signal_run_never_modifies_the_original_completed_entry() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    service.rollback_last_signal_run("ehitisregister", dry_run=False)

    completed = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert len(completed) == 1


def test_rollback_last_signal_run_twice_raises_on_the_second_call() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    service.rollback_last_signal_run("ehitisregister", dry_run=False)

    with pytest.raises(EntityNotFoundError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)


def test_rollback_last_signal_run_only_rolls_back_the_most_recent_run() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _, first_run = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")
    _, second_run = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    result = service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 2
    for signal in second_run:
        assert signal_repo.get_by_id(signal.id) is None
    for signal in first_run:
        assert signal_repo.get_by_id(signal.id) is not None


def test_rollback_last_signal_run_ignores_other_collectors() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="kv_ee")

    with pytest.raises(EntityNotFoundError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)
    assert signal_repo.count() == 2


def test_rollback_last_signal_run_with_no_completed_run_raises() -> None:
    service, _, _, _, _ = _service()

    with pytest.raises(EntityNotFoundError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)


def test_rollback_last_weather_run_real_run_deletes_exactly_the_inserted_events() -> None:
    service, _, weather_repo, audit_repo, _ = _service()
    _, stored = _seed_completed_weather_run(audit_repo, weather_repo, collector="ilmateenistus")

    result = service.rollback_last_weather_run("ilmateenistus", dry_run=False)

    assert result.record_count == 1
    assert weather_repo.count() == 0
    for event in stored:
        assert weather_repo.get_by_id(event.id) is None

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(entries) == 1
    assert entries[0].entity_type == "WeatherCollector"


def test_rollback_last_weather_run_dry_run_previews_without_deleting() -> None:
    service, _, weather_repo, audit_repo, _ = _service()
    _seed_completed_weather_run(audit_repo, weather_repo, collector="ilmateenistus")

    result = service.rollback_last_weather_run("ilmateenistus", dry_run=True)

    assert result.record_count == 1
    assert result.dry_run is True
    assert weather_repo.count() == 1


def test_rollback_signal_run_does_not_affect_weather_runs_with_the_same_collector_name() -> None:
    service, signal_repo, weather_repo, audit_repo, _ = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="shared_name")
    _seed_completed_weather_run(audit_repo, weather_repo, collector="shared_name")

    service.rollback_last_signal_run("shared_name", dry_run=False)

    assert signal_repo.count() == 0
    assert weather_repo.count() == 1


def test_rollback_with_zero_inserted_records_still_records_the_rollback() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(
        audit_repo, signal_repo, collector="ehitisregister", inserted_signal_ids=[]
    )

    result = service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 0
    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(entries) == 1
    assert entries[0].context["rolled_back_count"] == 0
    # The two signals the collector actually stored are untouched -- an
    # empty inserted_signal_ids list must never be treated as "delete
    # everything from this collector."
    assert signal_repo.count() == 2


# --- Metadata validation ----------------------------------------------------


def test_rollback_raises_on_a_malformed_execution_id() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(
        audit_repo, signal_repo, collector="ehitisregister", execution_id="not-a-uuid"
    )

    with pytest.raises(CorruptedRollbackMetadataError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)

    # Fail-closed: nothing was deleted.
    assert signal_repo.count() == 2


def test_rollback_raises_when_inserted_signal_ids_is_not_a_list() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    execution_id = str(uuid4())
    signal_repo.add(make_signal(source="ehitisregister"))
    audit_repo.add(
        AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
            entity_type="Collector",
            message="Collector 'ehitisregister' produced 1 signal(s).",
            context={
                "collector": "ehitisregister",
                "execution_id": execution_id,
                "inserted_signal_ids": "not-a-list",
            },
        )
    )

    with pytest.raises(CorruptedRollbackMetadataError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert signal_repo.count() == 1


def test_rollback_raises_when_an_inserted_id_is_not_a_valid_uuid() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    execution_id = str(uuid4())
    signal = signal_repo.add(make_signal(source="ehitisregister"))
    audit_repo.add(
        AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
            entity_type="Collector",
            message="Collector 'ehitisregister' produced 1 signal(s).",
            context={
                "collector": "ehitisregister",
                "execution_id": execution_id,
                "inserted_signal_ids": [str(signal.id), "definitely-not-a-uuid"],
            },
        )
    )

    with pytest.raises(CorruptedRollbackMetadataError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert signal_repo.count() == 1


def test_corrupted_metadata_is_also_reported_on_a_dry_run() -> None:
    service, signal_repo, _, audit_repo, _ = _service()
    _seed_completed_signal_run(
        audit_repo, signal_repo, collector="ehitisregister", execution_id="garbage"
    )

    with pytest.raises(CorruptedRollbackMetadataError):
        service.rollback_last_signal_run("ehitisregister", dry_run=True)


# --- Lead-reference handling -------------------------------------------------


def test_rollback_is_blocked_when_a_lead_still_cites_one_of_the_signals() -> None:
    service, signal_repo, _, audit_repo, lead_repo = _service()
    _, stored = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")
    other_signal = signal_repo.add(make_signal(source="kv_ee"))
    lead_repo.add(make_lead(supporting_signal_ids=[stored[0].id, other_signal.id]))

    with pytest.raises(RollbackBlockedByDependentDataError):
        service.rollback_last_signal_run("ehitisregister", dry_run=False)

    # Fail-closed: nothing was deleted, no rollback was recorded.
    assert signal_repo.count() == 3
    assert audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10) == []


def test_rollback_blocked_by_lead_reference_is_also_reported_on_a_dry_run() -> None:
    service, signal_repo, _, audit_repo, lead_repo = _service()
    _, stored = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")
    other_signal = signal_repo.add(make_signal(source="kv_ee"))
    lead_repo.add(make_lead(supporting_signal_ids=[stored[0].id, other_signal.id]))

    with pytest.raises(RollbackBlockedByDependentDataError):
        service.rollback_last_signal_run("ehitisregister", dry_run=True)


def test_rollback_proceeds_when_no_lead_references_these_signals() -> None:
    service, signal_repo, _, audit_repo, lead_repo = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")
    unrelated_signal_a = signal_repo.add(make_signal(source="kv_ee"))
    unrelated_signal_b = signal_repo.add(make_signal(source="kv_ee"))
    lead_repo.add(make_lead(supporting_signal_ids=[unrelated_signal_a.id, unrelated_signal_b.id]))

    result = service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 2
    assert signal_repo.count() == 2


def test_weather_rollback_ignores_lead_references_entirely() -> None:
    """WeatherEvents are never cited by a Lead directly -- no dependent-data check applies."""
    service, _, weather_repo, audit_repo, lead_repo = _service()
    _seed_completed_weather_run(audit_repo, weather_repo, collector="ilmateenistus")
    lead_repo.add(make_lead())  # present, but irrelevant to a weather-event rollback

    result = service.rollback_last_weather_run("ilmateenistus", dry_run=False)

    assert result.record_count == 1
    assert weather_repo.count() == 0


# --- Concurrent rollback guard -----------------------------------------------


def test_a_second_rollback_of_the_same_execution_is_rejected_even_if_re_selected() -> None:
    """Simulates the race: the unit of work's own guard catches what the service-level
    "already rolled back" check would otherwise miss if two callers both read stale state."""
    signal_repo = InMemorySignalRepository()
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    uow = InMemoryRollbackUnitOfWork(signal_repo, weather_repo, audit_repo)
    execution_id, _ = _seed_completed_signal_run(
        audit_repo, signal_repo, collector="ehitisregister"
    )

    rollback_entry = AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK,
        entity_type="Collector",
        message="Rolled back collector 'ehitisregister'.",
        context={"collector": "ehitisregister", "execution_id": execution_id},
    )
    # First writer wins.
    uow.delete_signals_and_record_rollback([], rollback_entry)

    # A second writer racing on the exact same execution_id must be rejected,
    # even though it built its own, distinct AuditLogEntry (a different id).
    second_rollback_entry = AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK,
        entity_type="Collector",
        message="Rolled back collector 'ehitisregister'.",
        context={"collector": "ehitisregister", "execution_id": execution_id},
    )
    with pytest.raises(RollbackConflictError):
        uow.delete_signals_and_record_rollback([], second_rollback_entry)

    entries = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(entries) == 1  # never a duplicate
