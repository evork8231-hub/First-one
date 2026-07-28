"""Tests for app.application.services.rollback_service.RollbackService."""

from __future__ import annotations

from uuid import uuid4

from app.application.services.rollback_service import RollbackService
from app.core.exceptions import EntityNotFoundError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository

from tests.fixtures.factories import make_signal, make_weather_event


def _service() -> tuple[
    RollbackService,
    InMemorySignalRepository,
    InMemoryWeatherEventRepository,
    InMemoryAuditLogRepository,
]:
    signal_repo = InMemorySignalRepository()
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()
    service = RollbackService(signal_repo, weather_repo, audit_repo)
    return service, signal_repo, weather_repo, audit_repo


def _seed_completed_signal_run(
    audit_repo: InMemoryAuditLogRepository, signal_repo: InMemorySignalRepository, *, collector: str
) -> tuple[str, list]:
    stored = [
        signal_repo.add(make_signal(source=collector)),
        signal_repo.add(make_signal(source=collector)),
    ]
    execution_id = str(uuid4())
    audit_repo.add(
        AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
            entity_type="Collector",
            message=f"Collector {collector!r} produced {len(stored)} signal(s).",
            context={
                "collector": collector,
                "execution_id": execution_id,
                "inserted_signal_ids": [str(s.id) for s in stored],
            },
        )
    )
    return execution_id, stored


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
    service, signal_repo, _, audit_repo = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    result = service.rollback_last_signal_run("ehitisregister", dry_run=True)

    assert result.record_count == 2
    assert result.dry_run is True
    assert signal_repo.count() == 2
    assert audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10) == []


def test_rollback_last_signal_run_real_run_deletes_exactly_the_inserted_signals() -> None:
    service, signal_repo, _, audit_repo = _service()
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
    service, signal_repo, _, audit_repo = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    service.rollback_last_signal_run("ehitisregister", dry_run=False)

    completed = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert len(completed) == 1


def test_rollback_last_signal_run_twice_raises_on_the_second_call() -> None:
    service, signal_repo, _, audit_repo = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    service.rollback_last_signal_run("ehitisregister", dry_run=False)

    try:
        service.rollback_last_signal_run("ehitisregister", dry_run=False)
        raise AssertionError("expected EntityNotFoundError")
    except EntityNotFoundError:
        pass


def test_rollback_last_signal_run_only_rolls_back_the_most_recent_run() -> None:
    service, signal_repo, _, audit_repo = _service()
    _, first_run = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")
    _, second_run = _seed_completed_signal_run(audit_repo, signal_repo, collector="ehitisregister")

    result = service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 2
    for signal in second_run:
        assert signal_repo.get_by_id(signal.id) is None
    for signal in first_run:
        assert signal_repo.get_by_id(signal.id) is not None


def test_rollback_last_signal_run_ignores_other_collectors() -> None:
    service, signal_repo, _, audit_repo = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="kv_ee")

    try:
        service.rollback_last_signal_run("ehitisregister", dry_run=False)
        raise AssertionError("expected EntityNotFoundError")
    except EntityNotFoundError:
        pass
    assert signal_repo.count() == 2


def test_rollback_last_signal_run_with_no_completed_run_raises() -> None:
    service, _, _, _ = _service()

    try:
        service.rollback_last_signal_run("ehitisregister", dry_run=False)
        raise AssertionError("expected EntityNotFoundError")
    except EntityNotFoundError:
        pass


def test_rollback_last_weather_run_real_run_deletes_exactly_the_inserted_events() -> None:
    service, _, weather_repo, audit_repo = _service()
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
    service, _, weather_repo, audit_repo = _service()
    _seed_completed_weather_run(audit_repo, weather_repo, collector="ilmateenistus")

    result = service.rollback_last_weather_run("ilmateenistus", dry_run=True)

    assert result.record_count == 1
    assert result.dry_run is True
    assert weather_repo.count() == 1


def test_rollback_signal_run_does_not_affect_weather_runs_with_the_same_collector_name() -> None:
    service, signal_repo, weather_repo, audit_repo = _service()
    _seed_completed_signal_run(audit_repo, signal_repo, collector="shared_name")
    _seed_completed_weather_run(audit_repo, weather_repo, collector="shared_name")

    service.rollback_last_signal_run("shared_name", dry_run=False)

    assert signal_repo.count() == 0
    assert weather_repo.count() == 1
