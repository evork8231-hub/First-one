"""Ilmateenistus (Estonian Weather Service) forecast collector.

Reads the public "Eesti prognoos XML" forecast feed and produces
``WeatherEvent`` records **only** for forecast entries whose reported
phenomenon matches an explicit Estonian severe-weather keyword --
routine forecasts (clear, partly cloudy, light rain) never produce an
event. Weather events are never turned into Signals or Leads here.

Known limitations (see ``docs/CONFIGURATION.md#ilmateenistus``):

- The exact feed URL could not be confirmed against a live source in
  this environment (outbound web access was unavailable while building
  this collector). ``IlmateenistusConfig.xml_url`` has no default; this
  collector raises ``CollectorError`` until an operator sets it.
- The parser targets a forecast-XML shape corroborated via public
  documentation search (``place`` elements carrying a ``phenomenon`` and
  optional wind data, grouped under day/night periods with a ``date``)
  and walks up the tree to find the nearest ``date``/period marker rather
  than assuming one fixed nesting depth -- but the precise element names
  are unverified. Verify against the live feed before production use.
- The feed reports place names (towns/regions), not Estonian
  administrative divisions. Only names present in
  ``IlmateenistusConfig.place_administrative_areas`` are mapped to a
  county/municipality; every other place is skipped, not guessed.
- The feed carries no numeric "severity" for most phenomena. Wind-related
  events derive severity from the feed's own reported gust speed against
  a documented reference threshold; other matched phenomena receive a
  fixed, configurable default. Neither is a value reported by the source.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import UTC, datetime, time, timedelta
from datetime import date as date_cls
from zoneinfo import ZoneInfo

from loguru import logger

from app.collectors.base_weather import BaseWeatherCollector
from app.collectors.http_client import HttpClient
from app.collectors.xml_utils import find_float, find_text, safe_parse_xml
from app.config.settings import HttpCollectorConfig, IlmateenistusConfig
from app.core.constants import DEFAULT_TIMEZONE
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy
from app.domain.enums import WeatherEventType
from app.domain.weather import WeatherEvent
from app.utils.time import utc_now

_TALLINN_TZ = ZoneInfo(DEFAULT_TIMEZONE)

#: Explicit Estonian phenomenon/forecast-text keywords mapped to a
#: WeatherEventType. Matching is case-insensitive substring matching
#: against the forecast's own reported text -- never inferred from
#: temperature, season, or anything not literally present in the feed.
SEVERE_WEATHER_KEYWORDS: dict[WeatherEventType, tuple[str, ...]] = {
    WeatherEventType.HAILSTORM: ("rahe",),
    WeatherEventType.HIGH_WIND: ("torm", "tugev tuul", "puhang"),
    WeatherEventType.HEAVY_SNOW: ("tugev lumesadu", "lumetorm", "lörtsisadu"),
    WeatherEventType.HEAVY_RAIN: ("paduvihm", "tugev vihm", "kõva vihm"),
    WeatherEventType.FLOOD: ("üleujutus",),
    WeatherEventType.ICE_STORM: ("jäide", "jäätev"),
    WeatherEventType.LIGHTNING: ("äike",),
}

_WIND_EVENT_TYPES = frozenset({WeatherEventType.HIGH_WIND, WeatherEventType.ICE_STORM})


class IlmateenistusCollector(BaseWeatherCollector):
    """Collects severe-weather WeatherEvents from the Estonia forecast XML feed."""

    def __init__(
        self, config: IlmateenistusConfig, *, retry_policy: RetryPolicy | None = None
    ) -> None:
        super().__init__(
            name="ilmateenistus_forecast",
            source="Ilmateenistus (Estonian Environment Agency Weather Service)",
            retry_policy=retry_policy or RetryPolicy(max_retries=config.max_retries),
        )
        self._config = config

    async def collect(self) -> list[WeatherEvent]:
        if not self._config.xml_url:
            raise CollectorError(
                "Ilmateenistus collector is not configured: 'collectors.ilmateenistus.xml_url' "
                "is unset. Set it to the real forecast XML feed URL before enabling this "
                "collector (see docs/CONFIGURATION.md)."
            )

        http_config = HttpCollectorConfig(
            base_url=self._config.base_url,
            timeout_seconds=self._config.timeout_seconds,
            request_delay_seconds=self._config.request_delay_seconds,
            max_retries=self._config.max_retries,
        )
        async with HttpClient(http_config, retry_policy=self._retry_policy) as client:
            xml_text = await client.get_text(self._config.xml_url)

        root = safe_parse_xml(xml_text)
        parent_map = {child: parent for parent in root.iter() for child in parent}

        events: list[WeatherEvent] = []
        skipped_unmapped_places: set[str] = set()

        for place_el in root.findall(".//place"):
            event = self._place_to_event(place_el, parent_map, skipped_unmapped_places)
            if event is not None:
                events.append(event)

        if skipped_unmapped_places:
            logger.info(
                "Ilmateenistus collector skipped {} unmapped place(s): {}",
                len(skipped_unmapped_places),
                ", ".join(sorted(skipped_unmapped_places)),
            )
        logger.info("Ilmateenistus collector produced {} severe-weather event(s).", len(events))
        return events

    def _place_to_event(
        self,
        place_el: ET.Element,
        parent_map: dict[ET.Element, ET.Element],
        skipped_unmapped_places: set[str],
    ) -> WeatherEvent | None:
        place_name = place_el.get("name")
        if not place_name:
            return None

        area = self._config.place_administrative_areas.get(place_name)
        if area is None:
            skipped_unmapped_places.add(place_name)
            return None

        phenomenon = place_el.get("phenomenon") or find_text(place_el, "phenomenon")
        text = find_text(place_el, "text") or self._nearest_ancestor_text(place_el, parent_map)
        event_type = self._classify(phenomenon, text)
        if event_type is None:
            return None

        gust_ms = find_float(place_el, "wind/gust") or find_float(place_el, "wind/speed/max")
        severity = self._severity_for(event_type, gust_ms)

        date_attr = self._nearest_ancestor_attr(place_el, parent_map, "date")
        period_name = self._nearest_period_name(place_el, parent_map)
        started_at, ended_at = self._period_window(date_attr, period_name)

        return WeatherEvent(
            event_type=event_type,
            source=self.source,
            source_url=self._config.xml_url,
            county=area.county,
            municipality=area.municipality,
            severity=severity,
            started_at=started_at,
            ended_at=ended_at,
            raw_payload={
                "place": place_name,
                "phenomenon": phenomenon,
                "text": text,
                "date": date_attr,
                "period": period_name,
                "wind_gust_ms": gust_ms,
            },
        )

    @staticmethod
    def _classify(*texts: str | None) -> WeatherEventType | None:
        haystack = " ".join(t for t in texts if t).casefold()
        if not haystack:
            return None
        for event_type, keywords in SEVERE_WEATHER_KEYWORDS.items():
            if any(keyword in haystack for keyword in keywords):
                return event_type
        return None

    def _severity_for(self, event_type: WeatherEventType, gust_ms: float | None) -> float:
        if event_type in _WIND_EVENT_TYPES and gust_ms is not None:
            return max(0.0, min(1.0, gust_ms / self._config.wind_severity_reference_ms))
        return self._config.categorical_event_severity

    @staticmethod
    def _nearest_ancestor_attr(
        element: ET.Element, parent_map: dict[ET.Element, ET.Element], attr: str
    ) -> str | None:
        current: ET.Element | None = element
        while current is not None:
            value = current.get(attr)
            if value:
                return value
            current = parent_map.get(current)
        return None

    @staticmethod
    def _nearest_ancestor_text(
        element: ET.Element, parent_map: dict[ET.Element, ET.Element]
    ) -> str | None:
        current = parent_map.get(element)
        while current is not None:
            text = find_text(current, "text")
            if text:
                return text
            current = parent_map.get(current)
        return None

    @staticmethod
    def _nearest_period_name(element: ET.Element, parent_map: dict[ET.Element, ET.Element]) -> str:
        current: ET.Element | None = element
        while current is not None:
            if current.tag in ("day", "night"):
                return current.tag
            current = parent_map.get(current)
        return "day"

    @staticmethod
    def _period_window(date_attr: str | None, period_name: str) -> tuple[datetime, datetime]:
        day: date_cls
        if date_attr:
            try:
                day = date_cls.fromisoformat(date_attr)
            except ValueError:
                day = utc_now().astimezone(_TALLINN_TZ).date()
        else:
            day = utc_now().astimezone(_TALLINN_TZ).date()

        # Approximation: the feed gives day-level forecasts, not exact hours.
        start_hour = 18 if period_name == "night" else 6
        start_local = datetime.combine(day, time(start_hour, 0), tzinfo=_TALLINN_TZ)
        end_local = start_local + timedelta(hours=12)
        return start_local.astimezone(UTC), end_local.astimezone(UTC)
