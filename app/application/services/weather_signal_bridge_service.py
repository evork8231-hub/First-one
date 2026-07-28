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

Persisting a bridged event's Signal, its dedup bookkeeping, and its audit
entry is delegated to ``WeatherBridgeUnitOfWork`` as one atomic write per
batch -- mirroring ``RollbackService``'s use of ``RollbackUnitOfWork``,
this service builds *what* to persist (pure, no I/O) and the unit of
work handles persisting it atomically, so an interrupted collection run
can never leave a Signal committed with no matching dedup record (which
would otherwise let the same real occurrence be bridged again on the
next run).
"""

from __future__ import annotations

from collections.abc import Sequence

from loguru import logger

from app.application.interfaces.weather_bridge_unit_of_work import (
    BridgedEvent,
    WeatherBridgeUnitOfWork,
)
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
        config: WeatherSignalBridgeConfig,
        deduplicator: WeatherBridgeDeduplicator,
        weather_bridge_unit_of_work: WeatherBridgeUnitOfWork,
    ) -> None:
        self._config = config
        self._deduplicator = deduplicator
        self._weather_bridge_unit_of_work = weather_bridge_unit_of_work

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

        Every new event's Signal, dedup entry, and audit entry are
        persisted together as one atomic batch (see
        ``WeatherBridgeUnitOfWork``) -- if persistence fails partway
        through, nothing in the batch is left committed.
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

        bridged = [self._build_bridged_event(event) for event in new_events]
        return self._weather_bridge_unit_of_work.bridge_events(bridged)

    def _build_bridged_event(self, event: WeatherEvent) -> BridgedEvent:
        signal = self._to_signal(event)
        dedup_entry = self._deduplicator.build_bridged_entry(event, signal_id=str(signal.id))
        audit_entry = AuditLogEntry(
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
        return BridgedEvent(signal=signal, dedup_entry=dedup_entry, audit_entry=audit_entry)

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
