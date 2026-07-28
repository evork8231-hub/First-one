"""Add leads.identity_key: a real, database-level unique constraint enforcing
Lead idempotency.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28

Closes a concurrency race in Lead generation: ``LeadGenerationService``
already checked ``LeadRepository.find_by_identity`` before persisting a
candidate Lead, but that check-then-insert was not atomic -- two
concurrent processes (e.g. an operator manually running ``sigint
pipeline`` while a scheduled run is also in progress) could both observe
"no existing Lead" and both insert, producing duplicate Leads for the
same real-world evidence. ``identity_key`` is a deterministic fingerprint
of ``(lead_type, supporting_signal_ids)`` -- order-independent, see
``app.domain.lead.compute_lead_identity_key`` -- with a real unique index,
so the *database* now refuses the second insert outright, regardless of
what any application-level check already believed.

Column types are written out explicitly (not imported from
``app.database.models``), matching ``0001_initial_schema``'s own stated
rationale: a migration is a frozen historical record of a schema change,
not a live reflection of current model code. ``_compute_identity_key``
below is therefore an intentional, frozen duplicate of
``app.domain.lead.compute_lead_identity_key``'s algorithm, used only to
backfill ``identity_key`` for any Lead rows that already existed before
this column did.

This migration does not delete or alter any existing Lead row's data --
if a database already contains two or more Lead rows that would collide
on the same computed ``identity_key`` (i.e. duplicate Leads created by
the race this migration closes going forward), creating the unique index
below will fail loudly rather than silently discarding one of them.
That failure is intentional and fail-closed: deciding which duplicate to
keep is an operational decision for whoever runs this migration, not
something this migration should guess at silently.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def _compute_identity_key(lead_type: str, supporting_signal_ids: list[str]) -> str:
    """Frozen copy of app.domain.lead.compute_lead_identity_key -- see module docstring."""
    sorted_ids = sorted(str(signal_id) for signal_id in supporting_signal_ids)
    raw = f"{lead_type}|{','.join(sorted_ids)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def upgrade() -> None:
    op.add_column("leads", sa.Column("identity_key", sa.String(length=64), nullable=True))

    connection = op.get_bind()
    # `id` is deliberately typed as a plain String here, not sa.Uuid() -- comparing
    # `leads.c.id == row.id` through a Core sa.table() proxy (rather than a fully
    # reflected Table) does not reliably round-trip through Uuid's bind/result
    # processing against SQLite's raw on-disk representation, and silently matches
    # zero rows instead of raising. A plain string comparison against the exact
    # value just read back has no such ambiguity.
    leads = sa.table(
        "leads",
        sa.column("id", sa.String()),
        sa.column("lead_type", sa.String()),
        sa.column("supporting_signal_ids", sa.JSON()),
        sa.column("identity_key", sa.String()),
    )
    existing_rows = connection.execute(
        sa.select(leads.c.id, leads.c.lead_type, leads.c.supporting_signal_ids)
    ).fetchall()
    for row in existing_rows:
        connection.execute(
            leads.update()
            .where(leads.c.id == row.id)
            .values(identity_key=_compute_identity_key(row.lead_type, row.supporting_signal_ids))
        )

    # SQLite has no native ALTER COLUMN; Alembic's batch mode (copy the table,
    # apply the change, swap it in) is required here regardless of how the
    # environment configures rendering elsewhere.
    with op.batch_alter_table("leads") as batch_op:
        batch_op.alter_column("identity_key", existing_type=sa.String(length=64), nullable=False)

    op.create_index("ix_leads_identity_key", "leads", ["identity_key"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_leads_identity_key", table_name="leads")
    op.drop_column("leads", "identity_key")
