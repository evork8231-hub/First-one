"""Lead generation interface.

Turns matched Rules into Lead entities. This is the only place in the
codebase permitted to construct a Lead. Signal-level scoring and
lead-level scoring are independent systems (see
``app.lead_generation.scoring``); both are consulted here.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.application.interfaces.rule_engine import RuleMatch
from app.domain.lead import Lead


class LeadGeneratorInterface(ABC):
    """Contract for turning RuleMatches into candidate Leads."""

    @abstractmethod
    def generate(self, matches: Sequence[RuleMatch]) -> list[Lead]:
        """Build Leads from ``matches``, deduplicating and combining as needed.

        Multiple RuleMatches for the same cluster and lead_type should be
        combined into a single Lead rather than producing duplicates.
        Every returned Lead must satisfy
        ``len(lead.supporting_signal_ids) >= MIN_SUPPORTING_SIGNALS``.
        """
