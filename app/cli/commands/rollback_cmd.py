"""``sigint rollback`` -- undo the last completed run of a single collector.

Uses the exact record ids and execution id that
``app.application.services.signal_service.SignalService`` and
``app.application.services.weather_event_service.WeatherEventService``
already write to the ``COLLECTOR_RUN_COMPLETED`` audit entry, so a
rollback never has to guess which rows belong to the run being reversed.

Like ``sigint purge``, every subcommand previews its effect by default (a
dry run: it reports what *would* be deleted) and only performs the actual
deletion when ``--yes`` is passed. A rollback never edits or deletes the
audit entries it reads -- it appends a new ``COLLECTOR_RUN_ROLLED_BACK``
entry, so the audit history stays complete and the same run cannot be
rolled back twice (see ``RollbackService`` for details).
"""

from __future__ import annotations

import typer
from rich.console import Console

from app.core.container import Container
from app.core.exceptions import EntityNotFoundError

console = Console()
app = typer.Typer(help="Preview or undo the last completed run of a collector (dry-run default).")


@app.command("signals")
def rollback_signals(
    ctx: typer.Context,
    collector: str = typer.Argument(..., help="Signal collector name, e.g. ehitisregister."),
    yes: bool = typer.Option(
        False, "--yes", help="Actually roll back. Without this flag, only previews the effect."
    ),
) -> None:
    """Preview or undo the last completed run of a Signal collector (dry-run unless ``--yes``)."""
    container: Container = ctx.obj
    service = container.rollback_service()
    try:
        result = service.rollback_last_signal_run(collector, dry_run=not yes)
    except EntityNotFoundError as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    if yes:
        console.print(
            f"[bold red]Rolled back[/bold red] run {result.execution_id} of collector "
            f"{collector!r}: deleted {result.record_count} signal(s)."
        )
    else:
        console.print(
            f"[yellow]DRY RUN[/yellow]: run {result.execution_id} of collector {collector!r} "
            f"would delete {result.record_count} signal(s). Re-run with --yes to actually "
            f"roll back."
        )


@app.command("weather-events")
def rollback_weather_events(
    ctx: typer.Context,
    collector: str = typer.Argument(..., help="Weather collector name, e.g. ilmateenistus."),
    yes: bool = typer.Option(
        False, "--yes", help="Actually roll back. Without this flag, only previews the effect."
    ),
) -> None:
    """Preview or undo the last completed run of a weather collector (dry-run unless ``--yes``)."""
    container: Container = ctx.obj
    service = container.rollback_service()
    try:
        result = service.rollback_last_weather_run(collector, dry_run=not yes)
    except EntityNotFoundError as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    if yes:
        console.print(
            f"[bold red]Rolled back[/bold red] run {result.execution_id} of collector "
            f"{collector!r}: deleted {result.record_count} weather event(s)."
        )
    else:
        console.print(
            f"[yellow]DRY RUN[/yellow]: run {result.execution_id} of collector {collector!r} "
            f"would delete {result.record_count} weather event(s). Re-run with --yes to "
            f"actually roll back."
        )
