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

import os
from pathlib import Path
from typing import Any

import yaml
from loguru import logger

from app.config.settings import AppSettings
from app.core.exceptions import ConfigurationError

DEFAULT_CONFIG_PATH = Path("config/default.yaml")

#: Cache of previously resolved settings, keyed by (config path, relevant
#: environment snapshot) so a change to either -- not just a repeated call
#: -- always produces a fresh result. Module-level rather than per-caller
#: because ``load_settings`` is a pure function of its inputs: the YAML
#: file on disk and the current ``SIGINT_*`` environment.
_CACHE: dict[tuple[str, tuple[tuple[str, str], ...]], AppSettings] = {}


def _env_snapshot() -> tuple[tuple[str, str], ...]:
    return tuple(sorted((k, v) for k, v in os.environ.items() if k.startswith("SIGINT_")))


def clear_settings_cache() -> None:
    """Drop every cached ``AppSettings`` result. Mainly useful for tests."""
    _CACHE.clear()


def load_settings(config_path: Path | None = None, *, use_cache: bool = True) -> AppSettings:
    """Build an ``AppSettings`` instance from YAML defaults and environment overrides.

    Results are cached in-process, keyed by ``config_path`` and the current
    ``SIGINT_*`` environment -- parsing YAML and re-validating the merged
    settings on every call is wasted work when nothing that could change
    the result has changed. Pass ``use_cache=False`` to always re-read
    from disk (e.g. after a YAML file is known to have changed on disk
    within the same process).

    Raises:
        ConfigurationError: If the YAML file exists but cannot be parsed,
            or if the merged configuration fails validation.
    """
    path = config_path if config_path is not None else DEFAULT_CONFIG_PATH
    cache_key = (str(path), _env_snapshot())

    if use_cache and cache_key in _CACHE:
        logger.debug("Configuration cache hit for {}.", path)
        return _CACHE[cache_key]

    yaml_values = _load_yaml(path)

    env_settings = AppSettings()
    env_overrides = env_settings.model_dump(include=env_settings.model_fields_set)

    merged = _deep_merge(yaml_values, env_overrides)

    try:
        settings = AppSettings(**merged)
    except Exception as exc:
        raise ConfigurationError(
            f"Invalid configuration after merging {path} with environment: {exc}"
        ) from exc

    logger.debug("Resolved configuration from {} (cached: {}).", path, use_cache)
    if use_cache:
        _CACHE[cache_key] = settings
    return settings


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
