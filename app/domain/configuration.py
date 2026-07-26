"""The ConfigurationEntry entity.

Represents a single named configuration value persisted to the database's
Configuration table. This is distinct from the file-based configuration
loaded at startup (see ``app.config``); it exists for configuration that
operators adjust at runtime (e.g. temporarily disabling a rule) without a
redeploy, with a full audit trail of who changed what and when.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.utils.ids import new_id
from app.utils.time import utc_now


class ConfigurationEntry(BaseModel):
    """A single runtime-adjustable configuration value.

    Attributes:
        id: Unique identifier for this entry.
        key: Dotted configuration key (e.g. ``"rules.roofing_storm.enabled"``).
        value: The configured value, stored as JSON-compatible data.
        description: Human-readable explanation of what this key controls.
        updated_at: When this entry was last changed. Timezone-aware.
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    key: str = Field(min_length=1)
    value: Any
    description: str | None = Field(default=None)
    updated_at: datetime = Field(default_factory=utc_now)

    @field_validator("updated_at")
    @classmethod
    def _updated_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("ConfigurationEntry.updated_at must be timezone-aware.")
        return value
