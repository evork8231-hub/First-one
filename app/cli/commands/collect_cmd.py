"""``sigint collect`` -- run one or every enabled collector."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from app.application.interfaces.weather_collector import WeatherCollectorInterface
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
    enabled = settings.collectors.enabled_set
    collectors = container.collector_registry().list_enabled(enabled)
    weather_collectors = container.weather_collector_registry().list_enabled(enabled)
    if not collectors and not weather_collectors:
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
            f"Collecting from {len(collectors) + len(weather_collectors)} source(s) "
            f"(concurrency={max_concurrency})...",
            total=None,
        )
        results: list[CollectorRunResult] = (
            asyncio.run(service.ingest_from_collectors(collectors, max_concurrency=max_concurrency))
            if collectors
            else []
        )
        weather_event_counts, weather_errors = _run_weather_collectors(
            container, weather_collectors
        )

    succeeded = [r for r in results if r.succeeded]
    failed = [r for r in results if not r.succeeded]
    total_signals = sum(len(r.signals) for r in succeeded)

    console.print(
        f"Ran {len(results)} signal collector(s): [green]{len(succeeded)} succeeded[/green] "
        f"({total_signals} signal(s) ingested), [red]{len(failed)} failed[/red]."
    )
    for result in failed:
        console.print(f"  [red]- {result.collector_name}: {result.error}[/red]")

    if weather_collectors:
        total_events = sum(weather_event_counts.values())
        console.print(
            f"Ran {len(weather_collectors)} weather collector(s): "
            f"{total_events} event(s) ingested, [red]{len(weather_errors)} failed[/red]."
        )
        for name, error in weather_errors.items():
            console.print(f"  [red]- {name}: {error}[/red]")

    any_succeeded = bool(succeeded) or bool(weather_event_counts)
    any_ran = bool(results) or bool(weather_collectors)
    if any_ran and not any_succeeded:
        raise typer.Exit(code=1)


def _run_weather_collectors(
    container: Container, weather_collectors: list[WeatherCollectorInterface]
) -> tuple[dict[str, int], dict[str, str]]:
    """Run each enabled weather collector, never letting one failure abort the others.

    Mirrors ``SignalService.ingest_from_collectors``' per-collector error
    isolation, kept as a simple sequential loop here since weather
    collectors are typically few (one, today) -- see
    ``app.application.services.weather_event_service.WeatherEventService``
    for the underlying, already-tested ingestion logic this only calls.
    """
    service = container.weather_event_service()
    event_counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    for weather_collector in weather_collectors:
        try:
            events = asyncio.run(service.ingest_from_collector(weather_collector))
            event_counts[weather_collector.name] = len(events)
        except CollectorError as exc:
            logger.error("Weather collector {} failed: {}", weather_collector.name, exc.message)
            errors[weather_collector.name] = exc.message
    return event_counts, errors
