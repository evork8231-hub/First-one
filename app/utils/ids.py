"""Entity ID generation."""

from __future__ import annotations

from uuid import UUID, uuid4


def new_id() -> UUID:
    """Generate a new random (v4) entity identifier."""
    return uuid4()
