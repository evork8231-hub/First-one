"""Tests for app.collectors.rate_limiting.RateLimiter."""

from __future__ import annotations

import asyncio

import pytest
from app.collectors.rate_limiting import RateLimiter


class _ClampedFakeClock:
    """Returns successive values from ``values``, repeating the last one once exhausted."""

    def __init__(self, values: list[float]) -> None:
        self._values = values
        self._index = 0

    def __call__(self) -> float:
        value = self._values[min(self._index, len(self._values) - 1)]
        self._index += 1
        return value


def test_rejects_negative_delay() -> None:
    with pytest.raises(ValueError):
        RateLimiter(-1.0)


def test_first_wait_does_not_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    limiter = RateLimiter(1.0)
    asyncio.run(limiter.wait())

    assert sleep_calls == []


def test_second_wait_sleeps_remaining_delay(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RateLimiter(1.0, clock=_ClampedFakeClock([0.0, 0.0, 0.3]))

    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    async def run() -> None:
        await limiter.wait()  # last_request_at set from second clock value (0.0)
        await limiter.wait()  # now = 0.3, elapsed = 0.3, remaining = 0.7

    asyncio.run(run())

    assert sleep_calls == [pytest.approx(0.7)]


def test_wait_does_not_sleep_when_delay_already_elapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = RateLimiter(1.0, clock=_ClampedFakeClock([0.0, 0.0, 5.0]))

    sleep_calls: list[float] = []

    async def _fake_sleep(delay: float) -> None:
        sleep_calls.append(delay)

    monkeypatch.setattr(asyncio, "sleep", _fake_sleep)

    async def run() -> None:
        await limiter.wait()
        await limiter.wait()

    asyncio.run(run())

    assert sleep_calls == []
