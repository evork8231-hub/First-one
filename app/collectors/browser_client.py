"""A reusable, retrying, rate-limited Playwright wrapper for browser-based collectors.

Every ``playwright_jsonld`` listing collector uses this instead of driving
Playwright directly, so browser lifecycle management, timeout handling,
retry behavior, rate limiting, and logging are implemented exactly once.

This client never attempts to bypass authentication or a CAPTCHA: a
blocked or challenged page simply surfaces as a failed navigation
(``CollectorUnavailableError``), retried per policy and ultimately
propagated -- never worked around.
"""

from __future__ import annotations

from types import TracebackType
from typing import Self
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from loguru import logger
from playwright.async_api import Browser, Playwright, async_playwright
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.collectors.rate_limiting import RateLimiter
from app.config.settings import BrowserCollectorConfig
from app.core.exceptions import CollectorUnavailableError, RetryExhaustedError
from app.core.retry import RetryPolicy, retry_async

_RETRYABLE_EXCEPTIONS = (CollectorUnavailableError, PlaywrightTimeoutError)


class BrowserClient:
    """Async context-manager wrapper around a headless Playwright Chromium session.

    Usage::

        async with BrowserClient(config) as browser:
            html = await browser.fetch_rendered_html("https://example.ee/listing/1")
    """

    def __init__(
        self, config: BrowserCollectorConfig, *, retry_policy: RetryPolicy | None = None
    ) -> None:
        self._config = config
        self._retry_policy = retry_policy or RetryPolicy(max_retries=config.max_retries)
        self._rate_limiter = RateLimiter(config.request_delay_seconds)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        #: Total retry attempts made across every navigation through this
        #: client instance (a fresh instance is constructed per collector
        #: run, so this naturally resets each run).
        self.retry_count = 0

    async def __aenter__(self) -> Self:
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self._config.headless)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def fetch_rendered_html(self, url: str) -> str:
        """Navigate to ``url`` and return the fully rendered page HTML.

        Raises:
            CollectorUnavailableError: If navigation fails or the response
                status indicates the page could not be loaded (e.g. a
                block page). Never retried into an authentication or
                CAPTCHA bypass -- the failure simply propagates.
        """
        if self._browser is None:
            raise RuntimeError("BrowserClient must be used as an 'async with' context manager.")
        browser = self._browser
        timeout_ms = self._config.timeout_seconds * 1000

        async def _do_fetch() -> str:
            await self._rate_limiter.wait()
            logger.debug("Browser navigating to {}", url)
            page = await browser.new_page(user_agent=self._config.user_agent)
            try:
                response = await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
                if response is None or response.status >= 400:
                    status = response.status if response is not None else "no response"
                    raise CollectorUnavailableError(
                        f"Navigation to {url!r} failed (status={status})."
                    )
                return await page.content()
            finally:
                await page.close()

        def _on_retry(attempt: int, exc: BaseException) -> None:
            self.retry_count += 1
            logger.warning(
                "Retrying navigation to {} (attempt {}) after error: {}", url, attempt, exc
            )

        try:
            return await retry_async(
                _do_fetch,
                policy=self._retry_policy,
                retry_on=_RETRYABLE_EXCEPTIONS,
                on_retry=_on_retry,
            )
        except RetryExhaustedError as exc:
            raise CollectorUnavailableError(
                f"Exhausted all retry attempts navigating to {url!r}: {exc.message}"
            ) from exc

    async def find_listing_links(self, url: str, css_selector: str) -> list[str]:
        """Navigate to a search-results page and return absolute listing URLs.

        ``css_selector`` must be supplied by the caller (from
        ``BrowserCollectorConfig.listing_link_selector``) -- this client
        never guesses which elements on a page are listing links.
        """
        html = await self.fetch_rendered_html(url)
        soup = BeautifulSoup(html, "html.parser")
        hrefs = [a.get("href") for a in soup.select(css_selector) if a.get("href")]
        return [urljoin(url, str(href)) for href in hrefs]
