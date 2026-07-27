"""``sigint discover-fields`` -- suggest ``field_map`` additions from a sample of real data.

Fetches a small, bounded sample of real Ehitisregister records (the
structured, JSON-based collector; see
``app.collectors.field_map_discovery``) and reports every source JSON key
the currently configured ``field_map`` does not yet account for, along
with ranked canonical-field guesses. Nothing is written to configuration
-- an operator reviews the suggestions and edits ``field_map`` in YAML
themselves, same as before, just with less manual key-name guesswork.
"""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from app.collectors.field_map_discovery import find_unmapped_keys, suggest_field_map
from app.core.container import Container
from app.core.exceptions import CollectorError

console = Console(width=140)


def discover_fields(
    ctx: typer.Context,
    sample_limit: Annotated[
        int, typer.Option("--sample-limit", help="How many real records to sample.")
    ] = 5,
    score_cutoff: Annotated[
        float,
        typer.Option(
            "--score-cutoff",
            help="Minimum fuzzy-match confidence (0-100) to report a suggestion.",
        ),
    ] = 60.0,
) -> None:
    """Sample real Ehitisregister records and suggest field_map candidates for unmapped keys."""
    if sample_limit <= 0:
        console.print("[red]--sample-limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    collector = container.ehitisregister_collector()
    field_map = container.settings().collectors.ehitisregister.field_map

    try:
        records = asyncio.run(collector.sample_raw_records(limit=sample_limit))
    except CollectorError as exc:
        console.print(f"[red]Could not sample records: {exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    if not records:
        console.print("The source returned no records; nothing to analyze.")
        return

    unmapped_keys = find_unmapped_keys(records, field_map)
    if not unmapped_keys:
        console.print(
            f"[green]Every key observed in {len(records)} sampled record(s) is already "
            f"covered by field_map.[/green]"
        )
        return

    suggestions = suggest_field_map(records, field_map, score_cutoff=score_cutoff)

    table = Table(title=f"Field-map suggestions (from {len(records)} sampled record(s))")
    table.add_column("Unmapped source key")
    table.add_column("Suggested canonical field")
    table.add_column("Confidence", justify="right")
    table.add_column("Sample value")

    for key in sorted(unmapped_keys):
        candidates = suggestions.get(key)
        if not candidates:
            table.add_row(key, "[yellow](no confident match)[/yellow]", "-", "-")
            continue
        for suggestion in candidates:
            table.add_row(
                suggestion.source_key,
                suggestion.canonical_field,
                f"{suggestion.confidence:.0%}",
                str(suggestion.sample_value),
            )

    console.print(table)
    console.print(
        "[yellow]These are suggestions only -- nothing has been changed.[/yellow] Review "
        "them and, if correct, add the key to the matching canonical field's candidate "
        "list under collectors.ehitisregister.field_map in your configuration."
    )
