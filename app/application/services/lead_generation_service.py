"""LeadGenerationService: turns RuleMatches into persisted Leads."""

from __future__ import annotations

from collections.abc import Sequence

from app.application.interfaces.lead_generation import LeadGeneratorInterface
from app.application.interfaces.repositories import AuditLogRepository, LeadRepository
from app.application.interfaces.rule_engine import RuleMatch
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.domain.lead import Lead


class LeadGenerationService:
    """Persists Leads built by a LeadGeneratorInterface implementation."""

    def __init__(
        self,
        lead_generator: LeadGeneratorInterface,
        lead_repository: LeadRepository,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._lead_generator = lead_generator
        self._lead_repository = lead_repository
        self._audit_log_repository = audit_log_repository

    def generate_from_matches(self, matches: Sequence[RuleMatch]) -> list[Lead]:
        """Build Leads from ``matches`` and persist each one."""
        candidates = self._lead_generator.generate(matches)

        persisted: list[Lead] = []
        for lead in candidates:
            stored = self._lead_repository.add(lead)
            persisted.append(stored)
            self._audit_log_repository.add(
                AuditLogEntry(
                    event_type=AuditEventType.LEAD_GENERATED,
                    entity_type="Lead",
                    entity_id=stored.id,
                    message=(
                        f"Generated {stored.lead_type.value} lead from "
                        f"{len(stored.supporting_signal_ids)} signal(s)."
                    ),
                    context={
                        "supporting_signal_ids": [str(sid) for sid in stored.supporting_signal_ids],
                        "intent_score": stored.intent_score,
                        "estimated_confidence": stored.estimated_confidence,
                    },
                )
            )
        return persisted
