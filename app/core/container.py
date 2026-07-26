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

from app.application.services.correlation_service import CorrelationService
from app.application.services.export_service import ExportService
from app.application.services.lead_generation_service import LeadGenerationService
from app.application.services.signal_service import SignalService
from app.application.services.verification_service import VerificationService
from app.collectors.registry import CollectorRegistry
from app.config.loader import load_settings
from app.correlation.engine import CorrelationEngine
from app.database.session import create_session_factory, create_sqlalchemy_engine
from app.lead_generation.generator import LeadGenerator
from app.lead_generation.scoring import LeadScorer
from app.logging.setup import configure_logging
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.configuration_repository import SQLiteConfigurationRepository
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from app.rule_engine.engine import RuleEngine
from app.rule_engine.loader import RuleLoader
from app.verification.structural_lead_verifier import StructuralLeadVerifier
from app.verification.structural_signal_verifier import StructuralSignalVerifier


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

    # --- Collectors --------------------------------------------------------
    # Empty by default -- the foundation ships no concrete collector. A
    # future phase registers real collectors here, e.g.:
    #   collector_registry.provided.register.call(SomeCollector(...))
    collector_registry = providers.Singleton(CollectorRegistry)

    # --- Verification --------------------------------------------------------
    structural_signal_verifier = providers.Singleton(
        StructuralSignalVerifier,
        min_confidence=settings.provided.verification.min_signal_confidence,
    )
    structural_lead_verifier = providers.Singleton(
        StructuralLeadVerifier,
        signal_repository=signal_repository,
        min_confidence=settings.provided.verification.min_lead_confidence,
    )
    signal_verifiers = providers.List(structural_signal_verifier)
    lead_verifiers = providers.List(structural_lead_verifier)

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
    export_service = providers.Factory(ExportService, lead_repository=lead_repository)
