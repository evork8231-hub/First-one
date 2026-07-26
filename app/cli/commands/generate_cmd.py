"""``sigint generate`` -- correlate verified Signals and persist the resulting Leads."""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from app.core.container import Container

console = Console()


def generate(
    ctx: typer.Context,
    limit: int = typer.Option(
        1000, "--limit", help="Maximum number of verified signals to consider."
    ),
) -> None:
    """Run correlation, then generate and persist Leads from the resulting rule matches."""
    container: Container = ctx.obj
    matches = container.correlation_service().run(limit=limit)
    leads = container.lead_generation_service().generate_from_matches(matches)

    if not leads:
        console.print("No leads were generated from the current signal set.")
        return

    table = Table(title=f"Generated {len(leads)} lead(s)")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("County")
    table.add_column("Municipality")
    table.add_column("Priority")
    table.add_column("Intent")
    table.add_column("Confidence")
    for lead in leads:
        table.add_row(
            str(lead.id),
            lead.lead_type.value,
            lead.county,
            lead.municipality,
            lead.priority.value,
            f"{lead.intent_score:.2f}",
            f"{lead.estimated_confidence:.2f}",
        )
    console.print(table)
