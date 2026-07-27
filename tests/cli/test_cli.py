"""Tests for the Typer CLI."""

from __future__ import annotations

from pathlib import Path

import app.collectors.ehitisregister_collector as ehr_module
import httpx
import pytest
from app.cli.main import app
from app.collectors.http_client import HttpClient
from app.core.retry import RetryPolicy
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType
from app.repositories.sqlite.audit_log_repository import SQLiteAuditLogRepository
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.repositories.sqlite.weather_repository import SQLiteWeatherEventRepository
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker
from typer.testing import CliRunner

from tests.fixtures.factories import make_signal, make_weather_event

runner = CliRunner()


def _seed_signal(db_path: Path, **overrides: object) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    SQLiteSignalRepository(session_factory).add(make_signal(**overrides))


def _seed_weather_event(db_path: Path, **overrides: object) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    SQLiteWeatherEventRepository(session_factory).add(make_weather_event(**overrides))


def _seed_collector_run(
    db_path: Path, *, collector: str, succeeded: bool, item_count: int = 3
) -> None:
    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteAuditLogRepository(session_factory)
    if succeeded:
        repo.add(
            AuditLogEntry(
                event_type=AuditEventType.COLLECTOR_RUN_COMPLETED,
                entity_type="Collector",
                message=f"Collector {collector!r} produced {item_count} signal(s).",
                context={
                    "collector": collector,
                    "signal_count": item_count,
                    "duration_seconds": 1.234,
                },
            )
        )
    else:
        repo.add(
            AuditLogEntry(
                event_type=AuditEventType.COLLECTOR_RUN_FAILED,
                entity_type="Collector",
                message=f"Collector {collector!r} failed: simulated failure.",
                context={"collector": collector, "duration_seconds": 0.5},
            )
        )


@pytest.fixture(autouse=True)
def _quiet_logging_and_isolated_rules(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_LOGGING__LOG_FILE", "")
    monkeypatch.setenv("SIGINT_RULES__DIRECTORY", str(tmp_path))


def test_config_validate_default_file_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["config", "validate", "--config", "config/default.yaml"])
    assert result.exit_code == 0, result.output


def test_config_validate_missing_file_still_succeeds_with_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["config", "validate", "--config", "does/not/exist.yaml"])
    assert result.exit_code == 0, result.output


def test_config_show_prints_yaml(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["config", "show"])
    assert result.exit_code == 0
    assert "environment:" in result.output


def test_collect_unknown_collector_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["collect", "--collector", "does_not_exist"])
    assert result.exit_code == 1
    assert "does_not_exist" in result.output


def test_init_creates_expected_tables(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0, result.output
    assert db_path.exists()

    engine = create_engine(f"sqlite:///{db_path}")
    tables = set(inspect(engine).get_table_names())
    assert {"signals", "leads", "weather_events", "audit_logs", "configuration"}.issubset(tables)


def test_correlate_reports_zero_matches_on_empty_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["correlate"])

    assert result.exit_code == 0, result.output
    assert "0" in result.output


def test_collect_requires_either_collector_or_all(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["collect"])
    assert result.exit_code == 2, result.output


def test_collect_rejects_collector_and_all_together(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["collect", "--collector", "x", "--all"])
    assert result.exit_code == 2, result.output


def test_collect_all_with_no_enabled_collectors_reports_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["collect", "--all"])
    assert result.exit_code == 1, result.output
    assert "No collectors are enabled" in result.output


def test_collect_all_runs_an_enabled_weather_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test for the audit finding that --all never ran weather collectors.

    ilmateenistus refuses to run without xml_url configured, so this
    exercises the real failure path -- proving weather_collector_registry
    and weather_event_service are actually invoked (they previously were
    not invoked at all), without needing network access.
    """
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SIGINT_COLLECTORS__ENABLED", '["ilmateenistus"]')
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["collect", "--all"])

    assert "weather collector(s)" in result.output
    assert "ilmateenistus" in result.output


def test_pipeline_skip_collect_does_not_touch_weather_collectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SIGINT_COLLECTORS__ENABLED", '["ilmateenistus"]')
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["pipeline", "--skip-collect"])

    assert result.exit_code == 0, result.output
    assert "Pipeline complete" in result.output


def test_pipeline_collect_stage_runs_an_enabled_weather_collector(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression test: the pipeline's collect stage previously never ran weather collectors."""
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SIGINT_COLLECTORS__ENABLED", '["ilmateenistus"]')
    monkeypatch.setenv("SIGINT_LOGGING__LEVEL", "ERROR")
    runner.invoke(app, ["init"])

    # ilmateenistus fails immediately (no xml_url configured); the pipeline must still
    # complete (the failure is caught, not propagated) and reach the final stage.
    result = runner.invoke(app, ["pipeline"])

    assert result.exit_code == 0, result.output
    assert "Pipeline complete" in result.output


