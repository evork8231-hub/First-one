"""Retry-safety tests for alembic/versions/0002_lead_identity_key.py.

Mandatory regression proof for a confirmed production blocker: the
migration used to issue a standalone ``ALTER TABLE ... ADD COLUMN`` that
SQLite commits immediately and irreversibly, independent of the
surrounding Alembic transaction. Interrupting the migration after that
statement but before ``alembic_version`` advances left a database where
``identity_key`` already existed but Alembic still believed it was at
revision ``0001`` -- so simply rerunning the migration (the only
documented recovery path, e.g. ``sigint init`` again) unconditionally
re-issued the same ``ADD COLUMN`` and failed with "duplicate column
name", permanently blocking the upgrade without manual SQL repair.

Every step in the migration now checks the database's actual current
state before acting and skips itself if already done, making the whole
migration safe to simply rerun after an interruption at any point.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from alembic import command as alembic_command
from alembic.config import Config
from app.domain.enums import ServiceCategory
from app.domain.lead import compute_lead_identity_key
from sqlalchemy import create_engine, inspect, text

# Crash injection must happen in a genuinely separate OS process. Simulating it via an
# in-process monkeypatched exception does not faithfully reproduce the real bug: Alembic's
# internal op/context state does not reset cleanly across repeated command.upgrade() calls
# within the same Python process after an exception (a proven test-harness artifact, not a
# reflection of production behaviour). In production a crashed process can never retry
# itself either -- recovery always happens via a fresh process (e.g. rerunning
# `sigint init`), exactly what these two subprocess scripts simulate.
_CRASH_AFTER_ADD_COLUMN_SCRIPT = """
import sys
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config
from sqlalchemy.engine import Connection

repo_root = Path.cwd()
cfg = Config(str(repo_root / "alembic.ini"))
cfg.set_main_option("script_location", str(repo_root / "alembic"))

orig_execute = Connection.execute


def _crash_after_add_column(self, statement, *args, **kwargs):
    if "ALTER TABLE leads ADD COLUMN identity_key" in str(statement):
        orig_execute(self, statement, *args, **kwargs)  # let it actually commit
        raise RuntimeError("simulated crash right after ADD COLUMN, before alembic_version updates")
    return orig_execute(self, statement, *args, **kwargs)


Connection.execute = _crash_after_add_column

try:
    alembic_command.upgrade(cfg, "0002")
except RuntimeError as exc:
    if "simulated crash" in str(exc):
        sys.exit(0)
    raise
else:
    sys.exit(1)  # migration unexpectedly completed without hitting the injected crash
"""

_RETRY_SCRIPT = """
from pathlib import Path

from alembic import command as alembic_command
from alembic.config import Config

repo_root = Path.cwd()
cfg = Config(str(repo_root / "alembic.ini"))
cfg.set_main_option("script_location", str(repo_root / "alembic"))
alembic_command.upgrade(cfg, "0002")
"""


def _run_in_subprocess(script: str, db_path: Path) -> subprocess.CompletedProcess[str]:
    repo_root = _repo_root()
    env = {**os.environ, "SIGINT_DATABASE__URL": f"sqlite:///{db_path}"}
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "alembic.ini").exists():
            return candidate
    raise FileNotFoundError("Could not locate alembic.ini above the tests package.")


def _alembic_config(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> Config:
    # alembic/env.py resolves the URL itself via app.config.loader.load_settings() at
    # migration-run time -- the environment variable is what actually controls which
    # database gets migrated; see tests/database/test_migrations.py for the same pattern.
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    repo_root = _repo_root()
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def _insert_raw_lead_at_0001_schema(
    engine, *, signal_ids: list[str], lead_type: str = "roofing"
) -> str:
    """Insert a Lead row using only columns that exist as of migration 0001 -- simulates
    a Lead persisted before this database was ever upgraded past 0001."""
    lead_id = str(uuid4())
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                INSERT INTO leads (id, lead_type, supporting_signal_ids, country, county,
                    municipality, estimated_location, estimated_confidence, intent_score,
                    priority, reasoning, created_at, verification_status)
                VALUES (:id, :lead_type, :signal_ids, :country, :county, :municipality, :loc,
                    :ec, :is_, :prio, :reasoning, :created_at, :vs)
                """
            ),
            {
                "id": lead_id,
                "lead_type": lead_type,
                "signal_ids": json.dumps(signal_ids),
                "country": "EE",
                "county": "Harju",
                "municipality": "Tallinn",
                "loc": json.dumps({"county": "Harju", "municipality": "Tallinn"}),
                "ec": 0.7,
                "is_": 0.65,
                "prio": "medium",
                "reasoning": "pre-existing row from before the identity_key migration",
                "created_at": datetime.now(UTC).isoformat(),
                "vs": "unverified",
            },
        )
    return lead_id


