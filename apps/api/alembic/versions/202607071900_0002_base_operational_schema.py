# ruff: noqa: E501
"""bootstrap platform

Revision ID: 202607071900
Revises: 202607071730
Create Date: 2026-07-07 19:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "202607071900"
down_revision: str | None = "202607071730"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
LEGAL_ENTITY_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
WAREHOUSE_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
AUDIT_EVENT_ID = "018f6f73-2d0a-74f0-8f1c-000000000007"


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "legal_entities",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=180), nullable=False),
        sa.Column("tax_id", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "branches",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "legal_entity_id",
            sa.String(length=36),
            sa.ForeignKey("legal_entities.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column(
            "timezone", sa.String(length=64), nullable=False, server_default="America/Chihuahua"
        ),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_branches_organization_code"),
    )
    op.create_table(
        "warehouses",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
            unique=True,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "roles",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("scope", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_roles_organization_name"),
    )
    op.create_table(
        "permissions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False, unique=True),
        sa.Column("description", sa.String(length=240), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("email", sa.String(length=180), nullable=False, unique=True),
        sa.Column("display_name", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="invited"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.String(length=36), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column(
            "permission_id", sa.String(length=36), sa.ForeignKey("permissions.id"), primary_key=True
        ),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("role_id", sa.String(length=36), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("branch_id", sa.String(length=36), sa.ForeignKey("branches.id"), nullable=True),
    )
    op.create_table(
        "audit_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.String(length=36), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("actor_user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(length=120), nullable=False),
        sa.Column("entity_type", sa.String(length=120), nullable=False),
        sa.Column("entity_id", sa.String(length=36), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("correlation_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    _seed_initial_data()


def downgrade() -> None:
    op.drop_table("audit_events")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_table("users")
    op.drop_table("permissions")
    op.drop_table("roles")
    op.drop_table("warehouses")
    op.drop_table("branches")
    op.drop_table("legal_entities")
    op.drop_table("organizations")


def _seed_initial_data() -> None:
    now = datetime(2026, 7, 7, 17, 30, tzinfo=UTC)
    organizations = sa.table(
        "organizations",
        *[sa.column(name) for name in ["id", "name", "status", "created_at", "updated_at"]],
    )
    legal_entities = sa.table(
        "legal_entities",
        *[
            sa.column(name)
            for name in [
                "id",
                "organization_id",
                "name",
                "tax_id",
                "status",
                "created_at",
                "updated_at",
            ]
        ],
    )
    branches = sa.table(
        "branches",
        *[
            sa.column(name)
            for name in [
                "id",
                "organization_id",
                "legal_entity_id",
                "name",
                "code",
                "timezone",
                "status",
                "created_at",
                "updated_at",
            ]
        ],
    )
    warehouses = sa.table(
        "warehouses",
        *[
            sa.column(name)
            for name in [
                "id",
                "organization_id",
                "branch_id",
                "name",
                "status",
                "created_at",
                "updated_at",
            ]
        ],
    )
    roles = sa.table(
        "roles",
        *[sa.column(name) for name in ["id", "organization_id", "name", "scope", "created_at"]],
    )
    users = sa.table(
        "users",
        *[
            sa.column(name)
            for name in [
                "id",
                "organization_id",
                "email",
                "display_name",
                "status",
                "created_at",
                "updated_at",
            ]
        ],
    )
    user_roles = sa.table(
        "user_roles", sa.column("user_id"), sa.column("role_id"), sa.column("branch_id")
    )
    audit_events = sa.table(
        "audit_events",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("branch_id"),
        sa.column("actor_user_id"),
        sa.column("action"),
        sa.column("entity_type"),
        sa.column("entity_id"),
        sa.column("payload", sa.JSON()),
        sa.column("correlation_id"),
        sa.column("created_at"),
    )

    op.bulk_insert(
        organizations,
        [
            {
                "id": ORGANIZATION_ID,
                "name": "Kiwi Restaurante",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        legal_entities,
        [
            {
                "id": LEGAL_ENTITY_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Kiwi Restaurante - Razon Social Pendiente",
                "tax_id": None,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        branches,
        [
            {
                "id": BRANCH_ID,
                "organization_id": ORGANIZATION_ID,
                "legal_entity_id": LEGAL_ENTITY_ID,
                "name": "Sucursal Piloto",
                "code": "PILOTO",
                "timezone": "America/Chihuahua",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        warehouses,
        [
            {
                "id": WAREHOUSE_ID,
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "name": "Almacen Sucursal Piloto",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        roles,
        [
            {
                "id": ADMIN_ROLE_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Administrador corporativo",
                "scope": "organization",
                "created_at": now,
            }
        ],
    )
    op.bulk_insert(
        users,
        [
            {
                "id": ADMIN_USER_ID,
                "organization_id": ORGANIZATION_ID,
                "email": "admin@kiwi.local",
                "display_name": "Administrador Kiwi",
                "status": "invited",
                "created_at": now,
                "updated_at": now,
            }
        ],
    )
    op.bulk_insert(
        user_roles, [{"user_id": ADMIN_USER_ID, "role_id": ADMIN_ROLE_ID, "branch_id": None}]
    )
    op.bulk_insert(
        audit_events,
        [
            {
                "id": AUDIT_EVENT_ID,
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "actor_user_id": ADMIN_USER_ID,
                "action": "platform.bootstrap_seeded",
                "entity_type": "organization",
                "entity_id": ORGANIZATION_ID,
                "payload": {"source": "alembic", "phase": "0.2"},
                "correlation_id": None,
                "created_at": now,
            }
        ],
    )
