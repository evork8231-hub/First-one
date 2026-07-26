"""Tests for app.lead_generation.scoring."""

from __future__ import annotations

import pytest
from app.config.settings import ScoringConfig
from app.domain.enums import LeadPriority
from app.lead_generation.scoring import LeadScorer, PriorityCalculator, SignalConfidenceAggregator

from tests.fixtures.factories import make_rule, make_signal


def test_signal_confidence_aggregator_mean() -> None:
    signals = [make_signal(confidence=0.4), make_signal(confidence=0.8)]
    assert SignalConfidenceAggregator.aggregate(signals, "mean") == pytest.approx(0.6)


def test_signal_confidence_aggregator_min() -> None:
    signals = [make_signal(confidence=0.4), make_signal(confidence=0.8)]
    assert SignalConfidenceAggregator.aggregate(signals, "min") == 0.4


def test_signal_confidence_aggregator_empty_is_zero() -> None:
    assert SignalConfidenceAggregator.aggregate([], "mean") == 0.0


def test_priority_calculator_picks_highest_satisfied_threshold() -> None:
    calculator = PriorityCalculator({"low": 0.0, "medium": 0.4, "high": 0.65, "critical": 0.85})
    assert calculator.calculate(0.9) == LeadPriority.CRITICAL
    assert calculator.calculate(0.7) == LeadPriority.HIGH
    assert calculator.calculate(0.5) == LeadPriority.MEDIUM
    assert calculator.calculate(0.1) == LeadPriority.LOW


def test_lead_scorer_without_weather_signals() -> None:
    scorer = LeadScorer(ScoringConfig())
    evidence = [make_signal(confidence=0.6), make_signal(confidence=0.8)]
    rule = make_rule(base_confidence=0.5, weight=1.0)

    score = scorer.score(matched_rules=[rule], evidence_signals=evidence, weather_signals=[])

    assert score.estimated_confidence == 0.7
    assert score.intent_score == 0.5


def test_lead_scorer_applies_weather_boost() -> None:
    scoring_config = ScoringConfig(weather_confidence_boost_factor=0.5)
    scorer = LeadScorer(scoring_config)
    evidence = [make_signal(confidence=0.6), make_signal(confidence=0.6)]
    weather = [make_signal(confidence=1.0)]
    rule = make_rule(base_confidence=0.5, weight=1.0)

    boosted = scorer.score(matched_rules=[rule], evidence_signals=evidence, weather_signals=weather)
    unboosted = scorer.score(matched_rules=[rule], evidence_signals=evidence, weather_signals=[])

    assert boosted.estimated_confidence > unboosted.estimated_confidence
    assert boosted.intent_score > unboosted.intent_score


def test_lead_scorer_score_never_exceeds_one() -> None:
    scoring_config = ScoringConfig(weather_confidence_boost_factor=1.0)
    scorer = LeadScorer(scoring_config)
    evidence = [make_signal(confidence=1.0), make_signal(confidence=1.0)]
    weather = [make_signal(confidence=1.0)]
    rule = make_rule(base_confidence=1.0, weight=1.0)

    score = scorer.score(matched_rules=[rule], evidence_signals=evidence, weather_signals=weather)

    assert score.estimated_confidence <= 1.0
    assert score.intent_score <= 1.0
