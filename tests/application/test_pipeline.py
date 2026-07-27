"""End-to-end pipeline test wiring real services (no DI container, no database):

Collect -> Verify Signals -> Store -> Correlate -> Generate Leads ->
Verify Leads -> Score -> Export.

Every stage is a real, production service; only the collector and the
rule source are test doubles, and every repository is the in-memory
implementation -- no live network, no live database file.
"""

from __future__ import annotations

import asyncio

from app.application.interfaces.rule_engine import RuleProvider
from app.application.services.correlation_service import CorrelationService
from app.application.services.export_service import ExportService
from app.application.services.lead_generation_service import LeadGenerationService
from app.application.services.signal_service import SignalService
from app.application.services.verification_service import VerificationService
from app.application.services.weather_event_service import WeatherEventService
from app.application.services.weather_signal_bridge_service import WeatherSignalBridgeService
from app.config.settings import DuplicateDetectionConfig, ScoringConfig, WeatherSignalBridgeConfig
from app.correlation.engine import CorrelationEngine
from app.domain.enums import ServiceCategory, SignalType, VerificationStatus
from app.domain.rule import Rule
from app.lead_generation.generator import LeadGenerator
from app.lead_generation.scoring import LeadScorer
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from app.repositories.in_memory.weather_repository import InMemoryWeatherEventRepository
from app.rule_engine.engine import RuleEngine
from app.verification.duplicate_detector import DuplicateDetector
from app.verification.duplicate_signal_verifier import DuplicateSignalVerifier
from app.verification.structural_lead_verifier import StructuralLeadVerifier
from app.verification.structural_signal_verifier import StructuralSignalVerifier

from tests.fixtures.factories import make_condition, make_rule, make_signal, make_weather_event
from tests.fixtures.fakes import FakeCollector, FakeWeatherCollector


class _StaticRuleProvider(RuleProvider):
    def __init__(self, rules: list[Rule]) -> None:
        self._rules = rules

    def get_active_rules(self) -> list[Rule]:
        return self._rules


def _build_pipeline(*, rule: Rule | None = None) -> dict[str, object]:
    signal_repo = InMemorySignalRepository()
    lead_repo = InMemoryLeadRepository()
    weather_repo = InMemoryWeatherEventRepository()
    audit_repo = InMemoryAuditLogRepository()

    dup_config = DuplicateDetectionConfig()
    signal_verifiers = [
        StructuralSignalVerifier(min_confidence=0.5),
        DuplicateSignalVerifier(signal_repo, DuplicateDetector(dup_config), dup_config),
    ]
    lead_verifiers = [StructuralLeadVerifier(signal_repo, min_confidence=0.5)]

    if rule is None:
        rule = make_rule(
            id="pipeline_test_rule",
            conditions=[
                make_condition(signal_type=SignalType.BUILDING_RECORD),
                make_condition(signal_type=SignalType.ROOF_MENTION),
            ],
        )

    return {
        "signal_repo": signal_repo,
        "lead_repo": lead_repo,
        "weather_repo": weather_repo,
        "audit_repo": audit_repo,
        "signal_service": SignalService(signal_repo, audit_repo),
        "weather_event_service": WeatherEventService(weather_repo, audit_repo),
        "weather_signal_bridge_service": WeatherSignalBridgeService(
            signal_repo, audit_repo, WeatherSignalBridgeConfig()
        ),
        "verification_service": VerificationService(
            signal_repo, lead_repo, audit_repo, signal_verifiers, lead_verifiers
        ),
        "correlation_service": CorrelationService(
            signal_repo, CorrelationEngine(), RuleEngine(), _StaticRuleProvider([rule]), audit_repo
        ),
        "lead_generation_service": LeadGenerationService(
            LeadGenerator(LeadScorer(ScoringConfig())), lead_repo, audit_repo
        ),
        "export_service": ExportService(lead_repo, signal_repo),
    }


