"""Tests for app.collectors.selector_discovery."""

from __future__ import annotations

from app.collectors.selector_discovery import analyze_html

_LISTING_PAGE_HTML = """
<html>
<head>
<script type="application/ld+json">
{"@type": "RealEstateListing", "name": "3-room apartment"}
</script>
</head>
<body>
<div class="search-results">
  <div class="listing-card">
    <a class="listing-link" href="/listing/1">3-room apartment, Tallinn</a>
    <span class="price">120 000 €</span>
    <span class="address">Tartu mnt 5, 10115 Tallinn</span>
  </div>
  <div class="listing-card">
    <a class="listing-link" href="/listing/2">2-room apartment, Tartu</a>
    <span class="price">85 000 €</span>
    <span class="address">Riia 20, 51010 Tartu</span>
  </div>
  <div class="listing-card">
    <a class="listing-link" href="/listing/3">House, Pärnu</a>
    <span class="price">250000 EUR</span>
    <span class="address">Ranna tee 1, 80010 Pärnu</span>
  </div>
</div>
<footer>
  <a href="/about">About</a>
  <a href="#">Top</a>
  <a href="mailto:info@example.ee">Contact</a>
</footer>
</body>
</html>
"""


def test_analyze_html_detects_jsonld_block() -> None:
    report = analyze_html(_LISTING_PAGE_HTML)
    assert report.jsonld_block_count == 1
    assert report.jsonld_types == ["RealEstateListing"]


def test_analyze_html_with_no_jsonld_reports_zero() -> None:
    report = analyze_html("<html><body><div>no jsonld here</div></body></html>")
    assert report.jsonld_block_count == 0
    assert report.jsonld_types == []


def test_analyze_html_detects_repeated_listing_cards() -> None:
    report = analyze_html(_LISTING_PAGE_HTML, min_repeat_count=3)

    assert len(report.repeated_card_candidates) == 1
    candidate = report.repeated_card_candidates[0]
    assert candidate.selector == "div.listing-card"
    assert candidate.occurrence_count == 3
    assert "apartment" in candidate.sample_text or "House" in candidate.sample_text


def test_analyze_html_below_min_repeat_count_reports_nothing() -> None:
    report = analyze_html(_LISTING_PAGE_HTML, min_repeat_count=4)
    assert report.repeated_card_candidates == []


def test_analyze_html_detects_listing_link_candidates() -> None:
    report = analyze_html(_LISTING_PAGE_HTML, min_repeat_count=3)

    assert len(report.listing_link_candidates) == 1
    candidate = report.listing_link_candidates[0]
    assert candidate.selector == "a.listing-link"
    assert candidate.occurrence_count == 3
    assert candidate.sample_href == "/listing/1"


def test_analyze_html_ignores_unclassed_and_non_navigable_footer_links() -> None:
    """The footer's #, mailto:, and unclassed 'About' link must never become candidates."""
    report = analyze_html(_LISTING_PAGE_HTML, min_repeat_count=1)

    selectors = {candidate.selector for candidate in report.listing_link_candidates}
    hrefs = {candidate.sample_href for candidate in report.listing_link_candidates}
    assert selectors == {"a.listing-link"}
    assert "/about" not in hrefs
    assert "#" not in hrefs


def test_analyze_html_detects_price_text_samples() -> None:
    report = analyze_html(_LISTING_PAGE_HTML)
    assert any("120" in sample for sample in report.price_text_samples)
    assert any("250000" in sample or "250 000" in sample for sample in report.price_text_samples)


def test_analyze_html_detects_postal_code_samples() -> None:
    report = analyze_html(_LISTING_PAGE_HTML)
    assert "10115" in report.postal_code_samples
    assert "51010" in report.postal_code_samples


def test_analyze_html_max_candidates_caps_results() -> None:
    cards = "".join(f'<div class="card-{i}">x</div><div class="card-{i}">y</div>' for i in range(5))
    html = f"<html><body>{cards}</body></html>"

    report = analyze_html(html, min_repeat_count=2, max_candidates=2)

    assert len(report.repeated_card_candidates) == 2
