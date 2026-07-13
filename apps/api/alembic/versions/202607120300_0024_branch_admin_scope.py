"""branch admin scope permissions

Revision ID: 0024_branch_admin_scope
Revises: 0023_physical_counts
Create Date: 2026-07-12 03:00:00.000000

Introduces three permissions for branch-scoped administration:
- ``branch.admin.access`` — enter the operational admin hub for a branch.
- ``branch.staff.read`` — read staff assigned to a branch.
- ``catalog.branch.manage`` — modify only availability and catalog exceptions
  for an authorized branch.

Assigns all three to the corporate Administrator and to the Branch Supervisor,
and ensures the Supervisor retains ``production.manage``. Does not grant any
of the three to Cajero or the legacy Caja role. Idempotent and reversible.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0024_branch_admin_scope"
down_revision: str | None = "0023_physical_counts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UTC = timezone.utc  # noqa: UP017

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
SUPERVISOR_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000016"

NEW_PERMISSIONS = [
    (
        "018f6f73-2d0a-74f0-8f1c-000000000624",
        "branch.admin.access",
        "Entrar al centro administrativo operativo de la sucursal.",
    ),
    (
        "018f6f73-2d0a-74f0-8f1c-000000000625",
        "branch.staff.read",
        "Consultar el personal asignado a la sucursal.",
    ),
    (
        "018f6f73-2d0a-74f0-8f1c-000000000626",
        "catalog.branch.manage",
        "Modificar disponibilidad y excepciones de cat\u00e1logo para una sucursal autorizada.",
    ),
]

NEW_PERMISSION_CODES = [code for _, code, _ in NEW_PERMISSIONS]


def _assign_permissions(role_id: str, codes: list[str]) -> None:
    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT :role_id, permissions.id FROM permissions
            WHERE permissions.code IN :codes
            ON CONFLICT DO NOTHING
            """
        ).bindparams(
            sa.bindparam("codes", expanding=True),
            role_id=role_id,
            codes=codes,
        )
    )


def upgrade() -> None:
    now = datetime(2026, 7, 12, 3, 0, tzinfo=UTC)

    for permission_id, code, description in NEW_PERMISSIONS:
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

    for role_id in (ADMIN_ROLE_ID, SUPERVISOR_ROLE_ID):
        _assign_permissions(role_id, NEW_PERMISSION_CODES)

    # Ensure the Supervisor retains production.manage (idempotent safety net).
    _assign_permissions(SUPERVISOR_ROLE_ID, ["production.manage"])


def downgrade() -> None:
    # Remove only the role_permissions and permissions introduced by this
    # migration. Never delete roles, users, or operational data.
    for role_id in (ADMIN_ROLE_ID, SUPERVISOR_ROLE_ID):
        op.execute(
            sa.text(
                """
                DELETE FROM role_permissions
                WHERE role_id = :role_id
                  AND permission_id IN (
                      SELECT id FROM permissions WHERE code IN :codes
                  )
                """
            ).bindparams(
                sa.bindparam("codes", expanding=True),
                role_id=role_id,
                codes=NEW_PERMISSION_CODES,
            )
        )

    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN :codes
              AND NOT EXISTS (
                  SELECT 1 FROM role_permissions
                  WHERE role_permissions.permission_id = permissions.id
              )
            """
        ).bindparams(
            sa.bindparam("codes", expanding=True),
            codes=NEW_PERMISSION_CODES,
        )
    )
