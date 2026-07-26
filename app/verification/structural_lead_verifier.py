"""A verifier that checks a Lead is properly backed by verified Signals.

This is the enforcement point for the mission's core rule: a Lead may
only stand if every Signal it cites actually exists and has itself
already passed Signal verification.
"""

from __future__ import annotations

from app.application.interfaces.repositories import SignalRepository
from app.application.interfaces.verifier import LeadVerifier, VerificationResult
from app.domain.enums import VerificationStatus
from app.domain.lead import MIN_SUPPORTING_SIGNALS, Lead


class StructuralLeadVerifier(LeadVerifier):
    """Rejects Leads whose supporting signals are missing, unverified, or too few."""

    def __init__(self, signal_repository: SignalRepository, *, min_confidence: float = 0.0) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be within [0.0, 1.0].")
        self._signal_repository = signal_repository
        self._min_confidence = min_confidence

    @property
    def name(self) -> str:
        return "structural_lead_verifier"

    async def verify(self, lead: Lead) -> VerificationResult:
        failures: list[str] = []

        if len(lead.supporting_signal_ids) < MIN_SUPPORTING_SIGNALS:
            failures.append(
                f"only {len(lead.supporting_signal_ids)} supporting signal(s); "
                f"at least {MIN_SUPPORTING_SIGNALS} are required"
            )

        signals = self._signal_repository.list_by_ids(lead.supporting_signal_ids)
        found_ids = {signal.id for signal in signals}
        missing_ids = set(lead.supporting_signal_ids) - found_ids
        if missing_ids:
            failures.append(f"{len(missing_ids)} supporting signal id(s) do not exist in storage")

        unverified = [s for s in signals if s.verified != VerificationStatus.VERIFIED]
        if unverified:
            failures.append(f"{len(unverified)} supporting signal(s) are not themselves VERIFIED")

        if lead.estimated_confidence < self._min_confidence:
            failures.append(
                f"estimated_confidence {lead.estimated_confidence:.2f} is below the required "
                f"minimum {self._min_confidence:.2f}"
            )

        if failures:
            return VerificationResult(
                status=VerificationStatus.REJECTED,
                reason="; ".join(failures),
                evidence={"failures": failures},
            )
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            reason="Lead is backed entirely by existing, verified signals.",
            evidence={"supporting_signal_count": len(signals)},
        )
