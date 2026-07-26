"""``sigint collect`` -- run one or every enabled collector."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from app.application.services.signal_service import CollectorRunResult
from app.core.container import Container
from app.core.exceptions import CollectorError, ConfigurationError

console = Console()


def collect(
    ctx: typer.Context,
    collector: Annotated[
        str | None,
        typer.Option("--collector", "-c", help="Name of a single registered collector to run."),
    ] = None,
    run_all: Annotated[
        bool,
        typer.Option(
            "--all", help="Run every collector listed in 'collectors.enabled', concurrently."
        ),
    ] = False,
) -> None:
    """Run a collector (or every enabled collector) and persist every Signal it returns.

    Exactly one of ``--collector`` or ``--all`` must be given. Use
    ``sigint config show`` to see which collectors are currently enabled.
    """
    if collector is None and not run_all:
        console.print("[red]Pass either --collector <name> or --all.[/red]")
        raise typer.Exit(code=2)
    if collector is not None and run_all:
        console.print("[red]--collector and --all are mutually exclusive.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    if run_all:
        _collect_all(container)
    else:
        assert collector is not None
        _collect_one(container, collector)


def _collect_one(container: Container, collector_name: str) -> None:
    registry = container.collector_registry()
    try:
        selected = registry.get(collector_name)
    except ConfigurationError as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    service = container.signal_service()
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(f"Running collector {collector_name!r}...", total=None)
        try:
            signals = asyncio.run(service.ingest_from_collector(selected))
        except CollectorError as exc:
            logger.error("Collector {} failed: {}", collector_name, exc.message)
            console.print(f"[red]Collector {collector_name!r} failed: {exc.message}[/red]")
            raise typer.Exit(code=1) from exc

    console.print(
        f"[bold green]Ingested {len(signals)} signal(s) from {collector_name!r}.[/bold green]"
    )


def _collect_all(container: Container) -> None:
    settings = container.settings()
    registry = container.collector_registry()
    collectors = registry.list_enabled(settings.collectors.enabled_set)
    if not collectors:
        console.print(
            "[yellow]No collectors are enabled -- set 'collectors.enabled' in configuration "
            "before running 'sigint collect --all'.[/yellow]"
        )
        raise typer.Exit(code=1)

    service = container.signal_service()
    max_concurrency = settings.concurrency.max_concurrent_collectors

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        TimeElapsedColumn(),
        console=console,
        transient=True,
    ) as progress:
        progress.add_task(
            f"Collecting from {len(collectors)} source(s) (concurrency={max_concurrency})...",
            total=None,
        )
        results: list[CollectorRunResult] = asyncio.run(
            service.ingest_from_collectors(collectors, max_concurrency=max_concurrency)
        )

    succeeded = [r for r in results if r.succeeded]
    failed = [r for r in results if not r.succeeded]
    total_signals = sum(len(r.signals) for r in succeeded)

    console.print(
        f"Ran {len(results)} collector(s): [green]{len(succeeded)} succeeded[/green] "
        f"({total_signals} signal(s) ingested), [red]{len(failed)} failed[/red]."
    )
    for result in failed:
        console.print(f"  [red]- {result.collector_name}: {result.error}[/red]")

    if failed and not succeeded:
        raise typer.Exit(code=1)
