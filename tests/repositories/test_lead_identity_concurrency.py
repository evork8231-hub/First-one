"""Tests proving Lead identity uniqueness is enforced at the database level.

Closes the concurrency race ``LeadGenerationService.generate_from_matches``'s
``find_by_identity``-then-``add`` alone could not: two callers can both
observe "no existing Lead" before either writes. ``leads.identity_key``
(see ``app.database.models.lead_model.LeadModel`` and
``app.domain.lead.compute_lead_identity_key``) is a real, database-level
unique index, and ``SQLiteLeadRepository.add()`` now catches the resulting
``IntegrityError`` and resolves it by returning the Lead that actually won
the race -- these tests exercise that against a real file-backed SQLite
database, including under genuinely concurrent OS threads, which an
in-memory repository or a single-threaded test cannot demonstrate at all.
"""

from __future__ import annotations

import threading
import time
from uuid import uuid4

from app.application.services.lead_generation_service import LeadGenerationService
from app.database.models import Base
from app.database.session import create_session_factory
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from sqlalchemy import create_engine

from tests.fixtures.factories import make_lead
from tests.fixtures.fakes import FakeLeadGenerator


def test_add_returns_the_existing_lead_when_a_conflicting_identity_already_exists(
    sqlite_session_factory,
) -> None:
    """Deterministic (non-threaded) proof of add()'s conflict-recovery path: if a Lead
    with the same identity already exists by the time add() is called, add() returns
    that existing Lead instead of raising or creating a duplicate -- true even if
    whatever called add() skipped (or lost a race on) its own find_by_identity check.
    """
    repo = SQLiteLeadRepository(sqlite_session_factory)
    signal_ids = [uuid4(), uuid4()]
    first = repo.add(make_lead(supporting_signal_ids=signal_ids))

    second_candidate = make_lead(supporting_signal_ids=signal_ids)  # fresh id, same identity
    assert second_candidate.id != first.id

    result = repo.add(second_candidate)

    assert result.id == first.id, "add() must return the Lead that actually won, not a new one"
    assert repo.count() == 1


def test_add_still_creates_a_new_lead_when_the_identity_is_genuinely_different(
    sqlite_session_factory,
) -> None:
    repo = SQLiteLeadRepository(sqlite_session_factory)
    first = repo.add(make_lead())
    second = repo.add(make_lead())  # make_lead() defaults to a fresh random signal-id pair

    assert first.id != second.id
    assert repo.count() == 2


def test_concurrent_add_for_the_same_identity_under_real_threads_never_duplicates(
    tmp_path,
) -> None:
    """The mandatory regression proof: several real OS threads racing to persist a Lead
    for the exact same evidence (identical lead_type + supporting_signal_ids, but each
    thread builds its own independent Lead object with a fresh id -- exactly what two
    concurrently-running 'sigint pipeline'/'sigint generate' processes would each
    independently produce from the same underlying verified Signals) against one real,
    file-backed SQLite database must leave exactly one Lead behind.

    The race window is forced open deterministically (a short sleep between
    find_by_identity's read and the caller's write) rather than left to incidental
    thread-scheduling luck -- against the pre-fix design (an application-level
    find_by_identity check with no database constraint backing it), this reliably
    produces multiple duplicate Leads, confirmed empirically while diagnosing this bug:
    5 threads, 5 duplicate Leads, zero errors. With the identity_key unique constraint
    and add()'s conflict handling, exactly one Lead survives no matter how many threads
    race, and every thread's call returns without error.
    """
    db_path = tmp_path / "lead_race.db"
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False, "timeout": 10}
    )
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    lead_repo = SQLiteLeadRepository(session_factory)
    audit_repo = SQLiteAuditLogRepository(session_factory)

    orig_find_by_identity = lead_repo.find_by_identity

    def _slow_find_by_identity(*args: object, **kwargs: object) -> object:
        result = orig_find_by_identity(*args, **kwargs)
        time.sleep(0.05)  # give every other thread a chance to reach the same conclusion
        return result

    lead_repo.find_by_identity = _slow_find_by_identity  # type: ignore[method-assign]

    fixed_signal_ids = [uuid4(), uuid4()]  # the same real-world evidence for every thread
    persisted_counts: list[int] = []
    errors: list[str] = []
    lock = threading.Lock()

    def _attempt() -> None:
        try:
            candidate = make_lead(supporting_signal_ids=fixed_signal_ids)
            service = LeadGenerationService(FakeLeadGenerator([candidate]), lead_repo, audit_repo)
            persisted = service.generate_from_matches([])
            with lock:
                persisted_counts.append(len(persisted))
        except Exception as exc:
            with lock:
                errors.append(f"{type(exc).__name__}: {exc}")

    threads = [threading.Thread(target=_attempt) for _ in range(5)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=15)

    engine.dispose()

    assert errors == [], f"no racing thread should see an unhandled error: {errors}"
    assert len(persisted_counts) == 5, "every thread must complete"
    assert lead_repo.count() == 1, "exactly one Lead must survive the concurrent race"
