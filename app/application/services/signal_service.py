"""SignalService: runs collectors and persists the Signals they return."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Sequence
from dataclasses import dataclass, field
from uuid import uuid4

from loguru import logger

from app.application.interfaces.collector import CollectorInterface
from app.application.interfaces.repositories import AuditLogRepository, SignalRepository
from app.core.exceptions import CollectorError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType, VerificationStatus
from app.domain.signal import Signal


def _retry_attempts(collector: CollectorInterface) -> int:
    """Read a collector's most-recent-run retry count, defaulting to 0 if untracked.

    Not every hypothetical ``CollectorInterface`` implementation tracks
    this (it lives on the concrete ``BaseCollector``, not the abstract
    interface), so 0 here is an honest "no known retries," never a guess.
    """
    return int(getattr(collector, "retry_count", 0))


@dataclass(frozen=True)
class CollectorRunResult:
    """The outcome of running a single collector as part of a batch."""

    collector_name: str
    signals: list[Signal] = field(default_factory=list)
    error: str | None = None

    @property
    def succeeded(self) -> bool:
        return self.error is None


class SignalService:
    """Orchestrates collector execution and Signal persistence.

    This service knows nothing about verification, correlation, or leads --
    its sole responsibility is turning a collector's output into
    persisted, UNVERIFIED Signal records with a full audit trail.
    """

    def __init__(
        self, signal_repository: SignalRepository, audit_log_repository: AuditLogRepository
    ) -> None:
        self._signal_repository = signal_repository
        self._audit_log_repository = audit_log_repository

    async def ingest_from_collector(self, collector: CollectorInterface) -> list[Signal]:
        """Run ``collector`` and persist every Signal it returns.

        Raises:
            CollectorError: If the collector fails; the failure is audit
                logged before being re-raised so callers can decide how to
                react (e.g. skip this source and continue with others).
        """
        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=AuditEventType.COLLECTOR_RUN_STARTED,
                entity_type="Collector",
                message=f"Starting collector {collector.name!r} (source={collector.source!r}).",
                context={"collector": collector.name, "source": collector.source},
            )
        )
        start = time.monotonic()
        try:
            signals = await collector.collect()
        except CollectorError as exc:
            duration_seconds = round(time.monotonic() - start, 3)
            logger.opt(exception=exc).error("Collector {} failed", collector.name)
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.COLLECTOR_RUN_FAILED,
                    entity_type="Collector",
                    message=f"Collector {collector.name!r} failed: {exc.message}",
                    context={
                        "collector": collector.name,
                        "duration_seconds": duration_seconds,
                        "retry_attempts": _retry_attempts(collector),
                        **exc.details,
                    },
                )
            )
            raise

        stored = self._signal_repository.add_many(signals)
        duration_seconds = round(time.monotonic() - start, 3)
        execution_id = uuid4()
        for stored_signal in stored:
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.SIGNAL_INGESTED,
                    entity_type="Signal",
                    entity_id=stored_signal.id,
                    message=(
                        f"Ingested {stored_signal.signal_type.value} signal from "
                        f"{collector.source!r}."
                    ),
                    context={"collector": collector.name},
                )
            )

        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
                entity_type="Collector",
                message=f"Collector {collector.name!r} produced {len(stored)} signal(s).",
                context={
                    "collector": collector.name,
                    "signal_count": len(stored),
                    "duration_seconds": duration_seconds,
                    "retry_attempts": _retry_attempts(collector),
                    "execution_id": str(execution_id),
                    "inserted_signal_ids": [str(signal.id) for signal in stored],
                },
            )
        )
        return stored

    async def ingest_from_collectors(
        self, collectors: Sequence[CollectorInterface], *, max_concurrency: int = 3
    ) -> list[CollectorRunResult]:
        """Run every collector in ``collectors`` concurrently, up to ``max_concurrency`` at once.

        Unlike :meth:`ingest_from_collector`, a single collector's failure
        never aborts the batch -- each result reports its own success or
        error so a caller (e.g. ``sigint collect --all``) can act on the
        ones that failed without losing signals already ingested by the
        ones that succeeded.
        """
        semaphore = asyncio.Semaphore(max(1, max_concurrency))

        async def _run(collector: CollectorInterface) -> CollectorRunResult:
            async with semaphore:
                try:
                    signals = await self.ingest_from_collector(collector)
                    return CollectorRunResult(collector_name=collector.name, signals=signals)
                except CollectorError as exc:
                    return CollectorRunResult(collector_name=collector.name, error=exc.message)

        results = await asyncio.gather(*(_run(collector) for collector in collectors))
        logger.info(
            "Ran {} collector(s) at concurrency {}: {} succeeded, {} failed.",
            len(results),
            max_concurrency,
            sum(1 for r in results if r.succeeded),
            sum(1 for r in results if not r.succeeded),
        )
        return list(results)

    def list_unverified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        """Return signals awaiting verification."""
        return self._signal_repository.list_unverified(limit=limit, offset=offset)

    def list_verified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        """Return signals that have passed verification."""
        return self._signal_repository.list_all(
            verified=VerificationStatus.VERIFIED, limit=limit, offset=offset
        )
