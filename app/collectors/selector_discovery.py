"""Selector discovery: analyzes a downloaded HTML page and proposes candidate selectors.

Backs the ``sigint discover-selectors`` CLI command for the
``playwright_jsonld`` real-estate collectors (KV.ee, Kinnisvara24,
City24; see ``app.collectors.real_estate.base_listing_collector``),
whose ``listing_link_selector`` has no default because the real
selector is genuinely site-specific and was never confirmed against a
live source.

This module performs pure, offline HTML analysis -- it detects
structural patterns already present in a downloaded page (JSON-LD
blocks, repeated sibling elements that look like listing cards,
grouped anchor tags, price-like and postal-code-like text) and reports
them as candidates with occurrence counts and samples. It never invents
a selector, never picks one automatically, and never writes
configuration: every finding is a diagnostic for an operator to review
and, if correct, copy into ``listing_link_selector`` themselves.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup

from app.collectors.jsonld import extract_jsonld_blocks

_CONTAINER_TAGS = ("div", "li", "article", "section")
_SAMPLE_TEXT_MAX_LENGTH = 160
_PRICE_PATTERN = re.compile(
    r"(?:€\s?\d[\d\s.,]{1,12}|\d[\d\s.,]{1,12}\s?€|\d[\d\s.,]{1,12}\s?EUR)", re.IGNORECASE
)
_POSTAL_CODE_PATTERN = re.compile(r"\b\d{5}\b")
_IGNORED_HREF_PREFIXES = ("#", "javascript:", "mailto:", "tel:")


@dataclass(frozen=True)
class RepeatedElementCandidate:
    """A tag+class combination that repeats often enough to look like a listing card."""

    selector: str
    tag: str
    css_classes: tuple[str, ...]
    occurrence_count: int
    sample_text: str


@dataclass(frozen=True)
class LinkCandidate:
    """A tag+class combination of ``<a href>`` elements that repeats across the page."""

    selector: str
    occurrence_count: int
    sample_href: str


@dataclass(frozen=True)
class SelectorDiscoveryReport:
    """Everything :func:`analyze_html` found in a single downloaded page."""

    jsonld_block_count: int
    jsonld_types: list[str]
    repeated_card_candidates: list[RepeatedElementCandidate]
    listing_link_candidates: list[LinkCandidate]
    price_text_samples: list[str]
    postal_code_samples: list[str]


def analyze_html(
    html: str, *, min_repeat_count: int = 3, max_candidates: int = 10
) -> SelectorDiscoveryReport:
    """Analyze a downloaded HTML page and propose selector candidates.

    ``min_repeat_count`` is how many times a tag+class combination must
    appear before it is reported as a repeated-card or link candidate --
    a real listing grid repeats its card markup many times, so a
    combination seen only once or twice is unlikely to be one.
    """
    soup = BeautifulSoup(html, "html.parser")

    jsonld_blocks = extract_jsonld_blocks(html)
    jsonld_types = _collect_jsonld_types(jsonld_blocks)

    repeated_cards = _find_repeated_elements(
        soup, min_repeat_count=min_repeat_count, max_candidates=max_candidates
    )
    listing_links = _find_link_candidates(
        soup, min_repeat_count=min_repeat_count, max_candidates=max_candidates
    )

    text = soup.get_text(separator=" ")
    price_samples = _unique_matches(_PRICE_PATTERN, text, limit=10)
    postal_samples = _unique_matches(_POSTAL_CODE_PATTERN, text, limit=10)

    return SelectorDiscoveryReport(
        jsonld_block_count=len(jsonld_blocks),
        jsonld_types=jsonld_types,
        repeated_card_candidates=repeated_cards,
        listing_link_candidates=listing_links,
        price_text_samples=price_samples,
        postal_code_samples=postal_samples,
    )


def _collect_jsonld_types(blocks: list[dict[str, object]]) -> list[str]:
    types: set[str] = set()
    for block in blocks:
        raw_type = block.get("@type")
        if isinstance(raw_type, str):
            types.add(raw_type)
        elif isinstance(raw_type, list):
            types.update(t for t in raw_type if isinstance(t, str))
    return sorted(types)


def _selector_for(tag_name: str, classes: tuple[str, ...]) -> str:
    if not classes:
        return tag_name
    return tag_name + "." + ".".join(classes)


def _find_repeated_elements(
    soup: BeautifulSoup, *, min_repeat_count: int, max_candidates: int
) -> list[RepeatedElementCandidate]:
    groups: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for tag in soup.find_all(_CONTAINER_TAGS):
        classes = tuple(sorted(tag.get("class") or []))
        if not classes:
            continue
        key = (str(tag.name), classes)
        groups.setdefault(key, []).append(tag.get_text(separator=" ", strip=True))

    candidates = [
        RepeatedElementCandidate(
            selector=_selector_for(tag_name, classes),
            tag=tag_name,
            css_classes=classes,
            occurrence_count=len(text_samples),
            sample_text=text_samples[0][:_SAMPLE_TEXT_MAX_LENGTH],
        )
        for (tag_name, classes), text_samples in groups.items()
        if len(text_samples) >= min_repeat_count
    ]
    candidates.sort(key=lambda candidate: candidate.occurrence_count, reverse=True)
    return candidates[:max_candidates]


def _find_link_candidates(
    soup: BeautifulSoup, *, min_repeat_count: int, max_candidates: int
) -> list[LinkCandidate]:
    groups: dict[tuple[str, tuple[str, ...]], list[str]] = {}
    for tag in soup.find_all("a", href=True):
        href = str(tag["href"])
        if not href or href.startswith(_IGNORED_HREF_PREFIXES):
            continue
        classes = tuple(sorted(tag.get("class") or []))
        if not classes:
            continue  # unclassed anchors are almost never a usable, specific selector
        key = ("a", classes)
        groups.setdefault(key, []).append(href)

    candidates = [
        LinkCandidate(
            selector=_selector_for(tag_name, classes),
            occurrence_count=len(hrefs),
            sample_href=hrefs[0],
        )
        for (tag_name, classes), hrefs in groups.items()
        if len(hrefs) >= min_repeat_count
    ]
    candidates.sort(key=lambda candidate: candidate.occurrence_count, reverse=True)
    return candidates[:max_candidates]


def _unique_matches(pattern: re.Pattern[str], text: str, *, limit: int) -> list[str]:
    seen: list[str] = []
    for match in pattern.finditer(text):
        value = match.group(0).strip()
        if value and value not in seen:
            seen.append(value)
        if len(seen) >= limit:
            break
    return seen
