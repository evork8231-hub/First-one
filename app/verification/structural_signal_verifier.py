"""A verifier that checks a Signal's internal structural integrity.

This verifier never contacts an external source -- it only checks that
the Signal, as collected, is internally consistent and meets the minimum
data-quality bar configured for the platform. Verifiers that
cross-reference an external public registry to confirm a fact are a
future phase; building one here would require calling a real,
documented API, which is out of scope for the foundation.

Every check below is deterministic and configuration-driven: nothing is
guessed, repaired, or inferred. A signal that fails any check is
rejected outright rather than silently coerced into a "close enough"
shape.
"""

from __future__ import annotations

import re

from app.application.interfaces.verifier import SignalVerifier, VerificationResult
from app.config.settings import CoordinateBounds
from app.domain.enums import Country, VerificationStatus
from app.domain.signal import Signal


class StructuralSignalVerifier(SignalVerifier):
    """Rejects Signals that are structurally implausible or below a confidence floor.

    Rejection conditions:

    - ``country`` is not Estonia.
    - ``confidence`` is below the configured floor.
    - ``raw_payload`` is empty (a signal must retain the data it was built from).
    - ``source_url``, if present, is not a well-formed HTTP(S) URL.
    - ``address.postal_code``, if present, does not match the configured
      Estonian postal code pattern (malformed address). This verifier
      never repairs or guesses a missing/invalid address component --
      it only rejects.
    - ``coordinates``, if present, fall outside ``coordinate_bounds``
      (i.e. outside Estonia).
    - ``coordinates`` are absent while ``require_coordinates`` is enabled.
    """

    def __init__(
        self,
        *,
        min_confidence: float = 0.0,
        coordinate_bounds: CoordinateBounds | None = None,
        require_coordinates: bool = False,
        postal_code_pattern: str = r"^\d{5}$",
    ) -> None:
        if not 0.0 <= min_confidence <= 1.0:
            raise ValueError("min_confidence must be within [0.0, 1.0].")
        self._min_confidence = min_confidence
        self._coordinate_bounds = coordinate_bounds or CoordinateBounds()
        self._require_coordinates = require_coordinates
        self._postal_code_regex = re.compile(postal_code_pattern)

    @property
    def name(self) -> str:
        return "structural_signal_verifier"

    async def verify(self, signal: Signal) -> VerificationResult:
        failures: list[str] = []

        if signal.country != Country.ESTONIA:
            failures.append(f"country {signal.country.value!r} is not Estonia")

        if not signal.county.strip():
            failures.append("county is missing")
        if not signal.municipality.strip():
            failures.append("municipality is missing")

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

        failures.extend(self._address_failures(signal))
        failures.extend(self._coordinate_failures(signal))

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

    def _address_failures(self, signal: Signal) -> list[str]:
        if signal.address is None:
            return []
        postal_code = signal.address.postal_code
        if postal_code is not None and not self._postal_code_regex.match(postal_code):
            return [f"address.postal_code {postal_code!r} is malformed"]
        return []

    def _coordinate_failures(self, signal: Signal) -> list[str]:
        if signal.coordinates is None:
            if self._require_coordinates:
                return ["coordinates are required but missing"]
            return []
        if not self._coordinate_bounds.contains(
            latitude=signal.coordinates.latitude, longitude=signal.coordinates.longitude
        ):
            return [
                f"coordinates ({signal.coordinates.latitude}, {signal.coordinates.longitude}) "
                "fall outside Estonia"
            ]
        return []
