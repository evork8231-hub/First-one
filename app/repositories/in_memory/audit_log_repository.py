"""In-memory AuditLogRepository implementation, used primarily in tests."""

from __future__ import annotations

from uuid import UUID

from app.application.interfaces.repositories import AuditLogRepository
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType


class InMemoryAuditLogRepository(AuditLogRepository):
    """Stores AuditLogEntry records in a process-local list. Not safe across processes."""

    def __init__(self) -> None:
        self._entries: list[AuditLogEntry] = []

    def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        self._entries.append(entry)
        return entry

    def list_all(
        self,
        *,
        event_type: AuditEventType | None = None,
        entity_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        results = list(self._entries)
        if event_type is not None:
            results = [entry for entry in results if entry.event_type == event_type]
        if entity_id is not None:
            results = [entry for entry in results if entry.entity_id == entity_id]
        # Mirror SQLiteAuditLogRepository's "created_at DESC, rowid DESC"
        # ordering: pair each entry with its append-order index so two
        # entries sharing a timestamp still resolve deterministically to
        # "most recently added first," matching the SQLite-backed behavior
        # instead of relying on Python's stable-sort tiebreak (which would
        # keep ties in their original, i.e. oldest-first, order here).
        indexed = list(enumerate(results))
        indexed.sort(key=lambda pair: (pair[1].created_at, pair[0]), reverse=True)
        ordered = [entry for _, entry in indexed]
        return ordered[offset : offset + limit]
