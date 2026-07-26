"""KV.ee real estate listing collector. See ``base_listing_collector`` for the shared logic."""

from __future__ import annotations

from app.collectors.real_estate.base_listing_collector import BaseListingCollector
from app.config.settings import BrowserCollectorConfig
from app.core.retry import RetryPolicy


class KvEeCollector(BaseListingCollector):
    """Collects renovation-indicator Signals from KV.ee listings."""

    def __init__(
        self, config: BrowserCollectorConfig, *, retry_policy: RetryPolicy | None = None
    ) -> None:
        super().__init__(name="kv_ee", source="KV.ee", config=config, retry_policy=retry_policy)
