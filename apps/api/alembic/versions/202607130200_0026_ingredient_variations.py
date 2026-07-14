"""ingredient variations

Revision ID: 0026_ingredient_variations
Revises: 0025_legacy_branch_catalog_import
Create Date: 2026-07-13 02:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0026_ingredient_variations"
down_revision: str | None = "0025_legacy_branch_catalog_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingredient_variations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column(
            "inventory_item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False
        ),
        sa.Column("add_label", sa.String(120), nullable=False),
        sa.Column("remove_label", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "inventory_item_id", name="uq_ingredient_variation_org_item"
        ),
    )
    op.create_table(
        "ingredient_variation_products",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "variation_id", sa.String(36), sa.ForeignKey("ingredient_variations.id"), nullable=False
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("allow_add", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("allow_remove", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("add_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("remove_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("charge_additional", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("add_price_delta_cents", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "add_option_id",
            sa.String(36),
            sa.ForeignKey("modifier_options.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column(
            "remove_option_id",
            sa.String(36),
            sa.ForeignKey("modifier_options.id"),
            nullable=True,
            unique=True,
        ),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("variation_id", "product_id", name="uq_ingredient_variation_product"),
        sa.CheckConstraint("allow_add OR allow_remove", name="ck_ingredient_variation_actions"),
        sa.CheckConstraint(
            "NOT allow_add OR add_quantity > 0", name="ck_ingredient_variation_add_quantity"
        ),
        sa.CheckConstraint("remove_quantity >= 0", name="ck_ingredient_variation_remove_quantity"),
        sa.CheckConstraint(
            "NOT charge_additional OR (allow_add AND add_price_delta_cents > 0)",
            name="ck_ingredient_variation_charge",
        ),
        sa.CheckConstraint(
            "charge_additional OR add_price_delta_cents = 0",
            name="ck_ingredient_variation_free_price",
        ),
    )


def downgrade() -> None:
    op.drop_table("ingredient_variation_products")
    op.drop_table("ingredient_variations")
