"""Typer CLI entry point.

Each subcommand builds nothing itself -- it resolves already-wired
services from the DI container (``app.core.container.Container``) set up
in the root callback and calls into the application layer. No business
logic lives in this package.
"""

from __future__ import annotations

import typer

from app.cli.commands import (
    collect_cmd,
    config_cmd,
    correlate_cmd,
    export_cmd,
    generate_cmd,
    init_cmd,
    pipeline_cmd,
    score_cmd,
    stats_cmd,
    verify_cmd,
)
from app.core.container import Container

app = typer.Typer(
    name="sigint",
    help="Estonia Signal Intelligence Platform -- foundation CLI.",
    no_args_is_help=True,
    add_completion=False,
)


@app.callback()
def main(ctx: typer.Context) -> None:
    """Build the dependency injection container once per invocation."""
    container = Container()
    container.init_resources()
    ctx.obj = container


app.command("init")(init_cmd.init)
app.command("collect")(collect_cmd.collect)
app.command("correlate")(correlate_cmd.correlate)
app.command("generate")(generate_cmd.generate)
app.command("export")(export_cmd.export)
app.command("score")(score_cmd.score)
app.command("pipeline")(pipeline_cmd.pipeline)
app.command("stats")(stats_cmd.stats)
app.add_typer(verify_cmd.app, name="verify", help="Verify pending Signals or a specific Lead.")
app.add_typer(config_cmd.app, name="config", help="Inspect and validate configuration.")


if __name__ == "__main__":
    app()
