"""physical count snapshots, blind capture and authorized adjustments

Revision ID: 0023_physical_counts
Revises: 0022_inventory_transfers
Create Date: 2026-07-12 02:00:00
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0023_physical_counts"
down_revision: str | None = "0022_inventory_transfers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "physical_count_sessions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("folio", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="counting"),
        sa.Column("scope", sa.String(32), nullable=False, server_default="all_active"),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("cancellation_reason", sa.String(400), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("submitted_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approval_idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("snapshot_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("branch_id", "folio", name="uq_physical_count_branch_folio"),
    )
    op.create_table(
        "physical_count_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("session_id", sa.String(36), sa.ForeignKey("physical_count_sessions.id"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
        sa.Column("theoretical_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("snapshot_unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("snapshot_value", sa.Numeric(18, 6), nullable=False),
        sa.Column("counted_quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("snapshot_difference", sa.Numeric(18, 6), nullable=True),
        sa.Column("approval_ledger_quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("adjustment_quantity", sa.Numeric(18, 6), nullable=True),
        sa.Column("adjustment_unit_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("adjustment_cost", sa.Numeric(18, 6), nullable=True),
        sa.Column("adjustment_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True),
        sa.Column("captured_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.UniqueConstraint("session_id", "item_id", name="uq_physical_count_line_item"),
    )


def downgrade() -> None:
    op.drop_table("physical_count_lines")
    op.drop_table("physical_count_sessions")
