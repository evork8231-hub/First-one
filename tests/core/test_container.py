"""Tests for app.core.container.Container."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.application.services.data_management_service import DataManagementService
from app.application.services.signal_service import SignalService
from app.core.container import Container
from app.correlation.engine import CorrelationEngine
from app.lead_generation.generator import LeadGenerator
from app.repositories.sqlite.lead_repository import SQLiteLeadRepository
from app.repositories.sqlite.signal_repository import SQLiteSignalRepository
from app.rule_engine.engine import RuleEngine
from app.verification.schema_drift import SchemaDriftDetector


@pytest.fixture()
def wired_container(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Container:
    monkeypatch.setenv("SIGINT_DATABASE__URL", "sqlite:///:memory:")
    monkeypatch.setenv("SIGINT_RULES__DIRECTORY", str(tmp_path))
    monkeypatch.setenv("SIGINT_LOGGING__LOG_FILE", "")
    container = Container()
    container.init_resources()
    return container


def test_repositories_resolve_to_sqlite_implementations(wired_container: Container) -> None:
    assert isinstance(wired_container.signal_repository(), SQLiteSignalRepository)
    assert isinstance(wired_container.lead_repository(), SQLiteLeadRepository)


def test_engines_resolve_to_default_implementations(wired_container: Container) -> None:
    assert isinstance(wired_container.correlation_engine(), CorrelationEngine)
    assert isinstance(wired_container.rule_engine(), RuleEngine)
    assert isinstance(wired_container.lead_generator(), LeadGenerator)


def test_services_are_constructible(wired_container: Container) -> None:
    service = wired_container.signal_service()
    assert isinstance(service, SignalService)


def test_data_management_service_is_constructible(wired_container: Container) -> None:
    service = wired_container.data_management_service()
    assert isinstance(service, DataManagementService)


def test_schema_drift_detector_is_constructible(wired_container: Container) -> None:
    detector = wired_container.schema_drift_detector()
    assert isinstance(detector, SchemaDriftDetector)


def test_repositories_are_singletons(wired_container: Container) -> None:
    assert wired_container.signal_repository() is wired_container.signal_repository()


def test_services_are_fresh_per_resolution(wired_container: Container) -> None:
    assert wired_container.signal_service() is not wired_container.signal_service()
