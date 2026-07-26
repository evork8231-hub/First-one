"""Tests for app.core.retry."""

from __future__ import annotations

import asyncio

import pytest
from app.core.exceptions import RetryExhaustedError
from app.core.retry import RetryPolicy, retry, retry_async


def test_retry_succeeds_without_retrying() -> None:
    calls = []

    def op() -> str:
        calls.append(1)
        return "ok"

    result = retry(op, policy=RetryPolicy(max_retries=3, initial_backoff_seconds=0.001))

    assert result == "ok"
    assert len(calls) == 1


def test_retry_succeeds_after_transient_failures() -> None:
    state = {"count": 0}

    def op() -> str:
        state["count"] += 1
        if state["count"] < 3:
            raise ValueError("transient")
        return "ok"

    result = retry(
        op, policy=RetryPolicy(max_retries=3, initial_backoff_seconds=0.001, jitter_seconds=0)
    )

    assert result == "ok"
    assert state["count"] == 3


def test_retry_exhausts_and_raises() -> None:
    def op() -> None:
        raise ValueError("always fails")

    with pytest.raises(RetryExhaustedError) as exc_info:
        retry(
            op, policy=RetryPolicy(max_retries=2, initial_backoff_seconds=0.001, jitter_seconds=0)
        )

    assert exc_info.value.attempts == 3


def test_retry_only_catches_configured_exception_types() -> None:
    def op() -> None:
        raise KeyError("not retried")

    with pytest.raises(KeyError):
        retry(
            op,
            policy=RetryPolicy(max_retries=2, initial_backoff_seconds=0.001),
            retry_on=(ValueError,),
        )


def test_retry_respects_timeout_budget() -> None:
    def op() -> None:
        raise ValueError("fails")

    policy = RetryPolicy(
        max_retries=5, initial_backoff_seconds=0.05, jitter_seconds=0, timeout_seconds=0.01
    )

    with pytest.raises(RetryExhaustedError):
        retry(op, policy=policy)


def test_retry_async_succeeds_after_transient_failures() -> None:
    state = {"count": 0}

    async def op() -> str:
        state["count"] += 1
        if state["count"] < 2:
            raise ValueError("transient")
        return "ok"

    result = asyncio.run(
        retry_async(
            op, policy=RetryPolicy(max_retries=3, initial_backoff_seconds=0.001, jitter_seconds=0)
        )
    )

    assert result == "ok"
    assert state["count"] == 2


def test_retry_async_propagates_cancelled_error() -> None:
    async def op() -> None:
        raise asyncio.CancelledError()

    async def run() -> None:
        await retry_async(op, policy=RetryPolicy(max_retries=3, initial_backoff_seconds=0.001))

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(run())
