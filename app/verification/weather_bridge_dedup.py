"""Deterministic deduplication for WeatherEvent -> Signal bridging.

``WeatherSignalBridgeService`` has no natural way to know whether "this"
severe-weather occurrence was already bridged into a Signal on a
previous collector run -- a forecast feed queried repeatedly (e.g. an
hourly cron) can report the same real event again and again, and
without this check each run would create another WEATHER_EVENT Signal
for the identical underlying fact, unboundedly.

This module fingerprints a WeatherEvent by the fields that together
describe *the same real occurrence* -- event type, location, the
forecast period, severity, and source -- deliberately excluding the
event's own generated ``id`` (which differs every time the same event
is re-collected). The fingerprint is stored via
``ConfigurationRepository``, whose ``key`` column carries a real
database-level unique constraint (see ``ConfigurationModel.key``) --
the same store ``app.verification.schema_drift.SchemaDriftDetector``
already uses for its own auto-maintained fingerprints.
"""

from __future__ import annotations

import hashlib

from app.application.interfaces.repositories import ConfigurationRepository
from app.domain.configuration import ConfigurationEntry
from app.domain.weather import WeatherEvent


def compute_fingerprint(event: WeatherEvent) -> str:
    """Return a stable fingerprint identifying ``event``'s real-world identity.

    Two WeatherEvents with identical event type, county, municipality,
    start/end timestamps, severity, and source are treated as the same
    real occurrence, regardless of their own (always-distinct) ``id``.
    """
    raw = "|".join(
        [
            event.event_type.value,
            event.county,
            event.municipality,
            event.started_at.isoformat(),
            event.ended_at.isoformat(),
            f"{event.severity:.6f}",
            event.source,
        ]
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _fingerprint_key(fingerprint: str) -> str:
    return f"weather_bridge_fingerprint.{fingerprint}"


class WeatherBridgeDeduplicator:
    """Tracks which WeatherEvent fingerprints have already been bridged into a Signal.

    Usage is check-then-act, not an atomic insert-or-fail: a caller must
    call :meth:`is_duplicate` before creating a Signal for an event and
    :meth:`mark_bridged` immediately after successfully persisting it,
    both against the same event. This is a deliberate, accepted
    narrow race under concurrent execution of the *same* collector (the
    same class of limitation already documented for
    ``SchemaDriftDetector``'s fingerprint store) -- collection runs are
    not expected to run concurrently against the same source today.
    """

    def __init__(self, configuration_repository: ConfigurationRepository) -> None:
        self._configuration_repository = configuration_repository

    def is_duplicate(self, event: WeatherEvent) -> bool:
        """Return ``True`` if this exact real-world event was already bridged."""
        fingerprint = compute_fingerprint(event)
        return self._configuration_repository.get(_fingerprint_key(fingerprint)) is not None

    def mark_bridged(self, event: WeatherEvent, *, signal_id: str) -> None:
        """Record that ``event`` has now been bridged into the Signal ``signal_id``."""
        fingerprint = compute_fingerprint(event)
        self._configuration_repository.set(
            ConfigurationEntry(
                key=_fingerprint_key(fingerprint),
                value={"weather_event_id": str(event.id), "signal_id": signal_id},
                description=("Auto-maintained by WeatherBridgeDeduplicator; do not edit by hand."),
            )
        )