def test_full_pipeline_produces_an_exportable_verified_lead() -> None:
    pipeline = _build_pipeline()
    signal_service: SignalService = pipeline["signal_service"]  # type: ignore[assignment]
    verification_service: VerificationService = pipeline["verification_service"]  # type: ignore[assignment]
    correlation_service: CorrelationService = pipeline["correlation_service"]  # type: ignore[assignment]
    lead_generation_service: LeadGenerationService = pipeline["lead_generation_service"]  # type: ignore[assignment]
    export_service: ExportService = pipeline["export_service"]  # type: ignore[assignment]

    # 1. Collect.
    collector = FakeCollector(
        [
            make_signal(
                signal_type=SignalType.BUILDING_RECORD,
                service_category=ServiceCategory.ROOFING,
                confidence=0.9,
                verified=VerificationStatus.UNVERIFIED,
            ),
            make_signal(
                signal_type=SignalType.ROOF_MENTION,
                service_category=ServiceCategory.ROOFING,
                confidence=0.9,
                verified=VerificationStatus.UNVERIFIED,
            ),
        ]
    )
    collected = asyncio.run(signal_service.ingest_from_collector(collector))
    assert len(collected) == 2
    assert all(s.verified == VerificationStatus.UNVERIFIED for s in collected)

    # 2. Verify signals, 3. store verified.
    verified = asyncio.run(verification_service.verify_pending_signals(limit=10))
    assert len(verified) == 2
    assert all(s.verified == VerificationStatus.VERIFIED for s in verified)

    # 4. Correlate verified signals.
    matches = correlation_service.run()
    assert len(matches) == 1
    assert matches[0].rule.id == "pipeline_test_rule"

    # 5. Generate leads.
    leads = lead_generation_service.generate_from_matches(matches)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.verification_status == VerificationStatus.UNVERIFIED

    # 6. Verify leads.
    verified_lead = asyncio.run(verification_service.verify_lead(lead.id))
    assert verified_lead.verification_status == VerificationStatus.VERIFIED

    # 7. Score (already computed at generation time; re-assert it's present and sane).
    assert 0.0 <= verified_lead.intent_score <= 1.0
    assert 0.0 <= verified_lead.estimated_confidence <= 1.0
    assert verified_lead.priority is not None

    # 8. Export VERIFIED leads only.
    exported = export_service.export_leads(export_format="csv")
    assert str(verified_lead.id) in exported


def test_weather_events_never_become_leads_in_the_full_pipeline() -> None:
    """A weather-only signal cannot, by itself, satisfy a rule that needs real evidence."""
    pipeline = _build_pipeline()
    signal_repo: InMemorySignalRepository = pipeline["signal_repo"]  # type: ignore[assignment]
    weather_event_service: WeatherEventService = pipeline["weather_event_service"]  # type: ignore[assignment]
    verification_service: VerificationService = pipeline["verification_service"]  # type: ignore[assignment]
    correlation_service: CorrelationService = pipeline["correlation_service"]  # type: ignore[assignment]
    lead_generation_service: LeadGenerationService = pipeline["lead_generation_service"]  # type: ignore[assignment]
    weather_repo: InMemoryWeatherEventRepository = pipeline["weather_repo"]  # type: ignore[assignment]
    lead_repo: InMemoryLeadRepository = pipeline["lead_repo"]  # type: ignore[assignment]

    # A WeatherEvent is collected and stored via the weather pipeline, never the lead pipeline.
    weather_collector = FakeWeatherCollector([make_weather_event()])
    stored_events = asyncio.run(weather_event_service.ingest_from_collector(weather_collector))
    assert len(stored_events) == 1
    assert weather_repo.get_by_id(stored_events[0].id) is not None
    assert lead_repo.list_all(limit=10) == []  # weather never touches the lead repository

    # Only a WEATHER_EVENT-typed signal (no other evidence) reaches correlation.
    weather_signal = signal_repo.add(
        make_signal(signal_type=SignalType.WEATHER_EVENT, verified=VerificationStatus.UNVERIFIED)
    )
    asyncio.run(verification_service.verify_signal(weather_signal.id))

    matches = correlation_service.run()
    leads = lead_generation_service.generate_from_matches(matches)

    assert leads == []  # weather alone can never generate a lead


