"""Independent scoring for Signal confidence and Lead intent.

Two systems live here, deliberately kept separate:

* :class:`SignalConfidenceAggregator` combines the ``confidence`` values
  already present on individual Signals -- it never invents a number.
* :class:`LeadScorer` combines matched Rule weights into an
  ``intent_score`` that is conceptually distinct from signal confidence,
  per the mission's "Signals have their own score. Leads have a different
  score. Keep both systems independent" requirement.

All weights and thresholds are sourced from ``ScoringConfig`` --
nothing here is hardcoded.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.config.settings import ScoringConfig
from app.domain.enums import LeadPriority
from app.domain.rule import Rule
from app.domain.signal import Signal


class SignalConfidenceAggregator:
    """Combines multiple Signals' own ``confidence`` values into one number."""

    @staticmethod
    def aggregate(signals: Sequence[Signal], strategy: Literal["mean", "min"]) -> float:
        if not signals:
            return 0.0
        values = [signal.confidence for signal in signals]
        if strategy == "min":
            return min(values)
        return sum(values) / len(values)


class PriorityCalculator:
    """Maps an ``intent_score`` to a :class:`LeadPriority` using configured thresholds."""

    def __init__(self, thresholds: Mapping[str, float]) -> None:
        self._sorted_thresholds = sorted(thresholds.items(), key=lambda item: item[1], reverse=True)

    def calculate(self, intent_score: float) -> LeadPriority:
        for name, threshold in self._sorted_thresholds:
            if intent_score >= threshold:
                return LeadPriority(name)
        return LeadPriority.LOW


class LeadScore(BaseModel):
    """The output of scoring a candidate lead."""

    model_config = ConfigDict(frozen=True)

    estimated_confidence: float = Field(ge=0.0, le=1.0)
    intent_score: float = Field(ge=0.0, le=1.0)
    priority: LeadPriority


class LeadScorer:
    """Computes a LeadScore from matched rules and their supporting signals."""

    def __init__(self, scoring_config: ScoringConfig) -> None:
        self._config = scoring_config
        self._priority_calculator = PriorityCalculator(scoring_config.priority_thresholds)

    def score(
        self,
        *,
        matched_rules: Sequence[Rule],
        evidence_signals: Sequence[Signal],
        weather_signals: Sequence[Signal],
    ) -> LeadScore:
        """Score a candidate lead.

        ``evidence_signals`` must exclude weather signals -- weather is
        passed separately and only ever scales the result, never
        contributes to it as primary evidence.
        """
        estimated_confidence = SignalConfidenceAggregator.aggregate(
            evidence_signals, self._config.confidence_aggregation
        )
        estimated_confidence = self._apply_weather_boost(estimated_confidence, weather_signals)

        total_weight = sum(rule.weight for rule in matched_rules)
        if total_weight <= 0:
            intent_score = 0.0
        else:
            intent_score = (
                sum(rule.base_confidence * rule.weight for rule in matched_rules) / total_weight
            )
        intent_score = self._apply_weather_boost(intent_score, weather_signals)

        return LeadScore(
            estimated_confidence=estimated_confidence,
            intent_score=intent_score,
            priority=self._priority_calculator.calculate(intent_score),
        )

    def _apply_weather_boost(self, value: float, weather_signals: Sequence[Signal]) -> float:
        if not weather_signals:
            return value
        weather_strength = SignalConfidenceAggregator.aggregate(weather_signals, "mean")
        boosted = value * (1 + self._config.weather_confidence_boost_factor * weather_strength)
        return min(boosted, 1.0)
