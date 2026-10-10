"""Enable governed POS branch selection for mobile operational profiles.

Revision ID: 0077_pos_branch_selection
Revises: 0076_operating_expenses
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

revision = "0077_pos_branch_selection"
down_revision = "0076_operating_expenses"
branch_labels = depends_on = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
PERMISSION_CODE = "pos.branch.select"
PERMISSION_ID = str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + PERMISSION_CODE))
AUDIT_ID = str(uuid5(NAMESPACE_URL, "restaurantos:migration:0077_pos_branch_selection"))
ROLES = {
    "Administrador corporativo": ("018f6f73-2d0a-74f0-8f1c-000000000005", "organization"),
    "Supervisor de sucursal": ("018f6f73-2d0a-74f0-8f1c-000000000016", "branch"),
    "Supervisor": ("018f6f73-2d0a-74f0-8f1c-000000001004", "branch"),
    "Administrador": ("018f6f73-2d0a-74f0-8f1c-000000001005", "branch"),
    "Dueño": ("018f6f73-2d0a-74f0-8f1c-000000001006", "organization"),
}
WORKSPACE_ROLE_NAMES = {"Supervisor de sucursal", "Supervisor", "Administrador"}


def _preflight(bind: sa.Connection) -> None:
    for name, (identifier, scope) in ROLES.items():
        row = bind.execute(
            sa.text("SELECT organization_id, name, scope FROM roles WHERE id = :id"),
            {"id": identifier},
        ).mappings().first()
        if not row or (row["organization_id"], row["name"], row["scope"]) != (
            ORGANIZATION_ID,
            name,
            scope,
        ):
            raise RuntimeError("0077 preflight failed: mobile role differs")
    if bind.execute(
        sa.text("SELECT 1 FROM permissions WHERE id = :id OR code = :code"),
        {"id": PERMISSION_ID, "code": PERMISSION_CODE},
    ).first():
        raise RuntimeError("0077 preflight failed: branch selection permission exists")
    if bind.execute(sa.text("SELECT 1 FROM audit_events WHERE id = :id"), {"id": AUDIT_ID}).first():
        raise RuntimeError("0077 preflight failed: audit identity exists")


def _replace_authority_constraint(expression: str) -> None:
    with op.batch_alter_table("role_authority_grants") as batch:
        batch.drop_constraint("ck_role_authority_grants_kind", type_="check")
        batch.create_check_constraint("ck_role_authority_grants_kind", expression)


def upgrade() -> None:
    bind = op.get_bind()
    _preflight(bind)
    now = datetime.now(timezone.utc)
    with op.batch_alter_table("users") as batch:
        batch.add_column(sa.Column("authorization_version", sa.Integer(), nullable=False, server_default="1"))
        batch.create_check_constraint("ck_users_authorization_version", "authorization_version >= 1")
    _replace_authority_constraint(
        "authority_kind IN ('organization_all_permissions', 'organization_branch_workspaces')"
    )
    op.create_table(
        "branch_selection_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("source_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("target_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("authorization_version", sa.Integer(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "actor_user_id", "idempotency_key",
            name="uq_branch_selection_commands_actor_key",
        ),
        sa.CheckConstraint("trim(idempotency_key) != ''", name="ck_branch_selection_commands_key"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_branch_selection_commands_hash"),
        sa.CheckConstraint("authorization_version >= 1", name="ck_branch_selection_commands_version"),
    )
    bind.execute(
        sa.text(
            "INSERT INTO permissions (id, code, description, created_at) "
            "VALUES (:id, :code, :description, :created_at)"
        ),
        {
            "id": PERMISSION_ID,
            "code": PERMISSION_CODE,
            "description": "Seleccionar una sucursal autorizada para operar el POS.",
            "created_at": now,
        },
    )
    for name, (role_id, _scope) in ROLES.items():
        bind.execute(
            sa.text(
                "INSERT INTO role_permissions (role_id, permission_id) "
                "VALUES (:role_id, :permission_id)"
            ),
            {"role_id": role_id, "permission_id": PERMISSION_ID},
        )
        if name in WORKSPACE_ROLE_NAMES:
            bind.execute(
                sa.text(
                    "INSERT INTO role_authority_grants (role_id, authority_kind, created_at) "
                    "VALUES (:role_id, 'organization_branch_workspaces', :created_at)"
                ),
                {"role_id": role_id, "created_at": now},
            )
    bind.execute(
        sa.text(
            "INSERT INTO audit_events "
            "(id, organization_id, branch_id, actor_user_id, action, entity_type, entity_id, payload, correlation_id, created_at) "
            "VALUES (:id, :organization_id, NULL, NULL, 'rbac.pos_branch_selection_enabled', "
            "'permission', :entity_id, :payload, NULL, :created_at)"
        ).bindparams(sa.bindparam("payload", type_=sa.JSON())),
        {
            "id": AUDIT_ID,
            "organization_id": ORGANIZATION_ID,
            "entity_id": PERMISSION_ID,
            "payload": {"revision": revision, "workspace_grants": sorted(WORKSPACE_ROLE_NAMES)},
            "created_at": now,
        },
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM branch_selection_commands LIMIT 1")).first():
        raise RuntimeError("0077 downgrade blocked: branch selection history exists")
    external = bind.execute(
        sa.text(
            "SELECT role_id FROM role_permissions WHERE permission_id = :permission_id "
            "AND role_id NOT IN :role_ids LIMIT 1"
        ).bindparams(sa.bindparam("role_ids", expanding=True)),
        {"permission_id": PERMISSION_ID, "role_ids": [value[0] for value in ROLES.values()]},
    ).first()
    if external:
        raise RuntimeError("0077 downgrade blocked: branch selection has external grants")
    bind.execute(sa.text("DELETE FROM audit_events WHERE id = :id"), {"id": AUDIT_ID})
    for name in WORKSPACE_ROLE_NAMES:
        bind.execute(
            sa.text(
                "DELETE FROM role_authority_grants WHERE role_id = :role_id "
                "AND authority_kind = 'organization_branch_workspaces'"
            ),
            {"role_id": ROLES[name][0]},
        )
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_id = :permission_id"),
        {"permission_id": PERMISSION_ID},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE id = :id AND code = :code"),
        {"id": PERMISSION_ID, "code": PERMISSION_CODE},
    )
    op.drop_table("branch_selection_commands")
    _replace_authority_constraint("authority_kind = 'organization_all_permissions'")
    with op.batch_alter_table("users") as batch:
        batch.drop_constraint("ck_users_authorization_version", type_="check")
        batch.drop_column("authorization_version")
