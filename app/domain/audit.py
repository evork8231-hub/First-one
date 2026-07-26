"""The AuditLogEntry entity.

Every meaningful state transition in the platform (a collector run, a
verification decision, a lead generation event, a configuration change)
should be recorded as an AuditLogEntry so the pipeline from public data to
lead is fully traceable and reviewable after the fact.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.domain.enums import AuditEventType
from app.utils.ids import new_id
from app.utils.time import utc_now


class AuditLogEntry(BaseModel):
    """An immutable record of a single noteworthy platform event.

    Attributes:
        id: Unique identifier for this entry.
        event_type: The category of event being recorded.
        entity_type: The kind of entity this event concerns (e.g.
            ``"Signal"``, ``"Lead"``, ``"Collector"``), if any.
        entity_id: The ID of the concerned entity, if any.
        message: Human-readable summary of what happened.
        created_at: When this entry was recorded. Timezone-aware.
        context: Structured extra detail (e.g. collector name, rule id).
    """

    model_config = ConfigDict(frozen=True)

    id: UUID = Field(default_factory=new_id)
    event_type: AuditEventType
    entity_type: str | None = Field(default=None)
    entity_id: UUID | None = Field(default=None)
    message: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=utc_now)
    context: dict[str, Any] = Field(default_factory=dict)

    @field_validator("created_at")
    @classmethod
    def _created_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("AuditLogEntry.created_at must be timezone-aware.")
        return value
