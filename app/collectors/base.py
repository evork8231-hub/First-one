"""Shared scaffolding for concrete Collector implementations."""

from __future__ import annotations

from abc import abstractmethod
from collections.abc import Awaitable, Callable

from loguru import logger

from app.application.interfaces.collector import CollectorInterface
from app.core.retry import RetryPolicy, retry_async
from app.domain.enums import SignalType
from app.domain.signal import Signal


class BaseCollector(CollectorInterface):
    """Common bookkeeping for collectors: identity, retry, and logging.

    Concrete subclasses implement :meth:`collect` and may use
    :meth:`_with_retry` to wrap individual transient operations (e.g. a
    single HTTP request) in the configured retry policy.
    """

    def __init__(
        self,
        *,
        name: str,
        source: str,
        supported_signal_types: frozenset[SignalType],
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        if not name:
            raise ValueError("Collector name must not be empty.")
        if not source:
            raise ValueError("Collector source must not be empty.")
        if not supported_signal_types:
            raise ValueError("Collector must declare at least one supported signal type.")
        self._name = name
        self._source = source
        self._supported_signal_types = supported_signal_types
        self._retry_policy = retry_policy or RetryPolicy()

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> str:
        return self._source

    @property
    def supported_signal_types(self) -> frozenset[SignalType]:
        return self._supported_signal_types

    async def _with_retry[T](self, operation: Callable[[], Awaitable[T]]) -> T:
        """Run ``operation`` under this collector's configured retry policy."""
        return await retry_async(
            operation,
            policy=self._retry_policy,
            on_retry=lambda attempt, exc: logger.warning(
                "Collector {} retrying (attempt {}) after error: {}", self._name, attempt, exc
            ),
        )

    @abstractmethod
    async def collect(self) -> list[Signal]:
        """Read the public source and return the Signals it currently reports."""
        raise NotImplementedError
