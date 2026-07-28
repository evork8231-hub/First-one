"""LeadGenerationService: turns RuleMatches into persisted Leads.

Lead generation is idempotent: ``CorrelationService.run()`` always
re-evaluates the *entire* current set of VERIFIED signals (it has no
"since last run" filter -- see that service's docstring), so a candidate
Lead built from exactly the same evidence (the same verified Signals)
that already produced a Lead on a previous call is the same real-world
opportunity, not a new one. Running ``sigint pipeline`` repeatedly with
no new Signals must produce zero new Leads. Before persisting a
candidate, this service checks ``LeadRepository.find_by_identity`` for an
existing Lead with the exact same ``(lead_type, supporting_signal_ids)``
and skips it if found -- mirroring the check-then-act pattern
``app.verification.weather_bridge_dedup.WeatherBridgeDeduplicator``
already uses for the same class of problem (both accept the same narrow,
documented race: this is not expected to run concurrently against the
same data).

If new Signals arrive and expand a location's evidence, the resulting
``supporting_signal_ids`` set differs from any existing Lead's, so a new
Lead is created for the new evidence rather than mutating the old one in
place. ``LeadRepository`` has no update mechanism for a Lead's evidence
(only ``update_verification_status``), and silently rewriting the
evidence behind an already-generated -- possibly already verified or
exported -- Lead is a materially different, higher-risk change than
deduplicating exact repeats; nothing here loses or fabricates data, and
both the old and new Lead remain in the audit trail.
"""

from __future__ import annotations

from collections.abc import Sequence

from loguru import logger

from app.application.interfaces.lead_generation import LeadGeneratorInterface
from app.application.interfaces.repositories import AuditLogRepository, LeadRepository
from app.application.interfaces.rule_engine import RuleMatch
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.domain.lead import Lead


class LeadGenerationService:
    """Persists Leads built by a LeadGeneratorInterface implementation, idempotently."""

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
        """Build Leads from ``matches`` and persist only the ones not already generated.

        Returns only the Leads newly persisted by this call -- a candidate
        matching an already-existing Lead's identity is skipped entirely
        (no new row, no new audit entry), so a caller that re-verifies or
        re-exports whatever this returns (e.g. the pipeline's own next
        stage) correctly does no redundant work on a no-op re-run.
        """
        candidates = self._lead_generator.generate(matches)

        persisted: list[Lead] = []
        skipped = 0
        for lead in candidates:
            existing = self._lead_repository.find_by_identity(
                lead.lead_type, lead.supporting_signal_ids
            )
            if existing is not None:
                skipped += 1
                continue

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
        if skipped:
            logger.info(
                "Lead generation: skipped {} already-generated lead(s) as duplicates.", skipped
            )
        return persisted
