"""``sigint inspect-lead`` -- print one Lead's full detail plus its supporting Signals.

Read-only: never re-runs verification (unlike ``sigint verify lead``) and
never mutates anything. Exists to give an operator everything the
lead-quality checklist in ``docs/STAGING_VALIDATION.md`` needs to manually
review a single Lead -- service category, location, reasoning, scores,
verification status, and every supporting Signal's source, confidence, and
verification state -- without hand-querying the database.
"""

from __future__ import annotations

from uuid import UUID

import typer
from rich.console import Console
from rich.table import Table

from app.core.container import Container

console = Console(width=160)

_STATUS_STYLE = {"verified": "green", "rejected": "red", "unverified": "yellow"}


def inspect_lead(
    ctx: typer.Context,
    lead_id: str = typer.Argument(..., help="UUID of the lead to inspect."),
) -> None:
    """Print a Lead's full detail and every supporting Signal, for manual review."""
    try:
        parsed_id = UUID(lead_id)
    except ValueError as exc:
        console.print(f"[red]Invalid lead id {lead_id!r}: {exc}[/red]")
        raise typer.Exit(code=2) from exc

    container: Container = ctx.obj
    lead = container.lead_repository().get_by_id(parsed_id)
    if lead is None:
        console.print(f"[red]No lead found with id {parsed_id}.[/red]")
        raise typer.Exit(code=1)

    status_style = _STATUS_STYLE.get(lead.verification_status.value, "white")
    console.print(f"[bold]Lead {lead.id}[/bold]")
    console.print(f"  Type:                {lead.lead_type.value}")
    console.print(
        f"  Location:            {lead.municipality}, {lead.county} ({lead.country.value})"
    )
    console.print(
        f"  Verification status: [{status_style}]{lead.verification_status.value}[/{status_style}]"
    )
    console.print(f"  Priority:            {lead.priority.value}")
    console.print(f"  Intent score:        {lead.intent_score:.2f}")
    console.print(f"  Confidence:          {lead.estimated_confidence:.2f}")
    console.print(f"  Created at:          {lead.created_at.isoformat()}")
    console.print(f"  Reasoning:           {lead.reasoning}")

    signals = container.signal_repository().list_by_ids(lead.supporting_signal_ids)
    found_ids = {signal.id for signal in signals}
    missing_ids = [sid for sid in lead.supporting_signal_ids if sid not in found_ids]

    table = Table(
        title=f"Supporting signals ({len(signals)}/{len(lead.supporting_signal_ids)} found)"
    )
    table.add_column("Signal ID")
    table.add_column("Type")
    table.add_column("Source")
    table.add_column("Verified")
    table.add_column("Confidence", justify="right")
    table.add_column("Timestamp")
    for signal in signals:
        verified_style = "green" if signal.verified.value == "verified" else "red"
        table.add_row(
            str(signal.id),
            signal.signal_type.value,
            signal.source,
            f"[{verified_style}]{signal.verified.value}[/{verified_style}]",
            f"{signal.confidence:.2f}",
            signal.timestamp.isoformat(),
        )
    console.print(table)

    if missing_ids:
        console.print(
            f"[red]{len(missing_ids)} supporting signal id(s) cited by this lead no longer "
            f"exist in storage: {', '.join(str(sid) for sid in missing_ids)}[/red]"
        )
