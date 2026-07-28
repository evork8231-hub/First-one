"""Tests for app.cli.schema_drift_support.check_schema_drift_safely."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from app.cli.schema_drift_support import check_schema_drift_safely
from app.verification.schema_drift import SchemaDriftResult
from sqlalchemy.exc import SQLAlchemyError


def _container_with_detector(detector: MagicMock) -> MagicMock:
    container = MagicMock()
    container.schema_drift_detector.return_value = detector
    return container


def test_returns_the_real_result_on_success() -> None:
    expected = SchemaDriftResult(
        collector_name="ehitisregister",
        is_first_observation=False,
        has_drift=True,
        added_keys=("new_field",),
        removed_keys=(),
    )
    detector = MagicMock()
    detector.check.return_value = expected
    container = _container_with_detector(detector)

    result = check_schema_drift_safely(container, "ehitisregister", [{"a": 1}])

    assert result is expected


def test_returns_none_and_does_not_raise_on_sqlalchemy_error() -> None:
    detector = MagicMock()
    detector.check.side_effect = SQLAlchemyError("database is locked")
    container = _container_with_detector(detector)

    result = check_schema_drift_safely(container, "ehitisregister", [{"a": 1}])

    assert result is None


def test_does_not_catch_unrelated_exceptions() -> None:
    """A bug in the detector's own logic must still surface, not be silently absorbed."""

    def _raise(*_args: Any, **_kwargs: Any) -> None:
        raise ValueError("not an infrastructure failure")

    detector = MagicMock()
    detector.check.side_effect = _raise
    container = _container_with_detector(detector)

    with pytest.raises(ValueError, match="not an infrastructure failure"):
        check_schema_drift_safely(container, "ehitisregister", [{"a": 1}])
