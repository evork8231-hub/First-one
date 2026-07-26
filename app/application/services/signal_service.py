"""SignalService: runs collectors and persists the Signals they return."""

from __future__ import annotations

from loguru import logger

from app.application.interfaces.collector import CollectorInterface
from app.application.interfaces.repositories import AuditLogRepository, SignalRepository
from app.core.exceptions import CollectorError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType, VerificationStatus
from app.domain.signal import Signal


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
        try:
            signals = await collector.collect()
        except CollectorError as exc:
            logger.opt(exception=exc).error("Collector {} failed", collector.name)
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.COLLECTOR_RUN_FAILED,
                    entity_type="Collector",
                    message=f"Collector {collector.name!r} failed: {exc.message}",
                    context={"collector": collector.name, **exc.details},
                )
            )
            raise

        stored: list[Signal] = []
        for signal in signals:
            stored_signal = self._signal_repository.add(signal)
            stored.append(stored_signal)
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
                context={"collector": collector.name, "signal_count": len(stored)},
            )
        )
        return stored

    def list_unverified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        """Return signals awaiting verification."""
        return self._signal_repository.list_unverified(limit=limit, offset=offset)

    def list_verified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        """Return signals that have passed verification."""
        return self._signal_repository.list_all(
            verified=VerificationStatus.VERIFIED, limit=limit, offset=offset
        )
