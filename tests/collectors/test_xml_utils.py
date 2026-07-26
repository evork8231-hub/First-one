"""Tests for app.collectors.xml_utils."""

from __future__ import annotations

import pytest
from app.collectors.xml_utils import find_float, find_text, safe_parse_xml
from app.core.exceptions import CollectorError


def test_safe_parse_xml_parses_valid_document() -> None:
    root = safe_parse_xml("<root><child>value</child></root>")
    assert root.tag == "root"
    assert root.find("child").text == "value"


def test_safe_parse_xml_rejects_malformed_document() -> None:
    with pytest.raises(CollectorError):
        safe_parse_xml("<root><unclosed></root>")


def test_safe_parse_xml_rejects_doctype_declarations() -> None:
    malicious = (
        '<?xml version="1.0"?>' '<!DOCTYPE root [<!ENTITY xxe "expanded">]>' "<root>&xxe;</root>"
    )
    with pytest.raises(CollectorError):
        safe_parse_xml(malicious)


def test_safe_parse_xml_accepts_bytes_input() -> None:
    root = safe_parse_xml(b"<root><child>value</child></root>")
    assert root.tag == "root"


def test_find_text_returns_stripped_value() -> None:
    root = safe_parse_xml("<root><name>  Tallinn  </name></root>")
    assert find_text(root, "name") == "Tallinn"


def test_find_text_returns_none_when_missing() -> None:
    root = safe_parse_xml("<root></root>")
    assert find_text(root, "name") is None


def test_find_text_returns_none_for_empty_element() -> None:
    root = safe_parse_xml("<root><name></name></root>")
    assert find_text(root, "name") is None


def test_find_float_parses_numeric_text() -> None:
    root = safe_parse_xml("<root><speed>12.5</speed></root>")
    assert find_float(root, "speed") == 12.5


def test_find_float_returns_none_for_unparseable_text() -> None:
    root = safe_parse_xml("<root><speed>strong</speed></root>")
    assert find_float(root, "speed") is None


def test_find_float_returns_none_when_missing() -> None:
    root = safe_parse_xml("<root></root>")
    assert find_float(root, "speed") is None
