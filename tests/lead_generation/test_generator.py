"""Tests for app.lead_generation.generator.LeadGenerator."""

from __future__ import annotations

from app.application.interfaces.correlation import SignalCluster
from app.application.interfaces.rule_engine import RuleMatch
from app.config.settings import ScoringConfig
from app.domain.enums import SignalType
from app.lead_generation.generator import LeadGenerator
from app.lead_generation.scoring import LeadScorer

from tests.fixtures.factories import make_rule, make_signal


def _generator() -> LeadGenerator:
    return LeadGenerator(LeadScorer(ScoringConfig()))


def test_generate_excludes_weather_from_supporting_signals() -> None:
    building = make_signal(signal_type=SignalType.BUILDING_RECORD)
    roof_mention = make_signal(signal_type=SignalType.ROOF_MENTION)
    weather = make_signal(signal_type=SignalType.WEATHER_EVENT)
    cluster = SignalCluster(
        county="Harju", municipality="Tallinn", signals=[building, roof_mention, weather]
    )
    rule = make_rule(
        conditions=[
            {"signal_type": SignalType.WEATHER_EVENT},
            {"signal_type": SignalType.BUILDING_RECORD},
            {"signal_type": SignalType.ROOF_MENTION},
        ]
    )
    match = RuleMatch(
        rule=rule, cluster=cluster, matched_signal_ids=[building.id, roof_mention.id, weather.id]
    )

    leads = _generator().generate([match])

    assert len(leads) == 1
    lead = leads[0]
    assert set(lead.supporting_signal_ids) == {building.id, roof_mention.id}
    assert weather.id not in lead.supporting_signal_ids
    assert "weather" in lead.reasoning.lower()


def test_generate_skips_when_only_weather_evidence_present() -> None:
    weather = make_signal(signal_type=SignalType.WEATHER_EVENT)
    building = make_signal(signal_type=SignalType.BUILDING_RECORD)
    cluster = SignalCluster(county="Harju", municipality="Tallinn", signals=[weather, building])
    rule = make_rule(
        conditions=[
            {"signal_type": SignalType.WEATHER_EVENT},
            {"signal_type": SignalType.BUILDING_RECORD},
        ]
    )
    match = RuleMatch(rule=rule, cluster=cluster, matched_signal_ids=[weather.id, building.id])

    leads = _generator().generate([match])

    assert leads == []


def test_generate_combines_multiple_matches_for_the_same_cluster_and_lead_type() -> None:
    building = make_signal(signal_type=SignalType.BUILDING_RECORD)
    roof_mention = make_signal(signal_type=SignalType.ROOF_MENTION)
    permit = make_signal(signal_type=SignalType.CONSTRUCTION_PERMIT)
    cluster = SignalCluster(
        county="Harju", municipality="Tallinn", signals=[building, roof_mention, permit]
    )

    rule_a = make_rule(
        id="rule_a",
        conditions=[
            {"signal_type": SignalType.BUILDING_RECORD},
            {"signal_type": SignalType.ROOF_MENTION},
        ],
    )
    rule_b = make_rule(
        id="rule_b",
        conditions=[
            {"signal_type": SignalType.CONSTRUCTION_PERMIT},
            {"signal_type": SignalType.ROOF_MENTION},
        ],
    )
    match_a = RuleMatch(
        rule=rule_a, cluster=cluster, matched_signal_ids=[building.id, roof_mention.id]
    )
    match_b = RuleMatch(
        rule=rule_b, cluster=cluster, matched_signal_ids=[permit.id, roof_mention.id]
    )

    leads = _generator().generate([match_a, match_b])

    assert len(leads) == 1
    assert set(leads[0].supporting_signal_ids) == {building.id, roof_mention.id, permit.id}
