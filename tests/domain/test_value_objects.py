"""Tests for app.domain.value_objects."""

from __future__ import annotations

import pytest
from app.domain.value_objects import Coordinates, EstimatedLocation
from pydantic import ValidationError


def test_coordinates_reject_out_of_range_latitude() -> None:
    with pytest.raises(ValidationError):
        Coordinates(latitude=95.0, longitude=10.0)


def test_coordinates_reject_out_of_range_longitude() -> None:
    with pytest.raises(ValidationError):
        Coordinates(latitude=10.0, longitude=-200.0)


def test_coordinates_accept_valid_values() -> None:
    coordinates = Coordinates(latitude=59.437, longitude=24.7536)
    assert coordinates.latitude == 59.437


def test_estimated_location_without_coordinates_is_valid() -> None:
    location = EstimatedLocation(county="Harju", municipality="Tallinn")
    assert location.approximate_coordinates is None


def test_estimated_location_radius_requires_coordinates() -> None:
    with pytest.raises(ValidationError):
        EstimatedLocation(county="Harju", municipality="Tallinn", precision_radius_meters=100.0)


def test_estimated_location_with_coordinates_and_radius_is_valid() -> None:
    location = EstimatedLocation(
        county="Harju",
        municipality="Tallinn",
        approximate_coordinates=Coordinates(latitude=59.437, longitude=24.7536),
        precision_radius_meters=250.0,
    )
    assert location.precision_radius_meters == 250.0
