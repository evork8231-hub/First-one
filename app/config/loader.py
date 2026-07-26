"""Loads AppSettings from a YAML file, environment variables, and defaults.

Precedence, highest to lowest:

1. Environment variables (``SIGINT_...``) and ``.env``.
2. The YAML file at ``config_path`` (defaults to ``config/default.yaml``).
3. The hardcoded defaults declared on ``AppSettings`` and its nested models.

This ordering exists specifically so secrets and per-deployment overrides
supplied via environment variables can never be silently overridden by a
committed YAML file, per the "read secrets from environment variables
only" security requirement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from app.config.settings import AppSettings
from app.core.exceptions import ConfigurationError

DEFAULT_CONFIG_PATH = Path("config/default.yaml")


def load_settings(config_path: Path | None = None) -> AppSettings:
    """Build an ``AppSettings`` instance from YAML defaults and environment overrides.

    Raises:
        ConfigurationError: If the YAML file exists but cannot be parsed,
            or if the merged configuration fails validation.
    """
    path = config_path if config_path is not None else DEFAULT_CONFIG_PATH
    yaml_values = _load_yaml(path)

    env_settings = AppSettings()
    env_overrides = env_settings.model_dump(include=env_settings.model_fields_set)

    merged = _deep_merge(yaml_values, env_overrides)

    try:
        return AppSettings(**merged)
    except Exception as exc:
        raise ConfigurationError(
            f"Invalid configuration after merging {path} with environment: {exc}"
        ) from exc


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigurationError(f"Invalid YAML in configuration file {path}: {exc}") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise ConfigurationError(f"Configuration file {path} must contain a top-level mapping.")
    return data


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge ``override`` into ``base``, without mutating either."""
    merged = dict(base)
    for key, value in override.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged
