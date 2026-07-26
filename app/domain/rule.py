"""Data-driven correlation rules.

Rules describe *which combinations of verified Signal types* justify
generating a Lead. They are never hardcoded in Python control flow --
production rules live in YAML files under ``config/rules/`` and are loaded
by ``app.rule_engine.loader.RuleLoader`` into these Pydantic models. See
``docs/CONFIGURATION.md`` for the file format.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.enums import ServiceCategory, SignalType


class SignalCondition(BaseModel):
    """One requirement a Rule places on a cluster of verified Signals.

    Attributes:
        signal_type: The kind of signal this condition looks for.
        min_count: How many distinct signals of ``signal_type`` must be
            present in the cluster for this condition to be satisfied.
        max_age_days: If set, only signals whose ``timestamp`` is within
            this many days of the correlation run count toward
            ``min_count``. ``None`` means no recency requirement.
        min_confidence: If set, only signals with ``confidence`` at or
            above this threshold count toward ``min_count``.
    """

    model_config = ConfigDict(frozen=True)

    signal_type: SignalType
    min_count: int = Field(default=1, ge=1)
    max_age_days: int | None = Field(default=None, ge=1)
    min_confidence: float | None = Field(default=None, ge=0.0, le=1.0)


class Rule(BaseModel):
    """A single, named, data-driven correlation rule.

    Example (illustrative, not hardcoded -- see ``config/rules/roofing.yaml``):
        Weather Event + Old Building record + Roof mention -> Roofing Lead.

    Attributes:
        id: Stable, unique slug for this rule (e.g. ``"roofing_storm_damage"``).
        name: Short human-readable name.
        description: Explains the real-world reasoning the rule encodes;
            copied into generated Leads' ``reasoning`` field.
        lead_type: The service category this rule produces leads for.
        conditions: The set of SignalConditions evaluated against a signal
            cluster.
        min_matching_conditions: How many of ``conditions`` must be
            satisfied for the rule to match. Defaults to requiring all of
            them (a logical AND across every condition).
        base_confidence: Starting confidence, in [0.0, 1.0], contributed by
            a match of this rule before Signal-level confidence is folded
            in by the scoring system.
        weight: Non-negative weight used by the lead scoring system to
            combine multiple simultaneously-matched rules.
        enabled: Rules can be disabled via configuration without deleting
            them, supporting safe rollout and rollback.
    """

    model_config = ConfigDict(frozen=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    lead_type: ServiceCategory
    conditions: list[SignalCondition] = Field(min_length=1)
    min_matching_conditions: int | None = Field(default=None, ge=1)
    base_confidence: float = Field(ge=0.0, le=1.0)
    weight: float = Field(ge=0.0)
    enabled: bool = True

    @model_validator(mode="after")
    def _resolve_and_validate_min_matching_conditions(self) -> Rule:
        effective = self.min_matching_conditions
        if effective is None:
            effective = len(self.conditions)
        if effective > len(self.conditions):
            raise ValueError(
                f"Rule {self.id!r}: min_matching_conditions ({effective}) "
                f"cannot exceed the number of conditions ({len(self.conditions)})."
            )
        if effective != self.min_matching_conditions:
            object.__setattr__(self, "min_matching_conditions", effective)
        return self
