"""Enumerations shared across the domain model.

Adding a new member to :class:`SignalType` or :class:`ServiceCategory` is
the primary extension point for supporting a new kind of public signal;
per the "future signal types should require minimal code changes"
requirement, no other domain code branches on a hardcoded list of types.
"""

from __future__ import annotations

from enum import StrEnum


class Country(StrEnum):
    """ISO 3166-1 alpha-2 country codes this platform is permitted to operate in.

    The foundation targets Estonia exclusively. Extending coverage to another
    country is a deliberate product decision, not a silent side effect, so
    new members must be added explicitly here and to
    ``app.core.constants.SUPPORTED_COUNTRY_CODES``.
    """

    ESTONIA = "EE"


class ServiceCategory(StrEnum):
    """The four home-improvement service categories this platform tracks."""

    ROOFING = "roofing"
    KITCHEN_REMODELING = "kitchen_remodeling"
    BATHROOM_REMODELING = "bathroom_remodeling"
    SOLAR_INSTALLATION = "solar_installation"


class SignalType(StrEnum):
    """The kinds of publicly available facts the platform records as Signals.

    Signals represent facts. They are never leads. See
    ``app.domain.signal.Signal`` and ``app.domain.lead.Lead`` for the
    distinction enforced throughout the codebase.
    """

    BUILDING_RECORD = "building_record"
    REAL_ESTATE_LISTING = "real_estate_listing"
    CONSTRUCTION_PERMIT = "construction_permit"
    WEATHER_EVENT = "weather_event"
    ENERGY_CERTIFICATE = "energy_certificate"
    ROOF_MENTION = "roof_mention"
    KITCHEN_MENTION = "kitchen_mention"
    BATHROOM_MENTION = "bathroom_mention"
    RENOVATION_MENTION = "renovation_mention"
    SOLAR_OPPORTUNITY = "solar_opportunity"


class WeatherEventType(StrEnum):
    """Categories of severe weather that can be recorded as WeatherEvent facts.

    Per the mission rules, weather events never directly become leads; they
    only ever influence the confidence of other signals during correlation.
    """

    HAILSTORM = "hailstorm"
    HIGH_WIND = "high_wind"
    HEAVY_SNOW = "heavy_snow"
    HEAVY_RAIN = "heavy_rain"
    FLOOD = "flood"
    ICE_STORM = "ice_storm"
    LIGHTNING = "lightning"


class VerificationStatus(StrEnum):
    """Lifecycle state shared by both Signal and Lead verification."""

    UNVERIFIED = "unverified"
    VERIFIED = "verified"
    REJECTED = "rejected"


class LeadPriority(StrEnum):
    """Operator-facing priority assigned to a generated Lead."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(StrEnum):
    """Categories of events recorded to the audit log for traceability."""

    COLLECTOR_RUN_STARTED = "collector_run_started"
    COLLECTOR_RUN_COMPLETED = "collector_run_completed"
    COLLECTOR_RUN_FAILED = "collector_run_failed"
    SIGNAL_INGESTED = "signal_ingested"
    SIGNAL_VERIFIED = "signal_verified"
    SIGNAL_REJECTED = "signal_rejected"
    SIGNAL_DUPLICATE_DETECTED = "signal_duplicate_detected"
    CORRELATION_RUN = "correlation_run"
    LEAD_GENERATED = "lead_generated"
    LEAD_VERIFIED = "lead_verified"
    LEAD_REJECTED = "lead_rejected"
    CONFIGURATION_CHANGED = "configuration_changed"
    DATA_PURGED = "data_purged"
    SCHEMA_DRIFT_DETECTED = "schema_drift_detected"
    ERROR = "error"
