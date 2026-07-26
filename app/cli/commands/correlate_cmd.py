"""``sigint correlate`` -- cluster verified Signals and evaluate rules against them."""

from __future__ import annotations

import typer
from rich.console import Console

from app.core.container import Container

console = Console()


def correlate(
    ctx: typer.Context,
    limit: int = typer.Option(
        1000, "--limit", help="Maximum number of verified signals to consider."
    ),
) -> None:
    """Run the correlation and rule engines over currently verified Signals.

    Prints how many rule matches were found, but does not persist Leads --
    use ``sigint generate`` for that.
    """
    container: Container = ctx.obj
    service = container.correlation_service()
    matches = service.run(limit=limit)

    console.print(
        f"Found [bold]{len(matches)}[/bold] rule match(es) across the current signal set."
    )
    for match in matches:
        console.print(
            f"  - rule={match.rule.id!r} lead_type={match.rule.lead_type.value} "
            f"county={match.cluster.county!r} municipality={match.cluster.municipality!r} "
            f"matched_signals={len(match.matched_signal_ids)}"
        )
