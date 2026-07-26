"""Configurable retry infrastructure with exponential backoff.

This module is intentionally free of any I/O library dependency (no httpx,
no Playwright) so it can be imported from the domain and application layers
as well as infrastructure. Collectors and repositories wrap transient
operations with :func:`retry` or :func:`retry_async`.
"""

from __future__ import annotations

import asyncio
import random
import time
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ConfigDict, Field

from app.core.exceptions import RetryExhaustedError


class RetryPolicy(BaseModel):
    """Declarative description of how a retryable operation should behave.

    Instances are typically constructed from configuration (see
    ``app.config.settings.RetryConfig``) rather than hardcoded at call
    sites, per the "configuration over hardcoding" principle.
    """

    model_config = ConfigDict(frozen=True)

    max_retries: int = Field(default=3, ge=0, description="Retries after the first attempt.")
    initial_backoff_seconds: float = Field(default=0.5, gt=0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: float = Field(default=30.0, gt=0)
    jitter_seconds: float = Field(default=0.1, ge=0)
    timeout_seconds: float | None = Field(
        default=None,
        gt=0,
        description="Total wall-clock budget across all attempts. None disables the budget.",
    )

    def backoff_for_attempt(self, attempt: int) -> float:
        """Return the delay, in seconds, before retry attempt ``attempt`` (1-indexed)."""
        raw = self.initial_backoff_seconds * (self.backoff_multiplier ** (attempt - 1))
        capped = min(raw, self.max_backoff_seconds)
        return capped + random.uniform(0, self.jitter_seconds)


def retry[
    T
](
    func: Callable[[], T],
    *,
    policy: RetryPolicy,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Call the zero-argument callable ``func`` synchronously, retrying per ``policy``.

    Callers that need to pass arguments to the underlying operation should
    wrap it in a closure or ``functools.partial`` -- keeping ``func``
    argument-free avoids ambiguity between the wrapped call's own
    arguments and this function's retry configuration.

    Args:
        func: The zero-argument callable to invoke.
        policy: Retry configuration (max attempts, backoff, timeout).
        retry_on: Exception types considered transient and worth retrying.
        on_retry: Optional callback invoked as ``on_retry(attempt, exception)``
            before each backoff sleep, useful for structured logging.

    Raises:
        RetryExhaustedError: If all attempts fail.
    """
    start = time.monotonic()
    last_exception: BaseException | None = None

    for attempt in range(1, policy.max_retries + 2):
        if (
            policy.timeout_seconds is not None
            and (time.monotonic() - start) > policy.timeout_seconds
        ):
            raise RetryExhaustedError(
                f"Retry timeout of {policy.timeout_seconds}s exceeded for {func.__name__!r}.",
                attempts=attempt - 1,
                last_exception=last_exception,
            )
        try:
            return func()
        except retry_on as exc:
            last_exception = exc
            if attempt > policy.max_retries:
                break
            if on_retry is not None:
                on_retry(attempt, exc)
            time.sleep(policy.backoff_for_attempt(attempt))

    raise RetryExhaustedError(
        f"Exhausted {policy.max_retries + 1} attempt(s) calling {func.__name__!r}.",
        attempts=policy.max_retries + 1,
        last_exception=last_exception,
    )


async def retry_async[
    T
](
    func: Callable[[], Awaitable[T]],
    *,
    policy: RetryPolicy,
    retry_on: tuple[type[BaseException], ...] = (Exception,),
    on_retry: Callable[[int, BaseException], None] | None = None,
) -> T:
    """Async counterpart to :func:`retry`.

    ``asyncio.CancelledError`` is never caught by ``retry_on`` matching
    ``Exception`` because it derives from ``BaseException``; cancellation
    always propagates immediately, as required.
    """
    start = time.monotonic()
    last_exception: BaseException | None = None

    for attempt in range(1, policy.max_retries + 2):
        if (
            policy.timeout_seconds is not None
            and (time.monotonic() - start) > policy.timeout_seconds
        ):
            raise RetryExhaustedError(
                f"Retry timeout of {policy.timeout_seconds}s exceeded for {func.__name__!r}.",
                attempts=attempt - 1,
                last_exception=last_exception,
            )
        try:
            return await func()
        except asyncio.CancelledError:
            raise
        except retry_on as exc:
            last_exception = exc
            if attempt > policy.max_retries:
                break
            if on_retry is not None:
                on_retry(attempt, exc)
            await asyncio.sleep(policy.backoff_for_attempt(attempt))

    raise RetryExhaustedError(
        f"Exhausted {policy.max_retries + 1} attempt(s) calling {func.__name__!r}.",
        attempts=policy.max_retries + 1,
        last_exception=last_exception,
    )
