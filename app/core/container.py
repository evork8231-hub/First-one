"""The composition root: wires every interface to its concrete implementation.

This is the only module in the codebase permitted to import from every
layer at once -- domain, application, and every infrastructure package.
Nothing else should reach across those boundaries directly.

Usage::

    from app.core.container import Container

    container = Container()
    container.init_resources()
    signal_service = container.signal_service()

To use the in-memory repositories (e.g. in tests) instead of SQLite,
override the relevant providers before resolving anything::

    from app.repositories.in_memory.signal_repository import InMemorySignalRepository

    container.signal_repository.override(providers.Singleton(InMemorySignalRepository))
"""

from __future__ import annotations

from pathlib import Path

from dependency_injector import containers, providers

from app.application.interfaces.collector import CollectorInterface
from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.application.services.collector_health_service import CollectorHealthService
from app.application.services.collector_lifecycle_service import CollectorLifecycleService
from app.application.services.correlation_service import CorrelationService
from app.application.services.data_management_service import DataManagementService
from app.application.services.export_service import ExportService
from app.application.services.lead_generation_service import LeadGenerationService
from app.application.services.rollback_service import RollbackService
from app.application.services.signal_service import SignalService
from app.application.services.verification_service import VerificationService
from app.application.services.weather_event_service import WeatherEventService
from app.application.services.weather_signal_bridge_service import WeatherSignalBridgeService
from app.collectors.ehitisregister_collector import EhitisregisterCollector
from app.collectors.ehitisregister_xtee_collector import EhitisregisterXTeeCollector
from app.collectors.ilmateenistus_collector import IlmateenistusCollector
from app.collectors.real_estate.city24_collector import City24Collector
from app.collectors.real_estate.kinnisvara24_collector import Kinnisvara24Collector
from app.collectors.real_estate.kv_ee_collector import KvEeCollector
from app.collectors.registry import CollectorRegistry
from app.collectors.weather_registry import WeatherCollectorRegistry
from app.config.loader import load_settings
from app.correlation.engine import CorrelationEngine
from app.database.session import create_session_factory, create_sqlalchemy_engine
from app.lead_generation.generator import LeadGenerator
from app.lead_generation.scoring import LeadScorer
from app.logging.setup import configure_logging
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.configuration_repository import SQLiteConfigurationRepository
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from app.repositories.sqlite.rollback_unit_of_work import SQLiteRollbackUnitOfWork
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from app.rule_engine.engine import RuleEngine
from app.rule_engine.loader import RuleLoader
from app.verification.duplicate_detector import DuplicateDetector
from app.verification.duplicate_signal_verifier import DuplicateSignalVerifier
from app.verification.schema_drift import SchemaDriftDetector
from app.verification.structural_lead_verifier import StructuralLeadVerifier
from app.verification.structural_signal_verifier import StructuralSignalVerifier
from app.verification.weather_bridge_dedup import WeatherBridgeDeduplicator


def _build_collector_registry(*collectors: CollectorInterface) -> CollectorRegistry:
    """Register every known Signal collector; which ones actually run is a config concern."""
    registry = CollectorRegistry()
    for collector in collectors:
        registry.register(collector)
    return registry


def _build_weather_collector_registry(
    *collectors: WeatherCollectorInterface,
) -> WeatherCollectorRegistry:
    """Register every known weather collector; which ones actually run is a config concern."""
    registry = WeatherCollectorRegistry()
    for collector in collectors:
        registry.register(collector)
    return registry