def test_migration_survives_a_crash_after_add_column_and_completes_on_retry(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The mandatory crash-recovery proof: interrupt migration 0002 immediately after its
    ADD COLUMN statement succeeds (the exact point that broke retries), confirm the
    database is left with the column present but alembic_version still at 0001, then
    rerun the upgrade exactly as an operator re-running 'sigint init' would -- it must
    complete successfully, with no manual SQL repair.
    """
    db_path = tmp_path / "crash_recovery.db"
    cfg = _alembic_config(db_path, monkeypatch)
    alembic_command.upgrade(cfg, "0001")

    engine = create_engine(f"sqlite:///{db_path}")
    signal_ids = [str(uuid4()), str(uuid4())]
    lead_id = _insert_raw_lead_at_0001_schema(engine, signal_ids=signal_ids)
    engine.dispose()

    crash_result = _run_in_subprocess(_CRASH_AFTER_ADD_COLUMN_SCRIPT, db_path)
    assert crash_result.returncode == 0, (
        "the crash-injection subprocess must observe the simulated RuntimeError right "
        f"after ADD COLUMN, not fail some other way:\nstdout={crash_result.stdout}\n"
        f"stderr={crash_result.stderr}"
    )

    # Confirm the exact broken state the bug report described.
    check_engine = create_engine(f"sqlite:///{db_path}")
    columns = {c["name"] for c in inspect(check_engine).get_columns("leads")}
    with check_engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    check_engine.dispose()
    assert (
        "identity_key" in columns
    ), "the column must have survived the crash (SQLite auto-commits DDL)"
    assert version == "0001", "alembic_version must not have advanced past the crash point"

    # The actual fix: rerunning the migration (a fresh process, exactly like an operator
    # re-running 'sigint init') must now succeed with no manual SQL repair.
    retry_result = _run_in_subprocess(_RETRY_SCRIPT, db_path)
    assert (
        retry_result.returncode == 0
    ), f"retry must succeed:\nstdout={retry_result.stdout}\nstderr={retry_result.stderr}"

    final_engine = create_engine(f"sqlite:///{db_path}")
    with final_engine.connect() as conn:
        final_version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
        row = conn.execute(
            text("SELECT identity_key FROM leads WHERE id = :id"), {"id": lead_id}
        ).fetchone()
    indexes = {ix["name"] for ix in inspect(final_engine).get_indexes("leads")}
    final_engine.dispose()

    assert final_version == "0002"
    assert "ix_leads_identity_key" in indexes
    expected = compute_lead_identity_key(ServiceCategory.ROOFING, [UUID(s) for s in signal_ids])
    assert (
        row is not None and row[0] == expected
    ), "the pre-existing row must be correctly backfilled"


def test_upgrade_against_an_empty_database(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "empty.db"
    cfg = _alembic_config(db_path, monkeypatch)

    alembic_command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar()
    indexes = {ix["name"] for ix in inspect(engine).get_indexes("leads")}
    engine.dispose()

    assert version == "0002"
    assert "ix_leads_identity_key" in indexes


def test_upgrade_against_a_database_with_one_existing_lead(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "one_lead.db"
    cfg = _alembic_config(db_path, monkeypatch)
    alembic_command.upgrade(cfg, "0001")

    engine = create_engine(f"sqlite:///{db_path}")
    signal_ids = [str(uuid4()), str(uuid4())]
    lead_id = _insert_raw_lead_at_0001_schema(engine, signal_ids=signal_ids)
    engine.dispose()

    alembic_command.upgrade(cfg, "head")

    engine2 = create_engine(f"sqlite:///{db_path}")
    with engine2.connect() as conn:
        row = conn.execute(
            text("SELECT identity_key FROM leads WHERE id = :id"), {"id": lead_id}
        ).fetchone()
    engine2.dispose()

    expected = compute_lead_identity_key(ServiceCategory.ROOFING, [UUID(s) for s in signal_ids])
    assert row is not None and row[0] == expected


def test_upgrade_against_a_database_with_multiple_existing_leads(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "many_leads.db"
    cfg = _alembic_config(db_path, monkeypatch)
    alembic_command.upgrade(cfg, "0001")

    engine = create_engine(f"sqlite:///{db_path}")
    lead_ids = [
        _insert_raw_lead_at_0001_schema(engine, signal_ids=[str(uuid4()), str(uuid4())])
        for _ in range(5)
    ]
    engine.dispose()
    assert len(lead_ids) == 5

    alembic_command.upgrade(cfg, "head")

    engine2 = create_engine(f"sqlite:///{db_path}")
    with engine2.connect() as conn:
        rows = conn.execute(text("SELECT id, identity_key FROM leads")).fetchall()
    engine2.dispose()

    assert len(rows) == 5
    assert all(identity_key is not None for _id, identity_key in rows)
    assert (
        len({identity_key for _id, identity_key in rows}) == 5
    ), "each distinct Lead must get its own key"

    # Rerunning the migration again (already fully applied) must be a safe no-op.
    alembic_command.upgrade(cfg, "head")
    engine3 = create_engine(f"sqlite:///{db_path}")
    with engine3.connect() as conn:
        rows_after_rerun = conn.execute(text("SELECT id, identity_key FROM leads")).fetchall()
    engine3.dispose()
    assert sorted(rows_after_rerun) == sorted(rows)
