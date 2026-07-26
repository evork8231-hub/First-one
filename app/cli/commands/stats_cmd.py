"""``sigint stats`` -- summary counts of stored Signals, Leads, and WeatherEvents.

Read-only reporting. Status/type breakdowns use
``SignalRepository.count`` / ``LeadRepository.count`` (a single SQL
``COUNT(*)`` per row, not a full table scan); the priority breakdown --
the one dimension no repository interface filters by -- tallies over a
bounded, configurable sample instead of the whole table. No new
business logic: every number here is already computed and stored by
verification/scoring, this command only reads it back.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from app.core.container import Container
from app.domain.enums import VerificationStatus

console = Console()


def stats(
    ctx: typer.Context,
    priority_sample_limit: Annotated[
        int,
        typer.Option(
            "--priority-sample-limit",
            help="Maximum VERIFIED leads scanned to build the priority breakdown.",
        ),
    ] = 10_000,
) -> None:
    """Show counts of Signals/Leads (by verification status), lead priority, and weather events."""
    if priority_sample_limit <= 0:
        console.print("[red]--priority-sample-limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    signal_repository = container.signal_repository()
    lead_repository = container.lead_repository()
    weather_event_repository = container.weather_event_repository()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task("Computing statistics...", total=None)

        signal_total = signal_repository.count()
        signal_by_status = {
            status: signal_repository.count(verified=status) for status in VerificationStatus
        }

        lead_total = lead_repository.count()
        lead_by_status = {
            status: lead_repository.count(verification_status=status)
            for status in VerificationStatus
        }
        verified_leads = lead_repository.list_all(
            verification_status=VerificationStatus.VERIFIED, limit=priority_sample_limit
        )
        priority_counts: dict[str, int] = {}
        for lead in verified_leads:
            priority_counts[lead.priority.value] = priority_counts.get(lead.priority.value, 0) + 1

        weather_total = weather_event_repository.count()

    signals_table = Table(title="Signals")
    signals_table.add_column("Verification status")
    signals_table.add_column("Count", justify="right")
    for status, count in signal_by_status.items():
        signals_table.add_row(status.value, str(count))
    signals_table.add_row("[bold]Total[/bold]", f"[bold]{signal_total}[/bold]")

    leads_table = Table(title="Leads")
    leads_table.add_column("Verification status")
    leads_table.add_column("Count", justify="right")
    for status, count in lead_by_status.items():
        leads_table.add_row(status.value, str(count))
    leads_table.add_row("[bold]Total[/bold]", f"[bold]{lead_total}[/bold]")

    priority_table = Table(title=f"VERIFIED lead priority (sample of {len(verified_leads)})")
    priority_table.add_column("Priority")
    priority_table.add_column("Count", justify="right")
    for priority, count in sorted(priority_counts.items()):
        priority_table.add_row(priority, str(count))

    console.print(signals_table)
    console.print(leads_table)
    console.print(priority_table)
    console.print(f"Weather events stored: [bold]{weather_total}[/bold]")
