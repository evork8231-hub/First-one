"""``sigint collector-status`` -- every registered collector's verification lifecycle state.

Read-only summary over ``CollectorLifecycleService`` (the same state
``sigint collect --all``/``sigint pipeline`` gate on) and the operator's
current ``collectors.enabled`` list -- gives a single place to see which
collectors are safe to mass-collect from without re-running
``sigint verify-collector`` just to check. Triggers no collection itself.
"""

from __future__ import annotations

import typer
from rich.console import Console
from rich.table import Table

from app.core.container import Container
from app.domain.enums import CollectorLifecycleState

console = Console(width=140)

_STATE_STYLE = {
    CollectorLifecycleState.VERIFIED: "green",
    CollectorLifecycleState.TESTED: "yellow",
    CollectorLifecycleState.DISCOVERED: "dim",
}


def collector_status(ctx: typer.Context) -> None:
    """Show every registered collector's lifecycle state and whether it actually runs."""
    container: Container = ctx.obj
    lifecycle = container.collector_lifecycle_service()
    enabled_names = container.settings().collectors.enabled_set

    collector_names = {c.name for c in container.collector_registry().list_all()}
    weather_collector_names = {c.name for c in container.weather_collector_registry().list_all()}
    all_names = sorted(collector_names | weather_collector_names)

    table = Table(title="Collector status")
    table.add_column("Collector")
    table.add_column("Lifecycle state")
    table.add_column("Listed in collectors.enabled")
    table.add_column("Actually runs via collect --all / pipeline")

    for name in all_names:
        state = lifecycle.get_state(name)
        listed = name in enabled_names
        runs = listed and state == CollectorLifecycleState.VERIFIED
        style = _STATE_STYLE.get(state, "white")
        table.add_row(
            name,
            f"[{style}]{state.value}[/{style}]",
            "yes" if listed else "no",
            "[green]yes[/green]" if runs else "[red]no[/red]",
        )
    console.print(table)
    console.print(
        "\nRun 'sigint verify-collector <name>' to move a collector from "
        "DISCOVERED/TESTED to VERIFIED."
    )
