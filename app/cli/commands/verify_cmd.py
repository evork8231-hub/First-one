"""``sigint verify`` -- run the configured verifiers against pending Signals or Leads."""

from __future__ import annotations

import asyncio
from uuid import UUID

import typer
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from app.core.container import Container
from app.core.exceptions import EntityNotFoundError

console = Console()
app = typer.Typer(help="Run verification against Signals or Leads.")


@app.command("signals")
def verify_signals(
    ctx: typer.Context,
    limit: int = typer.Option(100, "--limit", help="Maximum number of pending signals to verify."),
) -> None:
    """Verify every currently unverified Signal, up to ``--limit``."""
    if limit <= 0:
        console.print("[red]--limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    signal_service = container.signal_service()
    verification_service = container.verification_service()

    pending = signal_service.list_unverified(limit=limit)
    if not pending:
        console.print("No unverified signals to verify.")
        return

    verified = []
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Verifying signals...", total=len(pending))
        for signal in pending:
            verified.append(asyncio.run(verification_service.verify_signal(signal.id)))
            progress.advance(task)

    accepted = sum(1 for s in verified if s.verified.value == "verified")
    rejected = len(verified) - accepted
    console.print(
        f"Verified {len(verified)} signal(s): "
        f"[green]{accepted} verified[/green], [red]{rejected} rejected[/red]."
    )


@app.command("lead")
def verify_lead(
    ctx: typer.Context,
    lead_id: str = typer.Argument(..., help="UUID of the lead to verify."),
) -> None:
    """Verify a single Lead by ID."""
    try:
        parsed_id = UUID(lead_id)
    except ValueError as exc:
        console.print(f"[red]Invalid lead id {lead_id!r}: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    container: Container = ctx.obj
    service = container.verification_service()
    try:
        lead = asyncio.run(service.verify_lead(parsed_id))
    except EntityNotFoundError as exc:
        console.print(f"[red]{exc.message}[/red]")
        raise typer.Exit(code=1) from exc

    console.print(
        f"Lead {lead.id} verification result: [bold]{lead.verification_status.value}[/bold]"
    )
