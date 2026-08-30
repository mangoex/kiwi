"""Repair 0047 canonical-profile grants without inferring authority.

Revision ID: 0056_repair_0047_canonical_roles
Revises: 0055_admin_ai_proposals
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0056_repair_0047_canonical_roles"
down_revision: str | None = "0055_admin_ai_proposals"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
AUDIT_ID = "018f6f73-2d0a-74f0-8f1c-000000001198"
ROLE_IDS = {
    "Cajero": "018f6f73-2d0a-74f0-8f1c-000000001001",
    "Cajero jefe": "018f6f73-2d0a-74f0-8f1c-000000001002",
    "Líder": "018f6f73-2d0a-74f0-8f1c-000000001003",
    "Supervisor": "018f6f73-2d0a-74f0-8f1c-000000001004",
    "Administrador": "018f6f73-2d0a-74f0-8f1c-000000001005",
    "Dueño": "018f6f73-2d0a-74f0-8f1c-000000001006",
}
PROFILE_ADDITIONS = {
    "Cajero": {
        "pos.operate",
        "orders.read",
        "orders.create",
        "payments.read",
        "payments.confirm",
        "cash.concept.read",
        "cash.movement.withdraw",
    },
    "Cajero jefe": {
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.movement.deposit",
        "cash.movement.read",
        "cash.reconciliation.perform",
        "orders.amend",
        "purchases.read",
        "purchases.manage",
        "inventory.waste",
        "orders.reopen.request",
    },
    "Líder": {"cash.user_cut.read", "cash.user_cut.create", "orders.cancel"},
    "Supervisor": {
        "recipes.manage",
        "inventory.read",
        "reports.ingredient_sales.read",
        "reports.waste.read",
    },
    "Administrador": {"reports.sales.read", "reports.expenses.read"},
}
GRANTS_0047 = {
    "Cajero": {
        "pos.operate",
        "orders.read",
        "orders.create",
        "orders.amend",
        "payments.read",
        "payments.confirm",
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
    },
    "Cajero jefe": {
        "purchases.read",
        "purchases.manage",
        "inventory.read",
        "inventory.waste",
        "inventory.transfer.receive",
        "orders.read",
        "orders.create",
        "orders.amend",
        "orders.fulfill",
        "payments.read",
        "payments.confirm",
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.movement.read",
        "cash.movement.withdraw",
        "cash.movement.deposit",
        "cash.concept.read",
        "branch.admin.access",
        "branch.staff.read",
        "pos.operate",
    },
    "Líder": {
        "purchases.read",
        "purchases.manage",
        "inventory.read",
        "inventory.waste",
        "inventory.transfer.receive",
        "inventory.count",
        "orders.read",
        "orders.create",
        "orders.amend",
        "orders.cancel",
        "orders.fulfill",
        "orders.reopen.request",
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.movement.read",
        "cash.movement.withdraw",
        "cash.movement.deposit",
        "cash.user_cut.read",
        "cash.user_cut.create",
        "cash.user_cut.reopen.request",
        "branch.admin.access",
        "branch.staff.read",
        "pos.operate",
        "cash.withdraw",
        "production.manage",
        "payments.read",
        "payments.confirm",
    },
    "Supervisor": {
        "catalog.manage",
        "catalog.branch.manage",
        "recipes.manage",
        "purchases.manage",
        "purchases.read",
        "inventory.read",
        "inventory.waste",
        "inventory.transfer.send",
        "inventory.transfer.receive",
        "inventory.count",
        "orders.read",
        "orders.create",
        "orders.amend",
        "orders.cancel",
        "orders.fulfill",
        "orders.reopen.request",
        "orders.reopen.authorize",
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.movement.read",
        "cash.movement.withdraw",
        "cash.movement.deposit",
        "dashboard.read",
        "reports.sales.read",
        "reports.ingredient_sales.read",
        "reports.waste.read",
        "branch.admin.access",
        "branch.staff.read",
        "pos.operate",
        "cash.withdraw",
        "production.manage",
        "print.jobs.read",
        "print.jobs.retry",
        "payments.read",
        "payments.confirm",
    },
    "Administrador": {
        "admin.manage",
        "catalog.manage",
        "catalog.branch.manage",
        "recipes.manage",
        "purchases.manage",
        "purchases.read",
        "inventory.read",
        "inventory.adjust",
        "inventory.waste",
        "inventory.transfer.send",
        "inventory.transfer.receive",
        "inventory.count",
        "orders.read",
        "orders.create",
        "orders.amend",
        "orders.cancel",
        "orders.fulfill",
        "orders.reopen.request",
        "orders.reopen.authorize",
        "cash.shift.read",
        "cash.shift.open",
        "cash.shift.close",
        "cash.concept.manage",
        "cash.concept.read",
        "cash.movement.read",
        "cash.movement.withdraw",
        "cash.movement.deposit",
        "cash.movement.compensate",
        "cash.reconciliation.perform",
        "cash.user_cut.read",
        "cash.user_cut.create",
        "cash.user_cut.reopen.request",
        "cash.user_cut.reopen.authorize",
        "dashboard.read",
        "reports.sales.read",
        "reports.expenses.read",
        "reports.ingredient_sales.read",
        "reports.waste.read",
        "branch.admin.access",
        "branch.staff.read",
        "pos.operate",
        "cash.withdraw",
        "production.manage",
        "audit.read",
        "print.jobs.read",
        "print.jobs.retry",
        "payments.read",
        "payments.confirm",
    },
}


def _expected_profiles() -> dict[str, set[str]]:
    effective: set[str] = set()
    result: dict[str, set[str]] = {}
    for name in ("Cajero", "Cajero jefe", "Líder", "Supervisor", "Administrador"):
        effective |= PROFILE_ADDITIONS[name]
        result[name] = set(effective)
    return result


def _permission_codes(bind: sa.Connection, role_id: str) -> set[str]:
    return set(
        bind.execute(
            sa.text(
                """
                SELECT permissions.code
                FROM role_permissions
                JOIN permissions ON permissions.id = role_permissions.permission_id
                WHERE role_permissions.role_id = :role_id
                """
            ),
            {"role_id": role_id},
        ).scalars()
    )


def _preflight(bind: sa.Connection) -> dict[str, set[str]]:
    expected_profiles = _expected_profiles()
    rows = bind.execute(
        sa.text("SELECT id, organization_id, name, scope FROM roles WHERE id IN :role_ids").bindparams(
            sa.bindparam("role_ids", expanding=True), role_ids=list(ROLE_IDS.values())
        )
    ).mappings().all()
    roles_by_id = {str(row["id"]): row for row in rows}
    if len(roles_by_id) != len(ROLE_IDS):
        raise RuntimeError("0047 repair preflight failed: reserved canonical role is missing")

    for name, role_id in ROLE_IDS.items():
        role = roles_by_id[role_id]
        expected_scope = "organization" if name == "Dueño" else "branch"
        if (
            role["organization_id"] != ORGANIZATION_ID
            or role["name"] != name
            or role["scope"] != expected_scope
        ):
            raise RuntimeError("0047 repair preflight failed: canonical role identity differs")

    cross_organization = bind.execute(
        sa.text(
            "SELECT id FROM roles WHERE organization_id <> :organization_id "
            "AND LOWER(name) IN :role_names LIMIT 1"
        ).bindparams(
            sa.bindparam("role_names", expanding=True),
            organization_id=ORGANIZATION_ID,
            role_names=[name.lower() for name in ROLE_IDS],
        )
    ).first()
    if cross_organization:
        raise RuntimeError("0047 repair preflight failed: cross-organization role requires audit")

    required_codes = set().union(*expected_profiles.values(), *GRANTS_0047.values())
    existing_codes = set(
        bind.execute(
            sa.text("SELECT code FROM permissions WHERE code IN :codes").bindparams(
                sa.bindparam("codes", expanding=True), codes=sorted(required_codes)
            )
        ).scalars()
    )
    if existing_codes != required_codes:
        raise RuntimeError("0047 repair preflight failed: required permission is missing")

    for name, expected_after in expected_profiles.items():
        expected_before = expected_after | GRANTS_0047[name]
        if _permission_codes(bind, ROLE_IDS[name]) != expected_before:
            raise RuntimeError("0047 repair preflight failed: profile grants require manual audit")

    owner_grant = bind.execute(
        sa.text(
            "SELECT authority_kind FROM role_authority_grants WHERE role_id = :role_id"
        ),
        {"role_id": ROLE_IDS["Dueño"]},
    ).scalar_one_or_none()
    if owner_grant != "organization_all_permissions":
        raise RuntimeError("0047 repair preflight failed: owner authority differs")
    if bind.execute(sa.text("SELECT id FROM audit_events WHERE id = :id"), {"id": AUDIT_ID}).first():
        raise RuntimeError("0047 repair preflight failed: audit identity exists")
    return expected_profiles


def upgrade() -> None:
    bind = op.get_bind()
    expected_profiles = _preflight(bind)
    removed_grants = 0
    for name, expected_codes in expected_profiles.items():
        excess_codes = sorted(GRANTS_0047[name] - expected_codes)
        removed_grants += len(excess_codes)
        bind.execute(
            sa.text(
                """
                DELETE FROM role_permissions
                WHERE role_id = :role_id
                  AND permission_id IN (
                    SELECT id FROM permissions WHERE code IN :codes
                  )
                """
            ).bindparams(sa.bindparam("codes", expanding=True)),
            {"role_id": ROLE_IDS[name], "codes": excess_codes},
        )

    bind.execute(
        sa.text(
            """
            INSERT INTO audit_events (
                id, organization_id, branch_id, actor_user_id, action, entity_type,
                entity_id, payload, correlation_id, created_at
            ) VALUES (
                :id, :organization_id, :branch_id, NULL, :action, :entity_type,
                :entity_id, :payload, NULL, :created_at
            )
            """
        ).bindparams(sa.bindparam("payload", type_=sa.JSON())),
        {
            "id": AUDIT_ID,
            "organization_id": ORGANIZATION_ID,
            "branch_id": BRANCH_ID,
            "action": "rbac.canonical_profiles_repaired",
            "entity_type": "role_profile",
            "entity_id": ROLE_IDS["Dueño"],
            "payload": {"revision": revision, "removed_grants": removed_grants},
            "created_at": datetime(2026, 8, 30, 1, 0, tzinfo=timezone.utc),
        },
    )


def downgrade() -> None:
    raise RuntimeError(
        "0056 is forward-only: restoring over-granted RBAC permissions is not a safe rollback"
    )
