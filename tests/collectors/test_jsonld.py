"""Tests for app.collectors.jsonld."""

from __future__ import annotations

from app.collectors.jsonld import (
    extract_jsonld_blocks,
    find_additional_property,
    find_first_of_type,
    get_nested,
)


def _wrap(*script_bodies: str) -> str:
    scripts = "\n".join(
        f'<script type="application/ld+json">{body}</script>' for body in script_bodies
    )
    return f"<html><head>{scripts}</head><body></body></html>"


def test_extract_single_block() -> None:
    html = _wrap('{"@type": "Product", "name": "Test"}')
    blocks = extract_jsonld_blocks(html)
    assert blocks == [{"@type": "Product", "name": "Test"}]


def test_extract_multiple_blocks() -> None:
    html = _wrap('{"@type": "Product", "name": "A"}', '{"@type": "Offer", "price": "100"}')
    blocks = extract_jsonld_blocks(html)
    assert len(blocks) == 2


def test_extract_handles_malformed_block_without_raising() -> None:
    html = _wrap("{not valid json", '{"@type": "Product", "name": "Still parses"}')
    blocks = extract_jsonld_blocks(html)
    assert blocks == [{"@type": "Product", "name": "Still parses"}]


def test_extract_handles_graph_wrapper() -> None:
    html = _wrap('{"@graph": [{"@type": "Product", "name": "A"}, {"@type": "Offer"}]}')
    blocks = extract_jsonld_blocks(html)
    assert len(blocks) == 2


def test_extract_handles_top_level_array() -> None:
    html = _wrap('[{"@type": "Product", "name": "A"}, {"@type": "Product", "name": "B"}]')
    blocks = extract_jsonld_blocks(html)
    assert len(blocks) == 2


def test_extract_returns_empty_list_when_no_scripts_present() -> None:
    assert extract_jsonld_blocks("<html><body>No JSON-LD here</body></html>") == []


def test_find_first_of_type_matches_string_type() -> None:
    blocks = [{"@type": "WebPage"}, {"@type": "Product", "name": "Match"}]
    result = find_first_of_type(blocks, frozenset({"Product"}))
    assert result == {"@type": "Product", "name": "Match"}


def test_find_first_of_type_matches_list_type() -> None:
    blocks = [{"@type": ["Thing", "RealEstateListing"], "name": "Match"}]
    result = find_first_of_type(blocks, frozenset({"RealEstateListing"}))
    assert result is not None
    assert result["name"] == "Match"


def test_find_first_of_type_returns_none_when_absent() -> None:
    blocks = [{"@type": "WebPage"}]
    assert find_first_of_type(blocks, frozenset({"Product"})) is None


def test_get_nested_walks_dotted_path() -> None:
    block = {"address": {"addressRegion": "Harju", "addressLocality": "Tallinn"}}
    assert get_nested(block, "address", "addressRegion") == "Harju"


def test_get_nested_returns_none_for_missing_path() -> None:
    block = {"address": {"addressRegion": "Harju"}}
    assert get_nested(block, "address", "addressLocality") is None
    assert get_nested(block, "offers", "price") is None


def test_find_additional_property_matches_by_name_keyword() -> None:
    block = {
        "additionalProperty": [
            {"@type": "PropertyValue", "name": "Energy class", "value": "C"},
            {"@type": "PropertyValue", "name": "House type", "value": "Detached"},
        ]
    }
    assert find_additional_property(block, "energia") is None  # exact keyword not present
    assert find_additional_property(block, "energy") == "C"


def test_find_additional_property_returns_none_when_absent() -> None:
    assert find_additional_property({}, "energy") is None
