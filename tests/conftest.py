"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from app.config.loader import clear_settings_cache
from app.database.models import Base
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture(autouse=True)
def _isolated_settings_cache() -> Iterator[None]:
    """Keep app.config.loader's in-process settings cache from leaking between tests."""
    clear_settings_cache()
    yield
    clear_settings_cache()


@pytest.fixture()
def sqlite_engine() -> Iterator[Engine]:
    """An in-memory SQLite engine, shared across connections for the test's duration."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture()
def sqlite_session_factory(sqlite_engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(
        bind=sqlite_engine, autoflush=False, autocommit=False, expire_on_commit=False
    )
