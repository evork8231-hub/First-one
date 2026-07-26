"""The WeatherEvent entity.

Weather events are stored independently from Signals (their own database
table) but are also surfaced to the correlation engine as a
``SignalType.WEATHER_EVENT`` Signal so the rule engine can reason about
them uniformly. A WeatherEvent never becomes a Lead by itself -- per the
mission rules, weather only ever adjusts the confidence of other signals.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import WeatherEventType
from app.domain.value_objects import Coordinates
from app.utils.ids import new_id


class WeatherEvent(BaseModel):
    """A severe weather occurrence recorded from a public meteorological source.

    Attributes:
        id: Unique identifier for this event.
        event_type: The category of severe weather observed.
        source: Name of the meteorological data source (e.g. the Estonian
            Environment Agency, "ilmateenistus.ee").
        source_url: URL the event was retrieved from, if applicable.
        county: Estonian county the event affected.
        municipality: Estonian municipality the event affected.
        coordinates: Approximate coordinates of the event, if published.
        severity: Source-reported severity, normalized to [0.0, 1.0].
        started_at: When the event began.
        ended_at: When the event ended. Must not precede ``started_at``.
        raw_payload: The unmodified data retrieved from the source.
        metadata: Extension bag for source-specific detail.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID = Field(default_factory=new_id)
    event_type: WeatherEventType
    source: str = Field(min_length=1)
    source_url: str | None = Field(default=None)
    county: str = Field(min_length=1)
    municipality: str = Field(min_length=1)
    coordinates: Coordinates | None = Field(default=None)
    severity: float = Field(ge=0.0, le=1.0)
    started_at: datetime
    ended_at: datetime
    raw_payload: dict[str, Any]
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("started_at", "ended_at")
    @classmethod
    def _must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("WeatherEvent timestamps must be timezone-aware.")
        return value

    @model_validator(mode="after")
    def _ended_not_before_started(self) -> WeatherEvent:
        if self.ended_at < self.started_at:
            raise ValueError("WeatherEvent.ended_at cannot precede started_at.")
        return self
