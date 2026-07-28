"""``sigint verify-collector`` -- run a collector for real and report READY/NOT READY.

Dispatches to the discovery approach appropriate for each collector's
kind (field-map validation for the JSON-based Ehitisregister collector;
configuration/execution checks for the browser-based real-estate
listing collectors and the XML weather collector), then executes the
collector itself via ``collect()`` -- which never persists anything;
only ``SignalService``/``WeatherEventService`` write to storage -- so
this is a safe, read-only dry run.

Produces a final enablement report an operator uses to decide whether a
collector belongs in ``collectors.enabled``, with an exit code matching
the verdict (0 for READY, 1 for NOT READY/BLOCKED, 2 for a usage error).
Never enables a collector, never edits configuration, and never invents
a verdict beyond what the real run and sampled data show.

Every verdict (except the permanently ``BLOCKED`` ehitisregister_xtee,
which needs no lifecycle tracking) is recorded via
``app.application.services.collector_lifecycle_service.CollectorLifecycleService``.
``sigint collect --all`` and ``sigint pipeline`` read that record to
refuse to actually run a collector that is listed in
``collectors.enabled`` but was never verified READY here -- this command
is what moves a collector from merely configured to safe to mass-collect
from.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from typing import Annotated, Any

import typer
from rich.console import Console

from app.collectors.field_map_discovery import find_unmapped_keys, suggest_field_map
from app.core.container import Container
from app.core.exceptions import CollectorError

console = Console(width=160)

_LISTING_COLLECTORS = ("kv_ee", "kinnisvara24", "city24")

_XTEE_BLOCKED_MESSAGE = (
    "ehitisregister_xtee is DISABLED BY DESIGN. X-tee is a real, documented access path "
    "to Ehitisregister, but it requires a registered X-tee member agreement, a security "
    "server, and member certificates this platform cannot provision -- and even with "
    "those, the operation-specific request/response schema was never verified against a "
    "real service. See docs/COLLECTORS.md#ehitisregister and "
    "app/collectors/ehitisregister_xtee_collector.py. This collector will never run; "
    "no discovery is attempted."
)


def verify_collector(
    ctx: typer.Context,
    name: Annotated[str, typer.Argument(help="Registered collector name to verify.")],
    sample_limit: Annotated[
        int,
        typer.Option("--sample-limit", help="How many real records to sample, where applicable."),
    ] = 5,
) -> None:
    """Execute a collector end-to-end and report a READY/NOT READY enablement verdict."""
    if sample_limit <= 0:
        console.print("[red]--sample-limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj

    if name == "ehitisregister_xtee":
        console.print("\n[bold yellow]Enablement report: BLOCKED[/bold yellow]")
        console.print(f"  - {_XTEE_BLOCKED_MESSAGE}")
        raise typer.Exit(code=1)

    if name == "ehitisregister":
        ready = asyncio.run(_verify_ehitisregister(container, sample_limit))
    elif name == "ilmateenistus":
        ready = asyncio.run(_verify_ilmateenistus(container))
    elif name in _LISTING_COLLECTORS:
        ready = asyncio.run(_verify_listing_collector(container, name))
    else:
        console.print(
            f"[red]Unknown collector {name!r}. Known collectors: ehitisregister, "
            f"ehitisregister_xtee, ilmateenistus, {', '.join(_LISTING_COLLECTORS)}.[/red]"
        )
        raise typer.Exit(code=2)

    container.collector_lifecycle_service().record_verification_attempt(name, ready=ready)
    raise typer.Exit(code=0 if ready else 1)


def _print_verdict(verdict: str, reasons: Sequence[str]) -> bool:
    color = "green" if verdict == "READY" else "red"
    console.print(f"\n[bold {color}]Enablement report: {verdict}[/bold {color}]")
    for reason in reasons:
        console.print(f"  - {reason}")
    return verdict == "READY"


def _has_any(record: Mapping[str, Any], candidate_keys: Sequence[str]) -> bool:
    return any(key in record and record[key] not in (None, "") for key in candidate_keys)


async def _verify_ehitisregister(container: Container, sample_limit: int) -> bool:
    collector = container.ehitisregister_collector()
    field_map = container.settings().collectors.ehitisregister.field_map

    console.print("[bold]Step 1/3[/bold]: sampling real records...")
    try:
        records = await collector.sample_raw_records(limit=sample_limit)
    except CollectorError as exc:
        return _print_verdict("NOT READY", [f"Sampling failed: {exc.message}"])

    if not records:
        return _print_verdict("NOT READY", ["The source returned no records to sample."])

    console.print(f"Sampled {len(records)} record(s):")
    for record in records:
        console.print(json.dumps(record, ensure_ascii=False, default=str)[:500])

    console.print("\n[bold]Step 2/3[/bold]: validating field_map coverage...")
    unmapped = find_unmapped_keys(records, field_map)
    if unmapped:
        console.print(f"[yellow]{len(unmapped)} unmapped key(s) found: {sorted(unmapped)}[/yellow]")
        for key, suggestions in suggest_field_map(records, field_map).items():
            top = suggestions[0]
            console.print(
                f"  {key!r} -> suggest {top.canonical_field!r} "
                f"(confidence {top.confidence:.0%})"
            )
    else:
        console.print("[green]Every observed key is already covered by field_map.[/green]")

    required_present = sum(
        1
        for record in records
        if _has_any(record, field_map.get("county", []))
        and _has_any(record, field_map.get("municipality", []))
    )
    console.print(
        f"{required_present}/{len(records)} sampled record(s) have both county and "
        f"municipality present under the configured field_map."
    )

    reasons: list[str] = []
    if required_present == 0:
        reasons.append(
            "No sampled record has both a county and municipality value under any "
            "configured field_map key -- collect() will skip every such record."
        )

    console.print("\n[bold]Step 3/3[/bold]: executing the collector end-to-end (no persistence)...")
    try:
        signals = await collector.collect()
    except CollectorError as exc:
        reasons.append(f"collect() raised: {exc.message}")
        return _print_verdict("NOT READY", reasons)

    console.print(f"collect() produced {len(signals)} signal(s) from this run.")
    if not signals:
        reasons.append("collect() produced zero signals from the currently available records.")

    return _print_verdict("NOT READY" if reasons else "READY", reasons)


async def _verify_ilmateenistus(container: Container) -> bool:
    collector = container.weather_collector_registry().get("ilmateenistus")
    config = container.settings().collectors.ilmateenistus
    if not config.xml_url:
        return _print_verdict(
            "NOT READY",
            [
                "collectors.ilmateenistus.xml_url is unset. Use "
                "'sigint inspect-xml --url <feed>' to inspect the real feed structure "
                "first, then set xml_url before enabling this collector."
            ],
        )

    console.print("[bold]Executing the collector end-to-end (no persistence)...[/bold]")
    try:
        events = await collector.collect()
    except CollectorError as exc:
        return _print_verdict("NOT READY", [f"collect() raised: {exc.message}"])

    console.print(f"collect() produced {len(events)} weather event(s) from this run.")
    console.print(
        "[dim]Zero events can be a legitimate absence of severe weather right now -- "
        "this only confirms the collector runs against the real feed without error.[/dim]"
    )
    return _print_verdict("READY", [])


async def _verify_listing_collector(container: Container, name: str) -> bool:
    collector = container.collector_registry().get(name)
    config = getattr(container.settings().collectors, name)
    if not config.search_paths or not config.listing_link_selector:
        return _print_verdict(
            "NOT READY",
            [
                f"{name} is not configured: search_paths and listing_link_selector are "
                f"unset. Use 'sigint discover-selectors --url <search-page-url> "
                f"--collector {name}' first, then set both before enabling this collector."
            ],
        )

    console.print("[bold]Executing the collector end-to-end (no persistence)...[/bold]")
    try:
        signals = await collector.collect()
    except CollectorError as exc:
        return _print_verdict("NOT READY", [f"collect() raised: {exc.message}"])

    console.print(f"collect() produced {len(signals)} signal(s) from this run.")
    console.print(
        "[dim]Zero signals can be legitimate (no listing currently mentions a matched "
        "renovation phrase) -- this only confirms the collector runs end-to-end without "
        "error.[/dim]"
    )
    return _print_verdict("READY", [])
