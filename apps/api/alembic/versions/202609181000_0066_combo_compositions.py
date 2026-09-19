"""Add fixed, auditable combo compositions and order-line snapshots.

Revision ID: 0066_combo_compositions
Revises: 0065_admin_catalog
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0066_combo_compositions"
down_revision: str | None = "0065_admin_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "product_compositions",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("combo_product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="active"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_product_compositions_version"),
        sa.CheckConstraint(
            "status IN ('active', 'superseded')", name="ck_product_compositions_status"
        ),
        sa.UniqueConstraint(
            "combo_product_id", "branch_id", "version", name="uq_product_compositions_scope_version"
        ),
    )
    op.create_table(
        "product_composition_components",
        sa.Column(
            "composition_id",
            sa.String(36),
            sa.ForeignKey("product_compositions.id"),
            primary_key=True,
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_product_composition_components_quantity"),
    )
    op.create_table(
        "product_composition_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_product_composition_commands_key"
        ),
    )
    op.create_table(
        "order_line_component_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), nullable=False),
        sa.Column(
            "production_task_id",
            sa.String(36),
            sa.ForeignKey("production_tasks.id"),
            nullable=False,
        ),
        sa.Column(
            "composition_id",
            sa.String(36),
            sa.ForeignKey("product_compositions.id"),
            nullable=False,
        ),
        sa.Column("composition_version", sa.Integer(), nullable=False),
        sa.Column(
            "component_product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False
        ),
        sa.Column("component_product_name", sa.String(160), nullable=False),
        sa.Column("component_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("station", sa.String(32), nullable=False),
        sa.Column("recipe_id", sa.String(36), sa.ForeignKey("recipes.id"), nullable=True),
        sa.Column("recipe_version", sa.Integer(), nullable=True),
        sa.Column("recipe_components", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "order_line_id",
            "component_product_id",
            name="uq_order_line_component_snapshots_component",
        ),
        sa.UniqueConstraint("production_task_id", name="uq_order_line_component_snapshots_task"),
    )
    op.create_index(
        "ix_product_compositions_effective",
        "product_compositions",
        ["organization_id", "combo_product_id", "branch_id", "status"],
    )
    op.create_index(
        "ix_order_line_component_snapshots_line",
        "order_line_component_snapshots",
        ["order_line_id"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    used = connection.execute(
        sa.text("SELECT 1 FROM order_line_component_snapshots LIMIT 1")
    ).scalar_one_or_none()
    if used:
        raise RuntimeError("Cannot downgrade 0066 while combo order snapshots exist")
    op.drop_index(
        "ix_order_line_component_snapshots_line", table_name="order_line_component_snapshots"
    )
    op.drop_index("ix_product_compositions_effective", table_name="product_compositions")
    op.drop_table("order_line_component_snapshots")
    op.drop_table("product_composition_commands")
    op.drop_table("product_composition_components")
    op.drop_table("product_compositions")
