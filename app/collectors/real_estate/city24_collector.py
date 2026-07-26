"""City24 Estonia listing collector. See ``base_listing_collector`` for the shared logic."""

from __future__ import annotations

from app.collectors.real_estate.base_listing_collector import BaseListingCollector
from app.config.settings import BrowserCollectorConfig
from app.core.retry import RetryPolicy


class City24Collector(BaseListingCollector):
    """Collects renovation-indicator Signals from City24 Estonia listings."""

    def __init__(
        self, config: BrowserCollectorConfig, *, retry_policy: RetryPolicy | None = None
    ) -> None:
        super().__init__(
            name="city24", source="City24 Estonia", config=config, retry_policy=retry_policy
        )
