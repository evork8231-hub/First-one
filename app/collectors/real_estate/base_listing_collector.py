"""Shared logic for ``playwright_jsonld`` real estate listing collectors.

Extracts a schema.org listing (``Product``/``Offer``/``RealEstateListing``/
etc.) from each listing page's JSON-LD, and emits a Signal only for an
explicit Estonian renovation-indicator phrase found in the listing's own
description text -- never inferred from price, photos, or building age.

Known limitation: which CSS selector identifies "a listing link" on a
given site's search-results page, and which URL path(s) list houses for
sale, are genuinely site-specific and could not be confirmed against a
live site in this environment. ``BrowserCollectorConfig.search_paths``
and ``listing_link_selector`` have no default; this collector raises
``CollectorError`` until an operator configures them per site (see
docs/CONFIGURATION.md).
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urljoin

from loguru import logger

from app.collectors.base import BaseCollector
from app.collectors.browser_client import BrowserClient
from app.collectors.jsonld import (
    REAL_ESTATE_TYPES,
    extract_jsonld_blocks,
    find_additional_property,
    find_first_of_type,
    get_nested,
)
from app.collectors.phrase_matching import find_renovation_indicators
from app.config.settings import BrowserCollectorConfig
from app.core.exceptions import CollectorError
from app.core.retry import RetryPolicy
from app.domain.enums import ServiceCategory, SignalType
from app.domain.signal import Signal
from app.utils.time import utc_now

#: Documented default mapping from a matched phrase's SignalType to the
#: service category recorded on the Signal. The rule engine matches on
#: signal_type, not service_category (see app.rule_engine.matcher), so
#: this only affects descriptive/reporting metadata. RENOVATION_MENTION is
#: generic across both kitchen and bathroom rules in config/rules/ --
#: kitchen_remodeling is used here as the documented default.
_SIGNAL_TYPE_TO_CATEGORY: dict[SignalType, ServiceCategory] = {
    SignalType.KITCHEN_MENTION: ServiceCategory.KITCHEN_REMODELING,
    SignalType.BATHROOM_MENTION: ServiceCategory.BATHROOM_REMODELING,
    SignalType.ROOF_MENTION: ServiceCategory.ROOFING,
    SignalType.RENOVATION_MENTION: ServiceCategory.KITCHEN_REMODELING,
}


class BaseListingCollector(BaseCollector):
    """Discovers listing URLs, fetches each rendered page, and extracts Signals."""

    def __init__(
        self,
        *,
        name: str,
        source: str,
        config: BrowserCollectorConfig,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        super().__init__(
            name=name,
            source=source,
            supported_signal_types=frozenset(_SIGNAL_TYPE_TO_CATEGORY),
            retry_policy=retry_policy or RetryPolicy(max_retries=config.max_retries),
        )
        self._config = config

    async def collect(self) -> list[Signal]:
        if not self._config.search_paths or not self._config.listing_link_selector:
            raise CollectorError(
                f"{self.name} is not configured: 'search_paths' and 'listing_link_selector' "
                f"must both be set (see docs/CONFIGURATION.md) before enabling this collector."
            )

        signals: list[Signal] = []
        listing_urls: list[str] = []

        async with BrowserClient(self._config, retry_policy=self._retry_policy) as browser:
            for search_path in self._config.search_paths:
                search_url = urljoin(self._config.base_url, search_path)
                try:
                    urls = await browser.find_listing_links(
                        search_url, self._config.listing_link_selector
                    )
                except CollectorError as exc:
                    logger.warning(
                        "{}: could not load search page {}: {}", self.name, search_url, exc
                    )
                    continue
                listing_urls.extend(urls)

            for url in listing_urls[: self._config.max_listings_per_run]:
                try:
                    html = await browser.fetch_rendered_html(url)
                except CollectorError as exc:
                    logger.warning("{}: could not load listing {}: {}", self.name, url, exc)
                    continue
                signals.extend(self._parse_listing(html, url))

            self.retry_count = browser.retry_count

        logger.info(
            "{} collector produced {} signal(s) from {} listing(s) discovered.",
            self.name,
            len(signals),
            len(listing_urls),
        )
        return signals

    async def fetch_page_html(self, url: str) -> str:
        """Fetch and return the fully rendered HTML of ``url`` using this collector's settings.

        For operator-facing inspection tools (e.g. ``sigint discover-selectors``)
        that need a real rendered page without running full listing
        discovery/parsing. ``url`` is a caller-supplied parameter -- an
        operator can inspect any page (a search-results page, a single
        listing) regardless of whether ``search_paths``/``listing_link_selector``
        are configured yet.
        """
        async with BrowserClient(self._config, retry_policy=self._retry_policy) as browser:
            html = await browser.fetch_rendered_html(url)
            self.retry_count = browser.retry_count
        return html

    def _parse_listing(self, html: str, source_url: str) -> list[Signal]:
        blocks = extract_jsonld_blocks(html)
        listing = find_first_of_type(blocks, REAL_ESTATE_TYPES)
        if listing is None:
            logger.debug("{}: no schema.org listing JSON-LD found at {}", self.name, source_url)
            return []

        county = get_nested(listing, "address", "addressRegion")
        municipality = get_nested(listing, "address", "addressLocality")
        if not county or not municipality:
            logger.debug(
                "{}: listing at {} has no address region/locality; skipped.", self.name, source_url
            )
            return []

        description = listing.get("description") or listing.get("name")
        matches = find_renovation_indicators(str(description) if description else None)
        if not matches:
            return []

        metadata_base: dict[str, Any] = {}
        house_type = listing.get("additionalType") or find_additional_property(listing, "maja tüüp")
        if house_type:
            metadata_base["house_type"] = house_type
        # "energ" matches both English ("Energy class") and Estonian
        # ("Energiaklass") PropertyValue names -- the real label used by
        # each site's markup could not be confirmed in this environment.
        energy_class = find_additional_property(listing, "energ")
        if energy_class:
            metadata_base["energy_class"] = energy_class

        signals: list[Signal] = []
        for match in matches:
            metadata = dict(metadata_base)
            metadata["matched_phrase"] = match.matched_phrase
            signals.append(
                Signal(
                    signal_type=match.signal_type,
                    source=self.source,
                    source_url=source_url,
                    service_category=_SIGNAL_TYPE_TO_CATEGORY[match.signal_type],
                    county=str(county),
                    municipality=str(municipality),
                    timestamp=utc_now(),
                    raw_payload=listing,
                    confidence=self._config.default_confidence,
                    metadata=metadata,
                )
            )
        return signals
