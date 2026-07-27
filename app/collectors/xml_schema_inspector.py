"""XML schema inspection: visualizes an XML document's real element structure.

Backs the ``sigint inspect-xml`` CLI command for the Ilmateenistus
forecast-XML collector (see
``app.collectors.ilmateenistus_collector.IlmateenistusCollector``), whose
element paths (``phenomenon``, ``wind/gust``, ``text``, the ``date``/
``name`` attributes) were corroborated via documentation search but never
directly confirmed against the live feed.

This module performs pure, offline analysis of an already-parsed XML
document (via ``app.collectors.xml_utils.safe_parse_xml``, so the same
DOCTYPE/entity protection applies here as everywhere else XML is parsed):
it walks every element, groups them by structural path, and reports each
path's occurrence count, observed attribute names with a sample value,
and sample text content. It never infers a field mapping and never
rewrites parser code -- an operator reviews the real structure here and,
if the collector's hardcoded paths need correcting, edits the collector
source themselves.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass

from app.collectors.xml_utils import safe_parse_xml


@dataclass(frozen=True)
class XmlElementSummary:
    """Everything observed about every element sharing one structural path."""

    path: str
    occurrence_count: int
    attribute_names: tuple[str, ...]
    attribute_samples: dict[str, str]
    text_samples: list[str]


@dataclass(frozen=True)
class XmlSchemaReport:
    """The full element-structure summary of one XML document."""

    root_tag: str
    total_elements: int
    elements: list[XmlElementSummary]


def inspect_xml(
    xml_text: str | bytes, *, max_samples_per_path: int = 3, max_paths: int = 200
) -> XmlSchemaReport:
    """Parse ``xml_text`` and summarize its element structure.

    ``path`` is the sequence of tag names from the root to each element,
    joined by ``/`` (e.g. ``"forecast/tabular/time/place"``) -- elements at
    the same path are grouped together regardless of how many times that
    structure repeats, since a repeating path (e.g. many ``place``
    elements) is itself useful information, not noise to collapse away.

    Raises:
        CollectorError: If ``xml_text`` is malformed or declares a
            DOCTYPE -- the same protection ``safe_parse_xml`` applies
            everywhere else in the codebase.
    """
    root = safe_parse_xml(xml_text)

    paths: dict[str, _PathAccumulator] = {}
    total_elements = 0

    def walk(element: ET.Element, path: str) -> None:
        nonlocal total_elements
        total_elements += 1
        accumulator = paths.setdefault(path, _PathAccumulator())
        accumulator.record(element, max_samples_per_path=max_samples_per_path)
        for child in element:
            walk(child, f"{path}/{child.tag}")

    walk(root, root.tag)

    elements = sorted(
        (accumulator.to_summary(path) for path, accumulator in paths.items()),
        key=lambda summary: summary.path,
    )
    return XmlSchemaReport(
        root_tag=root.tag, total_elements=total_elements, elements=elements[:max_paths]
    )


class _PathAccumulator:
    """Mutable, per-path accumulator used only while walking the tree."""

    def __init__(self) -> None:
        self.count = 0
        self._attribute_samples: dict[str, list[str]] = {}
        self.text_samples: list[str] = []

    def record(self, element: ET.Element, *, max_samples_per_path: int) -> None:
        self.count += 1
        for attr_name, attr_value in element.attrib.items():
            samples = self._attribute_samples.setdefault(attr_name, [])
            if len(samples) < max_samples_per_path and attr_value not in samples:
                samples.append(attr_value)
        text = (element.text or "").strip()
        if text and len(self.text_samples) < max_samples_per_path and text not in self.text_samples:
            self.text_samples.append(text)

    def to_summary(self, path: str) -> XmlElementSummary:
        return XmlElementSummary(
            path=path,
            occurrence_count=self.count,
            attribute_names=tuple(sorted(self._attribute_samples)),
            attribute_samples={
                name: samples[0] for name, samples in self._attribute_samples.items()
            },
            text_samples=self.text_samples,
        )
