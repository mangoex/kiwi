"""Shared modifier sets assigned to multiple products.

Revision ID: 0075_shared_modifier_sets
Revises: 0074_dual_physical_counts
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0075_shared_modifier_sets"
down_revision: str | None = "0074_dual_physical_counts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "modifier_sets",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("station", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_modifier_sets_org_name"),
        sa.CheckConstraint("version >= 0", name="ck_modifier_sets_version"),
        sa.CheckConstraint("status IN ('active', 'archived')", name="ck_modifier_sets_status"),
    )
    op.create_table(
        "modifier_set_products",
        sa.Column(
            "modifier_set_id", sa.String(36), sa.ForeignKey("modifier_sets.id"), primary_key=True
        ),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('active', 'archived')", name="ck_modifier_set_products_status"
        ),
    )
    op.create_index(
        "ix_modifier_set_products_product_status",
        "modifier_set_products",
        ["product_id", "status"],
    )
    op.create_table(
        "modifier_set_configuration_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("modifier_set_id", sa.String(36), sa.ForeignKey("modifier_sets.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_modifier_set_commands_org_key"
        ),
    )
    with op.batch_alter_table("modifier_groups") as batch:
        batch.alter_column("product_id", existing_type=sa.String(36), nullable=True)
        batch.add_column(sa.Column("modifier_set_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_modifier_groups_modifier_set", "modifier_sets", ["modifier_set_id"], ["id"]
        )
        batch.create_unique_constraint(
            "uq_modifier_group_set_name", ["modifier_set_id", "name"]
        )
        batch.create_check_constraint(
            "ck_modifier_groups_single_owner",
            "(product_id IS NOT NULL AND modifier_set_id IS NULL) OR "
            "(product_id IS NULL AND modifier_set_id IS NOT NULL)",
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("LOCK TABLE modifier_sets IN ACCESS EXCLUSIVE MODE"))
        bind.execute(sa.text("LOCK TABLE modifier_groups IN ACCESS EXCLUSIVE MODE"))
    if bind.execute(sa.text("SELECT 1 FROM modifier_sets LIMIT 1")).first():
        raise RuntimeError("Cannot downgrade shared modifier sets while shared catalog data exists")
    with op.batch_alter_table("modifier_groups") as batch:
        batch.drop_constraint("ck_modifier_groups_single_owner", type_="check")
        batch.drop_constraint("uq_modifier_group_set_name", type_="unique")
        batch.drop_constraint("fk_modifier_groups_modifier_set", type_="foreignkey")
        batch.drop_column("modifier_set_id")
        batch.alter_column("product_id", existing_type=sa.String(36), nullable=False)
    op.drop_table("modifier_set_configuration_commands")
    op.drop_table("modifier_set_products")
    op.drop_table("modifier_sets")
