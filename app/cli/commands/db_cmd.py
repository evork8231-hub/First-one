"""``sigint db`` -- lightweight database health and migration-status checks.

Read-only diagnostics an operator runs before/after a migration, or on a
monitoring interval, per ``docs/DEPLOYMENT.md#health-checks`` and
``docs/STAGING_VALIDATION.md``. Neither command writes anything:

- ``check`` confirms the database is reachable and, for SQLite, runs the
  engine's own ``PRAGMA integrity_check`` -- catching file-level corruption
  (e.g. an interrupted OS-level copy, a truncated restore) without needing
  a shell and ``sqlite3`` on the operator's machine.
- ``migration-status`` compares the database's recorded Alembic revision
  against the migration scripts on disk, so "is this database up to date"
  never requires reading ``alembic_version`` by hand.

Implemented directly against SQLAlchemy/Alembic here rather than through a
new application service -- this mirrors ``init_cmd.py``'s existing direct
use of the Alembic API for the same class of infrastructure-level,
non-domain concern.
"""

from __future__ import annotations

from pathlib import Path

import typer
from alembic.config import Config
from alembic.script import ScriptDirectory
from rich.console import Console
from sqlalchemy import inspect, text

from app.core.container import Container

console = Console()
app = typer.Typer(help="Database health and migration-status checks.")


def _find_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "alembic.ini").exists():
            return candidate
    raise FileNotFoundError("Could not locate alembic.ini above the app.cli package.")


def _script_directory() -> ScriptDirectory:
    repo_root = _find_repo_root()
    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
    return ScriptDirectory.from_config(alembic_cfg)


@app.command("check")
def check(ctx: typer.Context) -> None:
    """Confirm the database is reachable and, for SQLite, structurally intact."""
    container: Container = ctx.obj
    engine = container.engine()

    try:
        with engine.connect() as connection:
            if engine.url.get_backend_name() == "sqlite":
                result = connection.execute(text("PRAGMA integrity_check")).scalar()
                if result != "ok":
                    console.print(f"[red]Database integrity check failed: {result}[/red]")
                    raise typer.Exit(code=1)
            table_names = set(inspect(engine).get_table_names())
    except typer.Exit:
        raise
    except Exception as exc:
        console.print(f"[red]Database is not reachable: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if "alembic_version" not in table_names:
        console.print(
            "[yellow]Database is reachable but has never been migrated -- "
            "run 'sigint init'.[/yellow]"
        )
        raise typer.Exit(code=1)

    console.print(
        f"[bold green]Database is reachable and healthy[/bold green] "
        f"({len(table_names)} table(s))."
    )


@app.command("migration-status")
def migration_status(ctx: typer.Context) -> None:
    """Show the database's current Alembic revision against the latest migration on disk."""
    container: Container = ctx.obj
    script_directory = _script_directory()
    head_revision = script_directory.get_current_head()

    engine = container.engine()
    try:
        with engine.connect() as connection:
            table_names = set(inspect(engine).get_table_names())
            current_revision = (
                connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
                if "alembic_version" in table_names
                else None
            )
    except Exception as exc:
        console.print(f"[red]Could not read migration status: {exc}[/red]")
        raise typer.Exit(code=1) from exc

    if current_revision is None:
        console.print(
            f"[yellow]Database has never been migrated.[/yellow] "
            f"Head revision is {head_revision!r}. Run 'sigint init'."
        )
        raise typer.Exit(code=1)

    if current_revision == head_revision:
        console.print(
            f"[bold green]Database is up to date[/bold green] at revision {current_revision!r}."
        )
        return

    try:
        pending = list(script_directory.iterate_revisions("head", current_revision))
    except Exception as exc:
        console.print(
            f"[red]Database is at an unrecognized revision {current_revision!r}: {exc}[/red]"
        )
        raise typer.Exit(code=1) from exc
    pending_ids = [script.revision for script in reversed(pending)]
    console.print(
        f"[yellow]Database is at revision {current_revision!r}; "
        f"head is {head_revision!r}.[/yellow]"
    )
    console.print(f"Pending migration(s): {', '.join(pending_ids)}")
    console.print("Run 'sigint init' to apply them.")
    raise typer.Exit(code=1)
