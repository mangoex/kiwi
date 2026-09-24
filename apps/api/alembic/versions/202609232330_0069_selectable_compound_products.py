"""Selectable compound products with versioned modifier configuration.

Revision ID: 0069_selectable_compound_product
Revises: 0068_admin_product_configuration
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0069_selectable_compound_product"
down_revision = "0068_admin_product_configuration"
branch_labels = depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("modifier_groups") as batch:
        batch.add_column(
            sa.Column("included_selections", sa.Integer(), nullable=False, server_default="0")
        )
        batch.create_check_constraint(
            "ck_modifier_groups_included_range",
            "included_selections >= 0 AND included_selections <= maximum_selections",
        )
    with op.batch_alter_table("modifier_options") as batch:
        batch.add_column(sa.Column("component_product_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("component_quantity", sa.Numeric(18, 6), nullable=True))
        batch.create_foreign_key(
            "fk_modifier_options_component_product",
            "products",
            ["component_product_id"],
            ["id"],
        )
        batch.create_index(
            "ix_modifier_options_component_product_id", ["component_product_id"]
        )
        batch.create_check_constraint(
            "ck_modifier_options_price_nonnegative",
            "price_delta_cents BETWEEN 0 AND 2147483647",
        )
        batch.create_check_constraint(
            "ck_modifier_options_component_quantity_positive",
            "component_quantity IS NULL OR component_quantity > 0",
        )
        batch.create_check_constraint(
            "ck_modifier_options_component_authority",
            "(effect_type = 'product_component' AND component_product_id IS NOT NULL "
            "AND component_quantity IS NOT NULL AND affected_item_id IS NULL "
            "AND replacement_item_id IS NULL) OR "
            "(effect_type <> 'product_component' AND component_product_id IS NULL "
            "AND component_quantity IS NULL)",
        )
    with op.batch_alter_table("branch_modifier_options") as batch:
        batch.create_check_constraint(
            "ck_branch_modifier_options_price_nonnegative",
            "price_delta_cents IS NULL OR price_delta_cents BETWEEN 0 AND 2147483647",
        )
    op.create_table(
        "product_modifier_configurations",
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("updated_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("version >= 0", name="ck_product_modifier_configurations_version"),
    )
    op.create_table(
        "modifier_configuration_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_modifier_configuration_commands_org_key",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_commands = bind.execute(
        sa.text("SELECT 1 FROM modifier_configuration_commands LIMIT 1")
    ).first()
    has_configuration = bind.execute(
        sa.text("SELECT 1 FROM product_modifier_configurations LIMIT 1")
    ).first()
    if has_commands is not None or has_configuration is not None:
        raise RuntimeError(
            "Cannot downgrade 0069 while compound-product configuration history exists"
        )
    op.drop_table("modifier_configuration_commands")
    op.drop_table("product_modifier_configurations")
    with op.batch_alter_table("branch_modifier_options") as batch:
        batch.drop_constraint(
            "ck_branch_modifier_options_price_nonnegative", type_="check"
        )
    with op.batch_alter_table("modifier_options") as batch:
        batch.drop_constraint("ck_modifier_options_component_authority", type_="check")
        batch.drop_constraint(
            "ck_modifier_options_component_quantity_positive", type_="check"
        )
        batch.drop_constraint("ck_modifier_options_price_nonnegative", type_="check")
        batch.drop_index("ix_modifier_options_component_product_id")
        batch.drop_constraint("fk_modifier_options_component_product", type_="foreignkey")
        batch.drop_column("component_quantity")
        batch.drop_column("component_product_id")
    with op.batch_alter_table("modifier_groups") as batch:
        batch.drop_constraint("ck_modifier_groups_included_range", type_="check")
        batch.drop_column("included_selections")
