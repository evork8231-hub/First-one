"""Initial schema: signals, weather_events, leads, audit_logs, configuration.

Revision ID: 0001
Revises:
Create Date: 2026-07-26

Column types are written out explicitly (not imported from
``app.database.models``) so this migration remains valid even if the ORM
models change shape later -- a migration is a frozen historical record of
a schema change, not a live reflection of current model code.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "signals",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("signal_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("service_category", sa.String(length=32), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("county", sa.String(length=100), nullable=False),
        sa.Column("municipality", sa.String(length=100), nullable=False),
        sa.Column("address", sa.JSON(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("building_identifier", sa.String(length=64), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("verified", sa.String(length=16), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_signals_signal_type", "signals", ["signal_type"])
    op.create_index("ix_signals_service_category", "signals", ["service_category"])
    op.create_index("ix_signals_county", "signals", ["county"])
    op.create_index("ix_signals_municipality", "signals", ["municipality"])
    op.create_index("ix_signals_building_identifier", "signals", ["building_identifier"])
    op.create_index("ix_signals_timestamp", "signals", ["timestamp"])
    op.create_index("ix_signals_verified", "signals", ["verified"])

    op.create_table(
        "weather_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=False),
        sa.Column("source_url", sa.String(length=2048), nullable=True),
        sa.Column("county", sa.String(length=100), nullable=False),
        sa.Column("municipality", sa.String(length=100), nullable=False),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("severity", sa.Float(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("metadata", sa.JSON(), nullable=False),
    )
    op.create_index("ix_weather_events_event_type", "weather_events", ["event_type"])
    op.create_index("ix_weather_events_county", "weather_events", ["county"])
    op.create_index("ix_weather_events_municipality", "weather_events", ["municipality"])
    op.create_index("ix_weather_events_started_at", "weather_events", ["started_at"])

    op.create_table(
        "leads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("lead_type", sa.String(length=32), nullable=False),
        sa.Column("supporting_signal_ids", sa.JSON(), nullable=False),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("county", sa.String(length=100), nullable=False),
        sa.Column("municipality", sa.String(length=100), nullable=False),
        sa.Column("estimated_location", sa.JSON(), nullable=False),
        sa.Column("estimated_confidence", sa.Float(), nullable=False),
        sa.Column("intent_score", sa.Float(), nullable=False),
        sa.Column("priority", sa.String(length=16), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("verification_status", sa.String(length=16), nullable=False),
    )
    op.create_index("ix_leads_lead_type", "leads", ["lead_type"])
    op.create_index("ix_leads_county", "leads", ["county"])
    op.create_index("ix_leads_municipality", "leads", ["municipality"])
    op.create_index("ix_leads_priority", "leads", ["priority"])
    op.create_index("ix_leads_created_at", "leads", ["created_at"])
    op.create_index("ix_leads_verification_status", "leads", ["verification_status"])

    op.create_table(
        "audit_logs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("entity_type", sa.String(length=64), nullable=True),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.JSON(), nullable=False),
    )
    op.create_index("ix_audit_logs_event_type", "audit_logs", ["event_type"])
    op.create_index("ix_audit_logs_entity_id", "audit_logs", ["entity_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])

    op.create_table(
        "configuration",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("value", sa.JSON(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_configuration_key", "configuration", ["key"], unique=True)


def downgrade() -> None:
    op.drop_table("configuration")
    op.drop_table("audit_logs")
    op.drop_table("leads")
    op.drop_table("weather_events")
    op.drop_table("signals")
