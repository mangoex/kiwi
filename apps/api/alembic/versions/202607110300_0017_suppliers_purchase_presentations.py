"""suppliers and purchase presentations

Revision ID: 0017_suppliers_purchase_presentations
Revises: 0016_customer_directory_snapshots
Create Date: 2026-07-11 03:00:00
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0017_suppliers_purchase_presentations"
down_revision: str | None = "0016_customer_directory_snapshots"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("inventory_units") as batch:
        batch.add_column(sa.Column("dimension", sa.String(24), nullable=False, server_default="discrete"))
    op.execute(sa.text("UPDATE inventory_units SET dimension = 'mass' WHERE UPPER(code) IN ('KG', 'G')"))
    op.execute(sa.text("UPDATE inventory_units SET dimension = 'volume' WHERE UPPER(code) IN ('L', 'ML')"))

    op.create_table(
        "suppliers",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("commercial_name", sa.String(180), nullable=False),
        sa.Column("legal_name", sa.String(180), nullable=True),
        sa.Column("tax_id", sa.String(16), nullable=True),
        sa.Column("tax_regime", sa.String(12), nullable=True),
        sa.Column("fiscal_address", sa.String(500), nullable=True),
        sa.Column("fiscal_postal_code", sa.String(12), nullable=True),
        sa.Column("municipality", sa.String(100), nullable=True),
        sa.Column("state", sa.String(100), nullable=True),
        sa.Column("country", sa.String(2), nullable=False, server_default="MX"),
        sa.Column("billing_email", sa.String(180), nullable=True),
        sa.Column("credit_days", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("credit_limit", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
        sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("usual_lead_time_days", sa.Integer(), nullable=True),
        sa.Column("delivery_days", sa.JSON(), nullable=False),
        sa.Column("payment_methods", sa.JSON(), nullable=False),
        sa.Column("accounting_reference", sa.String(120), nullable=True),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_suppliers_organization_code"),
    )
    op.create_table(
        "supplier_contacts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("position_area", sa.String(120), nullable=True), sa.Column("phone", sa.String(32), nullable=True),
        sa.Column("whatsapp", sa.String(32), nullable=True), sa.Column("email", sa.String(180), nullable=True),
        sa.Column("contact_type", sa.String(32), nullable=False), sa.Column("schedule", sa.String(160), nullable=True),
        sa.Column("primary_for_orders", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary_for_billing", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("primary_for_collection", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.String(400), nullable=True), sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "supplier_branch_terms",
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("lead_time_days", sa.Integer(), nullable=True), sa.Column("minimum_amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("notes", sa.String(400), nullable=True), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "purchase_presentations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False), sa.Column("name", sa.String(180), nullable=False),
        sa.Column("package_type", sa.String(40), nullable=False), sa.Column("commercial_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("commercial_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
        sa.Column("base_unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
        sa.Column("base_unit_yield", sa.Numeric(18, 6), nullable=False), sa.Column("gross_content", sa.Numeric(18, 6), nullable=True),
        sa.Column("net_content", sa.Numeric(18, 6), nullable=True), sa.Column("usable_content", sa.Numeric(18, 6), nullable=False),
        sa.Column("yield_percent", sa.Numeric(9, 6), nullable=False), sa.Column("barcode", sa.String(64), nullable=True),
        sa.Column("tax_rate", sa.Numeric(9, 6), nullable=False, server_default="0"),
        sa.Column("last_net_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("is_preferred", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_purchase_presentations_org_code"),
    )
    op.create_table(
        "supplier_price_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("presentation_id", sa.String(36), sa.ForeignKey("purchase_presentations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("net_price", sa.Numeric(18, 6), nullable=False), sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("recorded_by", sa.String(36), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("supplier_price_history")
    op.drop_table("purchase_presentations")
    op.drop_table("supplier_branch_terms")
    op.drop_table("supplier_contacts")
    op.drop_table("suppliers")
    with op.batch_alter_table("inventory_units") as batch:
        batch.drop_column("dimension")
