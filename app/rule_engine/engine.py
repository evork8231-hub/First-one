"""The default RuleEngine implementation."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from app.application.interfaces.correlation import SignalCluster
from app.application.interfaces.rule_engine import RuleEngineInterface, RuleMatch
from app.domain.rule import Rule
from app.rule_engine.matcher import match_condition


class RuleEngine(RuleEngineInterface):
    """Evaluates enabled Rules against a SignalCluster using ``matcher.match_condition``."""

    def __init__(self, *, clock: Callable[[], datetime] | None = None) -> None:
        self._clock = clock or (lambda: datetime.now(UTC))

    def evaluate(self, cluster: SignalCluster, rules: Sequence[Rule]) -> list[RuleMatch]:
        now = self._clock()
        matches: list[RuleMatch] = []

        for rule in rules:
            if not rule.enabled:
                continue

            matched_ids_per_condition = [
                match_condition(condition, cluster, now=now) for condition in rule.conditions
            ]
            satisfied_conditions = [ids for ids in matched_ids_per_condition if ids]

            if len(satisfied_conditions) >= (rule.min_matching_conditions or len(rule.conditions)):
                matched_signal_ids = sorted(
                    {signal_id for ids in satisfied_conditions for signal_id in ids},
                    key=str,
                )
                matches.append(
                    RuleMatch(rule=rule, cluster=cluster, matched_signal_ids=matched_signal_ids)
                )

        return matches
