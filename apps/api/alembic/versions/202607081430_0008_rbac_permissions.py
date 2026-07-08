"""rbac permissions

Revision ID: 202607081430
Revises: 202607081200
Create Date: 2026-07-08 14:30:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "202607081430"
down_revision: str | None = "202607081200"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"

PERMISSIONS = [
    (
        "018f6f73-2d0a-74f0-8f1c-000000000601",
        "admin.manage",
        "Administrar usuarios, roles y asignaciones.",
    ),
    (
        "018f6f73-2d0a-74f0-8f1c-000000000602",
        "catalog.manage",
        "Administrar sucursales, almacenes, productos y catalogos.",
    ),
    (
        "018f6f73-2d0a-74f0-8f1c-000000000603",
        "inventory.adjust",
        "Registrar movimientos administrativos de inventario.",
    ),
    (
        "018f6f73-2d0a-74f0-8f1c-000000000604",
        "orders.cancel",
        "Cancelar pedidos y clasificar cancelaciones producidas.",
    ),
]


def upgrade() -> None:
    now = datetime(2026, 7, 8, 14, 30, tzinfo=UTC)
    permissions = sa.table(
        "permissions",
        sa.column("id"),
        sa.column("code"),
        sa.column("description"),
        sa.column("created_at"),
    )
    role_permissions = sa.table(
        "role_permissions",
        sa.column("role_id"),
        sa.column("permission_id"),
    )

    op.bulk_insert(
        permissions,
        [
            {
                "id": permission_id,
                "code": code,
                "description": description,
                "created_at": now,
            }
            for permission_id, code, description in PERMISSIONS
        ],
    )
    op.bulk_insert(
        role_permissions,
        [
            {"role_id": ADMIN_ROLE_ID, "permission_id": permission_id}
            for permission_id, _, _ in PERMISSIONS
        ],
    )


def downgrade() -> None:
    permission_ids = ", ".join(f"'{permission_id}'" for permission_id, _, _ in PERMISSIONS)
    op.execute(sa.text(f"DELETE FROM role_permissions WHERE permission_id IN ({permission_ids})"))
    op.execute(sa.text(f"DELETE FROM permissions WHERE id IN ({permission_ids})"))
