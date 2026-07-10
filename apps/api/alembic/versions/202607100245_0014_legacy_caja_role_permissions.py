"""legacy caja role permissions

Revision ID: 0014_legacy_caja_role_permissions
Revises: 0013_pos_cash_rbac_permissions
Create Date: 2026-07-10 02:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_legacy_caja_role_permissions"
down_revision: str | None = "0013_pos_cash_rbac_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CAJA_PERMISSION_CODES = [
    "cash.shift.read",
    "cash.shift.open",
    "cash.shift.close",
    "orders.read",
    "orders.create",
    "payments.confirm",
    "pos.operate",
]


def upgrade() -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT roles.id, permissions.id
            FROM roles
            CROSS JOIN permissions
            WHERE lower(roles.name) IN ('caja', 'cajero')
              AND permissions.code IN :permission_codes
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            sa.bindparam("permission_codes", expanding=True),
            permission_codes=CAJA_PERMISSION_CODES,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE lower(name) = 'caja'
            )
            AND permission_id IN (
                SELECT id FROM permissions WHERE code IN :permission_codes
            )
            """
        ).bindparams(
            sa.bindparam("permission_codes", expanding=True),
            permission_codes=CAJA_PERMISSION_CODES,
        )
    )
