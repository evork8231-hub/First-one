"""The shared SQLAlchemy declarative base."""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base every ORM model in ``app.database.models`` inherits from.

    Kept in its own module (rather than alongside a specific model) so
    Alembic's ``env.py`` can import ``Base.metadata`` without pulling in
    every model module individually.
    """
