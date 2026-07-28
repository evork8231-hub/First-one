"""Tests for app.application.services.collector_lifecycle_service.CollectorLifecycleService."""

from __future__ import annotations

from app.application.services.collector_lifecycle_service import CollectorLifecycleService
from app.domain.enums import CollectorLifecycleState
from app.repositories.in_memory.configuration_repository import InMemoryConfigurationRepository


def _service() -> CollectorLifecycleService:
    return CollectorLifecycleService(InMemoryConfigurationRepository())


def test_unknown_collector_starts_discovered() -> None:
    service = _service()
    assert service.get_state("ehitisregister") == CollectorLifecycleState.DISCOVERED
    assert service.is_verified("ehitisregister") is False


def test_record_verification_attempt_ready_moves_to_verified() -> None:
    service = _service()

    new_state = service.record_verification_attempt("ehitisregister", ready=True)

    assert new_state == CollectorLifecycleState.VERIFIED
    assert service.get_state("ehitisregister") == CollectorLifecycleState.VERIFIED
    assert service.is_verified("ehitisregister") is True


def test_record_verification_attempt_not_ready_moves_to_tested() -> None:
    service = _service()

    new_state = service.record_verification_attempt("ilmateenistus", ready=False)

    assert new_state == CollectorLifecycleState.TESTED
    assert service.get_state("ilmateenistus") == CollectorLifecycleState.TESTED
    assert service.is_verified("ilmateenistus") is False


def test_a_later_failed_attempt_downgrades_a_previously_verified_collector() -> None:
    service = _service()
    service.record_verification_attempt("kv_ee", ready=True)
    assert service.is_verified("kv_ee") is True

    service.record_verification_attempt("kv_ee", ready=False)

    assert service.get_state("kv_ee") == CollectorLifecycleState.TESTED
    assert service.is_verified("kv_ee") is False


def test_a_later_successful_attempt_upgrades_a_previously_tested_collector() -> None:
    service = _service()
    service.record_verification_attempt("city24", ready=False)
    assert service.is_verified("city24") is False

    service.record_verification_attempt("city24", ready=True)

    assert service.is_verified("city24") is True


def test_lifecycle_state_is_tracked_independently_per_collector() -> None:
    service = _service()
    service.record_verification_attempt("ehitisregister", ready=True)

    assert service.is_verified("ehitisregister") is True
    assert service.is_verified("kv_ee") is False
    assert service.get_state("kv_ee") == CollectorLifecycleState.DISCOVERED
