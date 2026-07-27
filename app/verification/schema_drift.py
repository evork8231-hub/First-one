"""Schema-drift detection: warns when a collector's source structure changes.

Fingerprints each collector run by the set of raw-payload keys its
Signals/WeatherEvents actually carried (``Signal.raw_payload`` /
``WeatherEvent.raw_payload`` -- the unmodified record every collector
already stores), and compares that set against the fingerprint stored
from the collector's previous run (via ``ConfigurationRepository``, keyed
``f"schema_fingerprint.{collector_name}"``). A changed key set usually
means the source's structure changed -- new fields, renamed fields, or
fields that disappeared -- which can silently break a collector's
hardcoded parsing or a configured ``field_map``/selector.

This is diagnostic only: it never blocks a collection run, never changes
what data was ingested, and never modifies a collector's configuration.
It only warns (via an audit log entry) so an operator knows to check
whether the collector's assumptions still hold, then updates the stored
fingerprint to the new key set so the same drift is not re-reported on
every subsequent run.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.application.interfaces.repositories import AuditLogRepository, ConfigurationRepository
from app.domain.audit import AuditLogEntry
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import AuditEventType


def _fingerprint_key(collector_name: str) -> str:
    return f"schema_fingerprint.{collector_name}"


@dataclass(frozen=True)
class SchemaDriftResult:
    """The outcome of comparing one collector run's observed keys against its last fingerprint."""

    collector_name: str
    is_first_observation: bool
    has_drift: bool
    added_keys: tuple[str, ...]
    removed_keys: tuple[str, ...]


class SchemaDriftDetector:
    """Fingerprints raw-payload key sets per collector and flags changes between runs."""

    def __init__(
        self,
        configuration_repository: ConfigurationRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._configuration_repository = configuration_repository
        self._audit_log_repository = audit_log_repository

    def check(
        self, collector_name: str, raw_payloads: Sequence[Mapping[str, Any]]
    ) -> SchemaDriftResult:
        """Compare this run's observed keys against ``collector_name``'s stored fingerprint.

        A run with no payloads (e.g. a collector that found nothing) is
        never compared or stored -- an empty result carries no schema
        information and must never be mistaken for "every field
        disappeared".
        """
        if not raw_payloads:
            return SchemaDriftResult(
                collector_name=collector_name,
                is_first_observation=False,
                has_drift=False,
                added_keys=(),
                removed_keys=(),
            )

        observed_keys = {key for payload in raw_payloads for key in payload}
        fingerprint_key = _fingerprint_key(collector_name)
        stored_entry = self._configuration_repository.get(fingerprint_key)

        if stored_entry is None:
            self._store_fingerprint(fingerprint_key, observed_keys)
            return SchemaDriftResult(
                collector_name=collector_name,
                is_first_observation=True,
                has_drift=False,
                added_keys=(),
                removed_keys=(),
            )

        previous_keys = set(stored_entry.value or [])
        added = observed_keys - previous_keys
        removed = previous_keys - observed_keys

        if not added and not removed:
            return SchemaDriftResult(
                collector_name=collector_name,
                is_first_observation=False,
                has_drift=False,
                added_keys=(),
                removed_keys=(),
            )

        self._store_fingerprint(fingerprint_key, observed_keys)
        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=AuditEventType.SCHEMA_DRIFT_DETECTED,
                entity_type="Collector",
                message=(
                    f"Schema drift detected for collector {collector_name!r}: "
                    f"{len(added)} key(s) added, {len(removed)} key(s) removed."
                ),
                context={
                    "collector": collector_name,
                    "added_keys": sorted(added),
                    "removed_keys": sorted(removed),
                },
            )
        )
        return SchemaDriftResult(
            collector_name=collector_name,
            is_first_observation=False,
            has_drift=True,
            added_keys=tuple(sorted(added)),
            removed_keys=tuple(sorted(removed)),
        )

    def _store_fingerprint(self, fingerprint_key: str, keys: set[str]) -> None:
        self._configuration_repository.set(
            ConfigurationEntry(
                key=fingerprint_key,
                value=sorted(keys),
                description="Auto-maintained by SchemaDriftDetector; do not edit by hand.",
            )
        )
