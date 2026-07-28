"""Shared "is this enabled collector actually verified?" gate.

Used by both ``sigint collect --all`` and ``sigint pipeline`` (their
collect stage) -- the two entry points driven by the operator-controlled
``collectors.enabled`` config list -- to refuse to actually run a
collector's ``collect()`` when it is listed there but has never passed
``sigint verify-collector`` (see
``app.application.services.collector_lifecycle_service.CollectorLifecycleService``
for what "verified" means and how that state is recorded).

Deliberately not applied to ``sigint collect --collector <name>``: that
is an operator explicitly naming one collector to run right now, the
same kind of deliberate, individual action as ``verify-collector``
itself running ``collect()`` to test a collector -- gating it too would
make it impossible to ever reach VERIFIED for the first time.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from app.application.services.collector_lifecycle_service import CollectorLifecycleService


class _NamedCollector(Protocol):
    @property
    def name(self) -> str: ...


def split_by_verification[
    C: _NamedCollector
](lifecycle: CollectorLifecycleService, collectors: Sequence[C]) -> tuple[list[C], list[C]]:
    """Split ``collectors`` into (verified, unverified) by recorded lifecycle state."""
    verified = [c for c in collectors if lifecycle.is_verified(c.name)]
    unverified = [c for c in collectors if not lifecycle.is_verified(c.name)]
    return verified, unverified


def not_verified_message(name: str) -> str:
    """The reason shown in place of running an enabled-but-unverified collector."""
    return (
        f"not verified for mass collection -- run 'sigint verify-collector {name}' and "
        f"confirm it reports READY before enabling it in collectors.enabled."
    )
