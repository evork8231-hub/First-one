"""Tests for app.collectors.ilmateenistus_collector.IlmateenistusCollector.

No live network calls -- every HTTP interaction goes through
``httpx.MockTransport`` via a monkeypatched ``HttpClient`` factory.
"""

from __future__ import annotations

import asyncio

import app.collectors.ilmateenistus_collector as ilm_module
import httpx
import pytest
from app.collectors.http_client import HttpClient
from app.collectors.ilmateenistus_collector import IlmateenistusCollector
from app.config.settings import IlmateenistusConfig
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy
from app.domain.enums import WeatherEventType

_FIXTURE_XML = """<?xml version="1.0" encoding="UTF-8"?>
<forecast>
  <tabular>
    <day date="2026-07-27">
      <text>Ilus suveilm.</text>
      <place name="Tallinn" phenomenon="Selge">
        <wind><gust>3</gust></wind>
      </place>
      <place name="Pärnu" phenomenon="Tugev torm">
        <wind><gust>28</gust></wind>
      </place>
      <place name="Unmapped Village" phenomenon="Rahe" />
    </day>
    <night date="2026-07-27">
      <place name="Tartu" phenomenon="Äike" />
    </night>
  </tabular>
</forecast>
"""


def _patch_http_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    def factory(config: object, *, retry_policy: RetryPolicy | None = None) -> HttpClient:
        return HttpClient(config, retry_policy=retry_policy, transport=transport)  # type: ignore[arg-type]

    monkeypatch.setattr(ilm_module, "HttpClient", factory)


def _xml_transport(xml_text: str) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text=xml_text)

    return httpx.MockTransport(handler)


def _config(**overrides: object) -> IlmateenistusConfig:
    defaults: dict[str, object] = {"xml_url": "/teenused/eesti-prognoos.xml"}
    defaults.update(overrides)
    return IlmateenistusConfig(**defaults)  # type: ignore[arg-type]


def test_collect_raises_when_xml_url_not_configured() -> None:
    collector = IlmateenistusCollector(IlmateenistusConfig(xml_url=None))
    with pytest.raises(CollectorError):
        asyncio.run(collector.collect())


def test_collect_produces_event_only_for_matched_phenomenon(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_http_client(monkeypatch, _xml_transport(_FIXTURE_XML))
    collector = IlmateenistusCollector(_config())

    events = asyncio.run(collector.collect())

    # Tallinn (clear) -> no event. Pärnu (storm) -> event. Unmapped Village -> skipped
    # (not in place_administrative_areas). Tartu (lightning) -> event.
    assert len(events) == 2
    event_types = {e.event_type for e in events}
    assert event_types == {WeatherEventType.HIGH_WIND, WeatherEventType.LIGHTNING}


def test_wind_event_severity_derives_from_reported_gust(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http_client(monkeypatch, _xml_transport(_FIXTURE_XML))
    collector = IlmateenistusCollector(_config(wind_severity_reference_ms=25.0))

    events = asyncio.run(collector.collect())

    wind_event = next(e for e in events if e.event_type == WeatherEventType.HIGH_WIND)
    assert wind_event.severity == pytest.approx(1.0)  # clamped: 28 / 25 > 1.0
    assert wind_event.county == "Pärnu"
    assert wind_event.municipality == "Pärnu"


def test_categorical_event_uses_configured_default_severity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_http_client(monkeypatch, _xml_transport(_FIXTURE_XML))
    collector = IlmateenistusCollector(_config(categorical_event_severity=0.42))

    events = asyncio.run(collector.collect())

    lightning_event = next(e for e in events if e.event_type == WeatherEventType.LIGHTNING)
    assert lightning_event.severity == pytest.approx(0.42)


def test_collect_never_maps_unmapped_place_names(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http_client(monkeypatch, _xml_transport(_FIXTURE_XML))
    collector = IlmateenistusCollector(_config())

    events = asyncio.run(collector.collect())

    assert all(e.county != "" for e in events)
    assert not any("Unmapped" in str(e.raw_payload.get("place")) for e in events)


def test_benign_forecast_produces_no_events(monkeypatch: pytest.MonkeyPatch) -> None:
    benign_xml = """<forecast><tabular><day date="2026-07-27">
        <place name="Tallinn" phenomenon="Selge" />
    </day></tabular></forecast>"""
    _patch_http_client(monkeypatch, _xml_transport(benign_xml))
    collector = IlmateenistusCollector(_config())

    assert asyncio.run(collector.collect()) == []


def test_malformed_xml_raises_collector_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_http_client(monkeypatch, _xml_transport("<forecast><unclosed></forecast>"))
    collector = IlmateenistusCollector(_config())

    with pytest.raises(CollectorError):
        asyncio.run(collector.collect())


def test_collector_identity() -> None:
    collector = IlmateenistusCollector(_config())
    # Must match the "ilmateenistus" key under collectors.<name> in configuration --
    # collectors.enabled/WeatherCollectorRegistry.list_enabled filter by this exact name.
    assert collector.name == "ilmateenistus"
