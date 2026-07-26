"""Loads data-driven Rule definitions from YAML configuration files.

Rules never live in Python source. A rule file looks like::

    rules:
      - id: roofing_storm_damage
        name: "Roofing lead from storm damage"
        description: >
          A recent severe weather event, an older building, and a public
          mention of roof issues together indicate a likely roofing need.
        lead_type: roofing
        base_confidence: 0.6
        weight: 1.0
        conditions:
          - signal_type: weather_event
            min_count: 1
            max_age_days: 60
          - signal_type: building_record
            min_count: 1
          - signal_type: roof_mention
            min_count: 1

See ``config/rules/`` for the shipped examples and
``docs/CONFIGURATION.md`` for the full field reference.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from app.application.interfaces.rule_engine import RuleProvider
from app.core.exceptions import ConfigurationError
from app.domain.rule import Rule


class RuleLoader(RuleProvider):
    """Loads Rule definitions from every ``*.yaml`` file in a directory."""

    def __init__(self, rules_directory: Path) -> None:
        self._rules_directory = rules_directory

    def load_all(self) -> list[Rule]:
        """Parse and validate every rule file, returning all rules (enabled or not).

        Raises:
            ConfigurationError: If the directory is missing, a file is not
                valid YAML, or a rule fails Pydantic validation.
        """
        if not self._rules_directory.is_dir():
            raise ConfigurationError(f"Rules directory does not exist: {self._rules_directory}")

        rules: list[Rule] = []
        seen_ids: set[str] = set()

        for path in sorted(self._rules_directory.glob("*.yaml")):
            try:
                raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError as exc:
                raise ConfigurationError(f"Invalid YAML in rule file {path}: {exc}") from exc

            raw_rules = raw.get("rules", [])
            if not isinstance(raw_rules, list):
                raise ConfigurationError(f"Rule file {path} must define a top-level 'rules' list.")

            for raw_rule in raw_rules:
                try:
                    rule = Rule.model_validate(raw_rule)
                except ValidationError as exc:
                    raise ConfigurationError(f"Invalid rule definition in {path}: {exc}") from exc
                if rule.id in seen_ids:
                    raise ConfigurationError(f"Duplicate rule id {rule.id!r} found in {path}.")
                seen_ids.add(rule.id)
                rules.append(rule)

        return rules

    def get_active_rules(self) -> list[Rule]:
        """Return every loaded rule whose ``enabled`` flag is True."""
        return [rule for rule in self.load_all() if rule.enabled]
