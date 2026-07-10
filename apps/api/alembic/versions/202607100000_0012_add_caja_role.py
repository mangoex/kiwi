from __future__ import annotations

# ruff: noqa: E501
"""add caja role

Revision ID: 0012_add_caja_role
Revises: 0011_add_product_image_url
Create Date: 2026-07-10 00:00:00.000000

"""
from collections.abc import Sequence
from datetime import datetime, timezone
UTC = timezone.utc

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0012_add_caja_role'
down_revision: str | None = '0011_add_product_image_url'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
CAJA_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000008"

def upgrade() -> None:
    now = datetime(2026, 7, 10, 0, 0, tzinfo=UTC)
    op.execute(
        sa.text(
            """
            INSERT INTO roles (id, organization_id, name, scope, created_at)
            VALUES (:id, :organization_id, 'Caja', 'branch', :created_at)
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=CAJA_ROLE_ID,
            organization_id=ORGANIZATION_ID,
            created_at=now,
        )
    )

def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM roles WHERE id = :id
            """
        ).bindparams(id=CAJA_ROLE_ID)
    )
