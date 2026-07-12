"""two-sided inventory transfers with in-transit costing

Revision ID: 0022_inventory_transfers
Revises: 0021_real_waste
Create Date: 2026-07-12 01:00:00
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0022_inventory_transfers"
down_revision: str | None = "0021_real_waste"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_transfers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("source_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("source_warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("destination_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("destination_warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("folio", sa.String(64), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="draft"),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("cancellation_reason", sa.String(400), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("sent_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("received_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("send_idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("receive_idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("source_branch_id", "folio", name="uq_inventory_transfer_source_folio"),
    )
    op.create_table(
        "inventory_transfer_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("transfer_id", sa.String(36), sa.ForeignKey("inventory_transfers.id"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
        sa.Column("requested_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("sent_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("received_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("difference_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("sent_total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("received_total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("difference_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("difference_reason", sa.String(400), nullable=True),
        sa.Column("condition", sa.String(40), nullable=True),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("out_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True),
        sa.Column("in_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("transfer_id", "item_id", name="uq_inventory_transfer_line_item"),
    )


def downgrade() -> None:
    op.drop_table("inventory_transfer_lines")
    op.drop_table("inventory_transfers")
