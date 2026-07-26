"""Repository interfaces.

Every persistence operation the application layer needs is declared here
as an abstract method. Concrete implementations live under
``app.repositories`` (e.g. SQLite-backed or in-memory, for tests) and are
never imported by domain or application code -- only depended upon
through these interfaces (the Dependency Inversion Principle).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from datetime import datetime
from uuid import UUID

from app.domain.audit import AuditLogEntry
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import AuditEventType, ServiceCategory, VerificationStatus
from app.domain.lead import Lead
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent


class SignalRepository(ABC):
    """Persistence boundary for Signal entities."""

    @abstractmethod
    def add(self, signal: Signal) -> Signal:
        """Persist a new signal and return the stored copy."""

    @abstractmethod
    def get_by_id(self, signal_id: UUID) -> Signal | None:
        """Return the signal with ``signal_id``, or ``None`` if it does not exist."""

    @abstractmethod
    def list_by_ids(self, signal_ids: Sequence[UUID]) -> list[Signal]:
        """Return the signals matching ``signal_ids``, in no guaranteed order."""

    @abstractmethod
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
        """Return signals matching the given filters, newest first."""

    @abstractmethod
    def list_unverified(self, *, limit: int = 100, offset: int = 0) -> list[Signal]:
        """Return signals still awaiting verification."""

    @abstractmethod
    def update_verification(self, signal_id: UUID, status: VerificationStatus) -> Signal:
        """Advance a signal's verification status and return the updated signal."""


class LeadRepository(ABC):
    """Persistence boundary for Lead entities."""

    @abstractmethod
    def add(self, lead: Lead) -> Lead:
        """Persist a newly generated lead and return the stored copy."""

    @abstractmethod
    def get_by_id(self, lead_id: UUID) -> Lead | None:
        """Return the lead with ``lead_id``, or ``None`` if it does not exist."""

    @abstractmethod
    def list_all(
        self,
        *,
        lead_type: ServiceCategory | None = None,
        verification_status: VerificationStatus | None = None,
        county: str | None = None,
        municipality: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Lead]:
        """Return leads matching the given filters, newest first."""

    @abstractmethod
    def update_verification_status(self, lead_id: UUID, status: VerificationStatus) -> Lead:
        """Advance a lead's verification status and return the updated lead."""


class WeatherEventRepository(ABC):
    """Persistence boundary for WeatherEvent entities."""

    @abstractmethod
    def add(self, event: WeatherEvent) -> WeatherEvent:
        """Persist a new weather event and return the stored copy."""

    @abstractmethod
    def get_by_id(self, event_id: UUID) -> WeatherEvent | None:
        """Return the weather event with ``event_id``, or ``None`` if absent."""

    @abstractmethod
    def list_by_region_and_time(
        self,
        *,
        county: str,
        municipality: str | None = None,
        since: datetime,
        until: datetime,
    ) -> list[WeatherEvent]:
        """Return weather events affecting the given region within a time window."""


class AuditLogRepository(ABC):
    """Persistence boundary for AuditLogEntry records."""

    @abstractmethod
    def add(self, entry: AuditLogEntry) -> AuditLogEntry:
        """Persist a new audit log entry and return the stored copy."""

    @abstractmethod
    def list_all(
        self,
        *,
        event_type: AuditEventType | None = None,
        entity_id: UUID | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[AuditLogEntry]:
        """Return audit log entries matching the given filters, newest first."""


class ConfigurationRepository(ABC):
    """Persistence boundary for runtime-adjustable ConfigurationEntry records."""

    @abstractmethod
    def get(self, key: str) -> ConfigurationEntry | None:
        """Return the configuration entry for ``key``, or ``None`` if unset."""

    @abstractmethod
    def set(self, entry: ConfigurationEntry) -> ConfigurationEntry:
        """Create or replace the configuration entry for ``entry.key``."""

    @abstractmethod
    def list_all(self) -> list[ConfigurationEntry]:
        """Return every stored configuration entry."""
