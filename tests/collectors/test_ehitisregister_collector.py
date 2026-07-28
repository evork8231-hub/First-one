"""Tests for app.collectors.ehitisregister_collector.EhitisregisterCollector.

No live network calls -- every HTTP interaction goes through
``httpx.MockTransport`` via a monkeypatched ``HttpClient`` factory.
"""

from __future__ import annotations

import asyncio

import app.collectors.ehitisregister_collector as ehr_module
import httpx
import pytest
from app.collectors.ehitisregister_collector import EhitisregisterCollector
from app.collectors.http_client import HttpClient
from app.config.settings import EhitisregisterConfig
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy
from app.domain.enums import ServiceCategory, SignalType

_VALID_RECORD = {
    "maakond": "Harju",
    "omavalitsus": "Tallinn",
    "ehitisregistri_kood": "123456",
    "ehitusaasta": 1975,
    "ehitise_kasutamise_otstarve": "Elamu",
    "lat": 59.437,
    "lon": 24.7536,
    "energiaklass": "D",
}

_RECORD_MISSING_COUNTY = {
    "omavalitsus": "Tartu",
    "ehitisregistri_kood": "999999",
}


def _patch_http_client(monkeypatch: pytest.MonkeyPatch, transport: httpx.MockTransport) -> None:
    def factory(config: object, *, retry_policy: RetryPolicy | None = None) -> HttpClient:
        return HttpClient(config, retry_policy=retry_policy, transport=transport)  # type: ignore[arg-type]

    monkeypatch.setattr(ehr_module, "HttpClient", factory)


def _dataset_handler(records: list[dict[str, object]]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/datasets/ehitisregister":
            return httpx.Response(
                200,
                json={
                    "resources": [
                        {"format": "csv", "url": "/files/ehitisregister.csv"},
                        {"format": "json", "url": "/files/ehitisregister.json"},
                    ]
                },
            )
        if request.url.path == "/files/ehitisregister.json":
            return httpx.Response(200, json=records)
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def test_collect_builds_signals_from_valid_record(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _dataset_handler([_VALID_RECORD])
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig())

    signals = asyncio.run(collector.collect())

    assert len(signals) == 2
    building_signal = next(s for s in signals if s.signal_type == SignalType.BUILDING_RECORD)
    energy_signal = next(s for s in signals if s.signal_type == SignalType.ENERGY_CERTIFICATE)

    assert building_signal.county == "Harju"
    assert building_signal.municipality == "Tallinn"
    assert building_signal.building_identifier == "123456"
    assert building_signal.service_category == ServiceCategory.ROOFING
    assert building_signal.coordinates is not None
    assert building_signal.coordinates.latitude == pytest.approx(59.437)
    assert building_signal.metadata["construction_year"] == 1975

    assert energy_signal.service_category == ServiceCategory.SOLAR_INSTALLATION
    assert energy_signal.metadata["energy_class"] == "D"


def test_collect_skips_record_missing_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _dataset_handler([_RECORD_MISSING_COUNTY])
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig())

    signals = asyncio.run(collector.collect())

    assert signals == []


def test_collect_mixes_valid_and_invalid_records(monkeypatch: pytest.MonkeyPatch) -> None:
    transport = _dataset_handler([_VALID_RECORD, _RECORD_MISSING_COUNTY])
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig())

    signals = asyncio.run(collector.collect())

    assert len(signals) == 2  # only from the valid record


def test_collect_never_fabricates_confidence_or_coordinates(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record_without_coordinates = {
        "maakond": "Harju",
        "omavalitsus": "Tallinn",
        "ehitisregistri_kood": "555",
    }
    transport = _dataset_handler([record_without_coordinates])
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig())

    signals = asyncio.run(collector.collect())

    assert len(signals) == 1
    assert signals[0].coordinates is None


def test_collect_respects_max_records_per_run(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [{**_VALID_RECORD, "ehitisregistri_kood": str(i)} for i in range(5)]
    transport = _dataset_handler(records)
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig(max_records_per_run=2))

    signals = asyncio.run(collector.collect())

    assert len(signals) == 4  # 2 records processed * 2 signals each (building + energy)


