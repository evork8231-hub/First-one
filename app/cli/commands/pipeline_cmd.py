"""``sigint pipeline`` -- run the full Signal Intelligence pipeline end-to-end.

Orchestrates the same application services every other CLI command
resolves individually (``sigint collect`` / ``verify`` / ``correlate`` /
``generate`` / ``export``) in the mission's documented order:

    Collect -> Verify Signals -> Correlate -> Generate Leads ->
    Verify Leads -> Export (optional)

No new business logic lives here -- this command is pure orchestration
over already-implemented services, with staged progress reporting.
"""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Annotated

import typer
from loguru import logger
from rich.console import Console
from rich.progress import BarColumn, Progress, TextColumn, TimeElapsedColumn

from app.application.interfaces.rule_engine import RuleMatch
from app.config.settings import AppSettings
from app.core.container import Container
from app.core.exceptions import CollectorError, ExportError
from app.domain.enums import ServiceCategory
from app.domain.lead import Lead
from app.domain.signal import Signal

console = Console()

_EXPORT_FORMATS = ("json", "csv", "xlsx")


def pipeline(
    ctx: typer.Context,
    skip_collect: Annotated[
        bool,
        typer.Option(
            "--skip-collect", help="Skip collection; run from signals already in storage."
        ),
    ] = False,
    export_format: Annotated[
        str | None,
        typer.Option(
            "--export-format",
            "-f",
            help="If given, export VERIFIED leads in this format after the run: "
            "'json', 'csv', or 'xlsx'.",
        ),
    ] = None,
    output: Annotated[
        Path | None,
        typer.Option("--output", "-o", help="File to write the export to. Required for 'xlsx'."),
    ] = None,
    lead_type: Annotated[
        ServiceCategory | None,
        typer.Option("--lead-type", help="Filter the optional export by service category."),
    ] = None,
    limit: Annotated[
        int, typer.Option("--limit", help="Maximum signals/leads considered per stage.")
    ] = 1000,
) -> None:
    """Run collect -> verify -> correlate -> generate -> verify -> (optional) export."""
    if limit <= 0:
        console.print("[red]--limit must be a positive integer.[/red]")
        raise typer.Exit(code=2)
    if export_format is not None and export_format not in _EXPORT_FORMATS:
        console.print(
            f"[red]Unsupported --export-format {export_format!r}; use json/csv/xlsx.[/red]"
        )
        raise typer.Exit(code=2)
    if export_format == "xlsx" and output is None:
        console.print("[red]'--output' is required when --export-format is 'xlsx'.[/red]")
        raise typer.Exit(code=2)

    container: Container = ctx.obj
    settings = container.settings()

    stage_count = 5 + (0 if skip_collect else 1) + (1 if export_format else 0)

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        overall = progress.add_task("Pipeline", total=stage_count)

        if not skip_collect:
            _run_collect_stage(container, settings, progress)
            progress.advance(overall)

        verified_signals = _run_verify_signals_stage(container, progress, limit=limit)
        progress.advance(overall)

        matches = _run_correlate_stage(container, progress, limit=limit)
        progress.advance(overall)

        leads = _run_generate_stage(container, progress, matches)
        progress.advance(overall)

        verified_leads = _run_verify_leads_stage(container, progress, leads)
        progress.advance(overall)

        exported_path: Path | None = None
        if export_format:
            exported_path = _run_export_stage(
                container, progress, export_format=export_format, output=output, lead_type=lead_type
            )
            progress.advance(overall)

    console.print(
        f"[bold green]Pipeline complete:[/bold green] "
        f"{len(verified_signals)} signal(s) verified, {len(matches)} rule match(es), "
        f"{len(leads)} lead(s) generated, {len(verified_leads)} lead(s) verified."
    )
    if exported_path is not None:
        console.print(f"Exported verified leads to {exported_path}.")
    elif export_format:
        console.print("Export payload printed above.")


