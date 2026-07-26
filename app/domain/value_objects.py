"""Immutable value objects used by Signal and Lead entities.

All value objects are frozen Pydantic models: two instances with equal
field values are interchangeable, and none of them carry an identity of
their own.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Coordinates(BaseModel):
    """A WGS84 latitude/longitude pair.

    Coordinates must come from a verifiable public source (e.g. a building
    registry or municipal open-data set). This platform never estimates or
    invents coordinates.
    """

    model_config = ConfigDict(frozen=True)

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)


class Address(BaseModel):
    """A postal address as observed from a public source.

    ``county`` and ``municipality`` should match Estonian administrative
    division names (maakond / vald / linn), ideally cross-referenced against
    the official EHAK classifier in a future phase. The foundation does not
    hardcode or validate against that list; it only requires non-empty,
    whitespace-trimmed values so callers cannot silently pass blank strings.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    county: str = Field(min_length=1, description="Estonian county (maakond), e.g. 'Harju'.")
    municipality: str = Field(min_length=1, description="Municipality (vald/linn), e.g. 'Tallinn'.")
    settlement: str | None = Field(default=None, description="Town, village, or district (asula).")
    street: str | None = Field(default=None)
    house_number: str | None = Field(default=None)
    postal_code: str | None = Field(default=None)
    raw: str | None = Field(
        default=None,
        description="The address exactly as it appeared at the source, kept for auditability.",
    )


class EstimatedLocation(BaseModel):
    """A deliberately coarser location used on generated Leads.

    Leads describe *areas of opportunity* derived from correlated Signals,
    not exact addresses of individuals. ``precision_radius_meters``
    documents how coarse the estimate is so downstream consumers do not
    over-interpret precision the platform does not have.
    """

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    county: str = Field(min_length=1)
    municipality: str = Field(min_length=1)
    settlement: str | None = Field(default=None)
    approximate_coordinates: Coordinates | None = Field(default=None)
    precision_radius_meters: float | None = Field(
        default=None,
        ge=0,
        description="Radius describing the uncertainty of approximate_coordinates, if present.",
    )

    @model_validator(mode="after")
    def _radius_requires_coordinates(self) -> EstimatedLocation:
        if self.precision_radius_meters is not None and self.approximate_coordinates is None:
            raise ValueError("precision_radius_meters requires approximate_coordinates to be set.")
        return self
