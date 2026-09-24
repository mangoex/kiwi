"""ADMIN-PROD-001 idempotent product configuration commands."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0068_admin_product_configuration"
down_revision = "0067_offline_orders"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "catalog_product_configuration_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("command_type", sa.String(16), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "idempotency_key",
            name="uq_catalog_product_configuration_commands_org_key",
        ),
        sa.CheckConstraint(
            "command_type IN ('create', 'update')",
            name="ck_catalog_product_configuration_commands_type",
        ),
        sa.CheckConstraint(
            "status IN ('processing', 'completed')",
            name="ck_catalog_product_configuration_commands_status",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(
        sa.text("SELECT 1 FROM catalog_product_configuration_commands LIMIT 1")
    ).first() is not None:
        raise RuntimeError(
            "Cannot downgrade 0068 while product configuration command history exists"
        )
    op.drop_table("catalog_product_configuration_commands")