def test_weather_event_bridged_into_a_signal_enables_a_weather_conditioned_rule_to_match() -> None:
    """The WeatherSignalBridgeService is what closes the gap the previous test exercises:

    once a WeatherEvent is bridged into a real WEATHER_EVENT Signal, a rule that
    requires weather alongside real evidence can match end-to-end, and the
    resulting Lead's supporting_signal_ids still excludes the weather signal
    (weather only boosts confidence, per app.lead_generation.generator.LeadGenerator).
    """
    weather_conditioned_rule = make_rule(
        id="weather_conditioned_pipeline_test_rule",
        conditions=[
            make_condition(signal_type=SignalType.WEATHER_EVENT, min_count=1),
            make_condition(signal_type=SignalType.BUILDING_RECORD),
            make_condition(signal_type=SignalType.ROOF_MENTION),
        ],
    )
    pipeline = _build_pipeline(rule=weather_conditioned_rule)
    weather_event_service: WeatherEventService = pipeline["weather_event_service"]  # type: ignore[assignment]
    bridge_service: WeatherSignalBridgeService = pipeline["weather_signal_bridge_service"]  # type: ignore[assignment]
    signal_service: SignalService = pipeline["signal_service"]  # type: ignore[assignment]
    verification_service: VerificationService = pipeline["verification_service"]  # type: ignore[assignment]
    correlation_service: CorrelationService = pipeline["correlation_service"]  # type: ignore[assignment]
    lead_generation_service: LeadGenerationService = pipeline["lead_generation_service"]  # type: ignore[assignment]

    # 1. Collect a WeatherEvent, then bridge it into a real WEATHER_EVENT Signal.
    weather_collector = FakeWeatherCollector([make_weather_event()])
    events = asyncio.run(weather_event_service.ingest_from_collector(weather_collector))
    bridged_signals = bridge_service.bridge(events)
    assert len(bridged_signals) == 1
    assert bridged_signals[0].signal_type == SignalType.WEATHER_EVENT

    # 2. Collect the other, non-weather evidence a real detection would also have.
    evidence_collector = FakeCollector(
        [
            make_signal(
                signal_type=SignalType.BUILDING_RECORD,
                service_category=ServiceCategory.ROOFING,
                confidence=0.9,
                verified=VerificationStatus.UNVERIFIED,
            ),
            make_signal(
                signal_type=SignalType.ROOF_MENTION,
                service_category=ServiceCategory.ROOFING,
                confidence=0.9,
                verified=VerificationStatus.UNVERIFIED,
            ),
        ]
    )
    asyncio.run(signal_service.ingest_from_collector(evidence_collector))

    # 3. Verify everything (the bridged weather signal included).
    verified = asyncio.run(verification_service.verify_pending_signals(limit=10))
    assert len(verified) == 3
    assert all(s.verified == VerificationStatus.VERIFIED for s in verified)

    # 4. Correlate: the weather-conditioned rule now matches.
    matches = correlation_service.run()
    assert len(matches) == 1
    assert matches[0].rule.id == "weather_conditioned_pipeline_test_rule"

    # 5. Generate: a Lead is produced, and the weather signal boosted its
    # confidence/intent score without becoming supporting evidence itself.
    leads = lead_generation_service.generate_from_matches(matches)
    assert len(leads) == 1
    lead = leads[0]
    assert bridged_signals[0].id not in lead.supporting_signal_ids
    assert len(lead.supporting_signal_ids) == 2
    assert 0.0 <= lead.estimated_confidence <= 1.0
    assert 0.0 <= lead.intent_score <= 1.0
    assert "weather signal" in lead.reasoning
