"""expand alembic_version.version_num capacity

Revision ID: 0013a_expand_version_num
Revises: 0013_pos_cash_rbac_permissions
Create Date: 2026-07-10 02:00:00.000000

Bridge migration that widens ``alembic_version.version_num`` from
``VARCHAR(32)`` to ``VARCHAR(128)`` on PostgreSQL before the first revision
whose identifier exceeds 32 characters (0014_legacy_caja_role_permissions).
On SQLite the migration is a documented no-op because SQLite does not enforce
the declared column length.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by alembic to detect the version of the schema.
revision: str = "0013a_expand_version_num"
down_revision: str | None = "0013_pos_cash_rbac_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

TARGET_LENGTH = 128
RESTORED_LENGTH = 32


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(:length)"
            ).bindparams(length=TARGET_LENGTH)
        )
    # SQLite (and other backends) do not enforce the declared VARCHAR length,
    # so no schema change is required to admit longer revision identifiers.


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        # Guard: never shrink the column if the current revision would not fit.
        # At this point the version row holds the bridge revision ID, which is
        # well within 32 characters, so the reduction is safe.
        current = bind.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
        if current is not None and len(str(current)) > RESTORED_LENGTH:
            raise RuntimeError(
                f"Cannot shrink alembic_version.version_num to VARCHAR("
                f"{RESTORED_LENGTH}): current revision '{current}' exceeds it."
            )
        op.execute(
            sa.text(
                "ALTER TABLE alembic_version "
                "ALTER COLUMN version_num TYPE VARCHAR(:length)"
            ).bindparams(length=RESTORED_LENGTH)
        )
    # SQLite: no-op.
