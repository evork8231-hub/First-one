"""Shared SQLAlchemy column-type helpers used across ORM models."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Enum


def enum_column(enum_cls: type, *, length: int) -> Enum:
    """Build a portable, string-backed SQLAlchemy Enum column type.

    Stores the Python Enum's ``.value`` (not its ``.name``) as a plain
    VARCHAR, so the schema stays readable and portable to PostgreSQL
    without relying on a native database ENUM type.
    """
    return Enum(
        enum_cls,
        values_callable=lambda cls: [member.value for member in cls],
        length=length,
        native_enum=False,
    )


def to_storage_utc(value: datetime) -> datetime:
    """Normalize a timezone-aware datetime to UTC before persisting it.

    SQLite's ``DATETIME`` storage has no concept of an offset: SQLAlchemy's
    sqlite dialect silently drops ``tzinfo`` when formatting the value for
    storage, so a non-UTC input would otherwise be written using the wrong
    wall-clock numbers. Converting to UTC first makes the stored value
    correct regardless of the input's original timezone, and is a no-op
    for backends (e.g. PostgreSQL) that preserve the offset natively.
    """
    return value.astimezone(UTC)


def assume_utc(value: datetime) -> datetime:
    """Reattach UTC tzinfo to a datetime read back from storage, if missing.

    Pairs with :func:`to_storage_utc`: SQLite always returns naive
    datetimes on read, which the domain layer never accepts, since every
    persisted timestamp was normalized to UTC before being written.
    """
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)
