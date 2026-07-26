"""WeatherEventService: runs weather collectors and persists the WeatherEvents they return.

Mirrors ``app.application.services.signal_service.SignalService`` exactly,
for a ``WeatherCollectorInterface`` instead of a ``CollectorInterface``.
Weather events are never turned into Signals or Leads here -- this
service's sole responsibility is persisting what a weather collector
reported, with a full audit trail.
"""

from __future__ import annotations

from loguru import logger

from app.application.interfaces.repositories import AuditLogRepository, WeatherEventRepository
from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.core.exceptions import CollectorError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.domain.weather import WeatherEvent


class WeatherEventService:
    """Orchestrates weather-collector execution and WeatherEvent persistence."""

    def __init__(
        self,
        weather_event_repository: WeatherEventRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._weather_event_repository = weather_event_repository
        self._audit_log_repository = audit_log_repository

    async def ingest_from_collector(
        self, collector: WeatherCollectorInterface
    ) -> list[WeatherEvent]:
        """Run ``collector`` and persist every WeatherEvent it returns.

        Raises:
            CollectorError: If the collector fails; the failure is audit
                logged before being re-raised.
        """
        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=AuditEventType.COLLECTOR_RUN_STARTED,
                entity_type="WeatherCollector",
                message=(
                    f"Starting weather collector {collector.name!r} "
                    f"(source={collector.source!r})."
                ),
                context={"collector": collector.name, "source": collector.source},
            )
        )
        try:
            events = await collector.collect()
        except CollectorError as exc:
            logger.opt(exception=exc).error("Weather collector {} failed", collector.name)
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.COLLECTOR_RUN_FAILED,
                    entity_type="WeatherCollector",
                    message=f"Weather collector {collector.name!r} failed: {exc.message}",
                    context={"collector": collector.name, **exc.details},
                )
            )
            raise

        stored: list[WeatherEvent] = []
        for event in events:
            stored_event = self._weather_event_repository.add(event)
            stored.append(stored_event)

        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
                entity_type="WeatherCollector",
                message=f"Weather collector {collector.name!r} produced {len(stored)} event(s).",
                context={"collector": collector.name, "event_count": len(stored)},
            )
        )
        return stored
