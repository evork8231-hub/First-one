"""``sigint score`` -- display the Intent/Confidence/Priority scores of stored Leads.

Scores themselves are always computed once, at lead-generation time, by
``app.lead_generation.scoring.LeadScorer`` (see ``sigint generate``) --
this command never recomputes or overrides a score. It exists purely to
make already-computed scores inspectable without a full export.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.core.container import Container
from app.domain.enums import ServiceCategory, VerificationStatus

console = Console()


def score(
    ctx: typer.Context,
    lead_type: Annotated[
        ServiceCategory | None, typer.Option("--lead-type", help="Filter by service category.")
    ] = None,
    status: Annotated[
        VerificationStatus | None,
        typer.Option("--status", help="Filter by lead verification status."),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="Maximum number of leads to display.")
    ] = 100,
) -> None:
    """List stored Leads with their Intent Score, Confidence Score, and Priority."""
    if limit <= 0:
        console.print("[red]--limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    lead_repository = container.lead_repository()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Loading lead scores...", total=None)
        leads = lead_repository.list_all(
            lead_type=lead_type, verification_status=status, limit=limit
        )

    if not leads:
        console.print("No leads match the given filters.")
        return

    table = Table(title=f"{len(leads)} lead(s)")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Priority")
    table.add_column("Intent Score", justify="right")
    table.add_column("Confidence Score", justify="right")
    for lead in sorted(leads, key=lambda x: x.intent_score, reverse=True):
        table.add_row(
            str(lead.id),
            lead.lead_type.value,
            lead.verification_status.value,
            lead.priority.value,
            f"{lead.intent_score:.2f}",
            f"{lead.estimated_confidence:.2f}",
        )
    console.print(table)
