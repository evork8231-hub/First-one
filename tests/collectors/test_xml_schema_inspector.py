"""Tests for app.collectors.xml_schema_inspector."""

from __future__ import annotations

import pytest
from app.collectors.xml_schema_inspector import inspect_xml
from app.core.exceptions import CollectorError

_FORECAST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<forecast>
  <tabular>
    <time from="2026-07-27T06:00:00" to="2026-07-27T18:00:00">
      <place name="Tallinn" phenomenon="Tugev vihm">
        <text>Paduvihm ja äike.</text>
        <wind><gust>18.5</gust></wind>
      </place>
      <place name="Tartu" phenomenon="Selge">
        <text>Selge ilm.</text>
        <wind><gust>4.0</gust></wind>
      </place>
    </time>
  </tabular>
</forecast>
"""


def test_inspect_xml_reports_root_tag_and_total_elements() -> None:
    report = inspect_xml(_FORECAST_XML)
    assert report.root_tag == "forecast"
    # forecast, tabular, time, place*2, text*2, wind*2, gust*2 = 11
    assert report.total_elements == 11


def test_inspect_xml_groups_repeated_elements_under_one_path() -> None:
    report = inspect_xml(_FORECAST_XML)
    place_summary = next(e for e in report.elements if e.path == "forecast/tabular/time/place")
    assert place_summary.occurrence_count == 2


def test_inspect_xml_reports_attribute_names_and_a_sample_value() -> None:
    report = inspect_xml(_FORECAST_XML)
    place_summary = next(e for e in report.elements if e.path == "forecast/tabular/time/place")
    assert set(place_summary.attribute_names) == {"name", "phenomenon"}
    assert place_summary.attribute_samples["name"] in ("Tallinn", "Tartu")


def test_inspect_xml_reports_text_samples() -> None:
    report = inspect_xml(_FORECAST_XML)
    text_summary = next(e for e in report.elements if e.path == "forecast/tabular/time/place/text")
    assert "Paduvihm ja äike." in text_summary.text_samples


def test_inspect_xml_deep_nested_path_is_correct() -> None:
    report = inspect_xml(_FORECAST_XML)
    gust_summary = next(
        e for e in report.elements if e.path == "forecast/tabular/time/place/wind/gust"
    )
    assert gust_summary.occurrence_count == 2
    assert "18.5" in gust_summary.text_samples or "4.0" in gust_summary.text_samples


def test_inspect_xml_max_samples_per_path_caps_samples() -> None:
    xml = "<root>" + "".join(f"<item>{i}</item>" for i in range(10)) + "</root>"
    report = inspect_xml(xml, max_samples_per_path=2)
    item_summary = next(e for e in report.elements if e.path == "root/item")
    assert len(item_summary.text_samples) == 2
    assert item_summary.occurrence_count == 10


def test_inspect_xml_max_paths_caps_distinct_paths_returned() -> None:
    xml = "<root>" + "".join(f"<field{i}>x</field{i}>" for i in range(5)) + "</root>"
    report = inspect_xml(xml, max_paths=3)
    assert len(report.elements) == 3


def test_inspect_xml_rejects_doctype() -> None:
    malicious = '<?xml version="1.0"?><!DOCTYPE foo><root/>'
    with pytest.raises(CollectorError):
        inspect_xml(malicious)


def test_inspect_xml_rejects_malformed_xml() -> None:
    with pytest.raises(CollectorError):
        inspect_xml("<root><unclosed></root>")
