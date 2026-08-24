from __future__ import annotations

# ruff: noqa: E501
"""seed and sync 6 canonical roles and their permissions

Revision ID: 0047_canonical_roles_and_permissions
Revises: 0046_supplier_extended_fields
Create Date: 2026-08-24 15:00:00.000000

"""
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0047_canonical_roles_and_permissions"
down_revision: str | None = "0046_supplier_extended_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"

CANONICAL_ROLES = [
    {
        "name": "Dueño",
        "scope": "organization",
        "permissions": [
            "admin.manage", "catalog.manage", "catalog.branch.manage", "recipes.manage",
            "purchases.manage", "purchases.read", "inventory.read", "inventory.adjust",
            "inventory.waste", "inventory.transfer.send", "inventory.transfer.receive",
            "inventory.count", "orders.read", "orders.create", "orders.amend", "orders.cancel",
            "orders.fulfill", "orders.reopen.request", "orders.reopen.authorize",
            "cash.shift.read", "cash.shift.open", "cash.shift.close", "cash.concept.manage",
            "cash.concept.read", "cash.movement.read", "cash.movement.withdraw",
            "cash.movement.deposit", "cash.movement.compensate", "cash.reconciliation.perform",
            "cash.user_cut.read", "cash.user_cut.create", "cash.user_cut.reopen.request",
            "cash.user_cut.reopen.authorize", "dashboard.read", "reports.sales.read",
            "reports.expenses.read", "reports.ingredient_sales.read", "reports.waste.read",
            "branch.admin.access", "branch.staff.read", "pos.operate", "cash.withdraw",
            "production.manage", "access.organization.all_branches", "audit.read",
            "print.jobs.read", "print.jobs.retry", "payments.read", "payments.confirm",
        ],
    },
    {
        "name": "Administrador",
        "scope": "organization",
        "permissions": [
            "admin.manage", "catalog.manage", "catalog.branch.manage", "recipes.manage",
            "purchases.manage", "purchases.read", "inventory.read", "inventory.adjust",
            "inventory.waste", "inventory.transfer.send", "inventory.transfer.receive",
            "inventory.count", "orders.read", "orders.create", "orders.amend", "orders.cancel",
            "orders.fulfill", "orders.reopen.request", "orders.reopen.authorize",
            "cash.shift.read", "cash.shift.open", "cash.shift.close", "cash.concept.manage",
            "cash.concept.read", "cash.movement.read", "cash.movement.withdraw",
            "cash.movement.deposit", "cash.movement.compensate", "cash.reconciliation.perform",
            "cash.user_cut.read", "cash.user_cut.create", "cash.user_cut.reopen.request",
            "cash.user_cut.reopen.authorize", "dashboard.read", "reports.sales.read",
            "reports.expenses.read", "reports.ingredient_sales.read", "reports.waste.read",
            "branch.admin.access", "branch.staff.read", "pos.operate", "cash.withdraw",
            "production.manage", "audit.read", "print.jobs.read", "print.jobs.retry",
            "payments.read", "payments.confirm",
        ],
    },
    {
        "name": "Supervisor",
        "scope": "organization",
        "permissions": [
            "catalog.manage", "catalog.branch.manage", "recipes.manage", "purchases.manage",
            "purchases.read", "inventory.read", "inventory.waste", "inventory.transfer.send",
            "inventory.transfer.receive", "inventory.count", "orders.read", "orders.create",
            "orders.amend", "orders.cancel", "orders.fulfill", "orders.reopen.request",
            "orders.reopen.authorize", "cash.shift.read", "cash.shift.open", "cash.shift.close",
            "cash.movement.read", "cash.movement.withdraw", "cash.movement.deposit",
            "dashboard.read", "reports.sales.read", "reports.ingredient_sales.read",
            "reports.waste.read", "branch.admin.access", "branch.staff.read", "pos.operate",
            "cash.withdraw", "production.manage", "print.jobs.read", "print.jobs.retry",
            "payments.read", "payments.confirm",
        ],
    },
    {
        "name": "Líder",
        "scope": "branch",
        "permissions": [
            "purchases.read", "purchases.manage", "inventory.read", "inventory.waste",
            "inventory.transfer.receive", "inventory.count", "orders.read", "orders.create",
            "orders.amend", "orders.cancel", "orders.fulfill", "orders.reopen.request",
            "cash.shift.read", "cash.shift.open", "cash.shift.close", "cash.movement.read",
            "cash.movement.withdraw", "cash.movement.deposit", "cash.user_cut.read",
            "cash.user_cut.create", "cash.user_cut.reopen.request", "branch.admin.access",
            "branch.staff.read", "pos.operate", "cash.withdraw", "production.manage",
            "payments.read", "payments.confirm",
        ],
    },
    {
        "name": "Cajero Jefe",
        "scope": "branch",
        "permissions": [
            "purchases.read", "purchases.manage", "inventory.read", "inventory.waste",
            "inventory.transfer.receive", "orders.read", "orders.create", "orders.amend",
            "orders.fulfill", "payments.read", "payments.confirm", "cash.shift.read",
            "cash.shift.open", "cash.shift.close", "cash.movement.read", "cash.movement.withdraw",
            "cash.movement.deposit", "cash.concept.read", "branch.admin.access",
            "branch.staff.read", "pos.operate",
        ],
    },
    {
        "name": "Cajero",
        "scope": "branch",
        "permissions": [
            "pos.operate", "orders.read", "orders.create", "orders.amend",
            "payments.read", "payments.confirm", "cash.shift.read", "cash.shift.open",
            "cash.shift.close",
        ],
    },
]


def upgrade() -> None:
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # 1. Fetch existing permissions
    perm_rows = conn.execute(sa.text("SELECT id, code FROM permissions")).fetchall()
    perm_map = {row[1]: row[0] for row in perm_rows}

    # 2. For each canonical role, ensure it exists and has permissions
    for role_def in CANONICAL_ROLES:
        role_name = role_def["name"]
        role_scope = role_def["scope"]
        wanted_perms = role_def["permissions"]

        existing_role = conn.execute(
            sa.text("SELECT id FROM roles WHERE LOWER(name) = LOWER(:name) LIMIT 1"),
            {"name": role_name},
        ).fetchone()

        if existing_role:
            role_id = existing_role[0]
        else:
            role_id = str(uuid.uuid4())
            conn.execute(
                sa.text(
                    "INSERT INTO roles (id, organization_id, name, scope, created_at) "
                    "VALUES (:id, :org_id, :name, :scope, :created_at)"
                ),
                {
                    "id": role_id,
                    "org_id": ORGANIZATION_ID,
                    "name": role_name,
                    "scope": role_scope,
                    "created_at": now,
                },
            )

        # Ensure all wanted permissions are in role_permissions
        for perm_code in wanted_perms:
            perm_id = perm_map.get(perm_code)
            if not perm_id:
                continue
            has_perm = conn.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions WHERE role_id = :role_id AND permission_id = :perm_id"
                ),
                {"role_id": role_id, "perm_id": perm_id},
            ).fetchone()
            if not has_perm:
                conn.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) VALUES (:role_id, :perm_id)"
                    ),
                    {"role_id": role_id, "perm_id": perm_id},
                )


def downgrade() -> None:
    pass
