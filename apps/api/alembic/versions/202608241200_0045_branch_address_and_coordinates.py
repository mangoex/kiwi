from __future__ import annotations

# ruff: noqa: E501
"""add address cross streets and coordinates to branches

Revision ID: 0045_branch_address_and_coordinates
Revises: 0044_audit_fulfillment
Create Date: 2026-08-24 12:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0045_branch_address_and_coordinates"
down_revision: str | None = "0044_audit_fulfillment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("branches") as batch_op:
        batch_op.add_column(sa.Column("street", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("exterior_number", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("interior_number", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("neighborhood", sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column("postal_code", sa.String(length=12), nullable=True))
        batch_op.add_column(sa.Column("city", sa.String(length=100), nullable=True, server_default="Culiacán"))
        batch_op.add_column(sa.Column("state", sa.String(length=100), nullable=True, server_default="Sinaloa"))
        batch_op.add_column(sa.Column("cross_streets", sa.String(length=250), nullable=True))
        batch_op.add_column(sa.Column("latitude", sa.Numeric(10, 7), nullable=True))
        batch_op.add_column(sa.Column("longitude", sa.Numeric(10, 7), nullable=True))
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("branches") as batch_op:
        batch_op.drop_column("phone")
        batch_op.drop_column("longitude")
        batch_op.drop_column("latitude")
        batch_op.drop_column("cross_streets")
        batch_op.drop_column("state")
        batch_op.drop_column("city")
        batch_op.drop_column("postal_code")
        batch_op.drop_column("neighborhood")
        batch_op.drop_column("interior_number")
        batch_op.drop_column("exterior_number")
        batch_op.drop_column("street")