def test_collect_raises_when_no_json_resource_listed(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"resources": [{"format": "csv", "url": "/x.csv"}]})

    _patch_http_client(monkeypatch, httpx.MockTransport(handler))
    collector = EhitisregisterCollector(EhitisregisterConfig())

    with pytest.raises(CollectorError):
        asyncio.run(collector.collect())


def test_collect_raises_on_repeated_server_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    _patch_http_client(monkeypatch, httpx.MockTransport(handler))
    collector = EhitisregisterCollector(
        EhitisregisterConfig(max_retries=1),
        retry_policy=RetryPolicy(max_retries=1, initial_backoff_seconds=0.001),
    )

    with pytest.raises(CollectorError):
        asyncio.run(collector.collect())


def test_collect_tracks_retry_count_on_transient_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 503 followed by a success must be reflected in collector.retry_count."""
    attempts = {"dataset": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/datasets/ehitisregister":
            attempts["dataset"] += 1
            if attempts["dataset"] == 1:
                return httpx.Response(503)
            return httpx.Response(
                200,
                json={"resources": [{"format": "json", "url": "/files/ehitisregister.json"}]},
            )
        if request.url.path == "/files/ehitisregister.json":
            return httpx.Response(200, json=[_VALID_RECORD])
        return httpx.Response(404)

    _patch_http_client(monkeypatch, httpx.MockTransport(handler))
    collector = EhitisregisterCollector(
        EhitisregisterConfig(max_retries=2),
        retry_policy=RetryPolicy(max_retries=2, initial_backoff_seconds=0.001),
    )

    assert collector.retry_count == 0
    signals = asyncio.run(collector.collect())

    assert len(signals) == 2
    assert collector.retry_count == 1


def test_sample_raw_records_tracks_retry_count(monkeypatch: pytest.MonkeyPatch) -> None:
    attempts = {"resource": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/datasets/ehitisregister":
            return httpx.Response(
                200, json={"resources": [{"format": "json", "url": "/files/ehitisregister.json"}]}
            )
        if request.url.path == "/files/ehitisregister.json":
            attempts["resource"] += 1
            if attempts["resource"] == 1:
                return httpx.Response(503)
            return httpx.Response(200, json=[_VALID_RECORD])
        return httpx.Response(404)

    _patch_http_client(monkeypatch, httpx.MockTransport(handler))
    collector = EhitisregisterCollector(
        EhitisregisterConfig(max_retries=2),
        retry_policy=RetryPolicy(max_retries=2, initial_backoff_seconds=0.001),
    )

    sampled = asyncio.run(collector.sample_raw_records())

    assert sampled == [_VALID_RECORD]
    assert collector.retry_count == 1


def test_collector_identity() -> None:
    collector = EhitisregisterCollector(EhitisregisterConfig())
    assert collector.name == "ehitisregister"
    assert SignalType.BUILDING_RECORD in collector.supported_signal_types
    assert SignalType.ENERGY_CERTIFICATE in collector.supported_signal_types


def test_sample_raw_records_returns_unmodified_records(monkeypatch: pytest.MonkeyPatch) -> None:
    records = [{**_VALID_RECORD, "ehitisregistri_kood": str(i)} for i in range(3)]
    transport = _dataset_handler(records)
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig())

    sampled = asyncio.run(collector.sample_raw_records(limit=2))

    assert len(sampled) == 2
    assert sampled[0] == records[0]
    assert sampled == records[:2]  # raw, un-extracted records -- no Signal conversion applied


def test_sample_raw_records_does_not_skip_records_missing_required_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Unlike collect(), sampling is for inspection -- it must not silently drop anything."""
    transport = _dataset_handler([_RECORD_MISSING_COUNTY])
    _patch_http_client(monkeypatch, transport)
    collector = EhitisregisterCollector(EhitisregisterConfig())

    sampled = asyncio.run(collector.sample_raw_records())

    assert sampled == [_RECORD_MISSING_COUNTY]
