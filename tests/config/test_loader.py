"""Tests for app.config.loader.load_settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config.loader import load_settings
from app.core.exceptions import ConfigurationError


def test_load_settings_uses_yaml_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGINT_DATABASE__URL", raising=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text("database:\n  url: sqlite:///./custom.db\n", encoding="utf-8")

    settings = load_settings(config_file)

    assert settings.database.url == "sqlite:///./custom.db"


def test_env_var_overrides_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_file = tmp_path / "config.yaml"
    config_file.write_text("database:\n  url: sqlite:///./custom.db\n", encoding="utf-8")
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///./env-override.db")

    settings = load_settings(config_file)

    assert settings.database.url == "sqlite:///./env-override.db"


def test_missing_file_uses_hardcoded_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIGINT_DATABASE__URL", raising=False)

    settings = load_settings(tmp_path / "does_not_exist.yaml")

    assert settings.database.url == "sqlite:///./data/signals.db"


def test_invalid_yaml_raises_configuration_error(tmp_path: Path) -> None:
    config_file = tmp_path / "broken.yaml"
    config_file.write_text("not: [valid: yaml", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_settings(config_file)


def test_non_mapping_yaml_raises_configuration_error(tmp_path: Path) -> None:
    config_file = tmp_path / "list.yaml"
    config_file.write_text("- a\n- b\n", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_settings(config_file)
