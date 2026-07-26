"""Tests for app.rule_engine.loader.RuleLoader."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.core.exceptions import ConfigurationError
from app.rule_engine.loader import RuleLoader

_VALID_RULE_YAML = """
rules:
  - id: test_rule_one
    name: "Test rule one"
    description: "A rule used only in tests."
    lead_type: roofing
    base_confidence: 0.5
    weight: 1.0
    conditions:
      - signal_type: building_record
        min_count: 1
      - signal_type: roof_mention
        min_count: 1
"""

_DISABLED_RULE_YAML = """
rules:
  - id: test_rule_disabled
    name: "Disabled test rule"
    description: "Should not appear in active rules."
    lead_type: solar_installation
    base_confidence: 0.4
    weight: 1.0
    enabled: false
    conditions:
      - signal_type: energy_certificate
        min_count: 1
"""


def _write(path: Path, name: str, content: str) -> None:
    (path / name).write_text(content, encoding="utf-8")


def test_load_all_parses_every_yaml_file(tmp_path: Path) -> None:
    _write(tmp_path, "one.yaml", _VALID_RULE_YAML)
    _write(tmp_path, "two.yaml", _DISABLED_RULE_YAML)

    rules = RuleLoader(tmp_path).load_all()

    assert {rule.id for rule in rules} == {"test_rule_one", "test_rule_disabled"}


def test_get_active_rules_excludes_disabled(tmp_path: Path) -> None:
    _write(tmp_path, "one.yaml", _VALID_RULE_YAML)
    _write(tmp_path, "two.yaml", _DISABLED_RULE_YAML)

    active = RuleLoader(tmp_path).get_active_rules()

    assert [rule.id for rule in active] == ["test_rule_one"]


def test_missing_directory_raises_configuration_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        RuleLoader(tmp_path / "does_not_exist").load_all()


def test_invalid_yaml_raises_configuration_error(tmp_path: Path) -> None:
    _write(tmp_path, "broken.yaml", "rules: [this is not: valid: yaml")
    with pytest.raises(ConfigurationError):
        RuleLoader(tmp_path).load_all()


def test_invalid_rule_definition_raises_configuration_error(tmp_path: Path) -> None:
    _write(tmp_path, "bad.yaml", "rules:\n  - id: missing_fields\n")
    with pytest.raises(ConfigurationError):
        RuleLoader(tmp_path).load_all()


def test_duplicate_rule_id_raises_configuration_error(tmp_path: Path) -> None:
    _write(tmp_path, "one.yaml", _VALID_RULE_YAML)
    _write(tmp_path, "dup.yaml", _VALID_RULE_YAML)
    with pytest.raises(ConfigurationError):
        RuleLoader(tmp_path).load_all()
