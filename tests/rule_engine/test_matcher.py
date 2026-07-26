"""Tests for app.rule_engine.matcher.match_condition."""

from __future__ import annotations

from datetime import timedelta

from app.application.interfaces.correlation import SignalCluster
from app.domain.enums import SignalType
from app.rule_engine.matcher import match_condition
from app.utils.time import utc_now

from tests.fixtures.factories import make_condition, make_signal


def _cluster(*signals) -> SignalCluster:
    return SignalCluster(county="Harju", municipality="Tallinn", signals=list(signals))


def test_match_condition_returns_matching_ids_when_min_count_satisfied() -> None:
    signal = make_signal(signal_type=SignalType.ROOF_MENTION)
    cluster = _cluster(signal)
    condition = make_condition(signal_type=SignalType.ROOF_MENTION, min_count=1)

    matched = match_condition(condition, cluster, now=utc_now())

    assert matched == [signal.id]


def test_match_condition_returns_empty_when_min_count_not_satisfied() -> None:
    signal = make_signal(signal_type=SignalType.ROOF_MENTION)
    cluster = _cluster(signal)
    condition = make_condition(signal_type=SignalType.ROOF_MENTION, min_count=2)

    assert match_condition(condition, cluster, now=utc_now()) == []


def test_match_condition_filters_by_min_confidence() -> None:
    signal = make_signal(signal_type=SignalType.ROOF_MENTION, confidence=0.3)
    cluster = _cluster(signal)
    condition = make_condition(signal_type=SignalType.ROOF_MENTION, min_count=1, min_confidence=0.5)

    assert match_condition(condition, cluster, now=utc_now()) == []


def test_match_condition_filters_by_max_age_days() -> None:
    now = utc_now()
    old_signal = make_signal(
        signal_type=SignalType.ROOF_MENTION, timestamp=now - timedelta(days=90)
    )
    cluster = _cluster(old_signal)
    condition = make_condition(signal_type=SignalType.ROOF_MENTION, min_count=1, max_age_days=30)

    assert match_condition(condition, cluster, now=now) == []


def test_match_condition_ignores_other_signal_types() -> None:
    building = make_signal(signal_type=SignalType.BUILDING_RECORD)
    cluster = _cluster(building)
    condition = make_condition(signal_type=SignalType.ROOF_MENTION, min_count=1)

    assert match_condition(condition, cluster, now=utc_now()) == []
