"""Tests for app.collectors.ehitisregister_xtee_collector.EhitisregisterXTeeCollector.

This collector never performs network I/O -- it is a structurally
disabled adapter that always raises CollectorError, with a message that
depends on how complete its configuration is. These tests lock in that
staged behavior.
"""

from __future__ import annotations

import asyncio

import pytest
from app.collectors.ehitisregister_xtee_collector import EhitisregisterXTeeCollector
from app.config.settings import EhitisregisterXTeeConfig
from app.core.exceptions import CollectorError
from app.domain.enums import SignalType

_COMPLETE_IDENTITY: dict[str, object] = {
    "enabled": True,
    "security_server_url": "https://security-server.example.ee",
    "xroad_instance": "EE",
    "member_class": "GOV",
    "member_code": "70000310",
    "client_cert_path": "/etc/xtee/client.pem",
    "client_key_path": "/etc/xtee/client.key",
}

_COMPLETE_SERVICE: dict[str, object] = {
    "service_member_class": "GOV",
    "service_member_code": "70001234",
    "service_code": "buildingQuery",
    "service_version": "v1",
}


def test_collector_identity() -> None:
    collector = EhitisregisterXTeeCollector(EhitisregisterXTeeConfig())
    assert collector.name == "ehitisregister_xtee"
    assert collector.source == "Ehitisregister (Estonian Building Registry) via X-tee"
    assert collector.supported_signal_types == frozenset(
        {SignalType.BUILDING_RECORD, SignalType.ENERGY_CERTIFICATE}
    )


def test_disabled_by_default() -> None:
    collector = EhitisregisterXTeeCollector(EhitisregisterXTeeConfig())
    with pytest.raises(CollectorError, match="disabled"):
        asyncio.run(collector.collect())


def test_enabled_but_missing_identity_fields_reports_them() -> None:
    collector = EhitisregisterXTeeCollector(EhitisregisterXTeeConfig(enabled=True))
    with pytest.raises(CollectorError) as exc_info:
        asyncio.run(collector.collect())
    assert "security_server_url" in exc_info.value.message
    assert "client_cert_path" in exc_info.value.message


def test_partial_identity_still_reports_missing_fields() -> None:
    config = EhitisregisterXTeeConfig(
        enabled=True,
        security_server_url="https://security-server.example.ee",
        xroad_instance="EE",
    )
    collector = EhitisregisterXTeeCollector(config)
    with pytest.raises(CollectorError) as exc_info:
        asyncio.run(collector.collect())
    assert "member_class" in exc_info.value.message
    assert "member_code" in exc_info.value.message
    assert "client_cert_path" in exc_info.value.message
    assert "security_server_url" not in exc_info.value.message  # already satisfied


def test_complete_identity_but_missing_service_fields_reports_them() -> None:
    config = EhitisregisterXTeeConfig(**_COMPLETE_IDENTITY)  # type: ignore[arg-type]
    collector = EhitisregisterXTeeCollector(config)
    with pytest.raises(CollectorError) as exc_info:
        asyncio.run(collector.collect())
    assert "service_code" in exc_info.value.message
    assert "service_member_class" in exc_info.value.message


def test_fully_configured_still_refuses_to_run() -> None:
    """Even complete configuration cannot make this adapter functional.

    The operation-specific request/response schema was never verified
    against a live source, so collect() must still refuse rather than
    fabricate a request -- this is the whole point of the adapter.
    """
    config = EhitisregisterXTeeConfig(**_COMPLETE_IDENTITY, **_COMPLETE_SERVICE)  # type: ignore[arg-type]
    collector = EhitisregisterXTeeCollector(config)
    with pytest.raises(CollectorError, match="never verified"):
        asyncio.run(collector.collect())


def test_never_returns_signals() -> None:
    """collect() has no success path at all -- confirmed across every configuration state."""
    configs = [
        EhitisregisterXTeeConfig(),
        EhitisregisterXTeeConfig(enabled=True),
        EhitisregisterXTeeConfig(**_COMPLETE_IDENTITY, **_COMPLETE_SERVICE),  # type: ignore[arg-type]
    ]
    for config in configs:
        collector = EhitisregisterXTeeCollector(config)
        with pytest.raises(CollectorError):
            asyncio.run(collector.collect())
