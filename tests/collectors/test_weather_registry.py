"""Tests for app.collectors.weather_registry.WeatherCollectorRegistry."""

from __future__ import annotations

import pytest
from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.collectors.weather_registry import WeatherCollectorRegistry
from app.core.exceptions import ConfigurationError
from app.domain.weather import WeatherEvent


class _FakeWeatherCollector(WeatherCollectorInterface):
    def __init__(self, name: str) -> None:
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> str:
        return "fake-source"

    async def collect(self) -> list[WeatherEvent]:
        return []


def test_register_and_get() -> None:
    registry = WeatherCollectorRegistry()
    collector = _FakeWeatherCollector("fake")
    registry.register(collector)

    assert registry.get("fake") is collector


def test_get_missing_raises_configuration_error() -> None:
    registry = WeatherCollectorRegistry()
    with pytest.raises(ConfigurationError):
        registry.get("missing")


def test_register_duplicate_name_raises() -> None:
    registry = WeatherCollectorRegistry()
    registry.register(_FakeWeatherCollector("dup"))
    with pytest.raises(ConfigurationError):
        registry.register(_FakeWeatherCollector("dup"))


def test_list_enabled_filters_by_name() -> None:
    registry = WeatherCollectorRegistry()
    registry.register(_FakeWeatherCollector("a"))
    registry.register(_FakeWeatherCollector("b"))

    enabled = registry.list_enabled(frozenset({"a"}))

    assert [c.name for c in enabled] == ["a"]


def test_list_all_returns_every_registered_collector() -> None:
    registry = WeatherCollectorRegistry()
    registry.register(_FakeWeatherCollector("a"))
    registry.register(_FakeWeatherCollector("b"))

    assert {c.name for c in registry.list_all()} == {"a", "b"}
