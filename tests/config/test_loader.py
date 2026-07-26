"""Tests for app.config.loader.load_settings."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.config.loader import load_settings
from app.core.exceptions import ConfigurationError

_YAML_A = "database:\n  url: sqlite:///./a.db\n"
_YAML_B = "database:\n  url: sqlite:///./b.db\n"


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


def test_repeated_calls_are_served_from_cache(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIGINT_DATABASE__URL", raising=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(_YAML_A, encoding="utf-8")

    load_settings(config_file)
    config_file.write_text(_YAML_B, encoding="utf-8")  # changed on disk after the first call

    cached = load_settings(config_file)
    assert cached.database.url == "sqlite:///./a.db"  # still the first result


def test_use_cache_false_always_rereads_disk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("SIGINT_DATABASE__URL", raising=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(_YAML_A, encoding="utf-8")

    load_settings(config_file)
    config_file.write_text(_YAML_B, encoding="utf-8")

    fresh = load_settings(config_file, use_cache=False)
    assert fresh.database.url == "sqlite:///./b.db"


def test_a_changed_env_var_busts_the_cache(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SIGINT_DATABASE__URL", raising=False)
    config_file = tmp_path / "config.yaml"
    config_file.write_text(_YAML_A, encoding="utf-8")

    load_settings(config_file)
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///./env.db")

    settings = load_settings(config_file)
    assert settings.database.url == "sqlite:///./env.db"


def test_a_failed_load_is_never_cached(tmp_path: Path) -> None:
    config_file = tmp_path / "broken.yaml"
    config_file.write_text("not: [valid: yaml", encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(config_file)

    config_file.write_text("database:\n  url: sqlite:///./fixed.db\n", encoding="utf-8")
    assert load_settings(config_file).database.url == "sqlite:///./fixed.db"
