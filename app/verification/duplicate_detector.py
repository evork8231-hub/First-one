"""Configurable duplicate detection for Signals.

Compares a candidate Signal against a pool of existing Signals using, in
order of authority: an exact public-identifier match, coordinate
proximity, an exact phone-number match (if publicly present in
``metadata``), and finally RapidFuzz text similarity over composed
address text. No similarity value is hardcoded -- every threshold comes
from ``app.config.settings.DuplicateDetectionConfig``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from rapidfuzz import fuzz

from app.config.settings import DuplicateDetectionConfig
from app.domain.signal import Signal
from app.verification.geo import haversine_distance_meters


class DuplicateStatus(StrEnum):
    """The tri-state outcome of a duplicate comparison."""

    DUPLICATE = "duplicate"
    POSSIBLE_DUPLICATE = "possible_duplicate"
    UNIQUE = "unique"


@dataclass(frozen=True)
class DuplicateCheckResult:
    """The outcome of comparing one Signal against a candidate pool."""

    status: DuplicateStatus
    reason: str
    matched_signal_id: UUID | None = None
    similarity_score: float | None = None


def _composite_address_text(signal: Signal) -> str:
    """Compose the fine-grained address detail available for fuzzy comparison.

    Deliberately excludes ``county``/``municipality``: candidates are
    already scoped to the same county and municipality before reaching
    this comparison (see ``DuplicateSignalVerifier``), so including them
    would add no discriminating power and would falsely match any two
    unrelated signals that simply share a municipality and lack a
    finer-grained address. Returns "" when no street-level detail exists
    at all, so callers correctly treat that as "nothing to compare".
    """
    if signal.address is None:
        return ""
    parts = [
        value
        for value in (
            signal.address.settlement,
            signal.address.street,
            signal.address.house_number,
            signal.address.raw,
        )
        if value
    ]
    return " ".join(parts).casefold()


def _phone_number(signal: Signal) -> str | None:
    """Return a publicly-collected phone number if the collector recorded one, else None.

    Signal has no first-class phone field (it would not apply to most
    signal types); a collector that observes one records it under
    ``metadata["phone"]``. Never fabricated if absent.
    """
    phone = signal.metadata.get("phone")
    return str(phone).strip() if phone else None


class DuplicateDetector:
    """Pure comparison logic: given a signal and a candidate pool, classify duplication.

    Deliberately takes the candidate pool as a plain argument rather than
    querying a repository itself, so it is trivially unit-testable and
    reusable regardless of how candidates were scoped/fetched.
    """

    def __init__(self, config: DuplicateDetectionConfig) -> None:
        self._config = config

    def check(self, signal: Signal, candidates: list[Signal]) -> DuplicateCheckResult:
        """Classify ``signal`` against ``candidates`` (which may include ``signal`` itself)."""
        relevant = [
            c for c in candidates if c.id != signal.id and c.signal_type == signal.signal_type
        ]

        identifier_match = self._check_building_identifier(signal, relevant)
        if identifier_match is not None:
            return identifier_match

        phone_match = self._check_phone_number(signal, relevant)
        if phone_match is not None:
            return phone_match

        coordinate_match = self._check_coordinates(signal, relevant)
        if coordinate_match is not None:
            return coordinate_match

        fuzzy_match = self._check_fuzzy_address(signal, relevant)
        if fuzzy_match is not None:
            return fuzzy_match

        return DuplicateCheckResult(
            status=DuplicateStatus.UNIQUE, reason="No matching signal found."
        )

    @staticmethod
    def _check_building_identifier(
        signal: Signal, candidates: list[Signal]
    ) -> DuplicateCheckResult | None:
        if signal.building_identifier is None:
            return None
        for candidate in candidates:
            if candidate.building_identifier == signal.building_identifier:
                return DuplicateCheckResult(
                    status=DuplicateStatus.DUPLICATE,
                    reason=(
                        f"Same public identifier {signal.building_identifier!r} as "
                        f"signal {candidate.id}."
                    ),
                    matched_signal_id=candidate.id,
                )
        return None

    @staticmethod
    def _check_phone_number(
        signal: Signal, candidates: list[Signal]
    ) -> DuplicateCheckResult | None:
        signal_phone = _phone_number(signal)
        if signal_phone is None:
            return None
        for candidate in candidates:
            if _phone_number(candidate) == signal_phone:
                return DuplicateCheckResult(
                    status=DuplicateStatus.DUPLICATE,
                    reason=f"Same publicly-listed phone number as signal {candidate.id}.",
                    matched_signal_id=candidate.id,
                )
        return None

    def _check_coordinates(
        self, signal: Signal, candidates: list[Signal]
    ) -> DuplicateCheckResult | None:
        if signal.coordinates is None:
            return None
        for candidate in candidates:
            if candidate.coordinates is None:
                continue
            distance = haversine_distance_meters(signal.coordinates, candidate.coordinates)
            if distance <= self._config.coordinate_duplicate_radius_meters:
                return DuplicateCheckResult(
                    status=DuplicateStatus.DUPLICATE,
                    reason=(
                        f"Coordinates {distance:.1f}m from signal {candidate.id}, within the "
                        f"configured {self._config.coordinate_duplicate_radius_meters:.0f}m radius."
                    ),
                    matched_signal_id=candidate.id,
                )
        return None

    def _check_fuzzy_address(
        self, signal: Signal, candidates: list[Signal]
    ) -> DuplicateCheckResult | None:
        signal_text = _composite_address_text(signal)
        if not signal_text:
            return None

        best: tuple[Signal, float] | None = None
        for candidate in candidates:
            candidate_text = _composite_address_text(candidate)
            if not candidate_text:
                continue
            score = fuzz.token_sort_ratio(signal_text, candidate_text)
            if best is None or score > best[1]:
                best = (candidate, score)

        if best is None:
            return None
        candidate, score = best

        if score >= self._config.fuzzy_duplicate_threshold:
            return DuplicateCheckResult(
                status=DuplicateStatus.DUPLICATE,
                reason=f"Address text {score:.1f}% similar to signal {candidate.id}.",
                matched_signal_id=candidate.id,
                similarity_score=score,
            )
        if score >= self._config.fuzzy_possible_duplicate_threshold:
            return DuplicateCheckResult(
                status=DuplicateStatus.POSSIBLE_DUPLICATE,
                reason=f"Address text {score:.1f}% similar to signal {candidate.id}.",
                matched_signal_id=candidate.id,
                similarity_score=score,
            )
        return None