def test_verify_signals_on_empty_database_reports_zero(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["verify", "signals"])

    assert result.exit_code == 0, result.output
    assert "No unverified signals" in result.output


def test_verify_signals_rejects_a_non_positive_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify", "signals", "--limit", "0"])
    assert result.exit_code == 2, result.output


def test_verify_lead_invalid_uuid_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify", "lead", "not-a-uuid"])
    assert result.exit_code == 2, result.output


def test_verify_lead_missing_reports_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["verify", "lead", "00000000-0000-0000-0000-000000000000"])

    assert result.exit_code == 1, result.output


def test_export_unsupported_format_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["export", "--format", "yaml"])
    assert result.exit_code == 2, result.output


def test_export_xlsx_without_output_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["export", "--format", "xlsx"])
    assert result.exit_code == 2, result.output


def test_export_json_on_empty_database(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["export", "--format", "json"])

    assert result.exit_code == 0, result.output
    assert "[]" in result.output


def test_score_on_empty_database_reports_no_leads(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["score"])

    assert result.exit_code == 0, result.output
    assert "No leads match" in result.output


def test_stats_on_empty_database_reports_zero_counts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["stats"])

    assert result.exit_code == 0, result.output
    assert "Weather events stored" in result.output


def test_pipeline_skip_collect_completes_on_empty_database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["pipeline", "--skip-collect"])

    assert result.exit_code == 0, result.output
    assert "Pipeline complete" in result.output


def test_pipeline_rejects_an_unsupported_export_format(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["pipeline", "--export-format", "yaml"])
    assert result.exit_code == 2, result.output


def test_pipeline_xlsx_export_requires_output(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["pipeline", "--export-format", "xlsx"])
    assert result.exit_code == 2, result.output


def test_purge_signals_dry_run_previews_without_deleting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "purge.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])
    _seed_signal(db_path, source="stale_collector")
    _seed_signal(db_path, source="stale_collector")
    _seed_signal(db_path, source="keep_me")

    result = runner.invoke(app, ["purge", "signals", "--source", "stale_collector"])

    assert result.exit_code == 0, result.output
    assert "DRY RUN" in result.output
    assert "2 signal(s)" in result.output

    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteSignalRepository(session_factory)
    assert repo.count() == 3  # nothing was actually deleted


def test_purge_signals_with_yes_actually_deletes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "purge.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])
    _seed_signal(db_path, source="stale_collector")
    _seed_signal(db_path, source="keep_me")

    result = runner.invoke(app, ["purge", "signals", "--source", "stale_collector", "--yes"])

    assert result.exit_code == 0, result.output
    assert "Deleted 1 signal(s)" in result.output

    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    repo = SQLiteSignalRepository(session_factory)
    assert repo.count() == 1
    assert repo.list_all(limit=10)[0].source == "keep_me"


def test_purge_signals_invalid_before_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["purge", "signals", "--source", "x", "--before", "not-a-date"])
    assert result.exit_code == 2, result.output


def test_purge_weather_events_dry_run_then_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "purge.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])
    _seed_weather_event(db_path, source="ilmateenistus")

    preview = runner.invoke(app, ["purge", "weather-events", "--source", "ilmateenistus"])
    assert preview.exit_code == 0, preview.output
    assert "DRY RUN" in preview.output
    assert "1 weather event(s)" in preview.output

    engine = create_engine(f"sqlite:///{db_path}")
    session_factory = sessionmaker(bind=engine)
    assert SQLiteWeatherEventRepository(session_factory).count() == 1

    deletion = runner.invoke(app, ["purge", "weather-events", "--source", "ilmateenistus", "--yes"])
    assert deletion.exit_code == 0, deletion.output
    assert "Deleted 1 weather event(s)" in deletion.output
    assert SQLiteWeatherEventRepository(session_factory).count() == 0


def test_health_with_no_run_history_reports_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "empty.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 0, result.output
    assert "No collector run history" in result.output


def test_health_reports_succeeded_and_failed_collectors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "health.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])
    _seed_collector_run(db_path, collector="ehitisregister", succeeded=True)
    _seed_collector_run(db_path, collector="kv_ee", succeeded=False)

    result = runner.invoke(app, ["health"])

    assert result.exit_code == 0, result.output
    assert "ehitisregister" in result.output
    assert "succeeded" in result.output
    assert "kv_ee" in result.output
    assert "failed" in result.output
    assert "simulated failure" in result.output


def test_health_rejects_a_non_positive_sample_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["health", "--sample-limit", "0"])
    assert result.exit_code == 2, result.output


