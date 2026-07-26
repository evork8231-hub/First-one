"""Verification interfaces.

Signals are verified first; only verified signals reach the correlation
engine. Leads are verified second, after generation. Both verification
steps are pluggable so future phases can add verifiers that check against
external registries without touching the rest of the pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import VerificationStatus
from app.domain.lead import Lead
from app.domain.signal import Signal


class VerificationResult(BaseModel):
    """The outcome of running a single verifier against a Signal or Lead.

    Attributes:
        status: The resulting verification status. Must be VERIFIED or
            REJECTED -- a verifier that cannot reach a decision should
            raise a VerificationError rather than return UNVERIFIED.
        reason: Human-readable explanation of the decision, always
            populated so rejections and approvals are both auditable.
        evidence: Structured detail supporting the decision (e.g. which
            fields were checked, what threshold was applied).
    """

    model_config = ConfigDict(frozen=True)

    status: VerificationStatus
    reason: str = Field(min_length=1)
    evidence: dict[str, object] = Field(default_factory=dict)


class SignalVerifier(ABC):
    """Contract for a pluggable Signal verification strategy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A stable, unique identifier for this verifier."""

    @abstractmethod
    async def verify(self, signal: Signal) -> VerificationResult:
        """Evaluate ``signal`` and return a VERIFIED or REJECTED result."""


class LeadVerifier(ABC):
    """Contract for a pluggable Lead verification strategy."""

    @property
    @abstractmethod
    def name(self) -> str:
        """A stable, unique identifier for this verifier."""

    @abstractmethod
    async def verify(self, lead: Lead) -> VerificationResult:
        """Evaluate ``lead`` and return a VERIFIED or REJECTED result."""
