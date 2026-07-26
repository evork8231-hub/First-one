"""``sigint init`` -- apply Alembic migrations to bring the schema up to date."""

from __future__ import annotations

from pathlib import Path

import typer
from alembic import command as alembic_command
from alembic.config import Config
from rich.console import Console

from app.core.container import Container

console = Console()


def _find_repo_root() -> Path:
    for candidate in Path(__file__).resolve().parents:
        if (candidate / "alembic.ini").exists():
            return candidate
    raise FileNotFoundError("Could not locate alembic.ini above the app.cli package.")


def init(ctx: typer.Context) -> None:
    """Initialize (or upgrade) the database schema by running Alembic migrations to head."""
    container: Container = ctx.obj
    repo_root = _find_repo_root()

    alembic_cfg = Config(str(repo_root / "alembic.ini"))
    alembic_cfg.set_main_option("script_location", str(repo_root / "alembic"))
    # alembic/env.py resolves the URL itself via app.config.loader.load_settings(),
    # using the same environment/YAML precedence as the container -- this line is
    # only for the log message below and the Config object's own fallback value.
    alembic_cfg.set_main_option("sqlalchemy.url", container.settings().database.url)

    console.print(
        f"Applying migrations against [bold]{container.settings().database.url}[/bold] ..."
    )
    alembic_command.upgrade(alembic_cfg, "head")
    console.print("[bold green]Database schema is up to date.[/bold green]")
