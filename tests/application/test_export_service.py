"""Tests for app.application.services.export_service.ExportService."""

from __future__ import annotations

import csv
import io
import json
from datetime import UTC

from app.application.services.export_service import ExportService
from app.config.settings import ExcelExportConfig
from app.domain.enums import LeadPriority, VerificationStatus
from app.repositories.in_memory.lead_repository import InMemoryLeadRepository
from app.repositories.in_memory.signal_repository import InMemorySignalRepository
from openpyxl import load_workbook

from tests.fixtures.factories import make_lead, make_signal


def _seeded_service(**excel_overrides: object) -> tuple[ExportService, InMemoryLeadRepository]:
    signal_repo = InMemorySignalRepository()
    lead_repo = InMemoryLeadRepository()

    s1 = signal_repo.add(make_signal(source="KV.ee"))
    s2 = signal_repo.add(make_signal(source="Ehitisregister"))

    verified_lead = lead_repo.add(
        make_lead(
            supporting_signal_ids=[s1.id, s2.id],
            verification_status=VerificationStatus.VERIFIED,
            priority=LeadPriority.HIGH,
            intent_score=0.77,
            estimated_confidence=0.66,
        )
    )
    lead_repo.add(make_lead(verification_status=VerificationStatus.UNVERIFIED))
    lead_repo.add(make_lead(verification_status=VerificationStatus.REJECTED))

    excel_config = ExcelExportConfig(**excel_overrides) if excel_overrides else None
    service = ExportService(lead_repo, signal_repo, excel_config=excel_config)
    return service, verified_lead


def test_csv_export_includes_only_verified_leads() -> None:
    service, verified_lead = _seeded_service()

    csv_text = service.export_leads(export_format="csv")
    rows = list(csv.DictReader(io.StringIO(csv_text)))

    assert len(rows) == 1
    assert rows[0]["Lead ID"] == str(verified_lead.id)


def test_csv_export_uses_the_required_column_headers() -> None:
    service, _ = _seeded_service()
    csv_text = service.export_leads(export_format="csv")
    header = csv_text.splitlines()[0]
    for column in (
        "Lead ID",
        "Lead Type",
        "Intent Score",
        "Confidence Score",
        "Priority",
        "Verification Status",
        "Source",
        "Municipality",
        "County",
        "Reasoning",
        "Created At",
    ):
        assert column in header


def test_csv_export_derives_source_from_supporting_signals() -> None:
    service, _ = _seeded_service()
    csv_text = service.export_leads(export_format="csv")
    row = next(csv.DictReader(io.StringIO(csv_text)))
    assert row["Source"] == "Ehitisregister; KV.ee"


def test_json_export_includes_only_verified_leads() -> None:
    service, verified_lead = _seeded_service()
    payload = json.loads(service.export_leads(export_format="json"))
    assert len(payload) == 1
    assert payload[0]["id"] == str(verified_lead.id)


def test_export_filters_by_lead_type() -> None:
    from app.domain.enums import ServiceCategory

    service, verified_lead = _seeded_service()
    matching = service.export_leads(export_format="json", lead_type=verified_lead.lead_type)
    other = service.export_leads(export_format="json", lead_type=ServiceCategory.SOLAR_INSTALLATION)
    assert len(json.loads(matching)) == 1
    assert len(json.loads(other)) == 0


def test_unsupported_format_raises() -> None:
    from app.core.exceptions import ExportError

    service, _ = _seeded_service()
    import pytest

    with pytest.raises(ExportError):
        service.export_leads(export_format="yaml")  # type: ignore[arg-type]


# --- Excel-specific behavior -------------------------------------------------


def test_xlsx_export_produces_a_valid_workbook_with_one_data_row() -> None:
    service, verified_lead = _seeded_service()
    payload = service.export_leads(export_format="xlsx")

    assert isinstance(payload, bytes)
    workbook = load_workbook(io.BytesIO(payload))
    worksheet = workbook.active

    header = [cell.value for cell in worksheet[1]]
    assert header[0] == "Lead ID"
    assert worksheet.max_row == 2  # header + 1 verified lead
    assert worksheet.cell(row=2, column=1).value == str(verified_lead.id)


def test_xlsx_header_row_is_styled_per_config() -> None:
    service, _ = _seeded_service(header_fill_color="112233", header_font_color="AABBCC")
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active

    header_cell = worksheet.cell(row=1, column=1)
    assert header_cell.font.bold is True
    assert header_cell.font.color.rgb.endswith("AABBCC")
    assert header_cell.fill.fgColor.rgb.endswith("112233")


def test_xlsx_header_row_is_frozen_when_configured() -> None:
    service, _ = _seeded_service(freeze_header_row=True)
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active
    assert worksheet.freeze_panes == "A2"


def test_xlsx_header_row_not_frozen_when_disabled() -> None:
    service, _ = _seeded_service(freeze_header_row=False)
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active
    assert worksheet.freeze_panes is None


def test_xlsx_has_an_autofilter_covering_the_data_range() -> None:
    service, _ = _seeded_service(enable_autofilter=True)
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active
    assert worksheet.auto_filter.ref == "A1:K2"


def test_xlsx_columns_are_auto_sized_within_configured_bounds() -> None:
    service, _ = _seeded_service(auto_size_columns=True, min_column_width=10, max_column_width=25)
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active

    for column_letter in ("A", "B", "C"):
        width = worksheet.column_dimensions[column_letter].width
        assert 10 <= width <= 25


def test_xlsx_dates_are_native_datetime_with_configured_format() -> None:
    service, verified_lead = _seeded_service(date_format="yyyy-mm-dd")
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active

    created_at_column = 11  # "Created At" is the 11th configured column
    cell = worksheet.cell(row=2, column=created_at_column)
    # Excel stores dates as a floating-point day count, so sub-millisecond
    # precision is not preserved -- compare at second resolution.
    expected = verified_lead.created_at.astimezone(UTC).replace(tzinfo=None, microsecond=0)
    assert cell.value.replace(microsecond=0) == expected
    assert cell.number_format == "yyyy-mm-dd"


def test_xlsx_numeric_columns_have_proper_type_and_format() -> None:
    service, verified_lead = _seeded_service()
    payload = service.export_leads(export_format="xlsx")
    worksheet = load_workbook(io.BytesIO(payload)).active

    intent_score_cell = worksheet.cell(row=2, column=3)
    confidence_cell = worksheet.cell(row=2, column=4)
    assert isinstance(intent_score_cell.value, float)
    assert intent_score_cell.value == verified_lead.intent_score
    assert isinstance(confidence_cell.value, float)
    assert intent_score_cell.number_format == "0.00"
