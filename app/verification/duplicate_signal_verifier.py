"""A verifier that rejects Signals detected as duplicates of an already-stored one.

Candidate signals are scoped to the same county and municipality (via
``SignalRepository.list_all``) and the same ``signal_type``, then handed
to ``DuplicateDetector`` for the actual comparison -- this class owns
only the repository lookup and the VERIFIED/REJECTED policy decision.
"""

from __future__ import annotations

from loguru import logger

from app.application.interfaces.repositories import SignalRepository
from app.application.interfaces.verifier import SignalVerifier, VerificationResult
from app.config.settings import DuplicateDetectionConfig
from app.domain.enums import VerificationStatus
from app.domain.signal import Signal
from app.verification.duplicate_detector import DuplicateDetector, DuplicateStatus


class DuplicateSignalVerifier(SignalVerifier):
    """Rejects Signals classified as DUPLICATE; POSSIBLE_DUPLICATE is policy-driven."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        detector: DuplicateDetector,
        config: DuplicateDetectionConfig,
    ) -> None:
        self._signal_repository = signal_repository
        self._detector = detector
        self._config = config

    @property
    def name(self) -> str:
        return "duplicate_signal_verifier"

    async def verify(self, signal: Signal) -> VerificationResult:
        if not self._config.enabled:
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                reason="Duplicate detection is disabled.",
            )

        candidates = self._signal_repository.list_all(
            county=signal.county,
            municipality=signal.municipality,
            limit=self._config.comparison_scope_limit,
        )
        result = self._detector.check(signal, candidates)

        logger.info(
            "Duplicate check for signal {}: {} ({})",
            signal.id,
            result.status.value,
            result.reason,
        )

        evidence: dict[str, object] = {
            "duplicate_status": result.status.value,
            "matched_signal_id": (
                str(result.matched_signal_id) if result.matched_signal_id is not None else None
            ),
            "similarity_score": result.similarity_score,
        }

        if result.status == DuplicateStatus.DUPLICATE:
            return VerificationResult(
                status=VerificationStatus.REJECTED,
                reason=f"Duplicate: {result.reason}",
                evidence=evidence,
            )

        if result.status == DuplicateStatus.POSSIBLE_DUPLICATE:
            if self._config.possible_duplicate_policy == "reject":
                return VerificationResult(
                    status=VerificationStatus.REJECTED,
                    reason=f"Possible duplicate (rejected per policy): {result.reason}",
                    evidence=evidence,
                )
            return VerificationResult(
                status=VerificationStatus.VERIFIED,
                reason=f"Possible duplicate (flagged, not rejected): {result.reason}",
                evidence=evidence,
            )

        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            reason="No duplicate detected.",
            evidence=evidence,
        )
