"""The default CorrelationEngine implementation.

Signals are grouped into a SignalCluster using the most specific shared
identifier available:

1. A shared ``building_identifier`` (strongest signal -- both facts
   concern the exact same registered building).
2. A shared street + house number within the same county/municipality.
3. Falling back to county + municipality alone when no finer-grained
   location detail is available.

This is a deterministic grouping over fields the Signals already carry --
it never infers, estimates, or fabricates a shared location.
"""

from __future__ import annotations

from collections.abc import Sequence

from app.application.interfaces.correlation import CorrelationEngineInterface, SignalCluster
from app.core.exceptions import CorrelationError
from app.domain.enums import VerificationStatus
from app.domain.signal import Signal

_ClusterKey = tuple[str, ...]


class CorrelationEngine(CorrelationEngineInterface):
    """Groups verified Signals into SignalClusters by shared location identity."""

    def correlate(self, signals: Sequence[Signal]) -> list[SignalCluster]:
        groups: dict[_ClusterKey, list[Signal]] = {}
        for signal in signals:
            if signal.verified != VerificationStatus.VERIFIED:
                raise CorrelationError(
                    f"Correlation only accepts VERIFIED signals; signal {signal.id} is "
                    f"{signal.verified.value}."
                )
            groups.setdefault(self._cluster_key(signal), []).append(signal)

        clusters: list[SignalCluster] = []
        for key, group_signals in groups.items():
            county = {s.county for s in group_signals}
            municipality = {s.municipality for s in group_signals}
            if len(county) != 1 or len(municipality) != 1:
                raise CorrelationError(
                    f"Signals grouped under cluster key {key!r} disagree on county/municipality: "
                    f"{county=} {municipality=}."
                )
            building_identifiers = {
                s.building_identifier for s in group_signals if s.building_identifier
            }
            clusters.append(
                SignalCluster(
                    county=county.pop(),
                    municipality=municipality.pop(),
                    building_identifier=(
                        building_identifiers.pop() if len(building_identifiers) == 1 else None
                    ),
                    signals=group_signals,
                )
            )
        return clusters

    @staticmethod
    def _cluster_key(signal: Signal) -> _ClusterKey:
        if signal.building_identifier:
            return ("building", signal.building_identifier)
        if signal.address is not None and signal.address.street and signal.address.house_number:
            return (
                "address",
                signal.county.casefold(),
                signal.municipality.casefold(),
                signal.address.street.casefold(),
                signal.address.house_number.casefold(),
            )
        return ("region", signal.county.casefold(), signal.municipality.casefold())
