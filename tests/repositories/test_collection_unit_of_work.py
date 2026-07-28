"""Tests for app.repositories.sqlite.collection_unit_of_work.SQLiteCollectionUnitOfWork.

These specifically exercise real SQLite transaction/commit behavior --
in-memory-repository tests (``test_signal_service.py``/
``test_weather_event_service.py``) cover ``SignalService``/
``WeatherEventService``'s own logic in isolation, which cannot
demonstrate atomicity at all (a process-local dict has nothing to roll
back).

Mandatory proof for Production Blocker 2 (collection atomicity): the
Signal/WeatherEvent rows and the ``COLLECTOR_RUN_COMPLETED`` audit entry
must commit or fail together, so an interrupted collection run can never
leave records persisted with no completion entry -- which would
otherwise make them permanently invisible to
``RollbackService`` (it can only discover a run through that entry's
``inserted_signal_ids``/``inserted_event_ids``).
"""

from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest
from app.application.interfaces.collection_unit_of_work import CollectedSignal
from app.application.services.rollback_service import RollbackService
from app.application.services.signal_service import SignalService
from app.application.services.weather_event_service import WeatherEventService
from app.database.models.audit_log_model import AuditLogModel
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.collection_unit_of_work import SQLiteCollectionUnitOfWork
from app.repositories.sqlite.rollback_unit_of_work import SQLiteRollbackUnitOfWork
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from sqlalchemy.orm import Session

from tests.fixtures.factories import make_signal, make_weather_event
from tests.fixtures.fakes import FakeCollector, FakeWeatherCollector


def _collected_signal(*, source: str = "ehitisregister") -> CollectedSignal:
    signal = make_signal(source=source)
    entry = AuditLogEntry(
        event_type=AuditEventType.SIGNAL_INGESTED,
        entity_type="Signal",
        entity_id=signal.id,
        message=f"Ingested signal from {source!r}.",
        context={"collector": source},
    )
    return CollectedSignal(signal=signal, ingested_entry=entry)


def _completion_entry(*, collector: str, execution_id: str, record_ids: list[str]) -> AuditLogEntry:
    return AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
        entity_type="Collector",
        message=f"Collector {collector!r} produced {len(record_ids)} signal(s).",
        context={
            "collector": collector,
            "signal_count": len(record_ids),
            "execution_id": execution_id,
            "inserted_signal_ids": record_ids,
        },
    )


def test_record_signal_collection_happy_path_persists_signals_and_completion_audit(
    sqlite_session_factory,
) -> None:
    """Test 1: a successful collection persists every signal, its own audit entry, and the
    completion entry, all visible immediately after one call."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)

    collected = [_collected_signal(), _collected_signal()]
    entry = _completion_entry(
        collector="ehitisregister",
        execution_id=str(uuid4()),
        record_ids=[str(item.signal.id) for item in collected],
    )

    stored = uow.record_signal_collection(collected, entry)

    assert len(stored) == 2
    for item in collected:
        assert signal_repo.get_by_id(item.signal.id) is not None
    ingested = audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10)
    assert len(ingested) == 2
    completed = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert len(completed) == 1


def test_record_weather_collection_happy_path_persists_events_and_completion_audit(
    sqlite_session_factory,
) -> None:
    weather_repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)

    events = [make_weather_event(), make_weather_event()]
    entry = AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
        entity_type="WeatherCollector",
        message="Weather collector produced 2 event(s).",
        context={"collector": "ilmateenistus", "event_count": 2},
    )

    stored = uow.record_weather_collection(events, entry)

    assert len(stored) == 2
    for event in events:
        assert weather_repo.get_by_id(event.id) is not None
    completed = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert len(completed) == 1


def test_record_signal_collection_with_no_signals_still_records_the_completion_entry(
    sqlite_session_factory,
) -> None:
    """Mirrors the pre-existing behavior: a run that legitimately collected nothing new
    still gets a COLLECTOR_RUN_COMPLETED entry."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    entry = _completion_entry(collector="ehitisregister", execution_id=str(uuid4()), record_ids=[])

    stored = uow.record_signal_collection([], entry)

    assert stored == []
    assert signal_repo.count() == 0
    completed = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10)
    assert len(completed) == 1


