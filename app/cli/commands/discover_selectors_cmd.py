"""``sigint discover-selectors`` -- propose selector candidates from a listing page.

Backs manual selector configuration for the ``playwright_jsonld`` real
estate collectors (KV.ee, Kinnisvara24, City24), whose
``listing_link_selector`` has no default because the real value is
site-specific and was never confirmed against a live source. This
command never picks or writes a selector -- it only reports repeated
structural patterns for an operator to review (see
``app.collectors.selector_discovery``).

Two input modes, mutually exclusive:

- ``--url``: fetch the page live via the same headless-browser client a
  real collector run would use (requires network access).
- ``--html-file``: analyze a previously saved HTML file -- the only mode
  usable in a network-restricted environment, and useful for repeatable,
  offline review of a page an operator downloaded by hand.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from app.collectors.selector_discovery import SelectorDiscoveryReport, analyze_html
from app.core.container import Container
from app.core.exceptions import CollectorError

console = Console(width=160)

_BROWSER_COLLECTORS = ("kv_ee", "kinnisvara24", "city24")


def discover_selectors(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Fetch this URL live via a headless browser and analyze it."),
    ] = None,
    html_file: Annotated[
        Path | None,
        typer.Option("--html-file", help="Analyze a previously saved HTML file instead."),
    ] = None,
    collector: Annotated[
        str,
        typer.Option(
            "--collector",
            help=f"Which collector's browser settings to use for --url. One of: "
            f"{', '.join(_BROWSER_COLLECTORS)}.",
        ),
    ] = "kv_ee",
    min_repeat_count: Annotated[
        int,
        typer.Option(
            "--min-repeat-count",
            help="Minimum occurrences of a tag+class combination to report as a candidate.",
        ),
    ] = 3,
) -> None:
    """Analyze a listing page and propose repeated-card, link, price, and postal-code candidates."""
    if (url is None) == (html_file is None):
        console.print("[red]Pass exactly one of --url or --html-file.[/red]")
        raise typer.Exit(code=2)
    if min_repeat_count <= 0:
        console.print("[red]--min-repeat-count must be a positive integer.[/red]")
        raise typer.Exit(code=2)
    if url is not None and collector not in _BROWSER_COLLECTORS:
        console.print(
            f"[red]Unknown --collector {collector!r}; use one of: "
            f"{', '.join(_BROWSER_COLLECTORS)}.[/red]"
        )
        raise typer.Exit(code=2)

    if html_file is not None:
        if not html_file.is_file():
            console.print(f"[red]--html-file {str(html_file)!r} does not exist.[/red]")
            raise typer.Exit(code=1)
        html = html_file.read_text(encoding="utf-8")
    else:
        assert url is not None
        container: Container = ctx.obj
        listing_collector = getattr(container, f"{collector}_collector")()
        try:
            html = asyncio.run(listing_collector.fetch_page_html(url))
        except CollectorError as exc:
            console.print(f"[red]Could not fetch {url!r}: {exc.message}[/red]")
            raise typer.Exit(code=1) from exc

    report = analyze_html(html, min_repeat_count=min_repeat_count)
    _print_report(report)


def _print_report(report: SelectorDiscoveryReport) -> None:
    console.print(
        f"JSON-LD blocks found: [bold]{report.jsonld_block_count}[/bold] "
        f"(types: {', '.join(report.jsonld_types) or 'none'})"
    )

    cards_table = Table(title="Repeated element candidates (possible listing cards)")
    cards_table.add_column("Selector")
    cards_table.add_column("Occurrences", justify="right")
    cards_table.add_column("Sample text")
    for card_candidate in report.repeated_card_candidates:
        cards_table.add_row(
            card_candidate.selector,
            str(card_candidate.occurrence_count),
            card_candidate.sample_text,
        )
    console.print(cards_table)

    links_table = Table(title="Anchor candidates (possible listing_link_selector)")
    links_table.add_column("Selector")
    links_table.add_column("Occurrences", justify="right")
    links_table.add_column("Sample href")
    for link_candidate in report.listing_link_candidates:
        links_table.add_row(
            link_candidate.selector,
            str(link_candidate.occurrence_count),
            link_candidate.sample_href,
        )
    console.print(links_table)

    console.print(f"Price-like text samples: {report.price_text_samples or '(none found)'}")
    console.print(f"Postal-code-like samples: {report.postal_code_samples or '(none found)'}")
    console.print(f"Street address samples: {report.street_address_samples or '(none found)'}")
    console.print(f"Known city names found: {report.city_name_samples or '(none found)'}")
    console.print(
        "[yellow]These are candidates only -- nothing has been changed.[/yellow] Review "
        "them against the real page and, if correct, set listing_link_selector "
        "yourself in configuration."
    )
