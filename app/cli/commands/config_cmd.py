"""``sigint config`` -- inspect and validate the resolved configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
import yaml
from rich.console import Console

from app.config.loader import load_settings
from app.core.container import Container
from app.core.exceptions import ConfigurationError

console = Console()
app = typer.Typer(help="Inspect and validate configuration.")

_DEFAULT_CONFIG_PATH = Path("config/default.yaml")


@app.command("show")
def show(ctx: typer.Context) -> None:
    """Print the fully resolved configuration (YAML defaults + environment overrides)."""
    container: Container = ctx.obj
    settings = container.settings()
    console.print(yaml.safe_dump(settings.model_dump(mode="json"), sort_keys=False))


@app.command("validate")
def validate(
    config_path: Annotated[
        Path, typer.Option("--config", help="Path to the YAML configuration file to validate.")
    ] = _DEFAULT_CONFIG_PATH,
) -> None:
    """Validate that ``config_path`` merges into a valid AppSettings instance."""
    try:
        load_settings(config_path)
    except ConfigurationError as exc:
        console.print(f"[red]Configuration is invalid: {exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(f"[bold green]Configuration at {config_path} is valid.[/bold green]")
