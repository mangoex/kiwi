from __future__ import annotations

"""superadmin auth

Revision ID: 202607081700
Revises: 202607081430
Create Date: 2026-07-08 17:00:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone
UTC = timezone.utc

UTC = UTC

import sqlalchemy as sa
from alembic import op

revision: str = "202607081700"
down_revision: str | None = "202607081430"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
SUPERADMIN_EMAIL = "mangoex@gmail.com"
SUPERADMIN_DISPLAY_NAME = "Miguel Gonzalez"
SUPERADMIN_PASSWORD_SALT = "IdEBHHQsDzzwFutRvynLbQ"
SUPERADMIN_PASSWORD_HASH = "m41Sej4_KitaH9mHD0zauM9SZ-MGftHufm0D_Ga350s"


def upgrade() -> None:
    now = datetime(2026, 7, 8, 17, 0, tzinfo=UTC)
    bind = op.get_bind()
    op.create_table(
        "user_credentials",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("password_hash", sa.String(length=96), nullable=False),
        sa.Column("password_salt", sa.String(length=32), nullable=False),
        sa.Column("password_algorithm", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )

    existing_superadmin_id = bind.execute(
        sa.text("SELECT id FROM users WHERE email = :email").bindparams(email=SUPERADMIN_EMAIL)
    ).scalar_one_or_none()
    target_user_id = existing_superadmin_id or ADMIN_USER_ID

    if existing_superadmin_id:
        op.execute(
            sa.text(
                """
                UPDATE users
                SET display_name = :display_name,
                    status = 'active',
                    updated_at = :updated_at
                WHERE id = :user_id
                """
            ).bindparams(
                display_name=SUPERADMIN_DISPLAY_NAME,
                updated_at=now,
                user_id=target_user_id,
            )
        )
    else:
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
                user_id=target_user_id,
            )
        )

    op.execute(
        sa.text(
            """
            INSERT INTO user_roles (user_id, role_id, branch_id)
            VALUES (:user_id, :role_id, NULL)
            ON CONFLICT (user_id, role_id) DO NOTHING
            """
        ).bindparams(user_id=target_user_id, role_id=ADMIN_ROLE_ID)
    )
    op.execute(
        sa.text(
            """
            INSERT INTO user_credentials (
                user_id,
                password_hash,
                password_salt,
                password_algorithm,
                updated_at
            )
            VALUES (
                :user_id,
                :password_hash,
                :password_salt,
                'pbkdf2_sha256',
                :updated_at
            )
            ON CONFLICT (user_id) DO UPDATE
            SET password_hash = EXCLUDED.password_hash,
                password_salt = EXCLUDED.password_salt,
                password_algorithm = EXCLUDED.password_algorithm,
                updated_at = EXCLUDED.updated_at
            """
        ).bindparams(
            user_id=target_user_id,
            password_hash=SUPERADMIN_PASSWORD_HASH,
            password_salt=SUPERADMIN_PASSWORD_SALT,
            updated_at=now,
        )
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
