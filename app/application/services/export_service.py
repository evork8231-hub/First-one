"""ExportService: serializes stored Leads for external consumption.

Unlike collectors and production scraping, exporting already-persisted,
already-verified Leads involves no external data collection and no risk
of fabrication -- it is a pure serialization of data already in the
database, so the foundation implements it fully rather than as a
placeholder.
"""

from __future__ import annotations

import csv
import io
import json
from typing import Literal

from app.application.interfaces.repositories import LeadRepository
from app.core.exceptions import ExportError
from app.domain.enums import ServiceCategory, VerificationStatus
from app.domain.lead import Lead

ExportFormat = Literal["json", "csv"]

_CSV_FIELDS = (
    "id",
    "lead_type",
    "county",
    "municipality",
    "estimated_confidence",
    "intent_score",
    "priority",
    "verification_status",
    "supporting_signal_count",
    "reasoning",
    "created_at",
)


class ExportService:
    """Serializes Leads currently in the LeadRepository."""

    def __init__(self, lead_repository: LeadRepository) -> None:
        self._lead_repository = lead_repository

    def export_leads(
        self,
        *,
        export_format: ExportFormat,
        lead_type: ServiceCategory | None = None,
        verification_status: VerificationStatus | None = None,
        limit: int = 1000,
    ) -> str:
        """Return leads matching the given filters serialized as ``export_format``."""
        leads = self._lead_repository.list_all(
            lead_type=lead_type,
            verification_status=verification_status,
            limit=limit,
        )
        if export_format == "json":
            return self._to_json(leads)
        if export_format == "csv":
            return self._to_csv(leads)
        raise ExportError(f"Unsupported export format: {export_format!r}.")

    @staticmethod
    def _to_json(leads: list[Lead]) -> str:
        payload = [json.loads(lead.model_dump_json()) for lead in leads]
        return json.dumps(payload, indent=2, ensure_ascii=False)

    @staticmethod
    def _to_csv(leads: list[Lead]) -> str:
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=_CSV_FIELDS)
        writer.writeheader()
        for lead in leads:
            writer.writerow(
                {
                    "id": str(lead.id),
                    "lead_type": lead.lead_type.value,
                    "county": lead.county,
                    "municipality": lead.municipality,
                    "estimated_confidence": lead.estimated_confidence,
                    "intent_score": lead.intent_score,
                    "priority": lead.priority.value,
                    "verification_status": lead.verification_status.value,
                    "supporting_signal_count": len(lead.supporting_signal_ids),
                    "reasoning": lead.reasoning,
                    "created_at": lead.created_at.isoformat(),
                }
            )
        return buffer.getvalue()
