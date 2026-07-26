"""Minimal fake implementations of application interfaces, for tests only."""

from __future__ import annotations

from collections.abc import Sequence

from app.application.interfaces.collector import CollectorInterface
from app.application.interfaces.lead_generation import LeadGeneratorInterface
from app.application.interfaces.rule_engine import RuleMatch
from app.application.interfaces.verifier import LeadVerifier, SignalVerifier, VerificationResult
from app.application.interfaces.weather_collector import WeatherCollectorInterface
from app.core.exceptions import CollectorError
from app.domain.enums import SignalType, VerificationStatus
from app.domain.lead import Lead
from app.domain.signal import Signal
from app.domain.weather import WeatherEvent


class FakeCollector(CollectorInterface):
    """Returns a fixed, pre-built list of Signals; optionally raises on collect()."""

    def __init__(
        self,
        signals: Sequence[Signal],
        *,
        name: str = "fake_collector",
        source: str = "fake_source",
        supported_signal_types: frozenset[SignalType] | None = None,
        fail: bool = False,
    ) -> None:
        self._signals = list(signals)
        self._name = name
        self._source = source
        self._supported_signal_types = supported_signal_types or frozenset(
            {SignalType.BUILDING_RECORD}
        )
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> str:
        return self._source

    @property
    def supported_signal_types(self) -> frozenset[SignalType]:
        return self._supported_signal_types

    async def collect(self) -> list[Signal]:
        if self._fail:
            raise CollectorError("Simulated collector failure.")
        return list(self._signals)


class FakeWeatherCollector(WeatherCollectorInterface):
    """Returns a fixed, pre-built list of WeatherEvents; optionally raises on collect()."""

    def __init__(
        self,
        events: Sequence[WeatherEvent],
        *,
        name: str = "fake_weather_collector",
        source: str = "fake_source",
        fail: bool = False,
    ) -> None:
        self._events = list(events)
        self._name = name
        self._source = source
        self._fail = fail

    @property
    def name(self) -> str:
        return self._name

    @property
    def source(self) -> str:
        return self._source

    async def collect(self) -> list[WeatherEvent]:
        if self._fail:
            raise CollectorError("Simulated collector failure.")
        return list(self._events)


class FakeSignalVerifier(SignalVerifier):
    """Always returns a fixed VerificationStatus."""

    def __init__(self, status: VerificationStatus, *, name: str = "fake_signal_verifier") -> None:
        self._status = status
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def verify(self, signal: Signal) -> VerificationResult:
        return VerificationResult(
            status=self._status, reason=f"Fixed result: {self._status.value}."
        )


class FakeLeadVerifier(LeadVerifier):
    """Always returns a fixed VerificationStatus."""

    def __init__(self, status: VerificationStatus, *, name: str = "fake_lead_verifier") -> None:
        self._status = status
        self._name = name

    @property
    def name(self) -> str:
        return self._name

    async def verify(self, lead: Lead) -> VerificationResult:
        return VerificationResult(
            status=self._status, reason=f"Fixed result: {self._status.value}."
        )


class FakeLeadGenerator(LeadGeneratorInterface):
    """Returns a fixed, pre-built list of Leads regardless of input matches."""

    def __init__(self, leads: Sequence[Lead]) -> None:
        self._leads = list(leads)

    def generate(self, matches: Sequence[RuleMatch]) -> list[Lead]:
        return list(self._leads)
