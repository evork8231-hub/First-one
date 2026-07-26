"""Tests for app.collectors.phrase_matching."""

from __future__ import annotations

from app.collectors.phrase_matching import find_renovation_indicators
from app.domain.enums import SignalType


def test_finds_explicit_needs_renovation_phrase() -> None:
    matches = find_renovation_indicators("Maja vajab remonti, aga asukoht on hea.")
    assert any(m.signal_type == SignalType.RENOVATION_MENTION for m in matches)


def test_finds_explicit_original_kitchen_phrase() -> None:
    matches = find_renovation_indicators("Köögis on originaalne köök 1980ndatest.")
    assert any(m.signal_type == SignalType.KITCHEN_MENTION for m in matches)


def test_finds_explicit_roof_condition_phrase() -> None:
    matches = find_renovation_indicators("Katuse seisukord halb, vajab välja vahetamist.")
    assert any(m.signal_type == SignalType.ROOF_MENTION for m in matches)


def test_matching_is_case_insensitive() -> None:
    matches = find_renovation_indicators("VAJAB REMONTI kiiresti.")
    assert any(m.signal_type == SignalType.RENOVATION_MENTION for m in matches)


def test_returns_multiple_matches_when_several_phrases_present() -> None:
    text = "Vajab remonti. Originaalne köök. Katuse seisukord halb."
    matches = find_renovation_indicators(text)
    matched_types = {m.signal_type for m in matches}
    assert matched_types == {
        SignalType.RENOVATION_MENTION,
        SignalType.KITCHEN_MENTION,
        SignalType.ROOF_MENTION,
    }


def test_returns_empty_list_when_no_phrase_present() -> None:
    matches = find_renovation_indicators("Ilus renoveeritud maja heas seisukorras.")
    assert matches == []


def test_never_infers_from_related_but_non_matching_text() -> None:
    # "new kitchen" is the opposite claim -- must not match "original kitchen".
    matches = find_renovation_indicators("Uus köök paigaldatud 2023.")
    assert matches == []


def test_returns_empty_list_for_none_text() -> None:
    assert find_renovation_indicators(None) == []


def test_returns_empty_list_for_blank_text() -> None:
    assert find_renovation_indicators("   ") == []
