"""Seed default coordinates for branches without geo coordinates.

Revision ID: 0063_seed_branch_default_coordinates
Revises: 0062_seed_active_branch_public_order_keys
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0063_seed_branch_default_coordinates"
down_revision: str | None = "0062_seed_active_branch_public_order_keys"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    # If any active branch has NULL latitude or longitude, assign default coordinates (Culiacan Centro)
    bind.execute(
        sa.text(
            "UPDATE branches SET latitude = 24.8083000, longitude = -107.3938000 "
            "WHERE latitude IS NULL OR longitude IS NULL"
        )
    )


def downgrade() -> None:
    pass
