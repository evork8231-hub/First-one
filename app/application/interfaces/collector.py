"""The Collector interface.

Every collector -- regardless of what public source it reads from --
implements this single interface and returns nothing but ``Signal``
objects. Collectors never generate leads, never verify leads, never score
leads, and never contain business logic beyond "read a public source and
translate what it says into Signals."

See ``app.collectors.base.BaseCollector`` for the shared scaffolding
every concrete collector (``app.collectors.ehitisregister_collector``,
``app.collectors.real_estate.*``, etc.) builds on -- see
``docs/COLLECTORS.md`` for what each one does.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.domain.enums import SignalType
from app.domain.signal import Signal


class CollectorInterface(ABC):
    """Contract every signal collector must satisfy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A stable, unique identifier for this collector (e.g. ``"ehr_building_records"``)."""

    @property
    @abstractmethod
    def source(self) -> str:
        """The public data source this collector reads from, used as ``Signal.source``."""

    @property
    @abstractmethod
    def supported_signal_types(self) -> frozenset[SignalType]:
        """Which :class:`SignalType` values this collector can produce."""

    @abstractmethod
    async def collect(self) -> list[Signal]:
        """Read the public source and return the Signals it currently reports.

        Implementations must only return Signals built from data actually
        retrieved from ``source`` -- never fabricated, estimated, or
        invented values. Transient failures should be retried internally
        (see ``app.core.retry``) and terminal failures should raise a
        subclass of ``app.core.exceptions.CollectorError``.
        """
