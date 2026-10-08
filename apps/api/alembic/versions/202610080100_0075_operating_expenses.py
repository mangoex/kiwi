"""EXP-001: independent expense documents and explicit canonical-role grants."""

from datetime import datetime, timezone
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from alembic import op

from restaurant_os.expense_schema_v1 import tables

revision = "0075_operating_expenses"
down_revision = "0074_dual_physical_counts"
branch_labels = depends_on = None

PERMISSIONS = {
    "expense.concept.read": {"Supervisor", "Administrador", "Dueño"},
    "expense.concept.manage": {"Dueño"},
    "expenses.read": {"Supervisor", "Administrador", "Dueño"},
    "expenses.manage": {"Supervisor", "Administrador", "Dueño"},
    "expenses.cancel": {"Dueño"},
}
CANONICAL_ROLES = {
    "Supervisor": "018f6f73-2d0a-74f0-8f1c-000000001004",
    "Administrador": "018f6f73-2d0a-74f0-8f1c-000000001005",
    "Dueño": "018f6f73-2d0a-74f0-8f1c-000000001006",
}
ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"


def _preflight(bind: sa.Connection) -> None:
    for name, identifier in CANONICAL_ROLES.items():
        role = (
            bind.execute(
                sa.text("SELECT organization_id, name, scope FROM roles WHERE id = :id"),
                {"id": identifier},
            )
            .mappings()
            .first()
        )
        expected_scope = "organization" if name == "Dueño" else "branch"
        if not role or (role["organization_id"], role["name"], role["scope"]) != (
            ORGANIZATION_ID,
            name,
            expected_scope,
        ):
            raise RuntimeError("0075 preflight failed: canonical expense role differs")
    for code in PERMISSIONS:
        identifier = str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + code))
        if bind.execute(
            sa.text("SELECT 1 FROM permissions WHERE id = :id OR code = :code"),
            {"id": identifier, "code": code},
        ).first():
            raise RuntimeError("0075 preflight failed: expense permission identity exists")


def upgrade() -> None:
    bind = op.get_bind()
    _preflight(bind)
    metadata = sa.MetaData()
    for parent in ("organizations", "branches", "users", "cash_movements"):
        sa.Table(parent, metadata, sa.Column("id", sa.String(36), primary_key=True))
    for table in tables(metadata):
        table.create(bind)
    roles = bind.execute(sa.text("SELECT id, name FROM roles")).mappings().all()
    for code, allowed in PERMISSIONS.items():
        identifier = str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + code))
        bind.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, created_at) VALUES (:id, :code, :description, :now)"
            ),
            {
                "id": identifier,
                "code": code,
                "description": "Gastos operativos: " + code,
                "now": datetime.now(timezone.utc),
            },
        )
        for role in roles:
            if role["name"] in allowed and role["id"] == CANONICAL_ROLES[role["name"]]:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (:role, :permission)"
                    ),
                    {"role": role["id"], "permission": identifier},
                )


def downgrade() -> None:
    bind = op.get_bind()
    for code, allowed in PERMISSIONS.items():
        identifier = str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + code))
        grants = bind.execute(
            sa.text("SELECT role_id FROM role_permissions WHERE permission_id = :id"),
            {"id": identifier},
        ).scalars()
        if any(role_id not in {CANONICAL_ROLES[name] for name in allowed} for role_id in grants):
            raise RuntimeError("0075 downgrade blocked: expense permission has external grants")
    for name in ("expense_concepts", "expense_documents", "expense_commands"):
        if bind.execute(sa.text("SELECT 1 FROM " + name + " LIMIT 1")).first():
            raise RuntimeError("Expense history exists; downgrade would destroy audited records")
    if bind.execute(
        sa.text(
            "SELECT 1 FROM cash_movements WHERE source_type IN ('EXPENSE','EXPENSE_CANCELLATION') LIMIT 1"
        )
    ).first():
        raise RuntimeError("Expense cash movements exist; downgrade is not permitted")
    for code in PERMISSIONS:
        identifier = str(uuid5(NAMESPACE_URL, "restaurantos:permission:" + code))
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id = :id"),
            {"id": identifier},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id = :id AND code = :code"),
            {"id": identifier, "code": code},
        )
    for name in ("expense_commands", "expense_documents", "expense_concepts"):
        op.drop_table(name)