def _patch_ehitisregister_http_client(
    monkeypatch: pytest.MonkeyPatch, records: list[dict[str, object]]
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/datasets/ehitisregister":
            return httpx.Response(
                200, json={"resources": [{"format": "json", "url": "/files/ehitisregister.json"}]}
            )
        if request.url.path == "/files/ehitisregister.json":
            return httpx.Response(200, json=records)
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)

    def factory(config: object, *, retry_policy: RetryPolicy | None = None) -> HttpClient:
        return HttpClient(config, retry_policy=retry_policy, transport=transport)  # type: ignore[arg-type]

    monkeypatch.setattr(ehr_module, "HttpClient", factory)


def test_discover_fields_reports_unmapped_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    _patch_ehitisregister_http_client(
        monkeypatch,
        [{"maakond": "Harju", "omavalitsus": "Tallinn", "uus_valjand_2024": "value"}],
    )

    result = runner.invoke(app, ["discover-fields"])

    assert result.exit_code == 0, result.output
    assert "uus_valjand_2024" in result.output


def test_discover_fields_with_fully_mapped_sample_reports_nothing_unmapped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    _patch_ehitisregister_http_client(monkeypatch, [{"maakond": "Harju", "omavalitsus": "Tallinn"}])

    result = runner.invoke(app, ["discover-fields"])

    assert result.exit_code == 0, result.output
    assert "already" in result.output


def test_discover_fields_rejects_a_non_positive_sample_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["discover-fields", "--sample-limit", "0"])
    assert result.exit_code == 2, result.output


def test_discover_fields_reports_collector_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    def factory(config: object, *, retry_policy: RetryPolicy | None = None) -> HttpClient:
        return HttpClient(
            config, retry_policy=retry_policy, transport=httpx.MockTransport(handler)
        )  # type: ignore[arg-type]

    monkeypatch.setattr(ehr_module, "HttpClient", factory)

    result = runner.invoke(app, ["discover-fields"])

    assert result.exit_code == 1, result.output


def test_discover_selectors_requires_exactly_one_input_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["discover-selectors"])
    assert result.exit_code == 2, result.output


def test_discover_selectors_rejects_both_url_and_html_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    html_file = tmp_path / "page.html"
    html_file.write_text("<html></html>", encoding="utf-8")

    result = runner.invoke(
        app, ["discover-selectors", "--url", "https://example.ee", "--html-file", str(html_file)]
    )

    assert result.exit_code == 2, result.output


def test_discover_selectors_missing_html_file_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    missing = tmp_path / "does_not_exist.html"

    result = runner.invoke(app, ["discover-selectors", "--html-file", str(missing)])

    assert result.exit_code == 1, result.output


def test_discover_selectors_analyzes_a_local_html_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    html_file = tmp_path / "page.html"
    html_file.write_text(
        "<html><body>"
        '<div class="listing-card"><a class="listing-link" href="/l/1">A</a></div>'
        '<div class="listing-card"><a class="listing-link" href="/l/2">B</a></div>'
        '<div class="listing-card"><a class="listing-link" href="/l/3">C</a></div>'
        "</body></html>",
        encoding="utf-8",
    )

    result = runner.invoke(app, ["discover-selectors", "--html-file", str(html_file)])

    assert result.exit_code == 0, result.output
    assert "listing-card" in result.output
    assert "listing-link" in result.output


def test_discover_selectors_rejects_a_non_positive_min_repeat_count(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    html_file = tmp_path / "page.html"
    html_file.write_text("<html></html>", encoding="utf-8")

    result = runner.invoke(
        app, ["discover-selectors", "--html-file", str(html_file), "--min-repeat-count", "0"]
    )

    assert result.exit_code == 2, result.output


def test_discover_selectors_rejects_an_unknown_collector_for_url_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")

    result = runner.invoke(
        app, ["discover-selectors", "--url", "https://example.ee", "--collector", "not_real"]
    )

    assert result.exit_code == 2, result.output


_SAMPLE_FORECAST_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    "<forecast><tabular><time>"
    '<place name="Tallinn" phenomenon="Tugev vihm"><text>Paduvihm.</text>'
    "<wind><gust>18.5</gust></wind></place>"
    "</time></tabular></forecast>"
)


def test_inspect_xml_requires_exactly_one_input_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["inspect-xml"])
    assert result.exit_code == 2, result.output


def test_inspect_xml_missing_file_is_an_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    missing = tmp_path / "does_not_exist.xml"

    result = runner.invoke(app, ["inspect-xml", "--xml-file", str(missing)])

    assert result.exit_code == 1, result.output


def test_inspect_xml_analyzes_a_local_xml_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    xml_file = tmp_path / "forecast.xml"
    xml_file.write_text(_SAMPLE_FORECAST_XML, encoding="utf-8")

    result = runner.invoke(app, ["inspect-xml", "--xml-file", str(xml_file)])

    assert result.exit_code == 0, result.output
    assert "forecast/tabular/time/place" in result.output
    assert "forecast" in result.output


