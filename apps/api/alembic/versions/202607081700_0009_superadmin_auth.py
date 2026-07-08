"""superadmin auth

Revision ID: 202607081700
Revises: 202607081430
Create Date: 2026-07-08 17:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "202607081700"
down_revision: str | None = "202607081430"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
SUPERADMIN_EMAIL = "mangoex@gmail.com"
SUPERADMIN_DISPLAY_NAME = "Miguel Gonzalez"
SUPERADMIN_PASSWORD_SALT = "IdEBHHQsDzzwFutRvynLbQ"
SUPERADMIN_PASSWORD_HASH = "m41Sej4_KitaH9mHD0zauM9SZ-MGftHufm0D_Ga350s"


def upgrade() -> None:
    now = datetime(2026, 7, 8, 17, 0, tzinfo=UTC)
    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("password_hash", sa.String(length=96), nullable=False),
        sa.Column("password_salt", sa.String(length=32), nullable=False),
        sa.Column("password_algorithm", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.execute(
        sa.text(
            """
            UPDATE users
            SET email = :email,
                display_name = :display_name,
                status = 'active',
                updated_at = :updated_at
            WHERE id = :user_id
            """
        ).bindparams(
            email=SUPERADMIN_EMAIL,
            display_name=SUPERADMIN_DISPLAY_NAME,
            updated_at=now,
            user_id=ADMIN_USER_ID,
        )
    )
    op.bulk_insert(
        sa.table(
            "user_credentials",
            sa.column("user_id"),
            sa.column("password_hash"),
            sa.column("password_salt"),
            sa.column("password_algorithm"),
            sa.column("updated_at"),
        ),
        [
            {
                "user_id": ADMIN_USER_ID,
                "password_hash": SUPERADMIN_PASSWORD_HASH,
                "password_salt": SUPERADMIN_PASSWORD_SALT,
                "password_algorithm": "pbkdf2_sha256",
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    now = datetime(2026, 7, 8, 17, 0, tzinfo=UTC)
    op.execute(
        sa.text(
            """
            UPDATE users
            SET email = 'admin@kiwi.local',
                display_name = 'Administrador Kiwi',
                status = 'invited',
                updated_at = :updated_at
            WHERE id = :user_id
            """
        ).bindparams(updated_at=now, user_id=ADMIN_USER_ID)
    )
    op.drop_table("user_credentials")
