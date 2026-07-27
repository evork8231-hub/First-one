"""``sigint inspect-xml`` -- visualize an XML feed's real element structure.

Backs manual verification of the Ilmateenistus forecast-XML collector
(see ``app.collectors.ilmateenistus_collector.IlmateenistusCollector``),
whose element paths were corroborated via documentation search but never
directly confirmed against the live feed. This command never rewrites
parser code and never changes what the collector does -- it only shows
an operator what the real document actually looks like (see
``app.collectors.xml_schema_inspector``), and, with ``--interactive``,
lets them confirm which discovered path matches each field the collector
currently expects, as a diagnostic to compare against the collector's
hardcoded paths.

Two input modes, mutually exclusive:

- ``--url``: fetch the feed live via the same HTTP client a real
  collector run would use (requires network access).
- ``--xml-file``: analyze a previously saved XML file -- the only mode
  usable in a network-restricted environment.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from app.collectors.http_client import HttpClient
from app.collectors.xml_schema_inspector import XmlSchemaReport
from app.collectors.xml_schema_inspector import inspect_xml as inspect_xml_document
from app.config.settings import HttpCollectorConfig
from app.core.container import Container
from app.core.exceptions import CollectorError

console = Console(width=160)

#: The element paths and attribute IlmateenistusCollector currently reads,
#: relative to a `place` element -- see IlmateenistusCollector._place_to_event.
#: Shown to the operator during --interactive review as what to confirm
#: against the real feed structure; never fabricated from the discovered
#: report itself.
_ILMATEENISTUS_EXPECTED_FIELDS: tuple[str, ...] = (
    "place/@name",
    "place/@phenomenon or place/phenomenon",
    "place/text (or nearest ancestor's text)",
    "place/wind/gust or place/wind/speed/max",
    "nearest ancestor's @date attribute",
)


def inspect_xml(
    ctx: typer.Context,
    url: Annotated[
        str | None,
        typer.Option("--url", help="Fetch this XML feed live and analyze it."),
    ] = None,
    xml_file: Annotated[
        Path | None,
        typer.Option("--xml-file", help="Analyze a previously saved XML file instead."),
    ] = None,
    max_samples_per_path: Annotated[
        int,
        typer.Option(
            "--max-samples-per-path", help="Sample attribute/text values kept per element path."
        ),
    ] = 3,
    interactive: Annotated[
        bool,
        typer.Option(
            "--interactive",
            help="After showing the structure, walk through the fields "
            "IlmateenistusCollector expects and ask which discovered path matches each.",
        ),
    ] = False,
) -> None:
    """Parse an XML feed and show its real element paths, attributes, and sample text."""
    if (url is None) == (xml_file is None):
        console.print("[red]Pass exactly one of --url or --xml-file.[/red]")
        raise typer.Exit(code=2)
    if max_samples_per_path <= 0:
        console.print("[red]--max-samples-per-path must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    if xml_file is not None:
        if not xml_file.is_file():
            console.print(f"[red]--xml-file {str(xml_file)!r} does not exist.[/red]")
            raise typer.Exit(code=1)
        xml_text = xml_file.read_text(encoding="utf-8")
    else:
        assert url is not None
        container: Container = ctx.obj
        ilmateenistus_config = container.settings().collectors.ilmateenistus
        http_config = HttpCollectorConfig(
            base_url=ilmateenistus_config.base_url,
            timeout_seconds=ilmateenistus_config.timeout_seconds,
            request_delay_seconds=ilmateenistus_config.request_delay_seconds,
            max_retries=ilmateenistus_config.max_retries,
        )
        try:
            xml_text = asyncio.run(_fetch(http_config, url))
        except CollectorError as exc:
            console.print(f"[red]Could not fetch {url!r}: {exc.message}[/red]")
            raise typer.Exit(code=1) from exc

    try:
        report = inspect_xml_document(xml_text, max_samples_per_path=max_samples_per_path)
    except CollectorError as exc:
        console.print(f"[red]Could not parse XML: {exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    _print_report(report)

    if interactive:
        _run_interactive_review(report)


async def _fetch(http_config: HttpCollectorConfig, url: str) -> str:
    async with HttpClient(http_config) as client:
        return await client.get_text(url)


def _print_report(report: XmlSchemaReport) -> None:
    console.print(
        f"Root element: [bold]{report.root_tag}[/bold]  "
        f"Total elements: [bold]{report.total_elements}[/bold]  "
        f"Distinct paths: [bold]{len(report.elements)}[/bold]"
    )

    table = Table(title="Element structure")
    table.add_column("Path")
    table.add_column("Occurrences", justify="right")
    table.add_column("Attributes (sample)")
    table.add_column("Text samples")
    for element in report.elements:
        attrs = (
            ", ".join(
                f"{name}={element.attribute_samples[name]!r}" for name in element.attribute_names
            )
            or "-"
        )
        texts = ", ".join(repr(sample) for sample in element.text_samples) or "-"
        table.add_row(element.path, str(element.occurrence_count), attrs, texts)
    console.print(table)


def _run_interactive_review(report: XmlSchemaReport) -> None:
    console.print(
        "\n[bold]Interactive review[/bold]: IlmateenistusCollector currently expects the "
        "following, relative to each 'place' element. For each, confirm whether a matching "
        "path was found above -- nothing is changed here; use this to decide whether the "
        "collector's source needs a manual fix."
    )
    known_paths = {element.path for element in report.elements}
    place_related_paths = sorted(p for p in known_paths if "place" in p.split("/"))

    for expected_field in _ILMATEENISTUS_EXPECTED_FIELDS:
        console.print(f"\nExpected: [cyan]{expected_field}[/cyan]")
        if place_related_paths:
            console.print(f"  Candidate path(s) found under 'place': {place_related_paths}")
        else:
            console.print(
                "  [yellow]No 'place'-related path found in this document at all.[/yellow]"
            )
        typer.confirm("  Does the real structure above look consistent with this?", default=True)
