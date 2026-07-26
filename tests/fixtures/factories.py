"""Test-only factories for building valid domain entities with sensible defaults.

Every factory accepts keyword overrides so individual tests only specify
the fields they care about.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from uuid import uuid4

from app.domain.enums import ServiceCategory, SignalType, VerificationStatus, WeatherEventType
from app.domain.lead import Lead
from app.domain.rule import Rule, SignalCondition
from app.domain.signal import Signal
from app.domain.value_objects import EstimatedLocation
from app.domain.weather import WeatherEvent
from app.utils.time import utc_now


def make_signal(**overrides: Any) -> Signal:
    defaults: dict[str, Any] = {
        "signal_type": SignalType.BUILDING_RECORD,
        "source": "test_source",
        "source_url": "https://example.ee/record/1",
        "service_category": ServiceCategory.ROOFING,
        "county": "Harju",
        "municipality": "Tallinn",
        "timestamp": utc_now() - timedelta(days=1),
        "raw_payload": {"example": True},
        "confidence": 0.9,
        "verified": VerificationStatus.VERIFIED,
    }
    defaults.update(overrides)
    return Signal(**defaults)


def make_weather_event(**overrides: Any) -> WeatherEvent:
    defaults: dict[str, Any] = {
        "event_type": WeatherEventType.HAILSTORM,
        "source": "test_weather_source",
        "county": "Harju",
        "municipality": "Tallinn",
        "severity": 0.8,
        "started_at": utc_now() - timedelta(days=2),
        "ended_at": utc_now() - timedelta(days=2) + timedelta(hours=3),
        "raw_payload": {"example": True},
    }
    defaults.update(overrides)
    return WeatherEvent(**defaults)


def make_condition(**overrides: Any) -> SignalCondition:
    defaults: dict[str, Any] = {"signal_type": SignalType.BUILDING_RECORD, "min_count": 1}
    defaults.update(overrides)
    return SignalCondition(**defaults)


def make_rule(**overrides: Any) -> Rule:
    defaults: dict[str, Any] = {
        "id": "test_rule",
        "name": "Test rule",
        "description": "A rule used only in tests.",
        "lead_type": ServiceCategory.ROOFING,
        "conditions": [
            make_condition(signal_type=SignalType.BUILDING_RECORD),
            make_condition(signal_type=SignalType.ROOF_MENTION),
        ],
        "base_confidence": 0.6,
        "weight": 1.0,
    }
    defaults.update(overrides)
    return Rule(**defaults)


def make_lead(**overrides: Any) -> Lead:
    county = overrides.get("county", "Harju")
    municipality = overrides.get("municipality", "Tallinn")
    defaults: dict[str, Any] = {
        "lead_type": ServiceCategory.ROOFING,
        "supporting_signal_ids": [uuid4(), uuid4()],
        "county": county,
        "municipality": municipality,
        "estimated_location": EstimatedLocation(county=county, municipality=municipality),
        "estimated_confidence": 0.7,
        "intent_score": 0.65,
        "priority": "medium",
        "reasoning": "Two independent verified signals corroborate this need.",
    }
    defaults.update(overrides)
    return Lead(**defaults)
