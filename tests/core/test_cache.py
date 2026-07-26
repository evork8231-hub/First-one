"""Tests for app.core.cache.TTLCache."""

from __future__ import annotations

import pytest
from app.core.cache import TTLCache


def test_rejects_a_non_positive_ttl() -> None:
    with pytest.raises(ValueError):
        TTLCache(ttl_seconds=0)


def test_miss_on_an_absent_key() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60)
    assert cache.get("missing") is None
    assert cache.stats.misses == 1
    assert cache.stats.hits == 0


def test_hit_after_set() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60)
    cache.set("key", 42)
    assert cache.get("key") == 42
    assert cache.stats.hits == 1
    assert cache.stats.misses == 0


def test_entry_expires_after_ttl() -> None:
    fake_time = [0.0]
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=10, clock=lambda: fake_time[0])
    cache.set("key", 1)
    fake_time[0] = 11.0
    assert cache.get("key") is None
    assert cache.stats.misses == 1


def test_invalidate_single_key() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate("a")
    assert cache.get("a") is None
    assert cache.get("b") == 2


def test_invalidate_all() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60)
    cache.set("a", 1)
    cache.set("b", 2)
    cache.invalidate()
    assert len(cache) == 0


def test_hit_rate_and_len() -> None:
    cache: TTLCache[str, int] = TTLCache(ttl_seconds=60)
    cache.set("a", 1)
    cache.get("a")
    cache.get("missing")
    assert len(cache) == 1
    assert cache.stats.total == 2
    assert cache.stats.hit_rate == pytest.approx(0.5)
