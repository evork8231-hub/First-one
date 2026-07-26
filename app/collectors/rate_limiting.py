"""A minimal async rate limiter enforcing a fixed delay between requests.

Shared by the HTTP and browser clients so every collector respects the
same, configurable minimum spacing between outbound requests to a given
source -- never hardcoded, always sourced from
``app.config.settings.HttpCollectorConfig.request_delay_seconds`` (or the
browser equivalent).
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable


class RateLimiter:
    """Ensures at least ``delay_seconds`` elapses between successive ``wait()`` calls."""

    def __init__(self, delay_seconds: float, *, clock: Callable[[], float] | None = None) -> None:
        if delay_seconds < 0:
            raise ValueError("delay_seconds must be non-negative.")
        self._delay_seconds = delay_seconds
        self._clock = clock if clock is not None else time.monotonic
        self._last_request_at: float | None = None

    async def wait(self) -> None:
        """Sleep just long enough to enforce the configured minimum delay, if needed."""
        now = self._clock()
        if self._last_request_at is not None:
            elapsed = now - self._last_request_at
            remaining = self._delay_seconds - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
        self._last_request_at = self._clock()
