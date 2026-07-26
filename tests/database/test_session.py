"""Tests for app.database.session engine/session-factory construction."""

from __future__ import annotations

from app.config.settings import DatabaseConfig
from app.database.session import create_session_factory, create_sqlalchemy_engine, session_scope


def test_sqlite_engine_applies_the_configured_busy_timeout() -> None:
    config = DatabaseConfig(url="sqlite:///:memory:", busy_timeout_seconds=7.5)
    engine = create_sqlalchemy_engine(config)

    with engine.connect() as connection:
        (busy_timeout_ms,) = connection.exec_driver_sql("PRAGMA busy_timeout").fetchone()

    assert busy_timeout_ms == 7500


def test_sqlite_engine_uses_the_default_busy_timeout() -> None:
    config = DatabaseConfig(url="sqlite:///:memory:")
    engine = create_sqlalchemy_engine(config)

    with engine.connect() as connection:
        (busy_timeout_ms,) = connection.exec_driver_sql("PRAGMA busy_timeout").fetchone()

    assert busy_timeout_ms == 5000


def test_session_scope_commits_on_success() -> None:
    from app.database.models import Base

    config = DatabaseConfig(url="sqlite:///:memory:")
    engine = create_sqlalchemy_engine(config)
    Base.metadata.create_all(engine)
    session_factory = create_session_factory(engine)

    with session_scope(session_factory):
        pass  # no-op: just confirms the context manager commits without error


def test_session_scope_rolls_back_on_exception() -> None:
    config = DatabaseConfig(url="sqlite:///:memory:")
    engine = create_sqlalchemy_engine(config)
    session_factory = create_session_factory(engine)

    try:
        with session_scope(session_factory):
            raise ValueError("boom")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError to propagate")
