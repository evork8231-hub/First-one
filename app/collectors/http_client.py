"""A reusable, retrying, rate-limited httpx wrapper for HTTP-based collectors.

Every ``http_jsonld`` / ``rss_jsonld`` collector uses this instead of
constructing its own ``httpx.AsyncClient``, so timeout handling, retry
behavior, rate limiting, and logging are implemented exactly once.
"""

from __future__ import annotations

import json
from types import TracebackType
from typing import Any, Self

import httpx
from loguru import logger

from app.collectors.rate_limiting import RateLimiter
from app.config.settings import HttpCollectorConfig
from app.core.exceptions import CollectorError, CollectorUnavailableError, RetryExhaustedError
from app.core.retry import RetryPolicy, retry_async

#: Transient failures worth retrying: server errors we raise ourselves, and
#: httpx's own network/timeout exceptions. Client errors (4xx) are never
#: retried -- they indicate a request that will not succeed by repeating it.
_RETRYABLE_EXCEPTIONS = (CollectorUnavailableError, httpx.TransportError)


class HttpClient:
    """Async context-manager wrapper around ``httpx.AsyncClient``.

    Usage::

        async with HttpClient(config) as client:
            payload = await client.get_json("/api/datasets/example")

    ``transport`` lets tests substitute ``httpx.MockTransport`` instead of
    real network I/O; production code should never pass it.
    """

    def __init__(
        self,
        config: HttpCollectorConfig,
        *,
        retry_policy: RetryPolicy | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._config = config
        self._retry_policy = retry_policy or RetryPolicy(max_retries=config.max_retries)
        self._rate_limiter = RateLimiter(config.request_delay_seconds)
        self._transport = transport
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> Self:
        self._client = httpx.AsyncClient(
            base_url=self._config.base_url,
            timeout=self._config.timeout_seconds,
            headers={"User-Agent": self._config.user_agent},
            transport=self._transport,
        )
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_json(
        self, url: str, *, params: dict[str, Any] | None = None
    ) -> Any:  # noqa: ANN401
        """GET ``url`` and parse the response body as JSON.

        The return type is genuinely dynamic -- JSON content can be an
        object, array, or scalar -- so ``Any`` here reflects reality
        rather than a lazily-typed API.
        """
        response = await self._get(url, params=params)
        try:
            return response.json()
        except json.JSONDecodeError as exc:
            raise CollectorError(f"Response from {url!r} was not valid JSON: {exc}") from exc

    async def get_text(self, url: str, *, params: dict[str, Any] | None = None) -> str:
        """GET ``url`` and return the raw response body text."""
        response = await self._get(url, params=params)
        return response.text

    async def _get(self, url: str, *, params: dict[str, Any] | None) -> httpx.Response:
        if self._client is None:
            raise RuntimeError("HttpClient must be used as an 'async with' context manager.")
        client = self._client

        async def _do_request() -> httpx.Response:
            await self._rate_limiter.wait()
            logger.debug("HTTP GET {} (base_url={})", url, self._config.base_url)
            response = await client.get(url, params=params)
            if response.status_code >= 500:
                raise CollectorUnavailableError(
                    f"{url!r} returned server error {response.status_code}."
                )
            if response.status_code >= 400:
                raise CollectorError(f"{url!r} returned client error {response.status_code}.")
            return response

        try:
            return await retry_async(
                _do_request,
                policy=self._retry_policy,
                retry_on=_RETRYABLE_EXCEPTIONS,
                on_retry=lambda attempt, exc: logger.warning(
                    "Retrying GET {} (attempt {}) after error: {}", url, attempt, exc
                ),
            )
        except RetryExhaustedError as exc:
            raise CollectorUnavailableError(
                f"Exhausted all retry attempts for GET {url!r}: {exc.message}"
            ) from exc
