"""Reusable JSON-LD (schema.org) extraction utilities.

Shared by every ``playwright_jsonld`` listing collector so JSON-LD parsing
is implemented exactly once. Tolerant of the real-world messiness of
JSON-LD embedded in HTML: multiple ``<script>`` blocks, malformed JSON,
``@graph`` wrappers, and single-object vs. list payloads.
"""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup
from loguru import logger

#: schema.org @type values that plausibly represent a real estate listing.
#: Deliberately broad (schema.org offers several overlapping vocabularies
#: for property listings) since narrowing incorrectly would silently drop
#: real listings rather than fail loudly.
REAL_ESTATE_TYPES = frozenset(
    {
        "Product",
        "Offer",
        "RealEstateListing",
        "House",
        "Apartment",
        "Residence",
        "SingleFamilyResidence",
        "ApartmentComplex",
    }
)


def extract_jsonld_blocks(html: str) -> list[dict[str, Any]]:
    """Return every JSON object found in ``<script type="application/ld+json">`` blocks.

    Handles, without raising:

    - Multiple script blocks on one page.
    - A block containing a JSON array instead of a single object.
    - A block wrapped in ``{"@graph": [...]}``.
    - Malformed JSON in one block (skipped and logged; other blocks still parse).
    """
    soup = BeautifulSoup(html, "html.parser")
    blocks: list[dict[str, Any]] = []

    for tag in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = tag.string or tag.get_text()
        if not raw or not raw.strip():
            continue
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            logger.warning("Skipping malformed JSON-LD block: {}", exc)
            continue
        blocks.extend(_flatten(parsed))

    return blocks


def _flatten(parsed: Any) -> list[dict[str, Any]]:  # noqa: ANN401
    """Normalize a parsed JSON-LD payload into a flat list of objects."""
    if isinstance(parsed, dict):
        if "@graph" in parsed and isinstance(parsed["@graph"], list):
            return [item for item in parsed["@graph"] if isinstance(item, dict)]
        return [parsed]
    if isinstance(parsed, list):
        return [item for item in parsed if isinstance(item, dict)]
    return []


def find_first_of_type(
    blocks: list[dict[str, Any]], types: frozenset[str]
) -> dict[str, Any] | None:
    """Return the first block whose ``@type`` (string or list) intersects ``types``."""
    for block in blocks:
        block_type = block.get("@type")
        type_names = {block_type} if isinstance(block_type, str) else set(block_type or [])
        if type_names & types:
            return block
    return None


def find_additional_property(block: dict[str, Any], name_keyword: str) -> str | None:
    """Search a schema.org ``additionalProperty`` list for a PropertyValue whose name matches.

    ``additionalProperty`` (a list of ``PropertyValue`` objects, each with
    a ``name`` and ``value``) is a standard schema.org extension point
    sites commonly use for attributes with no dedicated property (e.g.
    energy class, house type). Returns ``None`` if no matching entry
    exists -- never guesses a value from an unrelated property.
    """
    properties = block.get("additionalProperty")
    if not isinstance(properties, list):
        return None
    keyword = name_keyword.casefold()
    for prop in properties:
        if not isinstance(prop, dict):
            continue
        name = prop.get("name")
        if isinstance(name, str) and keyword in name.casefold():
            value = prop.get("value")
            return str(value) if value is not None else None
    return None


def get_nested(block: dict[str, Any], *path: str) -> Any | None:  # noqa: ANN401
    """Safely walk a dotted path of dict keys, returning ``None`` if any segment is absent.

    Never raises and never fabricates a value -- an absent field is
    reported as ``None``, exactly reflecting that the source did not
    provide it.
    """
    current: Any = block
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return None
        current = current[key]
    return current