def test_forced_completion_audit_failure_rolls_back_every_signal_leaving_no_partial_state(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 2: forces the completion-audit entry's own construction to fail, specifically
    simulating "everything about the signals themselves was staged for persistence, then
    recording the run's completion failed" -- distinct from a generic disk/lock commit
    error (covered separately below). If signal persistence and the completion write were
    still two separate transactions (the pre-fix design), the signals would already have
    been committed in their own, earlier transaction by this point, with no
    COLLECTOR_RUN_COMPLETED entry to let RollbackService ever find them again. With one
    shared transaction, nothing reaches the database at all until the shared
    ``session.flush()``/commit, which this failure never reaches -- session_scope's
    `except Exception: session.rollback()` discards the whole pending batch, signals
    included.
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    collected = [_collected_signal(), _collected_signal(), _collected_signal()]
    entry = _completion_entry(
        collector="ehitisregister",
        execution_id=str(uuid4()),
        record_ids=[str(item.signal.id) for item in collected],
    )

    real_from_domain = AuditLogModel.from_domain
    call_count = {"n": 0}

    def _fail_on_completion_entry(
        cls: type[AuditLogModel], domain_entry: AuditLogEntry
    ) -> AuditLogModel:
        call_count["n"] += 1
        # Let the per-signal SIGNAL_INGESTED entries through; fail only on the
        # COLLECTOR_RUN_COMPLETED entry, which is always added last.
        if domain_entry.event_type == AuditEventType.COLLECTOR_RUN_COMPLETED:
            raise RuntimeError("simulated completion-audit write failure")
        return real_from_domain(domain_entry)

    monkeypatch.setattr(AuditLogModel, "from_domain", classmethod(_fail_on_completion_entry))

    with pytest.raises(RuntimeError):
        uow.record_signal_collection(collected, entry)

    monkeypatch.undo()  # restore AuditLogModel.from_domain before verifying via the repositories

    assert call_count["n"] >= 1
    for item in collected:
        assert signal_repo.get_by_id(item.signal.id) is None, "no signal must have persisted"
    assert audit_repo.list_all(event_type=AuditEventType.SIGNAL_INGESTED, limit=10) == []
    assert audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_COMPLETED, limit=10) == []


