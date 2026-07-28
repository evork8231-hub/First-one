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
that already-correct logic to see -- exactly once per real occurrence,
never once per collection run (see
``app.verification.weather_bridge_dedup.WeatherBridgeDeduplicator``).
"""

from __future__ import annotations

from collections.abc import Sequence

from loguru import logger

from app.application.interfaces.repositories import AuditLogRepository, SignalRepository
from app.config.settings import WeatherSignalBridgeConfig
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType, SignalType
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent
from app.utils.time import utc_now
from app.verification.weather_bridge_dedup import WeatherBridgeDeduplicator, compute_fingerprint


class WeatherSignalBridgeService:
    """Persists a WEATHER_EVENT Signal for each not-already-bridged WeatherEvent."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        audit_log_repository: AuditLogRepository,
        config: WeatherSignalBridgeConfig,
        deduplicator: WeatherBridgeDeduplicator,
    ) -> None:
        self._signal_repository = signal_repository
        self._audit_log_repository = audit_log_repository
        self._config = config
        self._deduplicator = deduplicator

    def bridge(self, events: Sequence[WeatherEvent]) -> list[Signal]:
        """Build and persist one Signal per not-already-bridged event, returning the stored copies.

        An event whose fingerprint (event type, location, forecast
        period, severity, source -- see ``WeatherBridgeDeduplicator``)
        was already bridged on a previous call is skipped entirely: no
        Signal is created, so verification/correlation never sees it
        (this only prevents *duplicate creation*, it never touches
        verification for events that do get bridged). The same check
        also applies within a single call -- if ``events`` itself
        contains the same real occurrence twice (a source repeating
        itself in one response), only the first is bridged. Every field
        carried over from a bridged ``event`` (source, source_url,
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

        new_events: list[WeatherEvent] = []
        seen_fingerprints_in_this_call: set[str] = set()
        skipped = 0
        for event in events:
            fingerprint = compute_fingerprint(event)
            if fingerprint in seen_fingerprints_in_this_call or self._deduplicator.is_duplicate(
                event
            ):
                skipped += 1
            else:
                seen_fingerprints_in_this_call.add(fingerprint)
                new_events.append(event)
        if skipped:
            logger.info(
                "Weather signal bridge: skipped {} already-bridged event(s) as duplicates.",
                skipped,
            )
        if not new_events:
            return []

        candidates = [self._to_signal(event) for event in new_events]
        stored = self._signal_repository.add_many(candidates)

        for signal, event in zip(stored, new_events, strict=True):
            self._deduplicator.mark_bridged(event, signal_id=str(signal.id))
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
