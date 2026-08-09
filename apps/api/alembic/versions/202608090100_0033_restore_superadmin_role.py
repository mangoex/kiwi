"""restore canonical superadmin role after failed self-edit

Revision ID: 0033_restore_superadmin_role
Revises: 0032_attendance_clock
Create Date: 2026-08-09 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

UTC = timezone.utc

revision: str = "0033_restore_superadmin_role"
down_revision: str | None = "0032_attendance_clock"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
SUPERADMIN_EMAIL = "mangoex@gmail.com"
REPAIR_AUDIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000033"


def upgrade() -> None:
    bind = op.get_bind()
    target_user_id = bind.execute(
        sa.text(
            """
            SELECT id
            FROM users
            WHERE organization_id = :organization_id
              AND lower(email) = :email
            """
        ),
        {"organization_id": ORGANIZATION_ID, "email": SUPERADMIN_EMAIL},
    ).scalar_one_or_none()
    if not target_user_id:
        raise RuntimeError("Canonical superadmin user was not found")

    role_exists = bind.execute(
        sa.text(
            """
            SELECT id
            FROM roles
            WHERE id = :role_id
              AND organization_id = :organization_id
            """
        ),
        {"role_id": ADMIN_ROLE_ID, "organization_id": ORGANIZATION_ID},
    ).scalar_one_or_none()
    if not role_exists:
        raise RuntimeError("Canonical administrator role was not found")

    inserted = bind.execute(
        sa.text(
            """
            INSERT INTO user_roles (user_id, role_id, branch_id)
            SELECT :user_id, :role_id, NULL
            WHERE NOT EXISTS (
                SELECT 1
                FROM user_roles
                WHERE user_id = :user_id
                  AND role_id = :role_id
            )
            """
        ),
        {"user_id": target_user_id, "role_id": ADMIN_ROLE_ID},
    )
    if inserted.rowcount != 1:
        return

    audit_events = sa.table(
        "audit_events",
        sa.column("id", sa.String()),
        sa.column("organization_id", sa.String()),
        sa.column("branch_id", sa.String()),
        sa.column("actor_user_id", sa.String()),
        sa.column("action", sa.String()),
        sa.column("entity_type", sa.String()),
        sa.column("entity_id", sa.String()),
        sa.column("payload", sa.JSON()),
        sa.column("correlation_id", sa.String()),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )
    op.bulk_insert(
        audit_events,
        [
            {
                "id": REPAIR_AUDIT_ID,
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "actor_user_id": target_user_id,
                "action": "platform.superadmin_role_restored",
                "entity_type": "user",
                "entity_id": target_user_id,
                "payload": {
                    "role_id": ADMIN_ROLE_ID,
                    "source": revision,
                },
                "correlation_id": None,
                "created_at": datetime(2026, 8, 9, 1, 0, tzinfo=UTC),
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DELETE FROM audit_events
            WHERE id = :audit_id
              AND action = 'platform.superadmin_role_restored'
            """
        ).bindparams(audit_id=REPAIR_AUDIT_ID)
    )
