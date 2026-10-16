"""Branch-scoped exclusions from the public digital menu.

Revision ID: 0095_branch_product_digital_visibility
Revises: 0094_purchase_delivery_details
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0095_branch_product_digital_visibility"
down_revision: str | None = "0094_purchase_delivery_details"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "branch_product_digital_visibility",
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("branches.id"),
            primary_key=True,
        ),
        sa.Column(
            "product_id",
            sa.String(36),
            sa.ForeignKey("products.id"),
            primary_key=True,
        ),
        sa.Column("is_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "is_visible = false",
            name="ck_branch_product_digital_visibility_exclusion",
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    has_exclusions = bind.execute(
        sa.text("SELECT 1 FROM branch_product_digital_visibility LIMIT 1")
    ).first()
    if has_exclusions:
        raise RuntimeError("0095 downgrade blocked: digital visibility exclusions exist")
    op.drop_table("branch_product_digital_visibility")
