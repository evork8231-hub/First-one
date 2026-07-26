"""Rule engine interfaces and the RuleMatch construct.

Rules are always data-driven (loaded from configuration, never hardcoded
in Python). See ``app.rule_engine`` for the concrete engine and loader,
and ``config/rules/`` for example rule definitions.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.application.interfaces.correlation import SignalCluster
from app.domain.rule import Rule


class RuleMatch(BaseModel):
    """The result of a single Rule matching a single SignalCluster.

    Attributes:
        rule: The rule that matched.
        cluster: The signal cluster it matched against.
        matched_signal_ids: IDs of the specific signals within the cluster
            that satisfied the rule's conditions -- these become a
            candidate Lead's ``supporting_signal_ids``.
    """

    model_config = ConfigDict(frozen=True)

    rule: Rule
    cluster: SignalCluster
    matched_signal_ids: list[UUID] = Field(min_length=1)


class RuleEngineInterface(ABC):
    """Contract for evaluating data-driven Rules against SignalClusters."""

    @abstractmethod
    def evaluate(self, cluster: SignalCluster, rules: Sequence[Rule]) -> list[RuleMatch]:
        """Return every rule in ``rules`` that matches ``cluster``.

        A cluster may satisfy more than one rule (e.g. both a roofing rule
        and a solar rule); all matches are returned so the lead generation
        stage can decide how to combine them.
        """


class RuleProvider(ABC):
    """Contract for loading the active set of data-driven Rules."""

    @abstractmethod
    def get_active_rules(self) -> list[Rule]:
        """Return every currently enabled Rule, sourced from configuration."""
