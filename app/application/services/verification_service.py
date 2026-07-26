"""VerificationService: runs pluggable verifiers against Signals and Leads."""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from loguru import logger

from app.application.interfaces.repositories import (
    AuditLogRepository,
    LeadRepository,
    SignalRepository,
)
from app.application.interfaces.verifier import LeadVerifier, SignalVerifier, VerificationResult
from app.core.exceptions import EntityNotFoundError, VerificationError
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType, VerificationStatus
from app.domain.lead import Lead
from app.domain.signal import Signal


class VerificationService:
    """Runs the configured verifiers against Signals and Leads.

    A Signal or Lead is VERIFIED only if every registered verifier for its
    kind agrees; it is REJECTED as soon as any verifier rejects it. An
    entity stays UNVERIFIED, and this service raises VerificationError,
    if a verifier cannot reach a decision -- verification never silently
    defaults to a status.
    """

    def __init__(
        self,
        signal_repository: SignalRepository,
        lead_repository: LeadRepository,
        audit_log_repository: AuditLogRepository,
        signal_verifiers: Sequence[SignalVerifier],
        lead_verifiers: Sequence[LeadVerifier],
    ) -> None:
        self._signal_repository = signal_repository
        self._lead_repository = lead_repository
        self._audit_log_repository = audit_log_repository
        self._signal_verifiers = list(signal_verifiers)
        self._lead_verifiers = list(lead_verifiers)

    async def verify_signal(self, signal_id: UUID) -> Signal:
        """Run every registered SignalVerifier against a single signal."""
        signal = self._signal_repository.get_by_id(signal_id)
        if signal is None:
            raise EntityNotFoundError(f"No signal found with id {signal_id}.")

        results = [await verifier.verify(signal) for verifier in self._signal_verifiers]
        status = self._combine(results, entity_label=f"signal {signal_id}")

        updated = self._signal_repository.update_verification(signal_id, status)
        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=(
                    AuditEventType.SIGNAL_VERIFIED
                    if status == VerificationStatus.VERIFIED
                    else AuditEventType.SIGNAL_REJECTED
                ),
                entity_type="Signal",
                entity_id=signal_id,
                message=f"Signal {signal_id} verification result: {status.value}.",
                context={"reasons": [r.reason for r in results]},
            )
        )
        return updated

    async def verify_pending_signals(self, *, limit: int = 100) -> list[Signal]:
        """Verify every currently unverified signal, up to ``limit``."""
        pending = self._signal_repository.list_unverified(limit=limit)
        return [await self.verify_signal(signal.id) for signal in pending]

    async def verify_lead(self, lead_id: UUID) -> Lead:
        """Run every registered LeadVerifier against a single lead."""
        lead = self._lead_repository.get_by_id(lead_id)
        if lead is None:
            raise EntityNotFoundError(f"No lead found with id {lead_id}.")

        results = [await verifier.verify(lead) for verifier in self._lead_verifiers]
        status = self._combine(results, entity_label=f"lead {lead_id}")

        updated = self._lead_repository.update_verification_status(lead_id, status)
        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=(
                    AuditEventType.LEAD_VERIFIED
                    if status == VerificationStatus.VERIFIED
                    else AuditEventType.LEAD_REJECTED
                ),
                entity_type="Lead",
                entity_id=lead_id,
                message=f"Lead {lead_id} verification result: {status.value}.",
                context={"reasons": [r.reason for r in results]},
            )
        )
        return updated

    @staticmethod
    def _combine(results: Sequence[VerificationResult], *, entity_label: str) -> VerificationStatus:
        if not results:
            raise VerificationError(f"No verifiers are registered to evaluate {entity_label}.")
        if any(r.status == VerificationStatus.REJECTED for r in results):
            logger.info(
                "{} rejected by verification: {}", entity_label, [r.reason for r in results]
            )
            return VerificationStatus.REJECTED
        if all(r.status == VerificationStatus.VERIFIED for r in results):
            return VerificationStatus.VERIFIED
        raise VerificationError(
            f"Verifiers returned an inconclusive result set for {entity_label}: "
            f"{[r.status.value for r in results]}."
        )
