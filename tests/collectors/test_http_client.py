"""Tests for app.collectors.http_client.HttpClient (no live network -- httpx.MockTransport only)."""

from __future__ import annotations

import asyncio

import httpx
import pytest
from app.collectors.http_client import HttpClient
from app.config.settings import HttpCollectorConfig
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy


def _config(**overrides: object) -> HttpCollectorConfig:
    defaults: dict[str, object] = {
        "base_url": "https://example.test",
        "request_delay_seconds": 0.0,
    }
    defaults.update(overrides)
    return HttpCollectorConfig(**defaults)  # type: ignore[arg-type]


def _fast_retry_policy() -> RetryPolicy:
    return RetryPolicy(max_retries=2, initial_backoff_seconds=0.001, jitter_seconds=0.0)


def test_get_json_returns_parsed_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hello": "world"})

    transport = httpx.MockTransport(handler)

    async def run() -> object:
        async with HttpClient(_config(), transport=transport) as client:
            return await client.get_json("/data")

    assert asyncio.run(run()) == {"hello": "world"}


def test_get_text_returns_raw_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<xml/>")

    transport = httpx.MockTransport(handler)

    async def run() -> str:
        async with HttpClient(_config(), transport=transport) as client:
            return await client.get_text("/feed.xml")

    assert asyncio.run(run()) == "<xml/>"


def test_get_json_raises_collector_error_on_invalid_json() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="not json")

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        async with HttpClient(_config(), transport=transport) as client:
            await client.get_json("/data")

    with pytest.raises(CollectorError):
        asyncio.run(run())


def test_client_error_is_not_retried() -> None:
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        async with HttpClient(
            _config(), transport=transport, retry_policy=_fast_retry_policy()
        ) as client:
            await client.get_json("/missing")

    with pytest.raises(CollectorError):
        asyncio.run(run())
    assert call_count["count"] == 1


def test_server_error_is_retried_then_succeeds() -> None:
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        if call_count["count"] < 3:
            return httpx.Response(503)
        return httpx.Response(200, json={"ok": True})

    transport = httpx.MockTransport(handler)

    async def run() -> object:
        async with HttpClient(
            _config(), transport=transport, retry_policy=_fast_retry_policy()
        ) as client:
            return await client.get_json("/flaky")

    result = asyncio.run(run())
    assert result == {"ok": True}
    assert call_count["count"] == 3


def test_cache_disabled_by_default_hits_the_server_every_time() -> None:
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        return httpx.Response(200, json={"n": call_count["count"]})

    transport = httpx.MockTransport(handler)

    async def run() -> tuple[object, object]:
        async with HttpClient(_config(), transport=transport) as client:
            first = await client.get_json("/data")
            second = await client.get_json("/data")
            return first, second

    first, second = asyncio.run(run())
    assert first == {"n": 1}
    assert second == {"n": 2}
    assert call_count["count"] == 2


def test_cache_enabled_avoids_a_second_request() -> None:
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        return httpx.Response(200, json={"n": call_count["count"]})

    transport = httpx.MockTransport(handler)

    async def run() -> tuple[object, object]:
        config = _config(cache_enabled=True, cache_ttl_seconds=60.0)
        async with HttpClient(config, transport=transport) as client:
            first = await client.get_json("/data")
            second = await client.get_json("/data")
            return first, second

    first, second = asyncio.run(run())
    assert first == second == {"n": 1}
    assert call_count["count"] == 1


def test_cache_is_keyed_by_url_and_params() -> None:
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        return httpx.Response(200, json={"n": call_count["count"]})

    transport = httpx.MockTransport(handler)

    async def run() -> None:
        config = _config(cache_enabled=True, cache_ttl_seconds=60.0)
        async with HttpClient(config, transport=transport) as client:
            await client.get_json("/data", params={"page": 1})
            await client.get_json("/data", params={"page": 2})

    asyncio.run(run())
    assert call_count["count"] == 2


def test_cache_expires_after_its_ttl() -> None:
    call_count = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        call_count["count"] += 1
        return httpx.Response(200, json={"n": call_count["count"]})

    transport = httpx.MockTransport(handler)

    async def run() -> tuple[object, object]:
        config = _config(cache_enabled=True, cache_ttl_seconds=0.01)
        async with HttpClient(config, transport=transport) as client:
            first = await client.get_json("/data")
            await asyncio.sleep(0.05)
            second = await client.get_json("/data")
            return first, second

    first, second = asyncio.run(run())
    assert first == {"n": 1}
    assert second == {"n": 2}
    assert call_count["count"] == 2


def test_using_client_without_context_manager_raises() -> None:
    client = HttpClient(_config())

    async def run() -> None:
        await client.get_json("/data")

    with pytest.raises(RuntimeError):
        asyncio.run(run())
