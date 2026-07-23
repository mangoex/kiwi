"""delivery assignments

Revision ID: 0031_delivery_assignments
Revises: 0030_driver_catalog
Create Date: 2026-07-23 02:30:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0031_delivery_assignments"
down_revision: str | None = "0030_driver_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "delivery_assignments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(36),
            sa.ForeignKey("branches.id"),
            nullable=False,
        ),
        sa.Column(
            "order_id",
            sa.String(36),
            sa.ForeignKey("orders.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "driver_id",
            sa.String(36),
            sa.ForeignKey("drivers.id"),
            nullable=False,
        ),
        sa.Column(
            "customer_id",
            sa.String(36),
            sa.ForeignKey("customers.id"),
            nullable=True,
        ),
        sa.Column("driver_name_snapshot", sa.String(160), nullable=False),
        sa.Column("customer_name_snapshot", sa.String(160), nullable=False),
        sa.Column("delivery_address_snapshot", sa.JSON(), nullable=False),
        sa.Column("order_total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("line_count", sa.Integer(), nullable=False),
        sa.Column("item_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="ASSIGNED",
        ),
        sa.Column(
            "assigned_by",
            sa.String(36),
            sa.ForeignKey("users.id"),
            nullable=False,
        ),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_delivery_assignments_driver_date",
        "delivery_assignments",
        ["driver_id", "assigned_at"],
    )
    op.create_index(
        "ix_delivery_assignments_branch_date",
        "delivery_assignments",
        ["branch_id", "assigned_at"],
    )


def downgrade() -> None:
    connection = op.get_bind()
    assignment_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM delivery_assignments")
    ).scalar_one()
    if assignment_count:
        raise RuntimeError("Cannot downgrade 0031 while delivery assignments exist")
    op.drop_index(
        "ix_delivery_assignments_branch_date",
        table_name="delivery_assignments",
    )
    op.drop_index(
        "ix_delivery_assignments_driver_date",
        table_name="delivery_assignments",
    )
    op.drop_table("delivery_assignments")
