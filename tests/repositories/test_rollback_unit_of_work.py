"""Tests for app.repositories.sqlite.rollback_unit_of_work.SQLiteRollbackUnitOfWork.

These specifically exercise real SQLite transaction/locking behavior --
``tests/application/test_rollback_service.py`` covers ``RollbackService``'s
own logic against the in-memory unit of work, which cannot demonstrate
atomicity or real cross-connection concurrency at all.
"""

from __future__ import annotations

import threading
from uuid import uuid4

import pytest
from app.database.models import Base
from app.database.session import create_session_factory
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.rollback_unit_of_work import SQLiteRollbackUnitOfWork
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from tests.fixtures.factories import make_signal, make_weather_event


def _rollback_entry(*, collector: str, execution_id: str, record_count: int = 0) -> AuditLogEntry:
    return AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK,
        entity_type="Collector",
        message=f"Rolled back collector {collector!r}.",
        context={
            "collector": collector,
            "execution_id": execution_id,
            "rolled_back_count": record_count,
        },
    )


def test_delete_signals_and_record_rollback_happy_path(sqlite_session_factory) -> None:
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)

    to_delete = signal_repo.add(make_signal(source="ehitisregister"))
    kept = signal_repo.add(make_signal(source="other"))
    entry = _rollback_entry(collector="ehitisregister", execution_id=str(uuid4()), record_count=1)

    deleted = uow.delete_signals_and_record_rollback([to_delete.id], entry)

    assert deleted == 1
    assert signal_repo.get_by_id(to_delete.id) is None
    assert signal_repo.get_by_id(kept.id) is not None
    rolled_back = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(rolled_back) == 1


def test_delete_weather_events_and_record_rollback_happy_path(sqlite_session_factory) -> None:
    weather_repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)

    to_delete = weather_repo.add(make_weather_event(source="ilmateenistus"))
    entry = _rollback_entry(collector="ilmateenistus", execution_id=str(uuid4()), record_count=1)

    deleted = uow.delete_weather_events_and_record_rollback([to_delete.id], entry)

    assert deleted == 1
    assert weather_repo.get_by_id(to_delete.id) is None
    rolled_back = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(rolled_back) == 1


def test_empty_id_list_still_records_the_rollback_but_deletes_nothing(
    sqlite_session_factory,
) -> None:
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)
    kept = signal_repo.add(make_signal(source="ehitisregister"))
    entry = _rollback_entry(collector="ehitisregister", execution_id=str(uuid4()), record_count=0)

    deleted = uow.delete_signals_and_record_rollback([], entry)

    assert deleted == 0
    assert signal_repo.get_by_id(kept.id) is not None  # never a mass delete
    assert (
        len(audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)) == 1
    )


def test_atomicity_a_failure_at_commit_leaves_nothing_persisted(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Simulates 'delete succeeded, then something failed before the transaction closed.'

    Forces Session.commit to raise -- by the time this fires, the audit
    INSERT has already been flushed to the connection and the DELETE has
    already executed, exactly mirroring a crash/disk-full/lock failure at
    the last moment. If the fix in this module were not atomic (still two
    separate session_scope calls), the delete would already be
    irreversibly committed by this point. With one shared transaction,
    session_scope's `except Exception: session.rollback()` must undo both.
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLiteRollbackUnitOfWork(sqlite_session_factory)
    to_delete = signal_repo.add(make_signal(source="ehitisregister"))
    entry = _rollback_entry(collector="ehitisregister", execution_id=str(uuid4()), record_count=1)

    def _failing_commit(self: Session) -> None:
        raise OperationalError("simulated commit failure (disk full / locked)", None, Exception())

    monkeypatch.setattr(Session, "commit", _failing_commit)

    with pytest.raises(OperationalError):
        uow.delete_signals_and_record_rollback([to_delete.id], entry)

    monkeypatch.undo()  # restore Session.commit before using the repositories again to verify

    assert signal_repo.get_by_id(to_delete.id) is not None, "the delete must not have persisted"
    assert (
        audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10) == []
    ), "the rollback audit entry must not have persisted either"