class Container(containers.DeclarativeContainer):
    """Application-wide dependency injection container."""

    settings = providers.Singleton(load_settings)

    logging_resource = providers.Resource(configure_logging, config=settings.provided.logging)

    # --- Persistence -----------------------------------------------------
    engine = providers.Singleton(create_sqlalchemy_engine, config=settings.provided.database)
    session_factory = providers.Singleton(create_session_factory, engine=engine)

    signal_repository = providers.Singleton(SQLiteSignalRepository, session_factory=session_factory)
    lead_repository = providers.Singleton(SQLiteLeadRepository, session_factory=session_factory)
    weather_event_repository = providers.Singleton(
        SQLiteWeatherEventRepository, session_factory=session_factory
    )
    audit_log_repository = providers.Singleton(
        SQLiteAuditLogRepository, session_factory=session_factory
    )
    configuration_repository = providers.Singleton(
        SQLiteConfigurationRepository, session_factory=session_factory
    )
    rollback_unit_of_work = providers.Singleton(
        SQLiteRollbackUnitOfWork, session_factory=session_factory
    )

    # --- Collectors --------------------------------------------------------
    # Every collector is registered regardless of whether it is enabled --
    # `collectors.enabled` (see CollectorRegistry.list_enabled) is what
    # actually gates which ones a `collect` run may use.
    ehitisregister_collector = providers.Singleton(
        EhitisregisterCollector, config=settings.provided.collectors.ehitisregister
    )
    # Registered like every other collector, but structurally disabled --
    # see app.collectors.ehitisregister_xtee_collector for why it always
    # refuses to run regardless of whether it's listed in collectors.enabled.
    ehitisregister_xtee_collector = providers.Singleton(
        EhitisregisterXTeeCollector, config=settings.provided.collectors.ehitisregister_xtee
    )
    kv_ee_collector = providers.Singleton(KvEeCollector, config=settings.provided.collectors.kv_ee)
    kinnisvara24_collector = providers.Singleton(
        Kinnisvara24Collector, config=settings.provided.collectors.kinnisvara24
    )
    city24_collector = providers.Singleton(
        City24Collector, config=settings.provided.collectors.city24
    )
    collector_registry = providers.Singleton(
        _build_collector_registry,
        ehitisregister_collector,
        ehitisregister_xtee_collector,
        kv_ee_collector,
        kinnisvara24_collector,
        city24_collector,
    )

    ilmateenistus_collector = providers.Singleton(
        IlmateenistusCollector, config=settings.provided.collectors.ilmateenistus
    )
    weather_collector_registry = providers.Singleton(
        _build_weather_collector_registry,
        ilmateenistus_collector,
    )

    # --- Verification --------------------------------------------------------
    structural_signal_verifier = providers.Singleton(
        StructuralSignalVerifier,
        min_confidence=settings.provided.verification.min_signal_confidence,
        coordinate_bounds=settings.provided.verification.coordinate_bounds,
        require_coordinates=settings.provided.verification.require_coordinates,
        postal_code_pattern=settings.provided.verification.postal_code_pattern,
    )
    duplicate_detector = providers.Singleton(
        DuplicateDetector, config=settings.provided.verification.duplicate_detection
    )
    duplicate_signal_verifier = providers.Singleton(
        DuplicateSignalVerifier,
        signal_repository=signal_repository,
        detector=duplicate_detector,
        config=settings.provided.verification.duplicate_detection,
    )
    structural_lead_verifier = providers.Singleton(
        StructuralLeadVerifier,
        signal_repository=signal_repository,
        min_confidence=settings.provided.verification.min_lead_confidence,
    )
    signal_verifiers = providers.List(structural_signal_verifier, duplicate_signal_verifier)
    lead_verifiers = providers.List(structural_lead_verifier)
    schema_drift_detector = providers.Factory(
        SchemaDriftDetector,
        configuration_repository=configuration_repository,
        audit_log_repository=audit_log_repository,
    )
    weather_bridge_deduplicator = providers.Factory(
        WeatherBridgeDeduplicator, configuration_repository=configuration_repository
    )

    # --- Correlation & rules --------------------------------------------------------
    correlation_engine = providers.Singleton(CorrelationEngine)
    rules_directory = providers.Singleton(Path, settings.provided.rules.directory)
    rule_provider = providers.Singleton(RuleLoader, rules_directory=rules_directory)
    rule_engine = providers.Singleton(RuleEngine)

    # --- Lead generation --------------------------------------------------------
    lead_scorer = providers.Singleton(LeadScorer, scoring_config=settings.provided.scoring)
    lead_generator = providers.Singleton(LeadGenerator, scorer=lead_scorer)

    # --- Application services --------------------------------------------------------
    signal_service = providers.Factory(
        SignalService,
        signal_repository=signal_repository,
        audit_log_repository=audit_log_repository,
    )
    verification_service = providers.Factory(
        VerificationService,
        signal_repository=signal_repository,
        lead_repository=lead_repository,
        audit_log_repository=audit_log_repository,
        signal_verifiers=signal_verifiers,
        lead_verifiers=lead_verifiers,
    )
    correlation_service = providers.Factory(
        CorrelationService,
        signal_repository=signal_repository,
        correlation_engine=correlation_engine,
        rule_engine=rule_engine,
        rule_provider=rule_provider,
        audit_log_repository=audit_log_repository,
    )
    lead_generation_service = providers.Factory(
        LeadGenerationService,
        lead_generator=lead_generator,
        lead_repository=lead_repository,
        audit_log_repository=audit_log_repository,
    )
    export_service = providers.Factory(
        ExportService,
        lead_repository=lead_repository,
        signal_repository=signal_repository,
        excel_config=settings.provided.export.excel,
    )
    weather_event_service = providers.Factory(
        WeatherEventService,
        weather_event_repository=weather_event_repository,
        audit_log_repository=audit_log_repository,
    )
    weather_signal_bridge_service = providers.Factory(
        WeatherSignalBridgeService,
        signal_repository=signal_repository,
        audit_log_repository=audit_log_repository,
        config=settings.provided.weather_signal_bridge,
        deduplicator=weather_bridge_deduplicator,
    )
    data_management_service = providers.Factory(
        DataManagementService,
        signal_repository=signal_repository,
        weather_event_repository=weather_event_repository,
        audit_log_repository=audit_log_repository,
    )
    collector_health_service = providers.Factory(
        CollectorHealthService, audit_log_repository=audit_log_repository
    )
    rollback_service = providers.Factory(
        RollbackService,
        audit_log_repository=audit_log_repository,
        lead_repository=lead_repository,
        rollback_unit_of_work=rollback_unit_of_work,
    )
    collector_lifecycle_service = providers.Factory(
        CollectorLifecycleService, configuration_repository=configuration_repository
    )
