"""Add granular human operational-observation grants.

Revision ID: 0057_operational_human_scope_permissions
Revises: 0056_repair_0047_canonical_roles
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0057_operational_human_scope_permissions"
down_revision: str | None = "0056_repair_0047_canonical_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
SYNC_PERMISSION_ID = "018f6f73-2d0a-74f0-8f1c-000000001120"
ROLE_IDS = {
    "Supervisor": "018f6f73-2d0a-74f0-8f1c-000000001004",
    "Administrador": "018f6f73-2d0a-74f0-8f1c-000000001005",
    "Dueño": "018f6f73-2d0a-74f0-8f1c-000000001006",
}
PERMISSION_IDS = {
    "kds.tasks.operate": "018f6f73-2d0a-74f0-8f1c-000000000928",
    "print.jobs.read": "018f6f73-2d0a-74f0-8f1c-000000000929",
    "print.jobs.retry": "018f6f73-2d0a-74f0-8f1c-000000000930",
}


def _preflight(bind: sa.Connection) -> None:
    roles = {
        str(row["id"]): row
        for row in bind.execute(
            sa.text(
                "SELECT id, organization_id, name, scope FROM roles WHERE id IN :role_ids"
            ).bindparams(
                sa.bindparam("role_ids", expanding=True), role_ids=list(ROLE_IDS.values())
            )
        ).mappings()
    }
    if len(roles) != len(ROLE_IDS):
        raise RuntimeError("0057 preflight failed: canonical operational role is missing")
    for name, role_id in ROLE_IDS.items():
        role = roles[role_id]
        expected_scope = "organization" if name == "Dueño" else "branch"
        if (
            role["organization_id"] != ORGANIZATION_ID
            or role["name"] != name
            or role["scope"] != expected_scope
        ):
            raise RuntimeError("0057 preflight failed: canonical operational role differs")

    existing = {
        str(row["code"]): str(row["id"])
        for row in bind.execute(
            sa.text("SELECT id, code FROM permissions WHERE code IN :codes").bindparams(
                sa.bindparam("codes", expanding=True), codes=list(PERMISSION_IDS)
            )
        ).mappings()
    }
    if existing != PERMISSION_IDS:
        raise RuntimeError("0057 preflight failed: operational permission identity differs")
    sync_collision = bind.execute(
        sa.text("SELECT id, code FROM permissions WHERE id = :id OR code = 'sync.events.read'"),
        {"id": SYNC_PERMISSION_ID},
    ).first()
    if sync_collision:
        raise RuntimeError("0057 preflight failed: sync permission identity exists")


def upgrade() -> None:
    bind = op.get_bind()
    _preflight(bind)
    bind.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, description, created_at)
            VALUES (:id, 'sync.events.read', :description, :created_at)
            """
        ),
        {
            "id": SYNC_PERMISSION_ID,
            "description": "Consultar eventos y estado de sincronización de una sucursal.",
            "created_at": datetime(2026, 8, 30, 2, 0, tzinfo=timezone.utc),
        },
    )
    permission_ids = [*PERMISSION_IDS.values(), SYNC_PERMISSION_ID]
    for role_id in ROLE_IDS.values():
        bind.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT :role_id, id FROM permissions WHERE id IN :permission_ids
                ON CONFLICT DO NOTHING
                """
            ).bindparams(sa.bindparam("permission_ids", expanding=True)),
            {"role_id": role_id, "permission_ids": permission_ids},
        )


def downgrade() -> None:
    bind = op.get_bind()
    external_sync_grant = bind.execute(
        sa.text(
            "SELECT 1 FROM role_permissions WHERE permission_id = :permission_id "
            "AND role_id NOT IN :role_ids LIMIT 1"
        ).bindparams(sa.bindparam("role_ids", expanding=True)),
        {"permission_id": SYNC_PERMISSION_ID, "role_ids": list(ROLE_IDS.values())},
    ).first()
    if external_sync_grant:
        raise RuntimeError("0057 downgrade blocked: sync.events.read has external grants")
    for role_id in ROLE_IDS.values():
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE role_id = :role_id "
                "AND permission_id IN :permission_ids"
            ).bindparams(sa.bindparam("permission_ids", expanding=True)),
            {
                "role_id": role_id,
                "permission_ids": [
                    PERMISSION_IDS["kds.tasks.operate"],
                    SYNC_PERMISSION_ID,
                ],
            },
        )
    for role_id in (ROLE_IDS["Supervisor"], ROLE_IDS["Administrador"]):
        bind.execute(
            sa.text(
                "DELETE FROM role_permissions WHERE role_id = :role_id "
                "AND permission_id IN :permission_ids"
            ).bindparams(sa.bindparam("permission_ids", expanding=True)),
            {
                "role_id": role_id,
                "permission_ids": [
                    PERMISSION_IDS["print.jobs.read"],
                    PERMISSION_IDS["print.jobs.retry"],
                ],
            },
        )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE id = :id AND code = 'sync.events.read'"),
        {"id": SYNC_PERMISSION_ID},
    )
