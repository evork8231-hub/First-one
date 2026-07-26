"""A small, dependency-free in-memory TTL cache.

Used for beneficial, safe-to-cache data only: HTTP responses (where a
collector's configuration opts in), parsed rule files, and resolved
configuration -- never mutable business data such as Signals or Leads.
Each cache tracks its own hit/miss counters so callers can log cache
effectiveness (see the "cache hits/misses" structured logging
requirement) without instrumenting every call site by hand.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class CacheStats:
    """Cumulative hit/miss counters for a single :class:`TTLCache` instance."""

    hits: int = 0
    misses: int = 0

    @property
    def total(self) -> int:
        return self.hits + self.misses

    @property
    def hit_rate(self) -> float:
        return self.hits / self.total if self.total else 0.0


@dataclass
class _Entry[V]:
    value: V
    expires_at: float


class TTLCache[K, V]:
    """A process-local cache where every entry expires after ``ttl_seconds``.

    Not thread-safe by design -- every current caller (collectors, the
    config loader, the rule loader) runs single-threaded per process, so
    adding locking here would be complexity without benefit.
    """

    def __init__(self, *, ttl_seconds: float, clock: Callable[[], float] = time.monotonic) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive.")
        self._ttl_seconds = ttl_seconds
        self._clock = clock
        self._entries: dict[K, _Entry[V]] = {}
        self.stats = CacheStats()

    def get(self, key: K) -> V | None:
        """Return the cached value for ``key``, or ``None`` on a miss or expiry."""
        entry = self._entries.get(key)
        if entry is None or entry.expires_at <= self._clock():
            self._entries.pop(key, None)
            self.stats.misses += 1
            return None
        self.stats.hits += 1
        return entry.value

    def set(self, key: K, value: V) -> None:
        """Store ``value`` under ``key``, expiring after this cache's TTL."""
        self._entries[key] = _Entry(value=value, expires_at=self._clock() + self._ttl_seconds)

    def invalidate(self, key: K | None = None) -> None:
        """Remove a single ``key``, or every entry if ``key`` is ``None``."""
        if key is None:
            self._entries.clear()
        else:
            self._entries.pop(key, None)

    def __len__(self) -> int:
        return len(self._entries)
