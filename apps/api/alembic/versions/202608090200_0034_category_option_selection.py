"""category option selection before POS products

Revision ID: 0034_category_option_selection
Revises: 0033_restore_superadmin_role
Create Date: 2026-08-09 02:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0034_category_option_selection"
down_revision: str | None = "0033_restore_superadmin_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "category_option_groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("product_categories.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("selection_mode", sa.String(16), nullable=False, server_default="single"),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="inactive"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("selection_mode = 'single'", name="ck_category_option_groups_selection_mode"),
        sa.CheckConstraint("is_required", name="ck_category_option_groups_required"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'archived')", name="ck_category_option_groups_status"),
        sa.UniqueConstraint("organization_id", "category_id", name="uq_category_option_groups_organization_category"),
    )
    op.create_table(
        "category_option_values",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("category_option_groups.id"), nullable=False),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("status IN ('active', 'inactive', 'archived')", name="ck_category_option_values_status"),
        sa.UniqueConstraint("group_id", "code", name="uq_category_option_values_group_code"),
    )
    op.create_table(
        "product_option_value_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("group_id", sa.String(36), sa.ForeignKey("category_option_groups.id"), nullable=False),
        sa.Column("option_value_id", sa.String(36), sa.ForeignKey("category_option_values.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "group_id", name="uq_product_option_value_assignments_product_group"),
    )
    op.create_index("ix_category_option_values_group_order", "category_option_values", ["group_id", "display_order"])
    op.create_index("ix_product_option_value_assignments_group_value", "product_option_value_assignments", ["group_id", "option_value_id"])


def downgrade() -> None:
    op.drop_index("ix_product_option_value_assignments_group_value", table_name="product_option_value_assignments")
    op.drop_index("ix_category_option_values_group_order", table_name="category_option_values")
    op.drop_table("product_option_value_assignments")
    op.drop_table("category_option_values")
    op.drop_table("category_option_groups")
