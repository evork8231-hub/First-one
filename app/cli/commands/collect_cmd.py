"""``sigint collect`` -- run one or every enabled collector.

``--all`` only actually executes an enabled collector that has passed
``sigint verify-collector`` (see
``app.cli.collector_verification_gate.split_by_verification``); an
enabled-but-unverified collector is reported as a skipped failure rather
than run. ``--collector <name>`` (a single, explicit, operator-named run)
is not gated -- see ``collector_verification_gate`` for why.
"""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.application.services.signal_service import CollectorRunResult
from app.cli.collector_verification_gate import not_verified_message, split_by_verification
from app.cli.schema_drift_support import check_schema_drift_safely
from app.core.container import Container
from app.core.exceptions import CollectorError, ConfigurationError
from app.domain.signal import Signal

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

    _warn_on_schema_drift(container, collector_name, signals)
    console.print(
        f"[bold green]Ingested {len(signals)} signal(s) from {collector_name!r}.[/bold green]"
    )


def _warn_on_schema_drift(
    container: Container, collector_name: str, signals: Sequence[Signal]
) -> None:
    """Non-blocking: report (but never fail on) a collector's source structure changing."""
    drift = check_schema_drift_safely(
        container, collector_name, [signal.raw_payload for signal in signals]
    )
    if drift is not None and drift.has_drift:
        console.print(
            f"[yellow]Schema drift detected for {collector_name!r}: "
            f"{len(drift.added_keys)} key(s) added, {len(drift.removed_keys)} key(s) removed "
            f"since the last run. See the audit log for details.[/yellow]"
        )


def _collect_all(container: Container) -> None:
    settings = container.settings()
    enabled = settings.collectors.enabled_set
    all_collectors = container.collector_registry().list_enabled(enabled)
    all_weather_collectors = container.weather_collector_registry().list_enabled(enabled)
    if not all_collectors and not all_weather_collectors:
        console.print(
            "[yellow]No collectors are enabled -- set 'collectors.enabled' in configuration "
            "before running 'sigint collect --all'.[/yellow]"
        )
        raise typer.Exit(code=1)

    lifecycle = container.collector_lifecycle_service()
    collectors, unverified_collectors = split_by_verification(lifecycle, all_collectors)
    weather_collectors, unverified_weather_collectors = split_by_verification(
        lifecycle, all_weather_collectors
    )

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
        results.extend(
            CollectorRunResult(collector_name=c.name, error=not_verified_message(c.name))
            for c in unverified_collectors
        )
        weather_event_counts, weather_errors = _run_weather_collectors(
            container, weather_collectors
        )
        for c in unverified_weather_collectors:
            weather_errors[c.name] = not_verified_message(c.name)

    succeeded = [r for r in results if r.succeeded]
    failed = [r for r in results if not r.succeeded]
    total_signals = sum(len(r.signals) for r in succeeded)

    for result in succeeded:
        _warn_on_schema_drift(container, result.collector_name, result.signals)

    console.print(
        f"Ran {len(results)} signal collector(s): [green]{len(succeeded)} succeeded[/green] "
        f"({total_signals} signal(s) ingested), [red]{len(failed)} failed[/red]."
    )
    for result in failed:
        console.print(f"  [red]- {result.collector_name}: {result.error}[/red]")

    if all_weather_collectors:
        total_events = sum(weather_event_counts.values())
        console.print(
            f"Ran {len(all_weather_collectors)} weather collector(s): "
            f"{total_events} event(s) ingested, [red]{len(weather_errors)} failed[/red]."
        )
        for name, error in weather_errors.items():
            console.print(f"  [red]- {name}: {error}[/red]")

    any_succeeded = bool(succeeded) or bool(weather_event_counts)
    any_ran = bool(results) or bool(all_weather_collectors)
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

    Every successfully-ingested batch of WeatherEvents is immediately
    bridged into WEATHER_EVENT Signals (see
    ``app.application.services.weather_signal_bridge_service.WeatherSignalBridgeService``)
    so the events can actually reach correlation and scoring -- without
    this, collected weather data would never influence a Lead.

    Deliberately not schema-drift-checked (see ``_warn_on_schema_drift``,
    used for the JSON-based signal collectors above): ``WeatherEvent.raw_payload``
    is a fixed-key dict IlmateenistusCollector itself constructs from parsed
    fields, not the source feed's own structure, so its key set never
    changes regardless of what the real XML looks like -- checking it would
    report false confidence rather than real drift.
    """
    service = container.weather_event_service()
    bridge = container.weather_signal_bridge_service()
    event_counts: dict[str, int] = {}
    errors: dict[str, str] = {}
    for weather_collector in weather_collectors:
        try:
            events = asyncio.run(service.ingest_from_collector(weather_collector))
            bridged = bridge.bridge(events)
            event_counts[weather_collector.name] = len(events)
            logger.info(
                "Bridged {} weather event(s) from {} into {} signal(s).",
                len(events),
                weather_collector.name,
                len(bridged),
            )
        except CollectorError as exc:
            logger.error("Weather collector {} failed: {}", weather_collector.name, exc.message)
            errors[weather_collector.name] = exc.message
    return event_counts, errors
