"""Geographic distance calculation used by duplicate detection."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt

from app.domain.value_objects import Coordinates

#: Mean Earth radius in meters (standard value used by the haversine formula).
_EARTH_RADIUS_METERS = 6_371_000.0


def haversine_distance_meters(a: Coordinates, b: Coordinates) -> float:
    """Return the great-circle distance between two coordinates, in meters."""
    lat1, lon1, lat2, lon2 = (
        radians(v) for v in (a.latitude, a.longitude, b.latitude, b.longitude)
    )
    delta_lat = lat2 - lat1
    delta_lon = lon2 - lon1
    h = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
    return 2 * _EARTH_RADIUS_METERS * asin(sqrt(h))
