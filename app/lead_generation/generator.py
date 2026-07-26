"""The default LeadGenerator implementation.

Groups RuleMatches by (location, lead_type), separates weather evidence
from primary evidence, scores each group, and builds a Lead only when
enough non-weather evidence exists to satisfy
``app.domain.lead.MIN_SUPPORTING_SIGNALS``.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from app.application.interfaces.lead_generation import LeadGeneratorInterface
from app.application.interfaces.rule_engine import RuleMatch
from app.domain.enums import ServiceCategory, SignalType
from app.domain.lead import MIN_SUPPORTING_SIGNALS, Lead
from app.domain.rule import Rule
from app.domain.signal import Signal
from app.domain.value_objects import Coordinates, EstimatedLocation
from app.lead_generation.scoring import LeadScorer

_GroupKey = tuple[str, str, str | None, ServiceCategory]


class LeadGenerator(LeadGeneratorInterface):
    """Combines RuleMatches into scored, reasoned Leads."""

    def __init__(self, scorer: LeadScorer) -> None:
        self._scorer = scorer

    def generate(self, matches: Sequence[RuleMatch]) -> list[Lead]:
        groups: dict[_GroupKey, list[RuleMatch]] = {}
        for match in matches:
            key: _GroupKey = (
                match.cluster.county,
                match.cluster.municipality,
                match.cluster.building_identifier,
                match.rule.lead_type,
            )
            groups.setdefault(key, []).append(match)

        leads: list[Lead] = []
        for (county, municipality, _building_id, lead_type), group in groups.items():
            cluster_signals_by_id = {s.id: s for s in group[0].cluster.signals}
            matched_signal_ids: set[UUID] = {
                sid for match in group for sid in match.matched_signal_ids
            }
            matched_signals = [cluster_signals_by_id[sid] for sid in matched_signal_ids]

            weather_signals = [
                s for s in matched_signals if s.signal_type == SignalType.WEATHER_EVENT
            ]
            evidence_signals = [
                s for s in matched_signals if s.signal_type != SignalType.WEATHER_EVENT
            ]

            if len(evidence_signals) < MIN_SUPPORTING_SIGNALS:
                # Weather alone (or too little non-weather evidence) can never
                # justify a lead -- per the mission, weather only affects confidence.
                continue

            matched_rules = [match.rule for match in group]
            score = self._scorer.score(
                matched_rules=matched_rules,
                evidence_signals=evidence_signals,
                weather_signals=weather_signals,
            )

            leads.append(
                Lead(
                    lead_type=lead_type,
                    supporting_signal_ids=sorted((s.id for s in evidence_signals), key=str),
                    country=evidence_signals[0].country,
                    county=county,
                    municipality=municipality,
                    estimated_location=self._estimate_location(
                        county, municipality, evidence_signals
                    ),
                    estimated_confidence=score.estimated_confidence,
                    intent_score=score.intent_score,
                    priority=score.priority,
                    reasoning=self._build_reasoning(
                        matched_rules, evidence_signals, weather_signals, municipality, county
                    ),
                )
            )
        return leads

    @staticmethod
    def _estimate_location(
        county: str, municipality: str, evidence_signals: Sequence[Signal]
    ) -> EstimatedLocation:
        observed = [s.coordinates for s in evidence_signals if s.coordinates is not None]
        if not observed:
            return EstimatedLocation(county=county, municipality=municipality)
        avg_lat = sum(c.latitude for c in observed) / len(observed)
        avg_lon = sum(c.longitude for c in observed) / len(observed)
        return EstimatedLocation(
            county=county,
            municipality=municipality,
            approximate_coordinates=Coordinates(latitude=avg_lat, longitude=avg_lon),
            precision_radius_meters=250.0 if len(observed) == 1 else 500.0,
        )

    @staticmethod
    def _build_reasoning(
        matched_rules: Sequence[Rule],
        evidence_signals: Sequence[Signal],
        weather_signals: Sequence[Signal],
        municipality: str,
        county: str,
    ) -> str:
        rule_summaries = "; ".join(
            f"{rule.name!r} ({rule.description.strip()})" for rule in matched_rules
        )
        evidence_types = ", ".join(sorted({s.signal_type.value for s in evidence_signals}))
        parts = [
            f"Matched rule(s): {rule_summaries}.",
            f"Supported by {len(evidence_signals)} verified signal(s) ({evidence_types}) "
            f"in {municipality}, {county}.",
        ]
        if weather_signals:
            parts.append(
                f"{len(weather_signals)} weather signal(s) were present and used only to adjust "
                "confidence, per platform policy that weather never independently justifies a lead."
            )
        return " ".join(parts)
