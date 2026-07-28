"""``sigint rollback`` -- undo the last completed run of a single collector.

Uses the exact record ids and execution id that
``app.application.services.signal_service.SignalService`` and
``app.application.services.weather_event_service.WeatherEventService``
already write to the ``COLLECTOR_RUN_COMPLETED`` audit entry, so a
rollback never has to guess which rows belong to the run being reversed.

Like ``sigint purge``, every subcommand previews its effect by default (a
dry run: it reports what *would* be deleted) and only performs the actual
deletion when ``--yes`` is passed. A real rollback deletes the records and
appends a new ``COLLECTOR_RUN_ROLLED_BACK`` entry as a single atomic
operation (see ``app.application.interfaces.rollback_unit_of_work``) --
it never edits or deletes the audit entries it reads, so the audit
history stays complete and the same run cannot be rolled back twice.

Every failure mode ``RollbackService`` can raise -- no matching run,
corrupted rollback metadata, a Signal still cited by a Lead, or a race
against a concurrent rollback -- is caught here and shown as a clean,
specific message. A database-level failure (locked, unavailable, disk
full) is also caught and reported clearly rather than dumping a raw
traceback at the operator; the full exception is still logged for
diagnosis, and the command still exits non-zero -- nothing here treats a
failure as a success.
"""

from __future__ import annotations

import typer
from loguru import logger
from rich.console import Console
from sqlalchemy.exc import SQLAlchemyError

from app.core.container import Container
from app.core.exceptions import EntityNotFoundError, RollbackError

console = Console()
app = typer.Typer(help="Preview or undo the last completed run of a collector (dry-run default).")


def _report_database_error(collector: str, exc: SQLAlchemyError) -> None:
    logger.opt(exception=exc).error(
        "Rollback of collector {} failed with a database error", collector
    )
    console.print(
        f"[red]Database error while rolling back {collector!r}: {exc}[/red]\n"
        f"[red]Rollback did not complete. See logs for details and retry once the "
        f"database is reachable.[/red]"
    )


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
    except (EntityNotFoundError, RollbackError) as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc
    except SQLAlchemyError as exc:
        _report_database_error(collector, exc)
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
    except (EntityNotFoundError, RollbackError) as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc
    except SQLAlchemyError as exc:
        _report_database_error(collector, exc)
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
