"""Collector registration and lookup.

New signal sources register a collector here by name; which collectors are
actually *enabled* is a configuration concern (see
``app.config.settings.CollectorsConfig``), not something this registry
decides on its own.
"""

from __future__ import annotations

from app.application.interfaces.collector import CollectorInterface
from app.core.exceptions import ConfigurationError


class CollectorRegistry:
    """An in-memory registry mapping collector name -> CollectorInterface instance."""

    def __init__(self) -> None:
        self._collectors: dict[str, CollectorInterface] = {}

    def register(self, collector: CollectorInterface) -> None:
        """Register ``collector``, keyed by its ``name``.

        Raises:
            ConfigurationError: If a collector with the same name is already registered.
        """
        if collector.name in self._collectors:
            raise ConfigurationError(f"A collector named {collector.name!r} is already registered.")
        self._collectors[collector.name] = collector

    def get(self, name: str) -> CollectorInterface:
        """Return the registered collector named ``name``.

        Raises:
            ConfigurationError: If no collector with that name is registered.
        """
        try:
            return self._collectors[name]
        except KeyError as exc:
            raise ConfigurationError(f"No collector named {name!r} is registered.") from exc

    def list_all(self) -> list[CollectorInterface]:
        """Return every registered collector."""
        return list(self._collectors.values())

    def list_enabled(self, enabled_names: frozenset[str]) -> list[CollectorInterface]:
        """Return the registered collectors whose name is in ``enabled_names``."""
        return [c for name, c in self._collectors.items() if name in enabled_names]
