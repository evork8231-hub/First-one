"""Shared scaffolding for concrete WeatherCollector implementations.

Mirrors ``app.collectors.base.BaseCollector`` exactly, for the same
reasons documented in
``app.application.interfaces.weather_collector.WeatherCollectorInterface``:
weather collectors are a distinct interface, not a variant of the signal
collector interface.
"""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Awaitable, Callable

from loguru import logger

from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.core.exceptions import CollectorUnavailableError, RetryExhaustedError
from app.core.retry import RetryPolicy, retry_async
from app.domain.weather import WeatherEvent


class BaseWeatherCollector(WeatherCollectorInterface):
    """Common bookkeeping for weather collectors: identity, retry, and logging."""

    def __init__(
        self,
        *,
        name: str,
        source: str,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not name:
            raise ValueError("Collector name must not be empty.")
        if not source:
            raise ValueError("Collector source must not be empty.")
        self._name = name
        self._source = source
        self._retry_policy = retry_policy or RetryPolicy()

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> str:
        return self._source

    async def _with_retry[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        """Run ``operation`` under this collector's configured retry policy.

        Raises:
            CollectorUnavailableError: If every retry attempt fails --
                translated from ``RetryExhaustedError`` so ``collect()``
                always fails with a ``CollectorError`` subclass.
        """
        try:
            return await retry_async(
                operation,
                policy=self._retry_policy,
                on_retry=lambda attempt, exc: logger.warning(
                    "Collector {} retrying (attempt {}) after error: {}", self._name, attempt, exc
                ),
            )
        except RetryExhaustedError as exc:
            raise CollectorUnavailableError(
                f"Collector {self._name!r} exhausted all retry attempts: {exc.message}"
            ) from exc

    @abstractmethod
    async def collect(self) -> list[WeatherEvent]:
        """Read the public source and return the WeatherEvents it currently reports."""
        raise NotImplementedError
