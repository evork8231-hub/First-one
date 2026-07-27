"""WeatherSignalBridgeService: turns a persisted WeatherEvent into a WEATHER_EVENT Signal.

Closes a previously-documented gap: weather events were collected and
stored in their own table, but nothing converted one into a
``SignalType.WEATHER_EVENT`` ``Signal`` -- the type the rule engine
(``app.rule_engine.matcher``) actually matches conditions against. Without
this bridge, no rule referencing a ``weather_event`` condition (e.g.
``config/rules/roofing.yaml``'s ``roofing_storm_damage``) could ever match
real data, no matter how much weather data was collected.

This service does not decide *whether* weather matters to a Lead -- that
was already correctly handled: ``LeadGenerator`` excludes
``WEATHER_EVENT``-typed signals from ``supporting_signal_ids`` and only
lets them scale ``estimated_confidence``/``intent_score`` via
``ScoringConfig.weather_confidence_boost_factor``
(``app.lead_generation.generator`` / ``app.lead_generation.scoring``).
This service's only job is making sure a WEATHER_EVENT Signal exists for
that already-correct logic to see.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.interfaces.repositories import AuditLogRepository, SignalRepository
from app.config.settings import WeatherSignalBridgeConfig
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType, SignalType
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent
from app.utils.time import utc_now


class WeatherSignalBridgeService:
    """Persists a WEATHER_EVENT Signal for each already-collected WeatherEvent."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        audit_log_repository: AuditLogRepository,
        config: WeatherSignalBridgeConfig,
    ) -> None:
        self._signal_repository = signal_repository
        self._audit_log_repository = audit_log_repository
        self._config = config

    def bridge(self, events: Sequence[WeatherEvent]) -> list[Signal]:
        """Build and persist one Signal per event in ``events``, returning the stored copies.

        Every field carried over from ``event`` (source, source_url,
        county, municipality, coordinates, raw_payload) is a direct,
        unmodified pass-through of what the weather collector actually
        reported -- nothing here is inferred or fabricated. ``timestamp``
        is set to collection time (``utc_now()``), not
        ``event.started_at``/``ended_at``, because a forecast's predicted
        period is often in the future and ``Signal.timestamp`` rejects
        future values; the underlying fact this Signal records is "this
        forecast was published," which happened now. The forecast's own
        period remains fully available in ``metadata`` and in the linked
        WeatherEvent record.
        """
        if not events:
            return []

        candidates = [self._to_signal(event) for event in events]
        stored = self._signal_repository.add_many(candidates)

        for signal, event in zip(stored, events, strict=True):
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.SIGNAL_INGESTED,
                    entity_type="Signal",
                    entity_id=signal.id,
                    message=(
                        f"Bridged weather event {event.id} ({event.event_type.value}) into a "
                        f"WEATHER_EVENT signal."
                    ),
                    context={
                        "source": "weather_signal_bridge",
                        "weather_event_id": str(event.id),
                        "weather_event_type": event.event_type.value,
                    },
                )
            )
        return stored

    def _to_signal(self, event: WeatherEvent) -> Signal:
        return Signal(
            signal_type=SignalType.WEATHER_EVENT,
            source=event.source,
            source_url=event.source_url,
            service_category=self._config.service_category,
            county=event.county,
            municipality=event.municipality,
            coordinates=event.coordinates,
            timestamp=utc_now(),
            raw_payload=event.raw_payload,
            confidence=self._config.signal_confidence,
            metadata={
                "weather_event_id": str(event.id),
                "weather_event_type": event.event_type.value,
                "severity": event.severity,
                "started_at": event.started_at.isoformat(),
                "ended_at": event.ended_at.isoformat(),
            },
        )
