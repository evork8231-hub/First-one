"""Safe XML parsing for untrusted external feeds (e.g. Ilmateenistus RSS/XML).

Python's stdlib ``xml.etree.ElementTree.fromstring`` resolves internally
declared general entities by default, making it vulnerable to
entity-expansion ("billion laughs") attacks when parsing XML from an
external source. This module parses through ``xml.parsers.expat``
directly with DOCTYPE declarations rejected outright, so no entity can be
declared in the first place -- the same mitigation strategy used by the
``defusedxml`` package, implemented here without adding a new dependency.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from xml.parsers import expat

from app.core.exceptions import CollectorError


def safe_parse_xml(content: str | bytes) -> ET.Element:
    """Parse ``content`` into an ElementTree root, rejecting any DOCTYPE declaration.

    Raises:
        CollectorError: If the document is malformed, or declares a
            DOCTYPE (and therefore could declare an entity).
    """
    parser = expat.ParserCreate()
    builder = ET.TreeBuilder()

    def _reject_doctype(
        doctype_name: str, system_id: str | None, public_id: str | None, has_internal_subset: bool
    ) -> None:
        raise CollectorError(
            "Rejected XML document: DOCTYPE declarations are not permitted "
            "(protects against XML entity-expansion attacks)."
        )

    parser.StartDoctypeDeclHandler = _reject_doctype
    parser.StartElementHandler = builder.start
    parser.EndElementHandler = builder.end
    parser.CharacterDataHandler = builder.data

    data = content.encode("utf-8") if isinstance(content, str) else content
    try:
        parser.Parse(data, True)
    except expat.ExpatError as exc:
        raise CollectorError(f"Malformed XML document: {exc}") from exc

    return builder.close()


def find_text(element: ET.Element, path: str) -> str | None:
    """Return the stripped text content at ``path`` relative to ``element``, or ``None``."""
    found = element.find(path)
    if found is None or found.text is None:
        return None
    stripped = found.text.strip()
    return stripped or None


def find_float(element: ET.Element, path: str) -> float | None:
    """Return the float value of ``path``'s text, or ``None`` if absent/unparseable.

    Never raises and never substitutes a guessed value -- an unparseable
    or missing value is reported as ``None``.
    """
    text = find_text(element, path)
    if text is None:
        return None
    try:
        return float(text)
    except ValueError:
        return None
