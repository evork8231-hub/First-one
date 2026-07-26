"""The Signal entity: a single verifiable public fact.

Signals represent facts observed at a public source. They are never leads,
never contain personal information, and never identify a homeowner. A
Signal's ``raw_payload`` must always be the actual data retrieved from its
``source`` -- this platform never fabricates or invents signal content.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.enums import Country, ServiceCategory, SignalType, VerificationStatus
from app.domain.value_objects import Address, Coordinates
from app.utils.ids import new_id

_FUTURE_TOLERANCE = timedelta(minutes=5)


class Signal(BaseModel):
    """An immutable record of a single publicly observed fact.

    Attributes:
        id: Unique identifier for this signal.
        signal_type: What kind of fact this signal represents.
        source: Human-readable name of the data source or collector that
            produced this signal (e.g. ``"ehr.ee"``, ``"kv.ee"``). Must
            identify a real, specific public source -- never a placeholder.
        source_url: The exact URL the fact was retrieved from, when the
            source is web-based.
        service_category: Which home-improvement service category this
            signal is relevant to.
        country: ISO country of the property this signal concerns.
        county: Estonian county (maakond).
        municipality: Estonian municipality (vald/linn).
        address: Structured address detail, if available from the source.
        coordinates: Geographic coordinates, if published by the source.
        building_identifier: A public building/property registry code
            (e.g. an Estonian Building Registry -- Ehitisregister -- code),
            never a personal identifier.
        timestamp: When the underlying fact occurred or was published at
            the source. Must be timezone-aware.
        raw_payload: The unmodified data retrieved from the source, kept
            for auditability and re-verification.
        confidence: The collector's own estimate, in [0.0, 1.0], of how
            reliable this signal's data is. Independent of verification
            and independent of any Lead's scoring.
        verified: Verification lifecycle state. Starts UNVERIFIED; only a
            SignalVerifier implementation may advance it.
        metadata: Extension bag for source-specific detail that does not
            warrant a first-class field (e.g. a linked WeatherEvent id).
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    id: UUID = Field(default_factory=new_id)
    signal_type: SignalType
    source: str = Field(min_length=1)
    source_url: str | None = Field(default=None)
    service_category: ServiceCategory
    country: Country = Country.ESTONIA
    county: str = Field(min_length=1)
    municipality: str = Field(min_length=1)
    address: Address | None = Field(default=None)
    coordinates: Coordinates | None = Field(default=None)
    building_identifier: str | None = Field(default=None)
    timestamp: datetime
    raw_payload: dict[str, Any]
    confidence: float = Field(ge=0.0, le=1.0)
    verified: VerificationStatus = VerificationStatus.UNVERIFIED
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _timestamp_must_be_timezone_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("Signal.timestamp must be timezone-aware.")
        if value > datetime.now(UTC).astimezone(value.tzinfo) + _FUTURE_TOLERANCE:
            raise ValueError("Signal.timestamp cannot be in the future.")
        return value

    @model_validator(mode="after")
    def _address_must_agree_with_top_level_location(self) -> Signal:
        if self.address is not None:
            if self.address.county.casefold() != self.county.casefold():
                raise ValueError("Signal.address.county must match Signal.county.")
            if self.address.municipality.casefold() != self.municipality.casefold():
                raise ValueError("Signal.address.municipality must match Signal.municipality.")
        return self

    def with_verification(self, status: VerificationStatus) -> Signal:
        """Return a copy of this signal with its verification status updated.

        Signals are frozen (immutable), so verification produces a new
        instance rather than mutating the original -- callers persist the
        returned copy via a SignalRepository.
        """
        return self.model_copy(update={"verified": status})
