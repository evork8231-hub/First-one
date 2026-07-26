"""Engine and session factory construction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config.settings import DatabaseConfig


def ensure_sqlite_directory(url: str) -> None:
    """Create the parent directory of a file-based SQLite URL if it does not exist.

    A no-op for non-SQLite URLs and for SQLite's in-memory URL.
    """
    prefix = "sqlite:///"
    if not url.startswith(prefix) or url == "sqlite:///:memory:":
        return
    db_path = Path(url[len(prefix) :])
    if db_path.parent != Path():
        db_path.parent.mkdir(parents=True, exist_ok=True)


def create_sqlalchemy_engine(config: DatabaseConfig) -> Engine:
    """Build the SQLAlchemy Engine for ``config``.

    For SQLite, ``timeout`` sets the busy-wait before a lock-contended
    write raises "database is locked" -- transient contention (e.g. a
    concurrent collector run and a CLI command writing at the same time)
    then resolves itself instead of failing on the first collision.
    """
    ensure_sqlite_directory(config.url)
    connect_args: dict[str, object] = (
        {"check_same_thread": False, "timeout": config.busy_timeout_seconds}
        if config.url.startswith("sqlite")
        else {}
    )
    return create_engine(config.url, echo=config.echo, connect_args=connect_args)


def create_session_factory(engine: Engine) -> sessionmaker[Session]:
    """Build a session factory bound to ``engine``."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


@contextmanager
def session_scope(session_factory: sessionmaker[Session]) -> Iterator[Session]:
    """Yield a Session, committing on success and rolling back on any exception."""
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
