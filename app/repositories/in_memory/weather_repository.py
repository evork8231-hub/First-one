"""In-memory WeatherEventRepository implementation, used primarily in tests."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.application.interfaces.repositories import WeatherEventRepository
from app.domain.weather import WeatherEvent


class InMemoryWeatherEventRepository(WeatherEventRepository):
    """Stores WeatherEvents in a process-local dict. Not safe across processes."""

    def __init__(self) -> None:
        self._events: dict[UUID, WeatherEvent] = {}

    def add(self, event: WeatherEvent) -> WeatherEvent:
        self._events[event.id] = event
        return event

    def add_many(self, events: Sequence[WeatherEvent]) -> list[WeatherEvent]:
        return [self.add(event) for event in events]

    def get_by_id(self, event_id: UUID) -> WeatherEvent | None:
        return self._events.get(event_id)

    def list_by_region_and_time(
        self,
        *,
        county: str,
        municipality: str | None = None,
        since: datetime,
        until: datetime,
    ) -> list[WeatherEvent]:
        results = [
            event
            for event in self._events.values()
            if event.county == county and event.started_at <= until and event.ended_at >= since
        ]
        if municipality is not None:
            results = [event for event in results if event.municipality == municipality]
        results.sort(key=lambda event: event.started_at, reverse=True)
        return results

    def count(self) -> int:
        return len(self._events)

    def delete_by_ids(self, event_ids: Sequence[UUID]) -> int:
        deleted = 0
        for eid in event_ids:
            if eid in self._events:
                del self._events[eid]
                deleted += 1
        return deleted

    def list_ids_by_source(self, source: str, *, before: datetime | None = None) -> list[UUID]:
        return [
            eid
            for eid, event in self._events.items()
            if event.source == source and (before is None or event.started_at < before)
        ]