def _run_collect_stage(container: Container, settings: AppSettings, progress: Progress) -> None:
    enabled = settings.collectors.enabled_set
    collectors = container.collector_registry().list_enabled(enabled)
    weather_collectors = container.weather_collector_registry().list_enabled(enabled)
    if not collectors and not weather_collectors:
        logger.warning("Pipeline: no collectors enabled; skipping collection.")
        return

    task = progress.add_task("Collecting signals...", total=None)
    if collectors:
        signal_service = container.signal_service()
        results = asyncio.run(
            signal_service.ingest_from_collectors(
                collectors, max_concurrency=settings.concurrency.max_concurrent_collectors
            )
        )
        failed = [r for r in results if not r.succeeded]
        total = sum(len(r.signals) for r in results if r.succeeded)
        logger.info(
            "Pipeline collect stage: {} collector(s) run, {} signal(s) ingested, {} failed.",
            len(results),
            total,
            len(failed),
        )

    if weather_collectors:
        weather_service = container.weather_event_service()
        for weather_collector in weather_collectors:
            try:
                events = asyncio.run(weather_service.ingest_from_collector(weather_collector))
                logger.info(
                    "Pipeline collect stage: weather collector {} ingested {} event(s).",
                    weather_collector.name,
                    len(events),
                )
            except CollectorError as exc:
                logger.error(
                    "Pipeline collect stage: weather collector {} failed: {}",
                    weather_collector.name,
                    exc.message,
                )
    progress.remove_task(task)


def _run_verify_signals_stage(
    container: Container, progress: Progress, *, limit: int
) -> list[Signal]:
    signal_service = container.signal_service()
    verification_service = container.verification_service()
    pending = signal_service.list_unverified(limit=limit)

    task = progress.add_task("Verifying signals...", total=max(len(pending), 1))
    verified: list[Signal] = []
    for signal in pending:
        verified.append(asyncio.run(verification_service.verify_signal(signal.id)))
        progress.advance(task)
    if not pending:
        progress.advance(task)
    progress.remove_task(task)

    accepted = sum(1 for s in verified if s.verified.value == "verified")
    logger.info(
        "Pipeline verify-signals stage: {} verified, {} rejected.",
        accepted,
        len(verified) - accepted,
    )
    return verified


def _run_correlate_stage(
    container: Container, progress: Progress, *, limit: int
) -> list[RuleMatch]:
    task = progress.add_task("Correlating verified signals...", total=None)
    matches = container.correlation_service().run(limit=limit)
    logger.info("Pipeline correlate stage: {} rule match(es) found.", len(matches))
    progress.remove_task(task)
    return matches


def _run_generate_stage(
    container: Container, progress: Progress, matches: list[RuleMatch]
) -> list[Lead]:
    task = progress.add_task(f"Scoring {len(matches)} candidate lead(s)...", total=None)
    leads = container.lead_generation_service().generate_from_matches(matches)
    logger.info("Pipeline generate stage: {} lead(s) generated.", len(leads))
    progress.remove_task(task)
    return leads


def _run_verify_leads_stage(
    container: Container, progress: Progress, leads: list[Lead]
) -> list[Lead]:
    verification_service = container.verification_service()
    task = progress.add_task("Verifying leads...", total=max(len(leads), 1))
    verified_leads: list[Lead] = []
    for lead in leads:
        verified_leads.append(asyncio.run(verification_service.verify_lead(lead.id)))
        progress.advance(task)
    if not leads:
        progress.advance(task)
    progress.remove_task(task)

    accepted = sum(1 for lead in verified_leads if lead.verification_status.value == "verified")
    logger.info(
        "Pipeline verify-leads stage: {} verified, {} rejected.",
        accepted,
        len(verified_leads) - accepted,
    )
    return verified_leads


def _run_export_stage(
    container: Container,
    progress: Progress,
    *,
    export_format: str,
    output: Path | None,
    lead_type: ServiceCategory | None,
) -> Path | None:
    task = progress.add_task(f"Exporting leads as {export_format}...", total=None)
    service = container.export_service()
    try:
        payload = service.export_leads(
            export_format=export_format,  # type: ignore[arg-type]
            lead_type=lead_type,
        )
    except ExportError as exc:
        progress.remove_task(task)
        console.print(f"[red]Export failed: {exc.message}[/red]")
        raise typer.Exit(code=1) from exc
    progress.remove_task(task)

    if output is None:
        console.print(payload)
        return None

    output.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(payload, bytes):
        output.write_bytes(payload)
    else:
        output.write_text(payload, encoding="utf-8")
    return output