def test_inspect_xml_malformed_file_reports_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    xml_file = tmp_path / "bad.xml"
    xml_file.write_text("<root><unclosed></root>", encoding="utf-8")

    result = runner.invoke(app, ["inspect-xml", "--xml-file", str(xml_file)])

    assert result.exit_code == 1, result.output


def test_inspect_xml_rejects_a_non_positive_max_samples(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    xml_file = tmp_path / "forecast.xml"
    xml_file.write_text(_SAMPLE_FORECAST_XML, encoding="utf-8")

    result = runner.invoke(
        app, ["inspect-xml", "--xml-file", str(xml_file), "--max-samples-per-path", "0"]
    )

    assert result.exit_code == 2, result.output


def test_inspect_xml_interactive_mode_walks_through_expected_fields(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    xml_file = tmp_path / "forecast.xml"
    xml_file.write_text(_SAMPLE_FORECAST_XML, encoding="utf-8")

    result = runner.invoke(
        app,
        ["inspect-xml", "--xml-file", str(xml_file), "--interactive"],
        input="y\ny\ny\ny\ny\n",
    )

    assert result.exit_code == 0, result.output
    assert "Interactive review" in result.output


def test_collect_first_run_reports_no_schema_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "drift.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])
    _patch_ehitisregister_http_client(monkeypatch, [{"maakond": "Harju", "omavalitsus": "Tallinn"}])

    result = runner.invoke(app, ["collect", "--collector", "ehitisregister"])

    assert result.exit_code == 0, result.output
    assert "Schema drift" not in result.output


def test_collect_second_run_with_new_keys_reports_schema_drift(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "drift.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    runner.invoke(app, ["init"])
    _patch_ehitisregister_http_client(monkeypatch, [{"maakond": "Harju", "omavalitsus": "Tallinn"}])
    runner.invoke(app, ["collect", "--collector", "ehitisregister"])

    _patch_ehitisregister_http_client(
        monkeypatch,
        [{"maakond": "Harju", "omavalitsus": "Tallinn", "uus_valjand_2024": "x"}],
    )
    result = runner.invoke(app, ["collect", "--collector", "ehitisregister"])

    assert result.exit_code == 0, result.output
    assert "Schema drift detected for 'ehitisregister'" in result.output
    assert "1 key(s) added" in result.output


def test_collect_all_reports_schema_drift(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "drift.db"
    monkeypatch.setenv("SIGINT_DATABASE__URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("SIGINT_COLLECTORS__ENABLED", '["ehitisregister"]')
    runner.invoke(app, ["init"])
    _patch_ehitisregister_http_client(monkeypatch, [{"maakond": "Harju", "omavalitsus": "Tallinn"}])
    runner.invoke(app, ["collect", "--all"])

    _patch_ehitisregister_http_client(
        monkeypatch,
        [{"maakond": "Harju", "omavalitsus": "Tallinn", "uus_valjand_2024": "x"}],
    )
    result = runner.invoke(app, ["collect", "--all"])

    assert result.exit_code == 0, result.output
    assert "Schema drift detected for 'ehitisregister'" in result.output


def test_verify_collector_xtee_is_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify-collector", "ehitisregister_xtee"])
    assert result.exit_code == 1, result.output
    assert "BLOCKED" in result.output
    assert "DISABLED BY DESIGN" in result.output


def test_verify_collector_unknown_name_is_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify-collector", "not_a_real_collector"])
    assert result.exit_code == 2, result.output


def test_verify_collector_rejects_a_non_positive_sample_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify-collector", "ehitisregister", "--sample-limit", "0"])
    assert result.exit_code == 2, result.output


def test_verify_collector_ehitisregister_ready_with_valid_records(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    _patch_ehitisregister_http_client(
        monkeypatch, [{"maakond": "Harju", "omavalitsus": "Tallinn", "ehitisregistri_kood": "1"}]
    )

    result = runner.invoke(app, ["verify-collector", "ehitisregister"])

    assert result.exit_code == 0, result.output
    assert "READY" in result.output


def test_verify_collector_ehitisregister_not_ready_when_required_fields_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    _patch_ehitisregister_http_client(monkeypatch, [{"ehitisregistri_kood": "999"}])

    result = runner.invoke(app, ["verify-collector", "ehitisregister"])

    assert result.exit_code == 1, result.output
    assert "NOT READY" in result.output


def test_verify_collector_ilmateenistus_not_ready_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify-collector", "ilmateenistus"])
    assert result.exit_code == 1, result.output
    assert "NOT READY" in result.output
    assert "xml_url" in result.output


def test_verify_collector_kv_ee_not_ready_when_unconfigured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    result = runner.invoke(app, ["verify-collector", "kv_ee"])
    assert result.exit_code == 1, result.output
    assert "NOT READY" in result.output
    assert "listing_link_selector" in result.output
