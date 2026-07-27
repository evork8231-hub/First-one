"""Field-map discovery: suggests candidate ``field_map`` keys, never applies them.

Structured collectors (currently ``EhitisregisterCollector``) map a
source's real JSON keys to canonical Signal fields via a configurable
``field_map`` (see ``app.config.settings.EhitisregisterConfig``) --
ordered candidate key lists an operator edits in YAML once the source's
real schema is known. This module closes the loop the other direction:
given a sample of real records and the currently configured field_map, it
finds keys the config does not yet account for and ranks canonical-field
guesses for each one by string similarity (RapidFuzz), with a confidence
score.

This never writes configuration and never guesses a value for a Signal
field -- it only produces suggestions for a human to review and, if
correct, add to ``field_map`` themselves. Per the platform's fail-closed
policy, an unmapped key with no plausible match is reported as such, not
silently dropped or invented.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz


@dataclass(frozen=True)
class FieldMapSuggestion:
    """A single candidate mapping from an observed source key to a canonical field."""

    source_key: str
    canonical_field: str
    confidence: float
    sample_value: Any


def find_unmapped_keys(
    records: Sequence[Mapping[str, Any]], field_map: Mapping[str, Sequence[str]]
) -> set[str]:
    """Return every key observed in ``records`` that no canonical field's candidate list covers."""
    mapped_keys = {key for candidates in field_map.values() for key in candidates}
    observed_keys = {key for record in records for key in record}
    return observed_keys - mapped_keys


def sample_value_for_key(records: Sequence[Mapping[str, Any]], key: str) -> Any:  # noqa: ANN401
    """Return the first non-empty value found for ``key`` across ``records``, or ``None``."""
    for record in records:
        if key in record and record[key] not in (None, ""):
            return record[key]
    return None


def suggest_field_map(
    records: Sequence[Mapping[str, Any]],
    field_map: Mapping[str, Sequence[str]],
    *,
    score_cutoff: float = 60.0,
    max_suggestions_per_key: int = 3,
) -> dict[str, list[FieldMapSuggestion]]:
    """Suggest canonical-field candidates for every key ``field_map`` does not yet cover.

    Each unmapped key is fuzzy-matched (RapidFuzz's ``token_sort_ratio``)
    against every canonical field's name and its currently configured
    candidate synonyms; the best-scoring canonical fields at or above
    ``score_cutoff`` (0-100) are returned, most confident first, capped at
    ``max_suggestions_per_key``. A key with no match at or above the
    cutoff is simply absent from the result -- callers must not infer a
    mapping in that case, only flag the key as unmapped.
    """
    unmapped_keys = find_unmapped_keys(records, field_map)

    suggestions: dict[str, list[FieldMapSuggestion]] = {}
    for key in sorted(unmapped_keys):
        scored: list[tuple[str, float]] = []
        for canonical_field, known_candidates in field_map.items():
            names_to_compare = [canonical_field, *known_candidates]
            best_score = max(fuzz.token_sort_ratio(key, name) for name in names_to_compare)
            scored.append((canonical_field, best_score))
        scored.sort(key=lambda pair: pair[1], reverse=True)

        top = [
            FieldMapSuggestion(
                source_key=key,
                canonical_field=canonical_field,
                confidence=round(score / 100.0, 3),
                sample_value=sample_value_for_key(records, key),
            )
            for canonical_field, score in scored
            if score >= score_cutoff
        ][:max_suggestions_per_key]
        if top:
            suggestions[key] = top

    return suggestions
