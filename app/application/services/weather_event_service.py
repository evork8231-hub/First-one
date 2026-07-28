"""WeatherEventService: runs weather collectors and persists the WeatherEvents they return.

Mirrors ``app.application.services.signal_service.SignalService`` exactly,
for a ``WeatherCollectorInterface`` instead of a ``CollectorInterface``.
Weather events are never turned into Signals or Leads here -- this
service's sole responsibility is persisting what a weather collector
reported, with a full audit trail.

Persisting a successful run's WeatherEvents and its completion audit
entry is delegated to ``CollectionUnitOfWork`` as one atomic write -- see
``app.application.services.signal_service`` for the full rationale
(identical here). ``WeatherEventRepository`` is not needed directly by
this service at all: unlike ``SignalService`` (which also reads via
``list_unverified``/``list_verified``), every interaction this service
has with weather events is the atomic write the unit of work now owns.
"""

from __future__ import annotations

import time
from uuid import uuid4

from loguru import logger

from app.application.interfaces.collection_unit_of_work import CollectionUnitOfWork
from app.application.interfaces.repositories import AuditLogRepository
from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.core.exceptions import CollectorError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.domain.weather import WeatherEvent


def _retry_attempts(collector: WeatherCollectorInterface) -> int:
    """Read a collector's most-recent-run retry count, defaulting to 0 if untracked."""
    return int(getattr(collector, "retry_count", 0))


class WeatherEventService:
    """Orchestrates weather-collector execution and WeatherEvent persistence."""

    def __init__(
        self,
        audit_log_repository: AuditLogRepository,
        collection_unit_of_work: CollectionUnitOfWork,
    ) -> None:
        self._audit_log_repository = audit_log_repository
        self._collection_unit_of_work = collection_unit_of_work

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
        start = time.monotonic()
        try:
            events = await collector.collect()
        except CollectorError as exc:
            duration_seconds = round(time.monotonic() - start, 3)
            logger.opt(exception=exc).error("Weather collector {} failed", collector.name)
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.COLLECTOR_RUN_FAILED,
                    entity_type="WeatherCollector",
                    message=f"Weather collector {collector.name!r} failed: {exc.message}",
                    context={
                        "collector": collector.name,
                        "duration_seconds": duration_seconds,
                        "retry_attempts": _retry_attempts(collector),
                        **exc.details,
                    },
                )
            )
            raise

        duration_seconds = round(time.monotonic() - start, 3)
        execution_id = uuid4()
        completion_entry = AuditLogEntry(
            event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
            entity_type="WeatherCollector",
            message=f"Weather collector {collector.name!r} produced {len(events)} event(s).",
            context={
                "collector": collector.name,
                "event_count": len(events),
                "duration_seconds": duration_seconds,
                "retry_attempts": _retry_attempts(collector),
                "execution_id": str(execution_id),
                "inserted_event_ids": [str(event.id) for event in events],
            },
        )
        return self._collection_unit_of_work.record_weather_collection(events, completion_entry)
