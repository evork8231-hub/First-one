"""The WeatherCollectorInterface.

Mirrors ``app.application.interfaces.collector.CollectorInterface`` but
for sources that report weather occurrences rather than property facts.
Kept as a separate, narrow interface (Interface Segregation) rather than
widening ``CollectorInterface.collect()`` to return a union type: a
WeatherEvent is not a Signal, and per the mission rule "weather never
becomes a lead, weather only affects confidence," collapsing the two
interfaces would blur a distinction the rest of the platform depends on.

A weather collector never returns a Signal and never generates a Lead.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.weather import WeatherEvent


class WeatherCollectorInterface(ABC):
    """Contract every weather-event collector must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A stable, unique identifier for this collector (e.g. ``"ilmateenistus_forecast"``)."""

    @property
    @abstractmethod
    def source(self) -> str:
        """The public data source this collector reads from, used as ``WeatherEvent.source``."""

    @abstractmethod
    async def collect(self) -> list[WeatherEvent]:
        """Read the public source and return the WeatherEvents it currently reports.

        Implementations must only return events built from data actually
        retrieved from ``source``. Transient failures should be retried
        internally (see ``app.core.retry``) and terminal failures should
        raise a subclass of ``app.core.exceptions.CollectorError``.
        """
