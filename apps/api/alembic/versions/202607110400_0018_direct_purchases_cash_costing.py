"""direct purchases, cash withdrawals and weighted average cost

Revision ID: 0018_direct_purchases_cash_costing
Revises: 0017_suppliers_purchase_presentations
Create Date: 2026-07-11 04:00:00
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0018_direct_purchases_cash_costing"
down_revision: str | None = "0017_suppliers_purchase_presentations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inventory_movements") as batch:
        batch.alter_column("quantity_delta", existing_type=sa.Integer(), type_=sa.Numeric(18, 6), nullable=False)
        batch.add_column(sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"))
        batch.add_column(sa.Column("total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"))
        batch.add_column(sa.Column("effective_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()))
        batch.add_column(sa.Column("actor_user_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("document_type", sa.String(48), nullable=True))
        batch.add_column(sa.Column("document_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("reference", sa.String(120), nullable=True))
        batch.add_column(sa.Column("notes", sa.String(600), nullable=True))
        batch.add_column(sa.Column("idempotency_key", sa.String(180), nullable=True))
        batch.add_column(sa.Column("status", sa.String(32), nullable=False, server_default="confirmed"))
        batch.add_column(sa.Column("reversal_of_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_inventory_movements_actor", "users", ["actor_user_id"], ["id"])
        batch.create_foreign_key("fk_inventory_movements_reversal", "inventory_movements", ["reversal_of_id"], ["id"])
        batch.create_unique_constraint("uq_inventory_movements_idempotency", ["idempotency_key"])
    op.execute(sa.text("UPDATE inventory_movements SET effective_at = created_at WHERE effective_at IS NULL"))
    with op.batch_alter_table("inventory_movements") as batch:
        batch.alter_column("effective_at", existing_type=sa.DateTime(timezone=True), nullable=False)

    op.create_table(
        "cash_movements",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
        sa.Column("movement_type", sa.String(32), nullable=False), sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("reason_code", sa.String(48), nullable=False), sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("source_type", sa.String(48), nullable=True), sa.Column("source_id", sa.String(36), nullable=True),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False, unique=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="confirmed"),
        sa.Column("reversal_of_id", sa.String(36), sa.ForeignKey("cash_movements.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "purchase_documents",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("document_type", sa.String(32), nullable=False), sa.Column("folio", sa.String(80), nullable=False),
        sa.Column("document_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False), sa.Column("discount_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("tax_total", sa.Numeric(18, 6), nullable=False), sa.Column("freight_total", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total", sa.Numeric(18, 6), nullable=False), sa.Column("payment_method", sa.String(32), nullable=False),
        sa.Column("paid_from_cash", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("cash_movement_id", sa.String(36), sa.ForeignKey("cash_movements.id"), nullable=True),
        sa.Column("evidence_url", sa.String(600), nullable=True), sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("status", sa.String(32), nullable=False), sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("confirmation_idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("cancellation_reason", sa.String(400), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True), sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("branch_id", "supplier_id", "document_type", "folio", name="uq_purchase_document_identity"),
    )
    op.create_table(
        "purchase_document_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("purchase_document_id", sa.String(36), sa.ForeignKey("purchase_documents.id"), nullable=False),
        sa.Column("presentation_id", sa.String(36), sa.ForeignKey("purchase_presentations.id"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("presentation_snapshot", sa.JSON(), nullable=False),
        sa.Column("presentation_quantity", sa.Numeric(18, 6), nullable=False), sa.Column("base_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False), sa.Column("discount", sa.Numeric(18, 6), nullable=False),
        sa.Column("tax", sa.Numeric(18, 6), nullable=False), sa.Column("line_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("inventory_cost", sa.Numeric(18, 6), nullable=False), sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "inventory_cost_states",
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), primary_key=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), primary_key=True),
        sa.Column("quantity_on_hand", sa.Numeric(18, 6), nullable=False),
        sa.Column("average_unit_cost", sa.Numeric(18, 6), nullable=False), sa.Column("last_unit_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("last_supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=True),
        sa.Column("last_cost_at", sa.DateTime(timezone=True), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("inventory_cost_states")
    op.drop_table("purchase_document_lines")
    op.drop_table("purchase_documents")
    op.drop_table("cash_movements")
    with op.batch_alter_table("inventory_movements") as batch:
        batch.drop_constraint("uq_inventory_movements_idempotency", type_="unique")
        batch.drop_constraint("fk_inventory_movements_reversal", type_="foreignkey")
        batch.drop_constraint("fk_inventory_movements_actor", type_="foreignkey")
        for column in ("reversal_of_id", "status", "idempotency_key", "notes", "reference", "document_id", "document_type", "actor_user_id", "effective_at", "total_cost", "unit_cost"):
            batch.drop_column(column)
        batch.alter_column("quantity_delta", existing_type=sa.Numeric(18, 6), type_=sa.Integer(), nullable=False)
