"""``sigint purge`` -- safely delete collected data by source, without manual SQL.

Every subcommand previews its effect by default (a dry run: it reports
how many records match, deletes nothing) and only performs the actual,
irreversible deletion when ``--yes`` is passed explicitly. This mirrors
the platform's fail-closed posture applied to destructive operations:
an operator retiring or reconfiguring a collector should never have to
touch the database directly, but also should never delete data by
accident.

Deliberately scoped to Signals and WeatherEvents (see
``app.application.services.data_management_service.DataManagementService``
for why Leads are excluded). Purging Signals refuses the whole operation
if any of them are still cited by an existing Lead -- see
``app.core.exceptions.PurgeBlockedByDependentDataError``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import typer
from rich.console import Console

from app.core.container import Container
from app.core.exceptions import PurgeBlockedByDependentDataError

console = Console()
app = typer.Typer(help="Preview or delete collected data by source (dry-run by default).")


def _parse_before(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        console.print(
            f"[red]Invalid --before value {value!r}; use an ISO-8601 date or "
            f"datetime, e.g. 2026-01-01 or 2026-01-01T00:00:00Z.[/red]"
        )
        raise typer.Exit(code=2) from exc
    return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)


@app.command("signals")
def purge_signals(
    ctx: typer.Context,
    source: str = typer.Option(..., "--source", help="Exact Signal.source value to purge."),
    before: str | None = typer.Option(
        None,
        "--before",
        help="Only delete signals older than this ISO-8601 date/datetime "
        "(compared against Signal.timestamp). Omit to delete every signal from --source.",
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Actually delete. Without this flag, only previews the count."
    ),
) -> None:
    """Preview or delete every Signal from ``--source`` (dry-run unless ``--yes``)."""
    parsed_before = _parse_before(before)
    container: Container = ctx.obj
    service = container.data_management_service()

    try:
        affected = service.purge_signals(source, before=parsed_before, dry_run=not yes)
    except PurgeBlockedByDependentDataError as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    if yes:
        console.print(f"[bold red]Deleted {affected} signal(s)[/bold red] from source {source!r}.")
    else:
        console.print(
            f"[yellow]DRY RUN[/yellow]: {affected} signal(s) from source {source!r} would be "
            f"deleted. Re-run with --yes to actually delete."
        )


@app.command("weather-events")
def purge_weather_events(
    ctx: typer.Context,
    source: str = typer.Option(..., "--source", help="Exact WeatherEvent.source value to purge."),
    before: str | None = typer.Option(
        None,
        "--before",
        help="Only delete events older than this ISO-8601 date/datetime "
        "(compared against WeatherEvent.started_at). Omit to delete every event from --source.",
    ),
    yes: bool = typer.Option(
        False, "--yes", help="Actually delete. Without this flag, only previews the count."
    ),
) -> None:
    """Preview or delete every WeatherEvent from ``--source`` (dry-run unless ``--yes``)."""
    parsed_before = _parse_before(before)
    container: Container = ctx.obj
    service = container.data_management_service()

    affected = service.purge_weather_events(source, before=parsed_before, dry_run=not yes)

    if yes:
        console.print(
            f"[bold red]Deleted {affected} weather event(s)[/bold red] from source {source!r}."
        )
    else:
        console.print(
            f"[yellow]DRY RUN[/yellow]: {affected} weather event(s) from source {source!r} would "
            f"be deleted. Re-run with --yes to actually delete."
        )
