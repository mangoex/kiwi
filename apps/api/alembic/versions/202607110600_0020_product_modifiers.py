"""product modifiers, branch overrides and order snapshots

Revision ID: 0020_product_modifiers
Revises: 0019_advanced_recipes_production
Create Date: 2026-07-11 06:00:00
"""

from __future__ import annotations
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0020_product_modifiers"
down_revision: str | None = "0019_advanced_recipes_production"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "modifier_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("minimum_selections", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("maximum_selections", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("station", sa.String(32), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "name", name="uq_modifier_group_product_name"),
    )
    op.create_table(
        "modifier_options",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("modifier_groups.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("effect_type", sa.String(24), nullable=False),
        sa.Column("price_delta_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("affected_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=True),
        sa.Column("replacement_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=True),
        sa.Column("remove_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("add_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("inventory_effect", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("kitchen_text", sa.String(240), nullable=False),
        sa.Column("station", sa.String(32), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("group_id", "name", name="uq_modifier_option_group_name"),
    )
    op.create_table(
        "branch_modifier_options",
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), primary_key=True),
        sa.Column("option_id", sa.String(36), sa.ForeignKey("modifier_options.id"), primary_key=True),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("price_delta_cents", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("order_lines") as batch:
        batch.add_column(sa.Column("selected_modifiers", sa.JSON(), nullable=False, server_default="[]"))
        batch.add_column(sa.Column("modifier_total_cents", sa.Integer(), nullable=False, server_default="0"))
        batch.add_column(sa.Column("line_notes", sa.String(500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("order_lines") as batch:
        batch.drop_column("line_notes")
        batch.drop_column("modifier_total_cents")
        batch.drop_column("selected_modifiers")
    op.drop_table("branch_modifier_options")
    op.drop_table("modifier_options")
    op.drop_table("modifier_groups")
