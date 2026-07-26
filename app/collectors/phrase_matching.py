"""Explicit-phrase renovation-indicator matching for real estate listing text.

Per the platform's non-negotiable rules, a renovation indicator is only
ever extracted when the exact phrase is explicitly present in listing
text -- never inferred from a photo, price, building age, or general
"appearance". This module deliberately uses plain case-insensitive
substring matching (not fuzzy matching) so a match always corresponds to
text that was actually written, with no risk of a near-miss false
positive standing in for real evidence.

``BATHROOM_PHRASES`` was constructed by direct analogy to the kitchen
phrase given in the task brief (``köök`` -> ``vannituba``) since no
example bathroom phrase was supplied; verify it against real listing
language before relying on it in production.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.enums import SignalType

#: Phrases given directly in the task brief, plus the analogous bathroom
#: phrase noted above. Each list is intentionally short and literal.
RENOVATION_PHRASES: dict[SignalType, tuple[str, ...]] = {
    SignalType.RENOVATION_MENTION: ("vajab remonti",),
    SignalType.KITCHEN_MENTION: ("originaalne köök",),
    SignalType.BATHROOM_MENTION: ("originaalne vannituba",),
    SignalType.ROOF_MENTION: ("katuse seisukord halb",),
}


@dataclass(frozen=True)
class PhraseMatch:
    """One explicit phrase found in a piece of listing text."""

    signal_type: SignalType
    matched_phrase: str


def find_renovation_indicators(text: str | None) -> list[PhraseMatch]:
    """Return every explicit renovation-indicator phrase found in ``text``.

    Returns an empty list for ``None`` or blank text -- this function
    never infers a signal from the absence of text.
    """
    if not text:
        return []

    haystack = text.casefold()
    matches: list[PhraseMatch] = []
    for signal_type, phrases in RENOVATION_PHRASES.items():
        for phrase in phrases:
            if phrase in haystack:
                matches.append(PhraseMatch(signal_type=signal_type, matched_phrase=phrase))
    return matches
