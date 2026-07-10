"""pos cash rbac permissions

Revision ID: 0013_pos_cash_rbac_permissions
Revises: 0012_add_caja_role
Create Date: 2026-07-10 01:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0013_pos_cash_rbac_permissions"
down_revision: str | None = "0012_add_caja_role"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UTC = timezone.utc  # noqa: UP017

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
CAJERO_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000008"

PERMISSIONS = [
    (
        "018f6f73-2d0a-74f0-8f1c-000000000605",
        "cash.shift.read",
        "Consultar turnos y resumen de caja.",
    ),
    ("018f6f73-2d0a-74f0-8f1c-000000000606", "cash.shift.open", "Abrir turno de caja."),
    (
        "018f6f73-2d0a-74f0-8f1c-000000000607",
        "cash.shift.close",
        "Cerrar turno de caja y generar corte.",
    ),
    ("018f6f73-2d0a-74f0-8f1c-000000000608", "orders.read", "Consultar pedidos."),
    ("018f6f73-2d0a-74f0-8f1c-000000000609", "orders.create", "Crear pedidos desde POS."),
    ("018f6f73-2d0a-74f0-8f1c-000000000610", "payments.read", "Consultar pagos."),
    ("018f6f73-2d0a-74f0-8f1c-000000000611", "payments.confirm", "Confirmar pagos."),
    ("018f6f73-2d0a-74f0-8f1c-000000000612", "dashboard.read", "Consultar dashboard operativo."),
    ("018f6f73-2d0a-74f0-8f1c-000000000613", "pos.operate", "Entrar y operar POS."),
]

CAJERO_PERMISSION_CODES = [
    "cash.shift.read",
    "cash.shift.open",
    "cash.shift.close",
    "orders.read",
    "orders.create",
    "payments.confirm",
    "pos.operate",
]


def upgrade() -> None:
    now = datetime(2026, 7, 10, 1, 30, tzinfo=UTC)
    for permission_id, code, description in PERMISSIONS:
        op.execute(
            sa.text(
                """
                INSERT INTO permissions (id, code, description, created_at)
                VALUES (:id, :code, :description, :created_at)
                ON CONFLICT (code) DO NOTHING
                """
            ).bindparams(
                id=permission_id,
                code=code,
                description=description,
                created_at=now,
            )
        )

    op.execute(
        sa.text(
            """
            UPDATE roles
            SET name = 'Cajero'
            WHERE id = :role_id
              AND name = 'Caja'
              AND NOT EXISTS (
                SELECT 1 FROM roles
                WHERE organization_id = :organization_id
                  AND name = 'Cajero'
              )
            """
        ).bindparams(role_id=CAJERO_ROLE_ID, organization_id=ORGANIZATION_ID)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO roles (id, organization_id, name, scope, created_at)
            VALUES (:id, :organization_id, 'Cajero', 'branch', :created_at)
            ON CONFLICT (id) DO NOTHING
            """
        ).bindparams(
            id=CAJERO_ROLE_ID,
            organization_id=ORGANIZATION_ID,
            created_at=now,
        )
    )

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT :admin_role_id, permissions.id
            FROM permissions
            WHERE permissions.code IN :permission_codes
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            sa.bindparam("permission_codes", expanding=True),
            admin_role_id=ADMIN_ROLE_ID,
            permission_codes=[code for _, code, _ in PERMISSIONS],
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT :cajero_role_id, permissions.id
            FROM permissions
            WHERE permissions.code IN :permission_codes
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            sa.bindparam("permission_codes", expanding=True),
            cajero_role_id=CAJERO_ROLE_ID,
            permission_codes=CAJERO_PERMISSION_CODES,
        )
    )


def downgrade() -> None:
    op.execute(
        sa.text("DELETE FROM role_permissions WHERE role_id = :role_id").bindparams(
            role_id=CAJERO_ROLE_ID
        )
    )
    codes = [code for _, code, _ in PERMISSIONS]
    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)
            """
        ).bindparams(
            sa.bindparam("codes", expanding=True),
            codes=codes,
        )
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
            sa.bindparam("codes", expanding=True),
            codes=codes,
        )
    )
