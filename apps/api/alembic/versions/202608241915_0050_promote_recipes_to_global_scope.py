from __future__ import annotations

# ruff: noqa: E501
"""promote existing recipes to global corporate scope (branch_id = NULL)

Revision ID: 0050_promote_recipes_to_global_scope
Revises: 0049_seed_la_primavera_branch_and_user
Create Date: 2026-08-24 19:15:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0050_promote_recipes_to_global_scope"
down_revision: str | None = "0049_seed_la_primavera_branch_and_user"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # Promote all active recipes to global corporate scope so all branches inherit them by default
    conn.execute(
        sa.text("""
            UPDATE recipes
            SET branch_id = NULL
            WHERE branch_id IS NOT NULL
        """)
    )


def downgrade() -> None:
    pass