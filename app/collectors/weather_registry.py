"""Weather collector registration and lookup.

Mirrors ``app.collectors.registry.CollectorRegistry`` exactly, kept as a
separate class (rather than modifying the existing, already-tested
registry) since it holds ``WeatherCollectorInterface`` instances, not
``CollectorInterface`` instances.
"""

from __future__ import annotations

from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.core.exceptions import ConfigurationError


class WeatherCollectorRegistry:
    """An in-memory registry mapping collector name -> WeatherCollectorInterface instance."""

    def __init__(self) -> None:
        self._collectors: dict[str, WeatherCollectorInterface] = {}

    def register(self, collector: WeatherCollectorInterface) -> None:
        """Register ``collector``, keyed by its ``name``.

        Raises:
            ConfigurationError: If a collector with the same name is already registered.
        """
        if collector.name in self._collectors:
            raise ConfigurationError(f"A collector named {collector.name!r} is already registered.")
        self._collectors[collector.name] = collector

    def get(self, name: str) -> WeatherCollectorInterface:
        """Return the registered collector named ``name``.

        Raises:
            ConfigurationError: If no collector with that name is registered.
        """
        try:
            return self._collectors[name]
        except KeyError as exc:
            raise ConfigurationError(f"No collector named {name!r} is registered.") from exc

    def list_all(self) -> list[WeatherCollectorInterface]:
        """Return every registered collector."""
        return list(self._collectors.values())

    def list_enabled(self, enabled_names: frozenset[str]) -> list[WeatherCollectorInterface]:
        """Return the registered collectors whose name is in ``enabled_names``."""
        return [c for name, c in self._collectors.items() if name in enabled_names]
