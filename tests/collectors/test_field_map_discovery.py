"""Tests for app.collectors.field_map_discovery."""

from __future__ import annotations

from app.collectors.field_map_discovery import (
    find_unmapped_keys,
    sample_value_for_key,
    suggest_field_map,
)

_FIELD_MAP = {
    "county": ["maakond", "county"],
    "municipality": ["omavalitsus", "vald", "municipality"],
    "construction_year": ["ehitusaasta", "valmimisaasta", "construction_year"],
}


def test_find_unmapped_keys_excludes_known_candidates() -> None:
    records = [{"maakond": "Harju", "omavalitsus": "Tallinn", "unknown_field": "x"}]

    unmapped = find_unmapped_keys(records, _FIELD_MAP)

    assert unmapped == {"unknown_field"}


def test_find_unmapped_keys_with_fully_covered_records_is_empty() -> None:
    records = [{"maakond": "Harju", "omavalitsus": "Tallinn"}]
    assert find_unmapped_keys(records, _FIELD_MAP) == set()


def test_sample_value_for_key_returns_first_non_empty_value() -> None:
    records = [{"x": None}, {"x": ""}, {"x": "real value"}, {"x": "second"}]
    assert sample_value_for_key(records, "x") == "real value"


def test_sample_value_for_key_absent_returns_none() -> None:
    assert sample_value_for_key([{"a": 1}], "does_not_exist") is None


def test_suggest_field_map_matches_a_near_identical_unmapped_key() -> None:
    """'ehitusaasta_uus' is close to the already-known 'ehitusaasta' synonym."""
    records = [{"ehitusaasta_uus": 1999}]

    suggestions = suggest_field_map(records, _FIELD_MAP)

    assert "ehitusaasta_uus" in suggestions
    top = suggestions["ehitusaasta_uus"][0]
    assert top.canonical_field == "construction_year"
    assert top.sample_value == 1999
    assert 0.0 < top.confidence <= 1.0


def test_suggest_field_map_omits_keys_with_no_confident_match() -> None:
    records = [{"totally_unrelated_xyz_123": "value"}]

    suggestions = suggest_field_map(records, _FIELD_MAP, score_cutoff=95.0)

    assert suggestions == {}


def test_suggest_field_map_never_reports_an_already_mapped_key() -> None:
    records = [{"maakond": "Harju"}]

    suggestions = suggest_field_map(records, _FIELD_MAP)

    assert suggestions == {}


def test_suggest_field_map_caps_suggestions_per_key() -> None:
    records = [{"county_x": "value"}]

    suggestions = suggest_field_map(
        records, _FIELD_MAP, score_cutoff=0.0, max_suggestions_per_key=1
    )

    assert len(suggestions["county_x"]) == 1


def test_suggest_field_map_ranks_best_match_first() -> None:
    records = [{"maakonnad": "Harju"}]  # closer to 'maakond' (county) than any other field

    suggestions = suggest_field_map(records, _FIELD_MAP, score_cutoff=0.0)

    assert suggestions["maakonnad"][0].canonical_field == "county"
