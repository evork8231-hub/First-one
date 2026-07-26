"""SQLAlchemy persistence infrastructure.

Depends on ``app.domain`` (to convert to/from domain entities) but is
never depended on by the domain or application layers -- only by
``app.repositories.sqlite`` and ``app.core.container``. Schema is
designed to be portable to PostgreSQL (see ``docs/ARCHITECTURE.md``):
UUID primary keys via SQLAlchemy's generic ``Uuid`` type, JSON columns
via the generic ``JSON`` type, and string-backed enums instead of
SQLite-only constructs.
"""
