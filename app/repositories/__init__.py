"""Concrete repository implementations.

``app.repositories.sqlite`` is the production backend (SQLAlchemy +
SQLite, portable to PostgreSQL later). ``app.repositories.in_memory`` is
a lightweight backend used by unit tests and local experimentation so
tests never need a real database file. Both implement the exact same
interfaces from ``app.application.interfaces.repositories`` and are
interchangeable via ``app.core.container``.
"""
