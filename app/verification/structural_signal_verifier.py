"""A verifier that checks a Signal's internal structural integrity.

This verifier never contacts an external source -- it only checks that
the Signal, as collected, is internally consistent and meets the minimum
data-quality bar configured for the platform. Verifiers that
cross-reference an external public registry to confirm a fact are a
future phase; building one here would require calling a real,
documented API, which is out of scope for the foundation.
"""

from __future__ import annotations

from app.application.interfaces.verifier import SignalVerifier, VerificationResult
from app.domain.enums import VerificationStatus
from app.domain.signal import Signal


class StructuralSignalVerifier(SignalVerifier):
    """Rejects Signals that are structurally implausible or below a confidence floor."""

    def __init__(self, *, min_confidence: float = 0.0) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be within [0.0, 1.0].")
        self._min_confidence = min_confidence

    @property
    def name(self) -> str:
        return "structural_signal_verifier"

    async def verify(self, signal: Signal) -> VerificationResult:
        failures: list[str] = []

        if signal.confidence < self._min_confidence:
            failures.append(
                f"confidence {signal.confidence:.2f} is below the required "
                f"minimum {self._min_confidence:.2f}"
            )
        if not signal.raw_payload:
            failures.append("raw_payload is empty; a signal must retain the data it was built from")
        if signal.source_url is not None and not signal.source_url.startswith(
            ("http://", "https://")
        ):
            failures.append(f"source_url {signal.source_url!r} is not a well-formed HTTP(S) URL")

        if failures:
            return VerificationResult(
                status=VerificationStatus.REJECTED,
                reason="; ".join(failures),
                evidence={"failures": failures},
            )
        return VerificationResult(
            status=VerificationStatus.VERIFIED,
            reason="Signal passed structural verification checks.",
            evidence={
                "min_confidence": self._min_confidence,
                "signal_confidence": signal.confidence,
            },
        )
