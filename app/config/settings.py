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

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.constants import PRIMARY_COUNTRY_CODE
from app.core.retry import RetryPolicy


class DatabaseConfig(BaseModel):
    """Database connection settings."""

    url: str = Field(default="sqlite:///./data/signals.db")
    echo: bool = Field(default=False, description="Log every SQL statement (development only).")


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


class VerificationConfig(BaseModel):
    """Thresholds consulted by the structural verifiers."""

    min_signal_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    min_lead_confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class CollectorsConfig(BaseModel):
    """Which registered collectors are permitted to run."""

    enabled: list[str] = Field(default_factory=list)

    @property
    def enabled_set(self) -> frozenset[str]:
        return frozenset(self.enabled)


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


class ExportConfig(BaseModel):
    """Default settings for the ``export`` CLI command."""

    default_format: Literal["json", "csv"] = "json"
    output_directory: str = Field(default="exports")


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
    collectors: CollectorsConfig = Field(default_factory=CollectorsConfig)
    rules: RulesConfig = Field(default_factory=RulesConfig)
    scoring: ScoringConfig = Field(default_factory=ScoringConfig)
    export: ExportConfig = Field(default_factory=ExportConfig)
