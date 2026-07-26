"""Ehitisregister (Estonian Building Registry) collector.

Reads building and (where present) energy-certificate records from
Estonia's central Building Registry via the state open-data portal's
generic Dataset API (https://andmed.eesti.ee/api/dataset-docs/), and
translates them into ``BUILDING_RECORD`` / ``ENERGY_CERTIFICATE`` Signals.

Known limitation: the exact JSON schema of the discovered dataset
resource could not be confirmed against a live source in this
environment (outbound web access was unavailable while building this
collector). Field extraction goes through
``EhitisregisterConfig.field_map`` -- a configurable, ordered list of
candidate source key names per canonical field -- so the mapping can be
corrected via configuration once the real schema is confirmed, without a
code change. A record missing a value under every candidate key for a
*required* Signal field (county, municipality) is skipped, never
fabricated.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from loguru import logger

from app.collectors.base import BaseCollector
from app.collectors.http_client import HttpClient
from app.config.settings import EhitisregisterConfig
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy
from app.domain.enums import ServiceCategory, SignalType
from app.domain.signal import Signal
from app.domain.value_objects import Coordinates
from app.utils.time import utc_now


class EhitisregisterCollector(BaseCollector):
    """Collects public Building Registry records as Signals.

    Two requests per run: dataset metadata is fetched first to discover
    the actual downloadable JSON resource URL (rather than assuming a
    fixed records endpoint), then that resource is fetched and parsed.

    Every ``BUILDING_RECORD`` signal is tagged ``service_category=ROOFING``
    as a documented default -- a building record is general-purpose
    evidence relevant to any of the four service categories (the rule
    engine matches on ``signal_type``, never on ``service_category``; see
    ``app.rule_engine.matcher``), and roofing is the one category every
    residential building is universally relevant to. Energy-certificate
    signals are tagged ``SOLAR_INSTALLATION``, matching the pairing used
    by ``config/rules/solar.yaml``.
    """

    def __init__(
        self, config: EhitisregisterConfig, *, retry_policy: RetryPolicy | None = None
    ) -> None:
        super().__init__(
            name="ehitisregister",
            source="Ehitisregister (Estonian Building Registry)",
            supported_signal_types=frozenset(
                {SignalType.BUILDING_RECORD, SignalType.ENERGY_CERTIFICATE}
            ),
            retry_policy=retry_policy or RetryPolicy(max_retries=config.max_retries),
        )
        self._config = config

    async def collect(self) -> list[Signal]:
        async with HttpClient(self._config, retry_policy=self._retry_policy) as client:
            resource_url = await self._discover_resource_url(client)
            payload = await client.get_json(resource_url)

        records = self._extract_records(payload)
        signals: list[Signal] = []
        skipped = 0

        for record in records[: self._config.max_records_per_run]:
            record_signals = self._record_to_signals(record)
            if record_signals:
                signals.extend(record_signals)
            else:
                skipped += 1

        logger.info(
            "Ehitisregister collector produced {} signal(s) from {} record(s); "
            "{} record(s) skipped for missing required fields.",
            len(signals),
            len(records),
            skipped,
        )
        return signals

    async def _discover_resource_url(self, client: HttpClient) -> str:
        """Find a JSON resource URL from the dataset's metadata.

        Raises:
            CollectorError: If the dataset metadata lists no JSON resource.
        """
        dataset = await client.get_json(f"/api/datasets/{self._config.dataset_slug}")
        resources = dataset.get("resources") or dataset.get("distributions") or []
        for resource in resources:
            fmt = str(resource.get("format") or "").lower()
            url = resource.get("url") or resource.get("downloadURL") or resource.get("download_url")
            if url and fmt in ("json", "jsonld", "json-ld", "application/json"):
                return str(url)
        raise CollectorError(
            f"No JSON resource found in Ehitisregister dataset metadata "
            f"({self._config.dataset_slug!r}); {len(resources)} resource(s) listed."
        )

    @staticmethod
    def _extract_records(payload: Any) -> list[dict[str, Any]]:  # noqa: ANN401
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if isinstance(payload, dict):
            if isinstance(payload.get("@graph"), list):
                return [item for item in payload["@graph"] if isinstance(item, dict)]
            for key in ("records", "results", "items", "data"):
                if isinstance(payload.get(key), list):
                    return [item for item in payload[key] if isinstance(item, dict)]
        return []

    def _field(self, record: dict[str, Any], canonical_name: str) -> Any | None:  # noqa: ANN401
        """Return the first present value among the configured candidate keys."""
        for key in self._config.field_map.get(canonical_name, []):
            if key in record and record[key] not in (None, ""):
                return record[key]
        return None

    def _record_timestamp(self, record: dict[str, Any]) -> datetime:
        raw = self._field(record, "last_updated")
        if isinstance(raw, str):
            try:
                parsed = datetime.fromisoformat(raw)
                return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
            except ValueError:
                logger.debug(
                    "Could not parse Ehitisregister record timestamp {!r}; using collection time.",
                    raw,
                )
        return utc_now()

    def _record_to_signals(self, record: dict[str, Any]) -> list[Signal]:
        county = self._field(record, "county")
        municipality = self._field(record, "municipality")
        if not county or not municipality:
            return []  # required Signal fields absent; never fabricate a location

        registry_code = self._field(record, "registry_code")
        building_identifier = str(registry_code) if registry_code else None
        coordinates = self._record_coordinates(record)
        timestamp = self._record_timestamp(record)

        metadata: dict[str, Any] = {}
        building_type = self._field(record, "building_type")
        if building_type is not None:
            metadata["building_type"] = building_type
        construction_year = self._field(record, "construction_year")
        if construction_year is not None:
            metadata["construction_year"] = construction_year

        signals = [
            Signal(
                signal_type=SignalType.BUILDING_RECORD,
                source=self.source,
                service_category=ServiceCategory.ROOFING,
                county=str(county),
                municipality=str(municipality),
                coordinates=coordinates,
                building_identifier=building_identifier,
                timestamp=timestamp,
                raw_payload=record,
                confidence=self._config.default_confidence,
                metadata=metadata,
            )
        ]

        energy_class = self._field(record, "energy_class")
        if energy_class is not None:
            energy_metadata: dict[str, Any] = {"energy_class": energy_class}
            valid_until = self._field(record, "energy_certificate_valid_until")
            if valid_until is not None:
                energy_metadata["valid_until"] = valid_until
            signals.append(
                Signal(
                    signal_type=SignalType.ENERGY_CERTIFICATE,
                    source=self.source,
                    service_category=ServiceCategory.SOLAR_INSTALLATION,
                    county=str(county),
                    municipality=str(municipality),
                    coordinates=coordinates,
                    building_identifier=building_identifier,
                    timestamp=timestamp,
                    raw_payload=record,
                    confidence=self._config.default_confidence,
                    metadata=energy_metadata,
                )
            )
        return signals

    def _record_coordinates(self, record: dict[str, Any]) -> Coordinates | None:
        latitude = self._field(record, "latitude")
        longitude = self._field(record, "longitude")
        if latitude is None or longitude is None:
            return None
        try:
            return Coordinates(latitude=float(latitude), longitude=float(longitude))
        except (TypeError, ValueError):
            logger.debug(
                "Could not parse Ehitisregister coordinates ({!r}, {!r}).", latitude, longitude
            )
            return None
