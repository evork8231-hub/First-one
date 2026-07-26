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
