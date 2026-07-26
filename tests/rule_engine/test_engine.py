"""Tests for app.rule_engine.engine.RuleEngine."""

from __future__ import annotations

from app.application.interfaces.correlation import SignalCluster
from app.domain.enums import SignalType
from app.rule_engine.engine import RuleEngine

from tests.fixtures.factories import make_condition, make_rule, make_signal


def test_evaluate_matches_rule_when_all_conditions_satisfied() -> None:
    building = make_signal(signal_type=SignalType.BUILDING_RECORD)
    roof_mention = make_signal(signal_type=SignalType.ROOF_MENTION)
    cluster = SignalCluster(
        county="Harju", municipality="Tallinn", signals=[building, roof_mention]
    )
    rule = make_rule(
        conditions=[
            make_condition(signal_type=SignalType.BUILDING_RECORD),
            make_condition(signal_type=SignalType.ROOF_MENTION),
        ]
    )

    matches = RuleEngine().evaluate(cluster, [rule])

    assert len(matches) == 1
    assert matches[0].rule.id == rule.id
    assert set(matches[0].matched_signal_ids) == {building.id, roof_mention.id}


def test_evaluate_skips_disabled_rules() -> None:
    building = make_signal(signal_type=SignalType.BUILDING_RECORD)
    roof_mention = make_signal(signal_type=SignalType.ROOF_MENTION)
    cluster = SignalCluster(
        county="Harju", municipality="Tallinn", signals=[building, roof_mention]
    )
    rule = make_rule(enabled=False)

    assert RuleEngine().evaluate(cluster, [rule]) == []


def test_evaluate_respects_partial_min_matching_conditions() -> None:
    roof_mention = make_signal(signal_type=SignalType.ROOF_MENTION)
    cluster = SignalCluster(county="Harju", municipality="Tallinn", signals=[roof_mention])
    rule = make_rule(
        conditions=[
            make_condition(signal_type=SignalType.BUILDING_RECORD),
            make_condition(signal_type=SignalType.ROOF_MENTION),
        ],
        min_matching_conditions=1,
    )

    matches = RuleEngine().evaluate(cluster, [rule])

    assert len(matches) == 1
    assert matches[0].matched_signal_ids == [roof_mention.id]


def test_evaluate_returns_no_match_when_conditions_unmet() -> None:
    roof_mention = make_signal(signal_type=SignalType.ROOF_MENTION)
    cluster = SignalCluster(county="Harju", municipality="Tallinn", signals=[roof_mention])
    rule = make_rule(
        conditions=[
            make_condition(signal_type=SignalType.BUILDING_RECORD),
            make_condition(signal_type=SignalType.ROOF_MENTION),
        ]
    )

    assert RuleEngine().evaluate(cluster, [rule]) == []
