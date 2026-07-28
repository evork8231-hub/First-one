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

Retry-safety. Every step below first checks the database's *actual*
current state (via a fresh ``sqlalchemy.inspect(connection)`` each time,
never a value cached from an earlier check in this same run) and skips
itself if that step's effect is already present, rather than
unconditionally re-issuing it. This is what makes the migration safe to
simply rerun (e.g. via ``sigint init`` again) after any interruption:

    ``ALTER TABLE ... ADD COLUMN`` is a standalone statement that SQLite
    commits immediately and irreversibly, independent of the surrounding
    Alembic transaction (confirmed by direct testing: interrupting the
    migration after this statement but before ``alembic_version`` is
    updated leaves the column durably present, but Alembic still
    believes the database is at revision ``0001`` and will unconditionally
    re-attempt this same ``ADD COLUMN`` on the very next run --
    previously failing outright with "duplicate column name"). The same
    reasoning applies to the backfill (guarded by only ever touching rows
    where ``identity_key IS NULL``, so a rerun does no redundant work and
    is unaffected by whatever subset of rows a prior, interrupted attempt
    already updated), the nullability change, and the index creation.
No step here ever requires an operator to run manual SQL to recover --
rerunning the migration is always sufficient.
"""

from __future__ import annotations

import hashlib
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.engine.interfaces import ReflectedColumn

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None

_TABLE = "leads"
_COLUMN = "identity_key"
_INDEX = "ix_leads_identity_key"


def _compute_identity_key(lead_type: str, supporting_signal_ids: list[str]) -> str:
    """Frozen copy of app.domain.lead.compute_lead_identity_key -- see module docstring."""
    sorted_ids = sorted(str(signal_id) for signal_id in supporting_signal_ids)
    raw = f"{lead_type}|{','.join(sorted_ids)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _column_info(connection: sa.Connection, table: str, column: str) -> ReflectedColumn | None:
    """Return this column's current reflected info, or None if it does not exist yet.

    Always re-inspects the live connection -- never reuses an Inspector
    result from earlier in this same migration run -- so it correctly
    sees a column this same ``upgrade()`` call just added.
    """
    for col in sa.inspect(connection).get_columns(table):
        if col["name"] == column:
            return col
    return None


def _index_exists(connection: sa.Connection, table: str, index_name: str) -> bool:
    return index_name in {ix["name"] for ix in sa.inspect(connection).get_indexes(table)}


def upgrade() -> None:
    connection = op.get_bind()

    if _column_info(connection, _TABLE, _COLUMN) is None:
        op.add_column(_TABLE, sa.Column(_COLUMN, sa.String(length=64), nullable=True))

    # `id` is deliberately typed as a plain String here, not sa.Uuid() -- comparing
    # `leads.c.id == row.id` through a Core sa.table() proxy (rather than a fully
    # reflected Table) does not reliably round-trip through Uuid's bind/result
    # processing against SQLite's raw on-disk representation, and silently matches
    # zero rows instead of raising. A plain string comparison against the exact
    # value just read back has no such ambiguity.
    leads = sa.table(
        _TABLE,
        sa.column("id", sa.String()),
        sa.column("lead_type", sa.String()),
        sa.column("supporting_signal_ids", sa.JSON()),
        sa.column(_COLUMN, sa.String()),
    )
    # Only rows that still need it -- makes a rerun after a partially-completed
    # backfill do no redundant work and remain correct regardless of exactly
    # which rows an earlier, interrupted attempt already updated.
    rows_needing_backfill = connection.execute(
        sa.select(leads.c.id, leads.c.lead_type, leads.c.supporting_signal_ids).where(
            leads.c.identity_key.is_(None)
        )
    ).fetchall()
    for row in rows_needing_backfill:
        connection.execute(
            leads.update()
            .where(leads.c.id == row.id)
            .values(identity_key=_compute_identity_key(row.lead_type, row.supporting_signal_ids))
        )

    column = _column_info(connection, _TABLE, _COLUMN)
    if column is not None and column.get("nullable", True):
        # SQLite has no native ALTER COLUMN; Alembic's batch mode (copy the table,
        # apply the change, swap it in) is required here regardless of how the
        # environment configures rendering elsewhere. Unlike the standalone
        # ADD COLUMN above, this sequence runs and rolls back as one unit if
        # interrupted (confirmed by direct testing), so it needs no separate
        # idempotency guard beyond the nullable check already gating this block.
        with op.batch_alter_table(_TABLE) as batch_op:
            batch_op.alter_column(_COLUMN, existing_type=sa.String(length=64), nullable=False)

    if not _index_exists(connection, _TABLE, _INDEX):
        op.create_index(_INDEX, _TABLE, [_COLUMN], unique=True)


def downgrade() -> None:
    connection = op.get_bind()
    if _index_exists(connection, _TABLE, _INDEX):
        op.drop_index(_INDEX, table_name=_TABLE)
    if _column_info(connection, _TABLE, _COLUMN) is not None:
        op.drop_column(_TABLE, _COLUMN)
