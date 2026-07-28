"""Migration-drift protection: proves the real Alembic migration chain produces exactly the
schema ``app.database.models.Base.metadata`` describes -- not merely a schema close enough
that ``Base.metadata.create_all()`` (what every other repository-level test fixture uses,
see ``tests/conftest.py``'s ``sqlite_engine``) would happen to work against it.

Without this test, a migration file falling out of sync with an ORM model change (a column
added to a model but never given a matching ``alembic revision``, or the reverse) would go
completely undetected: every other test drives schema creation through
``Base.metadata.create_all()``, which bypasses Alembic entirely, and only
``sigint init`` (exercised by ``tests/cli/test_cli.py``) runs the real migration chain --
without ever diffing the result against the ORM metadata it's supposed to match.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command as alembic_command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from app.database.models import Base
from sqlalchemy import create_engine


def _repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "alembic.ini").exists():
            return candidate
    raise FileNotFoundError("Could not locate alembic.ini above the tests package.")


def test_alembic_migrations_produce_a_schema_matching_orm_metadata(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Create an empty database, run every Alembic migration up to head (the exact same
    code path ``sigint init`` uses -- see ``app.cli.commands.init_cmd.init``), then diff the
    resulting live schema against ``Base.metadata`` with Alembic's own autogenerate comparison.
    A non-empty diff means a migration is missing, extra, or out of sync with the ORM models.
    """
    db_path = tmp_path / "migration_drift.db"
    # alembic/env.py resolves the URL itself via app.config.loader.load_settings() at
    # migration-run time -- setting alembic_cfg's own "sqlalchemy.url" option below is not
    # enough to redirect it (that only affects this Config object's fallback/log value), so
    # the environment variable is what actually controls which database gets migrated.
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")

    repo_root = _repo_root()
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
    alembic_cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")

    alembic_command.upgrade(alembic_cfg, "head")

    assert db_path.exists(), "the migration must have created the database file"

    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            diff = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diff == [], f"live schema (from Alembic migrations) drifted from Base.metadata: {diff}"
