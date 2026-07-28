"""Tests for the shared BaseListingCollector (exercised via KvEeCollector) and its
thin per-site subclasses. No live network / no real Playwright browser --
``BrowserClient`` is replaced with an in-memory fake.
"""

from __future__ import annotations

import asyncio
from types import TracebackType
from typing import Self

import app.collectors.real_estate.base_listing_collector as base_module
import pytest
from app.collectors.real_estate.base_listing_collector import BaseListingCollector
from app.collectors.real_estate.city24_collector import City24Collector
from app.collectors.real_estate.kinnisvara24_collector import Kinnisvara24Collector
from app.collectors.real_estate.kv_ee_collector import KvEeCollector
from app.config.settings import BrowserCollectorConfig
from app.core.exceptions import CollectorError
from app.domain.enums import SignalType

_LISTING_WITH_RENOVATION_PHRASES = """
<html><head>
<script type="application/ld+json">
{
  "@type": "Product",
  "name": "3-toaline korter",
  "description": "Vajab remonti. Originaalne köök. Hea asukoht.",
  "address": {"addressRegion": "Harju", "addressLocality": "Tallinn"},
  "additionalProperty": [
    {"@type": "PropertyValue", "name": "Energy class", "value": "D"}
  ]
}
</script>
</head><body></body></html>
"""

_LISTING_WITHOUT_INDICATORS = """
<html><head>
<script type="application/ld+json">
{
  "@type": "Product",
  "description": "Renoveeritud maja heas seisukorras.",
  "address": {"addressRegion": "Harju", "addressLocality": "Tallinn"}
}
</script>
</head><body></body></html>
"""

_LISTING_WITHOUT_JSONLD = "<html><body>No structured data.</body></html>"

_LISTING_MISSING_ADDRESS = """
<html><head>
<script type="application/ld+json">
{"@type": "Product", "description": "Vajab remonti."}
</script>
</head><body></body></html>
"""


class FakeBrowserClient:
    """A drop-in replacement for BrowserClient, backed by in-memory fixtures."""

    def __init__(
        self,
        *,
        links_by_search_url: dict[str, list[str]],
        html_by_listing_url: dict[str, str],
        fail_urls: frozenset[str] = frozenset(),
    ) -> None:
        self._links_by_search_url = links_by_search_url
        self._html_by_listing_url = html_by_listing_url
        self._fail_urls = fail_urls
        self.retry_count = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        return None

    async def find_listing_links(self, url: str, selector: str) -> list[str]:
        if url in self._fail_urls:
            raise CollectorError(f"Simulated failure loading search page {url}.")
        return self._links_by_search_url.get(url, [])

    async def fetch_rendered_html(self, url: str) -> str:
        if url in self._fail_urls:
            raise CollectorError(f"Simulated failure loading listing {url}.")
        return self._html_by_listing_url[url]


def _configured(**overrides: object) -> BrowserCollectorConfig:
    defaults: dict[str, object] = {
        "base_url": "https://example.test",
        "search_paths": ["/search"],
        "listing_link_selector": "a.listing-link",
        "request_delay_seconds": 0.0,
    }
    defaults.update(overrides)
    return BrowserCollectorConfig(**defaults)  # type: ignore[arg-type]


def _patch_browser_client(monkeypatch: pytest.MonkeyPatch, fake: FakeBrowserClient) -> None:
    monkeypatch.setattr(base_module, "BrowserClient", lambda config, retry_policy=None: fake)


def test_collect_raises_when_not_configured() -> None:
    collector = KvEeCollector(BrowserCollectorConfig(base_url="https://example.test"))
    with pytest.raises(CollectorError):
        asyncio.run(collector.collect())


def test_collect_extracts_signals_from_explicit_phrases(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeBrowserClient(
        links_by_search_url={"https://example.test/search": ["https://example.test/listing/1"]},
        html_by_listing_url={"https://example.test/listing/1": _LISTING_WITH_RENOVATION_PHRASES},
    )
    _patch_browser_client(monkeypatch, fake)
    collector = KvEeCollector(_configured())

    signals = asyncio.run(collector.collect())

    assert {s.signal_type for s in signals} == {
        SignalType.RENOVATION_MENTION,
        SignalType.KITCHEN_MENTION,
    }
    for signal in signals:
        assert signal.county == "Harju"
        assert signal.municipality == "Tallinn"
        assert signal.source_url == "https://example.test/listing/1"
        assert signal.metadata["energy_class"] == "D"


def test_collect_returns_no_signals_when_no_phrase_present(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeBrowserClient(
        links_by_search_url={"https://example.test/search": ["https://example.test/listing/1"]},
        html_by_listing_url={"https://example.test/listing/1": _LISTING_WITHOUT_INDICATORS},
    )
    _patch_browser_client(monkeypatch, fake)
    collector = KvEeCollector(_configured())

    assert asyncio.run(collector.collect()) == []


def test_collect_skips_listing_without_jsonld(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeBrowserClient(
        links_by_search_url={"https://example.test/search": ["https://example.test/listing/1"]},
        html_by_listing_url={"https://example.test/listing/1": _LISTING_WITHOUT_JSONLD},
    )
    _patch_browser_client(monkeypatch, fake)
    collector = KvEeCollector(_configured())

    assert asyncio.run(collector.collect()) == []


def test_collect_skips_listing_missing_address(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeBrowserClient(
        links_by_search_url={"https://example.test/search": ["https://example.test/listing/1"]},
        html_by_listing_url={"https://example.test/listing/1": _LISTING_MISSING_ADDRESS},
    )
    _patch_browser_client(monkeypatch, fake)
    collector = KvEeCollector(_configured())

    assert asyncio.run(collector.collect()) == []


def test_collect_continues_after_a_listing_fails_to_load(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeBrowserClient(
        links_by_search_url={
            "https://example.test/search": [
                "https://example.test/listing/broken",
                "https://example.test/listing/ok",
            ]
        },
        html_by_listing_url={"https://example.test/listing/ok": _LISTING_WITH_RENOVATION_PHRASES},
        fail_urls=frozenset({"https://example.test/listing/broken"}),
    )
    _patch_browser_client(monkeypatch, fake)
    collector = KvEeCollector(_configured())

    signals = asyncio.run(collector.collect())

    assert len(signals) == 2  # only the successfully loaded listing contributes


def test_collect_respects_max_listings_per_run(monkeypatch: pytest.MonkeyPatch) -> None:
    urls = [f"https://example.test/listing/{i}" for i in range(5)]
    fake = FakeBrowserClient(
        links_by_search_url={"https://example.test/search": urls},
        html_by_listing_url=dict.fromkeys(urls, _LISTING_WITH_RENOVATION_PHRASES),
    )
    _patch_browser_client(monkeypatch, fake)
    collector = KvEeCollector(_configured(max_listings_per_run=2))

    signals = asyncio.run(collector.collect())

    assert len(signals) == 4  # 2 listings * 2 phrases each


@pytest.mark.parametrize(
    ("collector_cls", "expected_name", "expected_source"),
    [
        (KvEeCollector, "kv_ee", "KV.ee"),
        (Kinnisvara24Collector, "kinnisvara24", "Kinnisvara24"),
        (City24Collector, "city24", "City24 Estonia"),
    ],
)
def test_each_site_collector_is_a_thin_identity_wrapper(
    collector_cls: type[BaseListingCollector], expected_name: str, expected_source: str
) -> None:
    collector = collector_cls(BrowserCollectorConfig(base_url="https://example.test"))
    assert collector.name == expected_name
    assert collector.source == expected_source
    assert isinstance(collector, BaseListingCollector)