def test_multi_record_collection_failure_leaves_every_signal_untouched(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 3: with several signals in the batch, a failure during the completion-audit
    write must leave *all* of them unpersisted -- not just some partial subset."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    collected = [_collected_signal() for _ in range(5)]
    entry = _completion_entry(
        collector="ehitisregister",
        execution_id=str(uuid4()),
        record_ids=[str(item.signal.id) for item in collected],
    )

    def _failing_commit(self: Session) -> None:
        raise RuntimeError("simulated commit failure (disk full / locked)")

    monkeypatch.setattr(Session, "commit", _failing_commit)

    with pytest.raises(RuntimeError):
        uow.record_signal_collection(collected, entry)

    monkeypatch.undo()

    for item in collected:
        assert signal_repo.get_by_id(item.signal.id) is None, "every signal must survive nothing"
    assert signal_repo.count() == 0


def test_record_signal_collection_issues_exactly_one_commit_per_call(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct regression guard, not just a proxy for it: the pre-fix design ran
    add_many, N per-signal audit writes, and the completion write as N+2 separate
    session_scope calls (N+2 commits). Counting Session.commit invocations during one
    record_signal_collection call and asserting exactly one is what would actually catch a
    regression back to that design -- a test that instead injects a failure on every commit
    cannot distinguish "one atomic transaction" from "several transactions that all happen
    to fail at the first one too" (see the equivalent lesson already documented in
    tests/repositories/test_weather_bridge_unit_of_work.py and
    tests/repositories/test_purge_unit_of_work.py).
    """
    uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    collected = [_collected_signal(), _collected_signal(), _collected_signal()]
    entry = _completion_entry(
        collector="ehitisregister",
        execution_id=str(uuid4()),
        record_ids=[str(item.signal.id) for item in collected],
    )

    commit_calls = 0
    orig_commit = Session.commit

    def _counting_commit(self: Session) -> None:
        nonlocal commit_calls
        commit_calls += 1
        orig_commit(self)

    monkeypatch.setattr(Session, "commit", _counting_commit)

    stored = uow.record_signal_collection(collected, entry)

    assert len(stored) == 3
    assert commit_calls == 1, (
        f"expected exactly one commit for the whole collection run, got {commit_calls} -- a "
        f"regression to per-write transactions (the pre-fix design) would show 5 here "
        f"(1 signal batch insert + 1 audit write/signal * 3 signals + 1 completion write) "
        f"and reintroduce the signals-with-no-completion-entry window this unit of work "
        f"exists to close."
    )


def test_rollback_can_always_discover_and_undo_a_completed_signal_collection(
    sqlite_session_factory,
) -> None:
    """Test (Blocker 2, requirement 3): drives the real SignalService -> real
    SQLiteCollectionUnitOfWork -> real RollbackService -> real SQLiteRollbackUnitOfWork
    path end to end, proving a successfully completed collection run can always be found
    and undone by 'sigint rollback' -- not just that its data was persisted."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    collection_uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    rollback_uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)
    lead_repo = InMemoryLeadRepository()  # no Leads involved in this scenario

    signal_service = SignalService(signal_repo, audit_repo, collection_uow)
    collector = FakeCollector([make_signal(), make_signal()], name="ehitisregister")
    stored = asyncio.run(signal_service.ingest_from_collector(collector))
    assert signal_repo.count() == 2

    rollback_service = RollbackService(audit_repo, lead_repo, rollback_uow)
    result = rollback_service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 2
    assert signal_repo.count() == 0, "rollback must have found and deleted every signal"
    for signal in stored:
        assert signal_repo.get_by_id(signal.id) is None


def test_rollback_can_always_discover_and_undo_a_completed_weather_collection(
    sqlite_session_factory,
) -> None:
    weather_repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    collection_uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    rollback_uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)
    lead_repo = InMemoryLeadRepository()

    weather_service = WeatherEventService(audit_repo, collection_uow)
    collector = FakeWeatherCollector([make_weather_event()], name="ilmateenistus")
    stored = asyncio.run(weather_service.ingest_from_collector(collector))
    assert weather_repo.count() == 1

    rollback_service = RollbackService(audit_repo, lead_repo, rollback_uow)
    result = rollback_service.rollback_last_weather_run("ilmateenistus", dry_run=False)

    assert result.record_count == 1
    assert weather_repo.count() == 0
    assert weather_repo.get_by_id(stored[0].id) is None


def test_interrupted_collection_leaves_nothing_for_rollback_to_ever_need_to_find(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test (Blocker 2, requirement 4): an interrupted collection run (completion-audit
    write fails) must never leave orphaned Signals that rollback can't locate -- because,
    with atomic persistence, it never leaves any Signals at all. A subsequent successful
    retry is then a completely ordinary, fully-rollback-discoverable run."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    collection_uow = SQLiteCollectionUnitOfWork(sqlite_session_factory)
    rollback_uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)
    lead_repo = InMemoryLeadRepository()

    signal_service = SignalService(signal_repo, audit_repo, collection_uow)

    def _failing_commit(self: Session) -> None:
        raise RuntimeError("simulated interrupted collection run")

    monkeypatch.setattr(Session, "commit", _failing_commit)
    interrupted_collector = FakeCollector([make_signal(), make_signal()], name="ehitisregister")
    with pytest.raises(RuntimeError):
        asyncio.run(signal_service.ingest_from_collector(interrupted_collector))
    monkeypatch.undo()

    assert signal_repo.count() == 0, "the interrupted run must not have left any signal orphaned"

    # The operator retries the collection normally.
    retry_collector = FakeCollector([make_signal(), make_signal()], name="ehitisregister")
    asyncio.run(signal_service.ingest_from_collector(retry_collector))
    assert signal_repo.count() == 2

    rollback_service = RollbackService(audit_repo, lead_repo, rollback_uow)
    result = rollback_service.rollback_last_signal_run("ehitisregister", dry_run=False)

    assert result.record_count == 2, "the retried run must be fully discoverable by rollback"
    assert signal_repo.count() == 0
