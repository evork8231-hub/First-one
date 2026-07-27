"""``sigint health`` -- per-collector run status, timing, and failure streaks.

Read-only reporting over the audit log, via
``app.application.services.collector_health_service.CollectorHealthService``.
No new business logic and no collection happens here -- this is purely a
summary of history already recorded by every ``collect``/``pipeline`` run.
"""

from __future__ import annotations

from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from app.core.container import Container

# Wide enough that collector names and every column stay unwrapped/untruncated
# even for the longest known collector name.
console = Console(width=140)


def health(
    ctx: typer.Context,
    sample_limit: Annotated[
        int,
        typer.Option("--sample-limit", help="Maximum recent audit entries per event type to scan."),
    ] = 500,
) -> None:
    """Show the last known status, duration, and failure streak for every collector."""
    if sample_limit <= 0:
        console.print("[red]--sample-limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    service = container.collector_health_service()
    reports = service.get_health(sample_limit=sample_limit)

    if not reports:
        console.print(
            "No collector run history found yet -- run 'sigint collect' or "
            "'sigint pipeline' first."
        )
        return

    table = Table(title="Collector health")
    table.add_column("Collector")
    table.add_column("Last status")
    table.add_column("Last run (UTC)")
    table.add_column("Duration (s)", justify="right")
    table.add_column("Items", justify="right")
    table.add_column("Consecutive failures", justify="right")

    for report in reports:
        status_style = "green" if report.last_status == "succeeded" else "red"
        table.add_row(
            report.collector_name,
            f"[{status_style}]{report.last_status}[/{status_style}]",
            report.last_run_at.strftime("%Y-%m-%d %H:%M:%S"),
            "-" if report.last_duration_seconds is None else f"{report.last_duration_seconds:.3f}",
            "-" if report.last_item_count is None else str(report.last_item_count),
            str(report.consecutive_failures),
        )
    console.print(table)

    for report in reports:
        if report.last_status == "failed" and report.last_error:
            console.print(f"[red]{report.collector_name}: {report.last_error}[/red]")
