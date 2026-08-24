from __future__ import annotations

# ruff: noqa: E501
"""add phone and supplier_type to suppliers

Revision ID: 0046_supplier_extended_fields
Revises: 0045_branch_address_and_coordinates
Create Date: 2026-08-24 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0046_supplier_extended_fields"
down_revision: str | None = "0045_branch_address_and_coordinates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.add_column(sa.Column("phone", sa.String(length=32), nullable=True))
        batch_op.add_column(
            sa.Column("supplier_type", sa.String(length=64), nullable=False, server_default="insumos")
        )


def downgrade() -> None:
    with op.batch_alter_table("suppliers") as batch_op:
        batch_op.drop_column("supplier_type")
        batch_op.drop_column("phone")
