"""Tests for app.repositories.sqlite.purge_unit_of_work.SQLitePurgeUnitOfWork.

These specifically exercise real SQLite transaction/commit behavior --
``tests/application/test_data_management_service.py`` covers
``DataManagementService``'s own dependency-check/dry-run logic against
the in-memory unit of work, which cannot demonstrate atomicity at all (a
process-local dict has nothing to roll back).

Mandatory proof for the purge-atomicity fix: the DELETE and the
``DATA_PURGED`` audit INSERT must commit or fail together, so a crash
between them can never leave data deleted with no audit trail of it.
"""

from __future__ import annotations

import pytest
from app.application.services.data_management_service import DataManagementService
from app.core.exceptions import PurgeBlockedByDependentDataError
from app.database.models.audit_log_model import AuditLogModel
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from app.repositories.sqlite.purge_unit_of_work import SQLitePurgeUnitOfWork
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from sqlalchemy.orm import Session

from tests.fixtures.factories import make_lead, make_signal, make_weather_event


def _purge_entry(*, entity_type: str, source: str, deleted_count: int) -> AuditLogEntry:
    return AuditLogEntry(
        event_type=AuditEventType.DATA_PURGED,
        entity_type=entity_type,
        message=f"Purged {deleted_count} record(s) from source {source!r}.",
        context={"source": source, "before": None, "deleted_count": deleted_count},
    )


def test_purge_signals_and_record_happy_path_deletes_and_writes_an_audit_entry(
    sqlite_session_factory,
) -> None:
    """Test 1: a successful purge deletes exactly the given signals and creates one
    DATA_PURGED audit entry, both visible immediately after one call."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)

    to_delete = signal_repo.add(make_signal(source="stale_collector"))
    kept = signal_repo.add(make_signal(source="other"))
    entry = _purge_entry(entity_type="Signal", source="stale_collector", deleted_count=1)

    deleted = uow.purge_signals_and_record([to_delete.id], entry)

    assert deleted == 1
    assert signal_repo.get_by_id(to_delete.id) is None
    assert signal_repo.get_by_id(kept.id) is not None
    entries = audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)
    assert len(entries) == 1
    assert entries[0].context["deleted_count"] == 1


def test_purge_weather_events_and_record_happy_path_deletes_and_writes_an_audit_entry(
    sqlite_session_factory,
) -> None:
    weather_repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)

    to_delete = weather_repo.add(make_weather_event(source="ilmateenistus"))
    entry = _purge_entry(entity_type="WeatherEvent", source="ilmateenistus", deleted_count=1)

    deleted = uow.purge_weather_events_and_record([to_delete.id], entry)

    assert deleted == 1
    assert weather_repo.get_by_id(to_delete.id) is None
    entries = audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)
    assert len(entries) == 1


def test_empty_id_list_still_records_the_purge_but_deletes_nothing(
    sqlite_session_factory,
) -> None:
    """Mirrors DataManagementService's existing behavior: a real (non-dry-run) purge that
    matched nothing still writes an audit entry recording that it ran and found nothing."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)
    kept = signal_repo.add(make_signal(source="stale_collector"))
    entry = _purge_entry(entity_type="Signal", source="does_not_exist", deleted_count=0)

    deleted = uow.purge_signals_and_record([], entry)

    assert deleted == 0
    assert signal_repo.get_by_id(kept.id) is not None  # never a mass delete
    assert len(audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10)) == 1


def test_forced_audit_write_failure_rolls_back_the_deletion_leaving_no_partial_state(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 2: forces the audit-log write step itself to fail -- not just a generic
    commit-time error -- specifically simulating "the deletion happened, then recording it
    failed." By the time this fires, ``session.execute(delete(...))`` has already run
    against the connection; if the delete and the audit write were still two separate
    transactions (the pre-fix design), the delete would already be irreversibly committed.
    With one shared transaction, session_scope's `except Exception: session.rollback()`
    must undo the delete too, since the exception propagates before ``session.commit()``
    is ever reached.
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)
    to_delete = signal_repo.add(make_signal(source="stale_collector"))
    entry = _purge_entry(entity_type="Signal", source="stale_collector", deleted_count=1)

    def _failing_from_domain(
        cls: type[AuditLogModel], domain_entry: AuditLogEntry
    ) -> AuditLogModel:
        raise RuntimeError("simulated audit log write failure")

    monkeypatch.setattr(AuditLogModel, "from_domain", classmethod(_failing_from_domain))

    with pytest.raises(RuntimeError):
        uow.purge_signals_and_record([to_delete.id], entry)

    monkeypatch.undo()  # restore AuditLogModel.from_domain before verifying via the repositories

    assert signal_repo.get_by_id(to_delete.id) is not None, "the delete must not have persisted"
    assert audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10) == []


