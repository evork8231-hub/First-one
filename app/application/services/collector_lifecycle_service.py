"""CollectorLifecycleService: tracks how far a collector has progressed toward enablement.

Every collector starts ``DISCOVERED`` (registered in
``app.core.container.Container``, but never tested). Running
``sigint verify-collector <name>`` moves it to ``TESTED`` (attempted, but
not yet passing) or ``VERIFIED`` (passed, per that command's own
READY/NOT READY verdict). ``ENABLED`` is never written here -- it is a
derived fact (a collector is only truly enabled once it is both listed
in the operator-controlled ``collectors.enabled`` config *and* the last
recorded state is ``VERIFIED``), so this service cannot grant it on its
own; see ``is_verified``, which is what ``sigint collect --all`` and
``sigint pipeline`` actually gate on.

States never regress except for the one case safety requires: a later
verification attempt that comes back NOT READY moves a previously
``VERIFIED`` collector back down to ``TESTED``, since only the most
recent verification result should ever be trusted to decide whether mass
collection may run a collector.

Persisted via ``ConfigurationRepository`` (reusing its existing
unique-keyed store, the same pattern already used by
``SchemaDriftDetector`` and ``WeatherBridgeDeduplicator``) rather than a
new table, keyed ``f"collector_lifecycle.{collector_name}"``.
"""

from __future__ import annotations

from app.application.interfaces.repositories import ConfigurationRepository
from app.domain.configuration import ConfigurationEntry
from app.domain.enums import CollectorLifecycleState


def _state_key(collector_name: str) -> str:
    return f"collector_lifecycle.{collector_name}"


class CollectorLifecycleService:
    """Reads and records each collector's verification lifecycle state."""

    def __init__(self, configuration_repository: ConfigurationRepository) -> None:
        self._configuration_repository = configuration_repository

    def get_state(self, collector_name: str) -> CollectorLifecycleState:
        """Return ``collector_name``'s current lifecycle state, ``DISCOVERED`` if never tested."""
        entry = self._configuration_repository.get(_state_key(collector_name))
        if entry is None:
            return CollectorLifecycleState.DISCOVERED
        return CollectorLifecycleState(entry.value)

    def record_verification_attempt(
        self, collector_name: str, *, ready: bool
    ) -> CollectorLifecycleState:
        """Record the outcome of a ``sigint verify-collector`` run and return the new state."""
        new_state = CollectorLifecycleState.VERIFIED if ready else CollectorLifecycleState.TESTED
        self._configuration_repository.set(
            ConfigurationEntry(
                key=_state_key(collector_name),
                value=new_state.value,
                description=(
                    "Auto-maintained by CollectorLifecycleService -- do not edit by hand. "
                    f"Records the outcome of the most recent 'sigint verify-collector "
                    f"{collector_name}' run."
                ),
            )
        )
        return new_state

    def is_verified(self, collector_name: str) -> bool:
        """Whether ``collector_name`` passed its most recent verification attempt."""
        return self.get_state(collector_name) == CollectorLifecycleState.VERIFIED
