"""Add isolated ADMIN-RETRO-001 catalog configuration and command records.

Revision ID: 0065_admin_catalog
Revises: 0064_add_branches_google_review_url
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0065_admin_catalog"
down_revision: str | None = "0064_add_branches_google_review_url"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_category_priority_configs",
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), primary_key=True
        ),
        sa.Column("view_category_ids", sa.JSON(), nullable=False),
        sa.Column("print_category_ids", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_admin_category_priority_configs_version"),
    )
    op.create_table(
        "inventory_stock_thresholds",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("minimum_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("maximum_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("minimum_quantity >= 0", name="ck_inventory_stock_thresholds_minimum"),
        sa.CheckConstraint(
            "maximum_quantity >= minimum_quantity", name="ck_inventory_stock_thresholds_range"
        ),
        sa.CheckConstraint("version > 0", name="ck_inventory_stock_thresholds_version"),
        sa.UniqueConstraint(
            "organization_id",
            "branch_id",
            "warehouse_id",
            "item_id",
            name="uq_inventory_stock_thresholds_scope_item",
        ),
    )
    op.create_index(
        "ix_inventory_stock_thresholds_branch_warehouse",
        "inventory_stock_thresholds",
        ["organization_id", "branch_id", "warehouse_id"],
    )
    op.create_table(
        "admin_recipe_bulk_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("preview_fingerprint", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("trim(idempotency_key) != ''", name="ck_admin_recipe_bulk_commands_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_admin_recipe_bulk_commands_hash"),
        sa.CheckConstraint(
            "length(preview_fingerprint) = 64", name="ck_admin_recipe_bulk_commands_preview_hash"
        ),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_admin_recipe_bulk_commands_key"
        ),
    )
    op.create_index(
        "ix_admin_recipe_bulk_commands_branch_created",
        "admin_recipe_bulk_commands",
        ["organization_id", "branch_id", "created_at"],
    )
    op.create_index(
        "ix_recipe_components_item_recipe",
        "recipe_components",
        ["item_id", "recipe_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_recipe_components_item_recipe", table_name="recipe_components")
    op.drop_index(
        "ix_admin_recipe_bulk_commands_branch_created", table_name="admin_recipe_bulk_commands"
    )
    op.drop_table("admin_recipe_bulk_commands")
    op.drop_index(
        "ix_inventory_stock_thresholds_branch_warehouse", table_name="inventory_stock_thresholds"
    )
    op.drop_table("inventory_stock_thresholds")
    op.drop_table("admin_category_priority_configs")