def test_second_writer_racing_the_same_execution_id_is_rejected(tmp_path) -> None:
    """Two independent connections to the same on-disk database, simulating two
    'sigint rollback --yes' processes racing on the same collector run."""
    db_path = tmp_path / "race.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 5}
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    signal_repo = SQLiteSignalRepository(session_factory)
    to_delete = signal_repo.add(make_signal(source="ehitisregister"))
    execution_id = str(uuid4())

    # Two independent unit-of-work instances, as two separate CLI
    # invocations would each build their own via the DI container.
    uow_a = SQLiteRollbackUnitOfWork(session_factory)
    uow_b = SQLiteRollbackUnitOfWork(session_factory)

    entry_a = _rollback_entry(collector="ehitisregister", execution_id=execution_id, record_count=1)
    entry_b = _rollback_entry(collector="ehitisregister", execution_id=execution_id, record_count=1)
    assert entry_a.id != entry_b.id  # distinct audit rows, same execution -- the actual race

    deleted_a = uow_a.delete_signals_and_record_rollback([to_delete.id], entry_a)
    assert deleted_a == 1

    with pytest.raises(Exception) as exc_info:
        uow_b.delete_signals_and_record_rollback([to_delete.id], entry_b)
    assert "already rolled back" in str(exc_info.value)

    audit_repo = SQLiteAuditLogRepository(session_factory)
    rolled_back = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(rolled_back) == 1, "the second, racing writer must never produce a duplicate entry"

    engine.dispose()


def test_concurrent_rollback_under_real_threads_never_duplicates(tmp_path) -> None:
    """A genuine multi-threaded race, not just a sequential simulation.

    The outcome of *which* thread wins is not deterministic and not
    asserted; the invariant that must hold regardless is that exactly one
    rollback is ever recorded and the records are deleted exactly once.
    """
    db_path = tmp_path / "thread_race.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 10}
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    signal_repo = SQLiteSignalRepository(session_factory)
    to_delete = signal_repo.add(make_signal(source="ehitisregister"))
    execution_id = str(uuid4())

    results: list[str] = []
    lock = threading.Lock()

    def _attempt() -> None:
        uow = SQLiteRollbackUnitOfWork(session_factory)
        entry = _rollback_entry(
            collector="ehitisregister", execution_id=execution_id, record_count=1
        )
        try:
            uow.delete_signals_and_record_rollback([to_delete.id], entry)
            outcome = "success"
        except Exception:
            outcome = "conflict"
        with lock:
            results.append(outcome)

    threads = [threading.Thread(target=_attempt) for _ in range(2)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    assert sorted(results) == ["conflict", "success"]
    assert signal_repo.get_by_id(to_delete.id) is None

    audit_repo = SQLiteAuditLogRepository(session_factory)
    rolled_back = audit_repo.list_all(event_type=AuditEventType.COLLECTOR_RUN_ROLLED_BACK, limit=10)
    assert len(rolled_back) == 1

    engine.dispose()


def test_audit_log_list_all_orders_identical_timestamps_deterministically(
    sqlite_session_factory,
) -> None:
    """ORDER BY created_at DESC alone is not deterministic for equal timestamps;
    the rowid DESC tiebreaker must make repeated calls agree with each other
    and reflect true insertion order (most recently inserted first)."""
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    from app.utils.time import utc_now

    tied_timestamp = utc_now()
    first = AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
        entity_type="Collector",
        message="first",
        created_at=tied_timestamp,
        context={"collector": "x", "execution_id": "1"},
    )
    second = AuditLogEntry(
        event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
        entity_type="Collector",
        message="second",
        created_at=tied_timestamp,
        context={"collector": "x", "execution_id": "2"},
    )
    audit_repo.add(first)
    audit_repo.add(second)

    first_call = audit_repo.list_all(limit=10)
    second_call = audit_repo.list_all(limit=10)

    assert [e.id for e in first_call] == [e.id for e in second_call], "must be repeatable"
    assert first_call[0].message == "second", "most recently inserted must sort first on a tie"
