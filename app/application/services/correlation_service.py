"""CorrelationService: clusters verified Signals and evaluates rules against them.

Collectors never call this service, and this service never constructs a
Lead -- it produces RuleMatch objects that ``LeadGenerationService``
consumes. Keeping correlation and lead generation as separate services
preserves the Signals -> Correlation -> Lead Generation boundary from the
mission's core pipeline.
"""

from __future__ import annotations

from app.application.interfaces.correlation import CorrelationEngineInterface
from app.application.interfaces.repositories import AuditLogRepository, SignalRepository
from app.application.interfaces.rule_engine import RuleEngineInterface, RuleMatch, RuleProvider
from app.domain.audit import AuditLogEntry
from app.domain.enums import AuditEventType, VerificationStatus


class CorrelationService:
    """Runs the correlation engine and rule engine over verified signals."""

    def __init__(
        self,
        signal_repository: SignalRepository,
        correlation_engine: CorrelationEngineInterface,
        rule_engine: RuleEngineInterface,
        rule_provider: RuleProvider,
        audit_log_repository: AuditLogRepository,
    ) -> None:
        self._signal_repository = signal_repository
        self._correlation_engine = correlation_engine
        self._rule_engine = rule_engine
        self._rule_provider = rule_provider
        self._audit_log_repository = audit_log_repository

    def run(self, *, limit: int = 1000) -> list[RuleMatch]:
        """Correlate verified signals and evaluate active rules against them.

        Returns every RuleMatch found across every cluster; it is the
        caller's responsibility (typically ``LeadGenerationService``) to
        turn matches into Leads.
        """
        verified_signals = self._signal_repository.list_all(
            verified=VerificationStatus.VERIFIED, limit=limit
        )
        clusters = self._correlation_engine.correlate(verified_signals)
        rules = self._rule_provider.get_active_rules()

        matches: list[RuleMatch] = []
        for cluster in clusters:
            matches.extend(self._rule_engine.evaluate(cluster, rules))

        self._audit_log_repository.add(
            AuditLogEntry(
                event_type=AuditEventType.CORRELATION_RUN,
                message=(
                    f"Correlated {len(verified_signals)} verified signal(s) into "
                    f"{len(clusters)} cluster(s), producing {len(matches)} rule match(es)."
                ),
                context={
                    "verified_signal_count": len(verified_signals),
                    "cluster_count": len(clusters),
                    "match_count": len(matches),
                    "active_rule_count": len(rules),
                },
            )
        )
        return matches
