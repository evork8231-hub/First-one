"""Tests for app.config.settings."""

from __future__ import annotations

import pytest
from app.config.settings import RetryConfig, ScoringConfig
from app.core.retry import RetryPolicy
from pydantic import ValidationError


def test_retry_config_to_policy_maps_fields() -> None:
    config = RetryConfig(max_retries=5, initial_backoff_seconds=1.0, timeout_seconds=10.0)
    policy = config.to_policy()

    assert isinstance(policy, RetryPolicy)
    assert policy.max_retries == 5
    assert policy.initial_backoff_seconds == 1.0
    assert policy.timeout_seconds == 10.0


def test_scoring_config_rejects_out_of_range_threshold() -> None:
    with pytest.raises(ValidationError):
        ScoringConfig(priority_thresholds={"critical": 1.5})


def test_scoring_config_defaults_are_valid() -> None:
    config = ScoringConfig()
    assert config.priority_thresholds["critical"] > config.priority_thresholds["low"]
