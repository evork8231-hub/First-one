"""Correlation interfaces and the SignalCluster construct.

The Correlation Engine consumes ONLY verified Signals. Collectors never
call it directly and know nothing about it -- the wiring happens in
``app.application.services.correlation_service``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from app.domain.signal import Signal


class SignalCluster(BaseModel):
    """A group of verified Signals plausibly concerning the same property.

    Clusters are the unit the Rule Engine evaluates against -- a single
    cluster's Signals are checked against each Rule's conditions. Clustering
    strategy (by ``building_identifier``, by address proximity, by
    county/municipality) is an infrastructure concern implemented by
    ``app.correlation.engine.CorrelationEngine``; this model only describes
    the resulting shape.

    Attributes:
        county: Estonian county shared by every signal in the cluster.
        municipality: Estonian municipality shared by every signal in the cluster.
        building_identifier: Shared building registry code, if every
            signal in the cluster carries one and they agree.
        signals: The verified signals that make up this cluster. Never
            empty.
    """

    model_config = ConfigDict(frozen=True)

    county: str = Field(min_length=1)
    municipality: str = Field(min_length=1)
    building_identifier: str | None = Field(default=None)
    signals: list[Signal] = Field(min_length=1)


class CorrelationEngineInterface(ABC):
    """Contract for grouping verified Signals into SignalClusters."""

    @abstractmethod
    def correlate(self, signals: Sequence[Signal]) -> list[SignalCluster]:
        """Group ``signals`` (all VERIFIED) into clusters for rule evaluation.

        Implementations must reject (raise ``CorrelationError``) if handed
        an unverified signal -- correlation is only ever performed on
        verified facts.
        """
