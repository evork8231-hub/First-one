"""Typed application settings.

``AppSettings`` is the single source of truth for every configurable
value in the platform. Structured defaults are supplied by
``config/default.yaml`` (see ``app.config.loader.load_settings``); any
field can be overridden by an environment variable prefixed
``SIGINT_`` (nested fields use a double underscore, e.g.
``SIGINT_DATABASE__URL``). Per the security requirements, secrets must
only ever be supplied via environment variables -- never committed to
``config/default.yaml``.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import PRIMARY_COUNTRY_CODE
from app.core.retry import RetryPolicy


class DatabaseConfig(BaseModel):
    """Database connection settings."""

    url: str = Field(default="sqlite:///./data/signals.db")
    echo: bool = Field(default=False, description="Log every SQL statement (development only).")
    busy_timeout_seconds: float = Field(
        default=5.0,
        ge=0,
        description=(
            "SQLite only: how long a write waits on a lock held by another connection "
            "before raising 'database is locked', instead of failing immediately."
        ),
    )


class LoggingConfig(BaseModel):
    """Structured logging settings for the Loguru sink configuration."""

    level: Literal["TRACE", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    json_logs: bool = Field(
        default=False, description="Emit JSON-formatted logs instead of human-readable text."
    )
    log_file: str | None = Field(
        default=None, description="Path to a log file; None logs to stderr only."
    )
    rotation: str = Field(default="10 MB", description="Loguru rotation policy for log_file.")
    retention: str = Field(default="30 days", description="Loguru retention policy for log_file.")


class RetryConfig(BaseModel):
    """Default retry policy applied to collectors and other transient operations."""

    max_retries: int = Field(default=3, ge=0)
    initial_backoff_seconds: float = Field(default=0.5, gt=0)
    backoff_multiplier: float = Field(default=2.0, ge=1.0)
    max_backoff_seconds: float = Field(default=30.0, gt=0)
    jitter_seconds: float = Field(default=0.1, ge=0)
    timeout_seconds: float | None = Field(default=60.0, gt=0)

    def to_policy(self) -> RetryPolicy:
        """Build the runtime ``RetryPolicy`` value object from this configuration."""
        return RetryPolicy(
            max_retries=self.max_retries,
            initial_backoff_seconds=self.initial_backoff_seconds,
            backoff_multiplier=self.backoff_multiplier,
            max_backoff_seconds=self.max_backoff_seconds,
            jitter_seconds=self.jitter_seconds,
            timeout_seconds=self.timeout_seconds,
        )


class CoordinateBounds(BaseModel):
    """A geographic bounding box used to reject coordinates outside Estonia.

    Defaults are Estonia's real, publicly known extent (approximately
    57.5-59.7 N, 21.5-28.2 E, including the islands) -- a geographic fact,
    not a business value, but still exposed here so a deployment can
    adjust it (e.g. to tolerate GPS noise near the border) without a code
    change.
    """

    min_latitude: float = Field(default=57.5, ge=-90.0, le=90.0)
    max_latitude: float = Field(default=59.7, ge=-90.0, le=90.0)
    min_longitude: float = Field(default=21.5, ge=-180.0, le=180.0)
    max_longitude: float = Field(default=28.2, ge=-180.0, le=180.0)

    @model_validator(mode="after")
    def _bounds_must_be_ordered(self) -> CoordinateBounds:
        if self.max_latitude <= self.min_latitude:
            raise ValueError("max_latitude must be greater than min_latitude.")
        if self.max_longitude <= self.min_longitude:
            raise ValueError("max_longitude must be greater than min_longitude.")
        return self

    def contains(self, *, latitude: float, longitude: float) -> bool:
        """Return whether ``(latitude, longitude)`` falls inside this bounding box."""
        return (
            self.min_latitude <= latitude <= self.max_latitude
            and self.min_longitude <= longitude <= self.max_longitude
        )


class DuplicateDetectionConfig(BaseModel):
    """Configurable thresholds for Signal duplicate detection.

    No similarity value is hardcoded in code -- every threshold used by
    ``app.verification.duplicate_detector.DuplicateDetector`` is sourced
    from this model.
    """

    enabled: bool = Field(default=True)
    comparison_scope_limit: int = Field(
        default=200,
        ge=1,
        description=(
            "Maximum candidate signals fetched (same county/municipality) " "to compare against."
        ),
    )
    coordinate_duplicate_radius_meters: float = Field(
        default=25.0,
        ge=0,
        description=(
            "Two signals with coordinates within this distance are treated " "as the same property."
        ),
    )
    fuzzy_duplicate_threshold: float = Field(
        default=95.0,
        ge=0.0,
        le=100.0,
        description="RapidFuzz similarity (0-100) at or above which two signals are a DUPLICATE.",
    )
    fuzzy_possible_duplicate_threshold: float = Field(
        default=80.0,
        ge=0.0,
        le=100.0,
        description=(
            "RapidFuzz similarity (0-100) at or above which two signals are "
            "a POSSIBLE_DUPLICATE."
        ),
    )
    possible_duplicate_policy: Literal["flag", "reject"] = Field(
        default="flag",
        description=(
            "'flag' keeps a POSSIBLE_DUPLICATE signal verifiable (status recorded in the audit "
            "log); 'reject' treats it the same as an exact DUPLICATE."
        ),
    )

    @model_validator(mode="after")
    def _possible_threshold_not_above_duplicate_threshold(self) -> DuplicateDetectionConfig:
        if self.fuzzy_possible_duplicate_threshold > self.fuzzy_duplicate_threshold:
            raise ValueError(
                "fuzzy_possible_duplicate_threshold cannot exceed fuzzy_duplicate_threshold."
            )
        return self


class VerificationConfig(BaseModel):
    """Thresholds consulted by the structural verifiers."""

    min_signal_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    min_lead_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    require_coordinates: bool = Field(
        default=False,
        description="Reject a signal that has no coordinates at all. Off by default -- many "
        "legitimate sources (e.g. listing sites) never publish precise coordinates.",
    )
    coordinate_bounds: CoordinateBounds = Field(default_factory=CoordinateBounds)
    postal_code_pattern: str = Field(
        default=r"^\d{5}$", description="Regex an Estonian postal code must match, if present."
    )
    duplicate_detection: DuplicateDetectionConfig = Field(default_factory=DuplicateDetectionConfig)


class HttpCollectorConfig(BaseModel):
    """Shared operational settings for an httpx-based collector."""

    base_url: str
    timeout_seconds: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="EstoniaSignalIntelligencePlatform/0.1 (public-data collector)")
    request_delay_seconds: float = Field(
        default=1.0, ge=0, description="Minimum delay enforced between outbound requests."
    )
    max_retries: int = Field(default=3, ge=0)
    max_records_per_run: int = Field(
        default=500, ge=1, description="Safety cap on records processed in a single collect() call."
    )
    cache_enabled: bool = Field(
        default=False,
        description=(
            "Cache GET response bodies in-process for cache_ttl_seconds, keyed by URL and "
            "query params. Off by default -- only safe to enable where the source's data "
            "changes slower than a typical collection run cadence."
        ),
    )
    cache_ttl_seconds: float = Field(
        default=300.0, gt=0, description="How long a cached response stays valid, if caching is on."
    )


class BrowserCollectorConfig(BaseModel):
    """Shared operational settings for a Playwright-based listing collector.

    ``listing_link_selector`` and ``search_paths`` have no safe hardcoded
    default -- they are site-specific CSS selectors and URL paths that must
    be confirmed against the live site's markup before the collector is
    enabled. Leaving them empty causes the collector to raise
    ``CollectorError`` rather than guess a selector.
    """

    base_url: str
    timeout_seconds: float = Field(default=30.0, gt=0)
    user_agent: str = Field(default="EstoniaSignalIntelligencePlatform/0.1 (public-data collector)")
    request_delay_seconds: float = Field(default=2.0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    headless: bool = Field(default=True)
    max_listings_per_run: int = Field(default=50, ge=1)
    default_confidence: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description=(
            "Confidence assigned to text-mined phrase signals "
            "(lower than an authoritative registry)."
        ),
    )
    search_paths: list[str] = Field(default_factory=list)
    listing_link_selector: str | None = Field(default=None)


class EhitisregisterConfig(HttpCollectorConfig):
    """Settings for the Ehitisregister (Estonian Building Registry) collector.

    ``field_map`` lists, per canonical field, the candidate source JSON key
    names to try in order -- the exact schema of the discovered dataset
    resource could not be confirmed against a live source in this
    environment, so the mapping is fully operator-adjustable rather than
    hardcoded to a single assumed key name. See
    ``docs/CONFIGURATION.md#ehitisregister``.
    """

    base_url: str = "https://andmed.eesti.ee"
    dataset_slug: str = Field(default="ehitisregister")
    default_confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    field_map: dict[str, list[str]] = Field(
        default_factory=lambda: {
            "building_type": ["ehitise_kasutamise_otstarve", "kasutusotstarve", "building_type"],
            "construction_year": ["ehitusaasta", "valmimisaasta", "construction_year"],
            "county": ["maakond", "county"],
            "municipality": ["omavalitsus", "vald", "municipality"],
            "settlement": ["asustusyksus", "asula", "settlement"],
            "latitude": ["lat", "latitude", "y_koordinaat"],
            "longitude": ["lon", "longitude", "x_koordinaat"],
            "registry_code": ["ehitisregistri_kood", "ehr_kood", "registry_code"],
            "energy_class": ["energiaklass", "energy_class"],
            "energy_certificate_valid_until": ["energiamargise_kehtivusaeg", "valid_until"],
        }
    )


class EhitisregisterXTeeConfig(BaseModel):
    """Settings for the disabled X-tee adapter to Ehitisregister.

    X-tee (Estonia's inter-organizational secure data-exchange layer) is a
    confirmed, real, government-documented access path to Ehitisregister
    (see ``docs/COLLECTORS.md#ehitisregister``) -- but it requires the
    calling party to be a registered X-tee member operating a security
    server with member certificates, which this platform cannot obtain or
    provision on an operator's behalf. Every field below has no default on
    purpose: X-tee membership, the security server, and the target
    service's exact identifiers are things only an operator with a real
    X-tee agreement can supply. Setting ``enabled: true`` and filling in
    every field below is still not sufficient to make this collector
    functional -- see ``EhitisregisterXTeeCollector`` for why.
    """

    enabled: bool = Field(
        default=False,
        description=(
            "Must be explicitly set to true, in addition to listing "
            "'ehitisregister_xtee' in collectors.enabled, before this adapter "
            "will even attempt to validate its configuration."
        ),
    )
    security_server_url: str | None = Field(
        default=None, description="This organization's X-tee security server URL."
    )
    xroad_instance: str | None = Field(
        default=None, description="X-Road instance identifier (e.g. an environment name)."
    )
    member_class: str | None = Field(
        default=None, description="This organization's X-Road member class."
    )
    member_code: str | None = Field(
        default=None, description="This organization's X-Road member code."
    )
    subsystem_code: str | None = Field(
        default=None, description="This organization's X-Road subsystem code, if applicable."
    )
    client_cert_path: str | None = Field(
        default=None,
        description="Path to the client TLS certificate issued for the security server.",
    )
    client_key_path: str | None = Field(
        default=None, description="Path to the private key matching client_cert_path."
    )
    service_member_class: str | None = Field(
        default=None, description="Ehitisregister's X-Road member class, as the service provider."
    )
    service_member_code: str | None = Field(
        default=None, description="Ehitisregister's X-Road member code, as the service provider."
    )
    service_subsystem_code: str | None = Field(
        default=None, description="Ehitisregister's X-Road subsystem code, if applicable."
    )
    service_code: str | None = Field(
        default=None,
        description=(
            "The exact X-Road service (operation) name to invoke -- not verified against a "
            "live source; must come from the operator's own confirmed WSDL/service catalog."
        ),
    )
    service_version: str | None = Field(default=None, description="The X-Road service version.")


class PlaceAdministrativeArea(BaseModel):
    """A forecast place name's known Estonian county and municipality."""

    county: str
    municipality: str


class IlmateenistusConfig(BaseModel):
    """Settings for the Ilmateenistus (Estonian Weather Service) collector.

    ``xml_url`` has no default -- the exact feed URL could not be confirmed
    against a live source in this environment. The collector raises
    ``CollectorError`` until an operator sets it explicitly, rather than
    guessing a path under ``base_url``.
    """

    base_url: str = "https://www.ilmateenistus.ee"
    xml_url: str | None = Field(default=None)
    timeout_seconds: float = Field(default=30.0, gt=0)
    request_delay_seconds: float = Field(default=1.0, ge=0)
    max_retries: int = Field(default=3, ge=0)
    cache_enabled: bool = Field(default=False, description="See HttpCollectorConfig.cache_enabled.")
    cache_ttl_seconds: float = Field(default=300.0, gt=0)
    default_confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    wind_severity_reference_ms: float = Field(
        default=25.0,
        gt=0,
        description=(
            "Wind speed, in m/s, treated as maximum severity (1.0) when scaling "
            "gust-based severity for wind-related events. Approximates Beaufort "
            "force 10 (storm); not itself a value reported by the feed."
        ),
    )
    categorical_event_severity: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description=(
            "Severity assigned to matched phenomena with no measurable magnitude in the feed."
        ),
    )
    place_administrative_areas: dict[str, PlaceAdministrativeArea] = Field(
        default_factory=lambda: {
            "Tallinn": PlaceAdministrativeArea(county="Harju", municipality="Tallinn"),
            "Tartu": PlaceAdministrativeArea(county="Tartu", municipality="Tartu"),
            "Pärnu": PlaceAdministrativeArea(county="Pärnu", municipality="Pärnu"),
            "Narva": PlaceAdministrativeArea(county="Ida-Viru", municipality="Narva"),
            "Kuressaare": PlaceAdministrativeArea(county="Saare", municipality="Saaremaa"),
            "Viljandi": PlaceAdministrativeArea(county="Viljandi", municipality="Viljandi"),
            "Rakvere": PlaceAdministrativeArea(county="Lääne-Viru", municipality="Rakvere"),
            "Kuressaare linn": PlaceAdministrativeArea(county="Saare", municipality="Saaremaa"),
        },
        description=(
            "Forecast place names not present in this table are skipped -- the "
            "feed reports place names, not administrative divisions, and this "
            "platform never guesses a county/municipality."
        ),
    )


class CollectorsConfig(BaseModel):
    """Which registered collectors are permitted to run, and their settings."""

    enabled: list[str] = Field(default_factory=list)
    ehitisregister: EhitisregisterConfig = Field(default_factory=EhitisregisterConfig)
    ehitisregister_xtee: EhitisregisterXTeeConfig = Field(default_factory=EhitisregisterXTeeConfig)
    ilmateenistus: IlmateenistusConfig = Field(default_factory=IlmateenistusConfig)
    kv_ee: BrowserCollectorConfig = Field(
        default_factory=lambda: BrowserCollectorConfig(base_url="https://www.kv.ee")
    )
    kinnisvara24: BrowserCollectorConfig = Field(
        default_factory=lambda: BrowserCollectorConfig(base_url="https://www.kinnisvara24.ee")
    )
    city24: BrowserCollectorConfig = Field(
        default_factory=lambda: BrowserCollectorConfig(base_url="https://www.city24.ee")
    )

    @property
    def enabled_set(self) -> frozenset[str]:
        return frozenset(self.enabled)


class ConcurrencyConfig(BaseModel):
    """Bounds on how much work runs in parallel, all operator-adjustable."""

    max_concurrent_collectors: int = Field(
        default=3,
        ge=1,
        description=(
            "Maximum number of collectors 'sigint collect --all'/'sigint pipeline' run at once."
        ),
    )


class RulesConfig(BaseModel):
    """Where data-driven correlation rules are loaded from."""

    directory: str = Field(default="config/rules")


class ScoringConfig(BaseModel):
    """Configurable weights for the independent Signal and Lead scoring systems.

    ``priority_thresholds`` maps a LeadPriority value to the minimum
    ``intent_score`` required to reach that priority; the lead generator
    picks the highest priority whose threshold the score meets or exceeds.
    """

    confidence_aggregation: Literal["mean", "min"] = "mean"
    weather_confidence_boost_factor: float = Field(
        default=0.2,
        ge=0.0,
        le=1.0,
        description=(
            "Multiplicative boost applied to confidence/intent scores when matched "
            "weather signals are present. Weather never counts as supporting "
            "evidence on its own -- it only scales an already-evidenced score."
        ),
    )
    priority_thresholds: dict[str, float] = Field(
        default_factory=lambda: {
            "critical": 0.85,
            "high": 0.65,
            "medium": 0.4,
            "low": 0.0,
        }
    )

    @field_validator("priority_thresholds")
    @classmethod
    def _thresholds_must_be_in_unit_interval(cls, value: dict[str, float]) -> dict[str, float]:
        for priority, threshold in value.items():
            if not 0.0 <= threshold <= 1.0:
                raise ValueError(f"priority threshold for {priority!r} must be within [0.0, 1.0].")
        return value


class ExcelExportConfig(BaseModel):
    """Formatting options for the ``.xlsx`` export, all operator-adjustable."""

    header_fill_color: str = Field(
        default="1F4E78", description="Header row background, RRGGBB hex."
    )
    header_font_color: str = Field(
        default="FFFFFF", description="Header row text color, RRGGBB hex."
    )
    freeze_header_row: bool = Field(default=True)
    enable_autofilter: bool = Field(default=True)
    auto_size_columns: bool = Field(default=True)
    min_column_width: int = Field(default=10, ge=1)
    max_column_width: int = Field(default=60, ge=1)
    date_format: str = Field(default="yyyy-mm-dd hh:mm:ss")

    @model_validator(mode="after")
    def _column_width_bounds_ordered(self) -> ExcelExportConfig:
        if self.max_column_width < self.min_column_width:
            raise ValueError("max_column_width cannot be less than min_column_width.")
        return self


class ExportConfig(BaseModel):
    """Default settings for the ``export`` CLI command."""

    default_format: Literal["json", "csv", "xlsx"] = "json"
    output_directory: str = Field(default="exports")
    excel: ExcelExportConfig = Field(default_factory=ExcelExportConfig)


class AppSettings(BaseSettings):
    """Root settings object composing every configurable subsystem."""

    model_config = SettingsConfigDict(
        env_prefix="SIGINT_",
        env_nested_delimiter="__",
        extra="ignore",
    )

    environment: Literal["development", "staging", "production"] = "development"
    country_code: str = Field(default=PRIMARY_COUNTRY_CODE)

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    retry: RetryConfig = Field(default_factory=RetryConfig)
    verification: VerificationConfig = Field(default_factory=VerificationConfig)
    concurrency: ConcurrencyConfig = Field(default_factory=ConcurrencyConfig)
    collectors: CollectorsConfig = Field(default_factory=CollectorsConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
