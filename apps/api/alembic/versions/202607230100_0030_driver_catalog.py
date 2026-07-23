"""driver catalog

Revision ID: 0030_driver_catalog
Revises: 0029_order_amendments_deferred
Create Date: 2026-07-23 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0030_driver_catalog"
down_revision: str | None = "0029_order_amendments_deferred"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "drivers",
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
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("license_number", sa.String(80), nullable=False),
        sa.Column("motorcycle_plate", sa.String(32), nullable=False),
        sa.Column("phone", sa.String(32), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("emergency_contact_name", sa.String(160), nullable=False),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_drivers_organization_branch", "drivers", ["organization_id", "branch_id"])


def downgrade() -> None:
    connection = op.get_bind()
    driver_count = connection.execute(sa.text("SELECT COUNT(*) FROM drivers")).scalar_one()
    if driver_count:
        raise RuntimeError("Cannot downgrade 0030 while driver records exist")
    op.drop_index("ix_drivers_organization_branch", table_name="drivers")
    op.drop_table("drivers")
