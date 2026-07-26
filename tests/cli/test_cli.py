"""Tests for the Typer CLI."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.cli.main import app
from sqlalchemy import create_engine, inspect
from typer.testing import CliRunner

runner = CliRunner()


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
