"""In-memory SignalRepository implementation, used primarily in tests."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.interfaces.repositories import SignalRepository
from app.core.exceptions import EntityNotFoundError
from app.domain.enums import ServiceCategory, VerificationStatus
from app.domain.signal import Signal


class InMemorySignalRepository(SignalRepository):
    """Stores Signals in a process-local dict. Not safe across processes."""

    def __init__(self) -> None:
        self._signals: dict[UUID, Signal] = {}

    def add(self, signal: Signal) -> Signal:
        self._signals[signal.id] = signal
        return signal

    def get_by_id(self, signal_id: UUID) -> Signal | None:
        return self._signals.get(signal_id)

    def list_by_ids(self, signal_ids: Sequence[UUID]) -> list[Signal]:
        return [self._signals[sid] for sid in signal_ids if sid in self._signals]

    def list_all(
        self,
        *,
        service_category: ServiceCategory | None = None,
        verified: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Signal]:
        results = list(self._signals.values())
        if service_category is not None:
            results = [s for s in results if s.service_category == service_category]
        if verified is not None:
            results = [s for s in results if s.verified == verified]
        if county is not None:
            results = [s for s in results if s.county == county]
        if municipality is not None:
            results = [s for s in results if s.municipality == municipality]
        results.sort(key=lambda s: s.timestamp, reverse=True)
        return results[offset : offset + limit]

    def list_unverified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        return self.list_all(verified=VerificationStatus.UNVERIFIED, limit=limit, offset=offset)

    def update_verification(self, signal_id: UUID, status: VerificationStatus) -> Signal:
        existing = self._signals.get(signal_id)
        if existing is None:
            raise EntityNotFoundError(f"No signal found with id {signal_id}.")
        updated = existing.with_verification(status)
        self._signals[signal_id] = updated
        return updated
