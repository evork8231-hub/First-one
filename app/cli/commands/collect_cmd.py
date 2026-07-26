"""``sigint collect`` -- run a single registered collector."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console

from app.core.container import Container
from app.core.exceptions import CollectorError, ConfigurationError

console = Console()


def collect(
    ctx: typer.Context,
    collector: str = typer.Option(
        ..., "--collector", "-c", help="Name of a registered collector to run."
    ),
) -> None:
    """Run ``collector`` and persist every Signal it returns.

    The foundation ships no production collector implementation, so this
    command will report that no collector is registered until a future
    phase adds one via ``Container.collector_registry().register(...)``.
    The command's validation and orchestration logic is fully functional.
    """
    container: Container = ctx.obj
    registry = container.collector_registry()

    try:
        selected = registry.get(collector)
    except ConfigurationError as exc:
        console.print(f"[red]{exc.message}[/red]")
        console.print(
            "[yellow]No collectors are registered in this foundation build -- "
            "building the first production collector is a future phase.[/yellow]"
        )
        raise typer.Exit(code=1) from exc

    service = container.signal_service()
    try:
        signals = asyncio.run(service.ingest_from_collector(selected))
    except CollectorError as exc:
        console.print(f"[red]Collector {collector!r} failed: {exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Ingested {len(signals)} signal(s) from {collector!r}.[/bold green]")