def test_multi_record_purge_failure_leaves_every_record_untouched(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Test 3: with several signals in the batch, a failure during the audit write must
    leave *all* of them in place -- not just the first, and not some partial subset."""
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)
    to_delete = [
        signal_repo.add(make_signal(source="stale_collector")),
        signal_repo.add(
            make_signal(source="stale_collector", county="Pärnu", municipality="Pärnu")
        ),
        signal_repo.add(
            make_signal(source="stale_collector", county="Tartu", municipality="Tartu")
        ),
    ]
    entry = _purge_entry(entity_type="Signal", source="stale_collector", deleted_count=3)

    def _failing_from_domain(
        cls: type[AuditLogModel], domain_entry: AuditLogEntry
    ) -> AuditLogModel:
        raise RuntimeError("simulated audit log write failure")

    monkeypatch.setattr(AuditLogModel, "from_domain", classmethod(_failing_from_domain))

    with pytest.raises(RuntimeError):
        uow.purge_signals_and_record([s.id for s in to_delete], entry)

    monkeypatch.undo()

    for signal in to_delete:
        assert signal_repo.get_by_id(signal.id) is not None, "every record must survive the failure"
    assert audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10) == []


def test_purge_signals_and_record_issues_exactly_one_commit_per_call(
    sqlite_session_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct regression guard, not just a proxy for it: the pre-fix design ran
    ``delete_by_source`` and ``audit_log_repository.add`` as two separate ``session_scope``
    calls (two commits). Counting ``Session.commit`` invocations during one
    ``purge_signals_and_record`` call and asserting exactly one is what would actually catch
    a regression back to that design -- a test that instead injects a failure on every
    commit cannot distinguish "one atomic transaction" from "several transactions that all
    happen to fail at the first one too" (see the equivalent lesson already documented in
    ``tests/repositories/test_weather_bridge_unit_of_work.py``).
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)
    to_delete = [
        signal_repo.add(make_signal(source="stale_collector")),
        signal_repo.add(
            make_signal(source="stale_collector", county="Pärnu", municipality="Pärnu")
        ),
    ]
    entry = _purge_entry(entity_type="Signal", source="stale_collector", deleted_count=2)

    commit_calls = 0
    orig_commit = Session.commit

    def _counting_commit(self: Session) -> None:
        nonlocal commit_calls
        commit_calls += 1
        orig_commit(self)

    monkeypatch.setattr(Session, "commit", _counting_commit)

    deleted = uow.purge_signals_and_record([s.id for s in to_delete], entry)

    assert deleted == 2
    assert commit_calls == 1, (
        f"expected exactly one commit for the delete + audit write, got {commit_calls} -- a "
        f"regression to separate transactions would show 2 and reintroduce the "
        f"deleted-with-no-audit-trail window this unit of work exists to close."
    )


def test_purge_signals_referenced_by_a_lead_is_blocked_before_reaching_the_unit_of_work(
    sqlite_session_factory,
) -> None:
    """Test 4: DataManagementService's existing dependency-blocking behavior is unchanged --
    the check happens entirely in the service, before the unit of work is ever called, so
    this exercises the real SQLite-backed repositories end to end through the service to
    confirm nothing about the new unit of work weakened that guarantee.
    """
    signal_repo = SQLiteSignalRepository(sqlite_session_factory)
    weather_repo = SQLiteWeatherEventRepository(sqlite_session_factory)
    lead_repo = SQLiteLeadRepository(sqlite_session_factory)
    uow = SQLitePurgeUnitOfWork(sqlite_session_factory)
    service = DataManagementService(signal_repo, weather_repo, lead_repo, uow)

    referenced = signal_repo.add(make_signal(source="stale_collector"))
    other_signal = signal_repo.add(make_signal(source="stale_collector"))
    lead_repo.add(make_lead(supporting_signal_ids=[referenced.id, other_signal.id]))

    with pytest.raises(PurgeBlockedByDependentDataError):
        service.purge_signals("stale_collector", dry_run=False)

    assert signal_repo.get_by_id(referenced.id) is not None
    assert signal_repo.get_by_id(other_signal.id) is not None
    audit_repo = SQLiteAuditLogRepository(sqlite_session_factory)
    assert audit_repo.list_all(event_type=AuditEventType.DATA_PURGED, limit=10) == []
