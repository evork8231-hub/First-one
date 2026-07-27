"""Tests for app.verification.schema_drift.SchemaDriftDetector."""

from __future__ import annotations

from app.domain.enums import AuditEventType
from app.repositories.in_memory.audit_log_repository import InMemoryAuditLogRepository
from app.repositories.in_memory.configuration_repository import InMemoryConfigurationRepository
from app.verification.schema_drift import SchemaDriftDetector


def _detector() -> (
    tuple[SchemaDriftDetector, InMemoryConfigurationRepository, InMemoryAuditLogRepository]
):
    config_repo = InMemoryConfigurationRepository()
    audit_repo = InMemoryAuditLogRepository()
    return SchemaDriftDetector(config_repo, audit_repo), config_repo, audit_repo


def test_check_with_no_payloads_is_a_noop() -> None:
    detector, config_repo, audit_repo = _detector()

    result = detector.check("ehitisregister", [])

    assert result.has_drift is False
    assert result.is_first_observation is False
    assert config_repo.get("schema_fingerprint.ehitisregister") is None
    assert audit_repo.list_all(limit=10) == []


def test_check_first_observation_stores_fingerprint_without_drift() -> None:
    detector, config_repo, audit_repo = _detector()

    result = detector.check("ehitisregister", [{"maakond": "Harju", "omavalitsus": "Tallinn"}])

    assert result.is_first_observation is True
    assert result.has_drift is False
    entry = config_repo.get("schema_fingerprint.ehitisregister")
    assert entry is not None
    assert set(entry.value) == {"maakond", "omavalitsus"}
    assert audit_repo.list_all(limit=10) == []


def test_check_identical_keys_on_second_run_reports_no_drift() -> None:
    detector, _config_repo, audit_repo = _detector()
    detector.check("ehitisregister", [{"maakond": "Harju"}])

    result = detector.check("ehitisregister", [{"maakond": "Tartu"}])

    assert result.has_drift is False
    assert result.is_first_observation is False
    assert audit_repo.list_all(limit=10) == []


def test_check_detects_added_keys() -> None:
    detector, config_repo, audit_repo = _detector()
    detector.check("ehitisregister", [{"maakond": "Harju"}])

    result = detector.check("ehitisregister", [{"maakond": "Harju", "new_field": "x"}])

    assert result.has_drift is True
    assert result.added_keys == ("new_field",)
    assert result.removed_keys == ()
    entries = audit_repo.list_all(event_type=AuditEventType.SCHEMA_DRIFT_DETECTED, limit=10)
    assert len(entries) == 1
    assert entries[0].context["added_keys"] == ["new_field"]
    assert entries[0].context["removed_keys"] == []
    # the fingerprint is updated to the new key set
    entry = config_repo.get("schema_fingerprint.ehitisregister")
    assert entry is not None
    assert set(entry.value) == {"maakond", "new_field"}


def test_check_detects_removed_keys() -> None:
    detector, _config_repo, audit_repo = _detector()
    detector.check("ehitisregister", [{"maakond": "Harju", "omavalitsus": "Tallinn"}])

    result = detector.check("ehitisregister", [{"maakond": "Harju"}])

    assert result.has_drift is True
    assert result.added_keys == ()
    assert result.removed_keys == ("omavalitsus",)
    entries = audit_repo.list_all(event_type=AuditEventType.SCHEMA_DRIFT_DETECTED, limit=10)
    assert len(entries) == 1


def test_check_does_not_repeat_alert_once_fingerprint_is_updated() -> None:
    detector, _config_repo, audit_repo = _detector()
    detector.check("ehitisregister", [{"maakond": "Harju"}])
    detector.check("ehitisregister", [{"maakond": "Harju", "new_field": "x"}])  # drift #1

    result = detector.check("ehitisregister", [{"maakond": "Harju", "new_field": "y"}])

    assert result.has_drift is False  # same key set as the last stored fingerprint
    entries = audit_repo.list_all(event_type=AuditEventType.SCHEMA_DRIFT_DETECTED, limit=10)
    assert len(entries) == 1  # only the first drift was reported


def test_check_tracks_multiple_collectors_independently() -> None:
    detector, config_repo, _audit_repo = _detector()
    detector.check("ehitisregister", [{"maakond": "Harju"}])
    detector.check("ilmateenistus", [{"phenomenon": "torm"}])

    assert config_repo.get("schema_fingerprint.ehitisregister") is not None
    assert config_repo.get("schema_fingerprint.ilmateenistus") is not None

    result = detector.check("ehitisregister", [{"maakond": "Harju", "new": "x"}])
    assert result.has_drift is True
    assert result.collector_name == "ehitisregister"


def test_check_merges_keys_across_multiple_payloads_in_one_run() -> None:
    detector, config_repo, _audit_repo = _detector()

    detector.check("ehitisregister", [{"a": 1}, {"b": 2}])

    entry = config_repo.get("schema_fingerprint.ehitisregister")
    assert entry is not None
    assert set(entry.value) == {"a", "b"}
