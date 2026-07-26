"""``sigint export`` -- serialize VERIFIED Leads to JSON, CSV, or Excel (.xlsx)."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from app.core.container import Container
from app.domain.enums import ServiceCategory

console = Console()

_TEXT_FORMATS = ("json", "csv")
_BINARY_FORMATS = ("xlsx",)


def export(
    ctx: typer.Context,
    export_format: Annotated[
        str, typer.Option("--format", "-f", help="Output format: 'json', 'csv', or 'xlsx'.")
    ] = "json",
    output: Annotated[
        Path | None,
        typer.Option(
            "--output",
            "-o",
            help="File to write to. Required for 'xlsx'; defaults to stdout otherwise.",
        ),
    ] = None,
    lead_type: Annotated[
        ServiceCategory | None, typer.Option("--lead-type", help="Filter by service category.")
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="Maximum number of leads to export.")
    ] = 1000,
) -> None:
    """Export VERIFIED Leads matching the given filters. Never exports raw Signals."""
    if export_format not in (*_TEXT_FORMATS, *_BINARY_FORMATS):
        console.print(
            f"[red]Unsupported format {export_format!r}; use 'json', 'csv', or 'xlsx'.[/red]"
        )
        raise typer.Exit(code=1)

    if export_format in _BINARY_FORMATS and output is None:
        console.print(f"[red]'--output' is required when exporting as {export_format!r}.[/red]")
        raise typer.Exit(code=1)

    container: Container = ctx.obj
    service = container.export_service()
    payload = service.export_leads(
        export_format=export_format,  # type: ignore[arg-type]
        lead_type=lead_type,
        limit=limit,
    )

    if output is None:
        console.print(payload)
        return

    output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        output.write_bytes(payload)
    else:
        output.write_text(payload, encoding="utf-8")
    console.print(f"[bold green]Wrote export to {output}.[/bold green]")
