"""Matches a single SignalCondition against a SignalCluster."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from app.application.interfaces.correlation import SignalCluster
from app.domain.rule import SignalCondition


def match_condition(
    condition: SignalCondition, cluster: SignalCluster, *, now: datetime
) -> list[UUID]:
    """Return the IDs of signals in ``cluster`` that satisfy ``condition``.

    Returns an empty list if fewer than ``condition.min_count`` signals in
    the cluster satisfy the type, recency, and confidence requirements.
    """
    candidates = [s for s in cluster.signals if s.signal_type == condition.signal_type]

    if condition.min_confidence is not None:
        candidates = [s for s in candidates if s.confidence >= condition.min_confidence]

    if condition.max_age_days is not None:
        cutoff = now - timedelta(days=condition.max_age_days)
        candidates = [s for s in candidates if s.timestamp >= cutoff]

    if len(candidates) < condition.min_count:
        return []
    return [s.id for s in candidates]
