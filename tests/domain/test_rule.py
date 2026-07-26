"""Tests for app.domain.rule.Rule."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tests.fixtures.factories import make_condition, make_rule


def test_min_matching_conditions_defaults_to_all_conditions() -> None:
    rule = make_rule(
        conditions=[make_condition(), make_condition(), make_condition()],
        min_matching_conditions=None,
    )
    assert rule.min_matching_conditions == 3


def test_explicit_min_matching_conditions_is_honored() -> None:
    rule = make_rule(
        conditions=[make_condition(), make_condition(), make_condition()],
        min_matching_conditions=2,
    )
    assert rule.min_matching_conditions == 2


def test_min_matching_conditions_cannot_exceed_condition_count() -> None:
    with pytest.raises(ValidationError):
        make_rule(conditions=[make_condition()], min_matching_conditions=2)


def test_rule_requires_at_least_one_condition() -> None:
    with pytest.raises(ValidationError):
        make_rule(conditions=[])
