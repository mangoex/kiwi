"""seed cumulative profiles with persisted organization authority

Revision ID: 0035_cumulative_profiles_rbac
Revises: 0034_category_option_selection
Create Date: 2026-08-10 03:00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0035_cumulative_profiles_rbac"
down_revision: str | None = "0034_category_option_selection"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UTC = timezone.utc
ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
LEGACY_CAJERO_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000008"
ROLE_IDS = {
    "Cajero": "018f6f73-2d0a-74f0-8f1c-000000001001",
    "Cajero jefe": "018f6f73-2d0a-74f0-8f1c-000000001002",
    "Líder": "018f6f73-2d0a-74f0-8f1c-000000001003",
    "Supervisor": "018f6f73-2d0a-74f0-8f1c-000000001004",
    "Administrador": "018f6f73-2d0a-74f0-8f1c-000000001005",
    "Dueño": "018f6f73-2d0a-74f0-8f1c-000000001006",
}
PERMISSIONS = [
    ("018f6f73-2d0a-74f0-8f1c-000000001101", "cash.movement.withdraw", "Registrar retiro manual de efectivo."),
    ("018f6f73-2d0a-74f0-8f1c-000000001102", "cash.movement.deposit", "Registrar depósito de efectivo."),
    ("018f6f73-2d0a-74f0-8f1c-000000001103", "cash.movement.read", "Consultar libro de movimientos de caja."),
    ("018f6f73-2d0a-74f0-8f1c-000000001104", "cash.movement.compensate", "Compensar un movimiento de caja."),
    ("018f6f73-2d0a-74f0-8f1c-000000001105", "cash.concept.read", "Consultar conceptos efectivos de caja."),
    ("018f6f73-2d0a-74f0-8f1c-000000001106", "cash.concept.manage", "Versionar y archivar conceptos de caja."),
    ("018f6f73-2d0a-74f0-8f1c-000000001107", "cash.reconciliation.perform", "Realizar arqueo operativo de caja."),
    ("018f6f73-2d0a-74f0-8f1c-000000001108", "cash.user_cut.read", "Consultar cortes por usuario."),
    ("018f6f73-2d0a-74f0-8f1c-000000001109", "cash.user_cut.create", "Crear y finalizar corte por usuario."),
    ("018f6f73-2d0a-74f0-8f1c-000000001110", "cash.user_cut.reopen.request", "Solicitar reapertura de corte."),
    ("018f6f73-2d0a-74f0-8f1c-000000001111", "cash.user_cut.reopen.authorize", "Autorizar o compensar reapertura de corte."),
    ("018f6f73-2d0a-74f0-8f1c-000000001112", "orders.reopen.request", "Solicitar reapertura de pedido."),
    ("018f6f73-2d0a-74f0-8f1c-000000001113", "orders.reopen.authorize", "Autorizar reapertura de pedido."),
    ("018f6f73-2d0a-74f0-8f1c-000000001114", "reports.sales.read", "Consultar reportes de ventas."),
    ("018f6f73-2d0a-74f0-8f1c-000000001115", "reports.expenses.read", "Consultar reportes de gastos."),
    ("018f6f73-2d0a-74f0-8f1c-000000001116", "reports.ingredient_sales.read", "Consultar venta por insumos."),
    ("018f6f73-2d0a-74f0-8f1c-000000001117", "reports.waste.read", "Consultar reporte de merma."),
    ("018f6f73-2d0a-74f0-8f1c-000000001118", "recipes.manage", "Crear versiones de receta por sucursal."),
    ("018f6f73-2d0a-74f0-8f1c-000000001119", "access.organization.all_branches", "Alcance a todas las sucursales de la organización."),
]
PROFILE_CODES = {
    "Cajero": ["pos.operate", "orders.read", "orders.create", "payments.read", "payments.confirm", "cash.concept.read", "cash.movement.withdraw"],
    "Cajero jefe": ["cash.shift.read", "cash.shift.open", "cash.shift.close", "cash.movement.deposit", "cash.movement.read", "cash.reconciliation.perform", "orders.amend", "purchases.read", "purchases.manage", "inventory.waste", "orders.reopen.request"],
    "Líder": ["cash.user_cut.read", "cash.user_cut.create", "orders.cancel"],
    "Supervisor": ["recipes.manage", "inventory.read", "reports.ingredient_sales.read", "reports.waste.read"],
    "Administrador": ["reports.sales.read", "reports.expenses.read"],
}
MIGRATION_AUDIT_ID = "018f6f73-2d0a-74f0-8f1c-000000001199"


def _seed_preflight(bind: sa.Connection) -> None:
    permission_ids = [permission_id for permission_id, _, _ in PERMISSIONS]
    permission_codes = [code for _, code, _ in PERMISSIONS]
    permission_collision = bind.execute(
        sa.text("SELECT id, code FROM permissions WHERE id IN :ids OR code IN :codes").bindparams(
            sa.bindparam("ids", expanding=True),
            sa.bindparam("codes", expanding=True),
            ids=permission_ids,
            codes=permission_codes,
        )
    ).first()
    if permission_collision:
        raise RuntimeError("Cumulative profile seed collision: reserved permission identity exists")

    role_collision = bind.execute(
        sa.text(
            """
            SELECT id, organization_id, name, scope
            FROM roles
            WHERE id IN :role_ids
               OR (organization_id = :organization_id AND name IN :role_names)
            """
        ).bindparams(
            sa.bindparam("role_ids", expanding=True),
            sa.bindparam("role_names", expanding=True),
            role_ids=list(ROLE_IDS.values()),
            role_names=[*ROLE_IDS, "Cajero legacy"],
            organization_id=ORGANIZATION_ID,
        )
    ).mappings().all()
    for role in role_collision:
        if (
            role["id"] == LEGACY_CAJERO_ROLE_ID
            and role["organization_id"] == ORGANIZATION_ID
            and role["name"] == "Cajero"
        ):
            continue
        raise RuntimeError("Cumulative profile seed collision: reserved role identity exists")

    legacy_role = bind.execute(
        sa.text("SELECT organization_id, name FROM roles WHERE id = :role_id"),
        {"role_id": LEGACY_CAJERO_ROLE_ID},
    ).mappings().first()
    if legacy_role and (
        legacy_role["organization_id"] != ORGANIZATION_ID or legacy_role["name"] != "Cajero"
    ):
        raise RuntimeError("Cumulative profile seed collision: legacy Cajero identity differs")

    audit_collision = bind.execute(
        sa.text("SELECT id FROM audit_events WHERE id = :id"), {"id": MIGRATION_AUDIT_ID}
    ).first()
    if audit_collision:
        raise RuntimeError("Cumulative profile seed collision: reserved audit identity exists")


def _assign_permissions(role_id: str, codes: list[str]) -> None:
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT :role_id, id FROM permissions WHERE code IN :codes
        ON CONFLICT DO NOTHING
    """).bindparams(sa.bindparam("codes", expanding=True), role_id=role_id, codes=codes))


def upgrade() -> None:
    now = datetime(2026, 8, 10, 3, 0, tzinfo=UTC)
    bind = op.get_bind()
    _seed_preflight(bind)
    op.create_table(
        "role_authority_grants",
        sa.Column("role_id", sa.String(36), sa.ForeignKey("roles.id"), primary_key=True),
        sa.Column("authority_kind", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("authority_kind = 'organization_all_permissions'", name="ck_role_authority_grants_kind"),
    )
    op.create_table(
        "profile_transition_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("legacy_role_id", sa.String(36), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("target_role_id", sa.String(36), sa.ForeignKey("roles.id"), nullable=False),
        sa.Column("target_branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("mapped_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("role_snapshot", sa.JSON(), nullable=True),
        sa.Column("provenance", sa.String(160), nullable=True),
        sa.Column("create_idempotency_key", sa.String(128), nullable=True),
        sa.Column("apply_idempotency_key", sa.String(128), nullable=True),
        sa.Column("reverse_idempotency_key", sa.String(128), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'mapped', 'reversed')", name="ck_profile_transition_mappings_status"),
        sa.UniqueConstraint(
            "organization_id",
            "create_idempotency_key",
            name="uq_profile_transition_mappings_create_key",
        ),
    )
    op.create_index(
        "uq_profile_transition_mappings_open_target",
        "profile_transition_mappings",
        ["user_id", "target_role_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('pending', 'mapped')"),
        postgresql_where=sa.text("status IN ('pending', 'mapped')"),
    )
    legacy_name = bind.execute(sa.text("SELECT name FROM roles WHERE id = :role_id"), {"role_id": LEGACY_CAJERO_ROLE_ID}).scalar_one_or_none()
    if legacy_name == "Cajero":
        conflicting_legacy = bind.execute(sa.text("SELECT id FROM roles WHERE organization_id = :organization_id AND name = 'Cajero legacy'"), {"organization_id": ORGANIZATION_ID}).scalar_one_or_none()
        if conflicting_legacy:
            raise RuntimeError("Cannot preserve Cajero compatibility: legacy role name already exists")
        op.execute(sa.text("UPDATE roles SET name = 'Cajero legacy' WHERE id = :role_id").bindparams(role_id=LEGACY_CAJERO_ROLE_ID))
    for permission_id, code, description in PERMISSIONS:
        op.execute(sa.text("""
            INSERT INTO permissions (id, code, description, created_at)
            VALUES (:id, :code, :description, :created_at)
        """).bindparams(id=permission_id, code=code, description=description, created_at=now))
    for name, role_id in ROLE_IDS.items():
        scope = "organization" if name == "Dueño" else "branch"
        op.execute(sa.text("""
            INSERT INTO roles (id, organization_id, name, scope, created_at)
            VALUES (:id, :organization_id, :name, :scope, :created_at)
        """).bindparams(id=role_id, organization_id=ORGANIZATION_ID, name=name, scope=scope, created_at=now))
    inherited: list[str] = []
    for name in ("Cajero", "Cajero jefe", "Líder", "Supervisor", "Administrador"):
        inherited.extend(PROFILE_CODES.get(name, []))
        _assign_permissions(ROLE_IDS[name], inherited)
    _assign_permissions(ROLE_IDS["Dueño"], [row[1] for row in PERMISSIONS])
    existing_codes = bind.execute(sa.text("SELECT code FROM permissions")).scalars().all()
    _assign_permissions(ROLE_IDS["Dueño"], list(existing_codes))
    op.execute(sa.text("""
        INSERT INTO role_authority_grants (role_id, authority_kind, created_at)
        VALUES (:role_id, 'organization_all_permissions', :created_at)
    """).bindparams(role_id=ROLE_IDS["Dueño"], created_at=now))
    op.execute(sa.text("""
        INSERT INTO audit_events (id, organization_id, branch_id, actor_user_id, action, entity_type, entity_id, payload, correlation_id, created_at)
        VALUES (:id, :organization_id, :branch_id, NULL, 'rbac.cumulative_profiles_seeded', 'role_profile', :entity_id, :payload, NULL, :created_at)
    """).bindparams(
        sa.bindparam("payload", type_=sa.JSON()),
        id=MIGRATION_AUDIT_ID,
        organization_id=ORGANIZATION_ID,
        branch_id=BRANCH_ID,
        entity_id=ROLE_IDS["Dueño"],
        payload={"revision": revision, "automatic_owner_assignments": 0},
        created_at=now,
    ))


def downgrade() -> None:
    bind = op.get_bind()
    role_ids = list(ROLE_IDS.values())
    permission_ids = [permission_id for permission_id, _, _ in PERMISSIONS]
    mapped = bind.execute(sa.text("SELECT COUNT(*) FROM profile_transition_mappings")).scalar_one()
    assigned = bind.execute(sa.text("SELECT COUNT(*) FROM user_roles WHERE role_id IN :role_ids").bindparams(sa.bindparam("role_ids", expanding=True), role_ids=role_ids)).scalar_one()
    externally_granted = bind.execute(sa.text("""
        SELECT COUNT(*) FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        WHERE p.id IN :permission_ids AND rp.role_id NOT IN :role_ids
    """).bindparams(sa.bindparam("permission_ids", expanding=True), sa.bindparam("role_ids", expanding=True), permission_ids=permission_ids, role_ids=role_ids)).scalar_one()
    if mapped or assigned or externally_granted:
        raise RuntimeError("Safe downgrade blocked: cumulative profile data must be reversed before schema downgrade")
    op.execute(sa.text("DELETE FROM audit_events WHERE id = :id").bindparams(id=MIGRATION_AUDIT_ID))
    op.execute(sa.text("DELETE FROM role_authority_grants WHERE role_id IN :role_ids").bindparams(sa.bindparam("role_ids", expanding=True), role_ids=role_ids))
    op.execute(sa.text("DELETE FROM role_permissions WHERE role_id IN :role_ids").bindparams(sa.bindparam("role_ids", expanding=True), role_ids=role_ids))
    op.execute(sa.text("DELETE FROM roles WHERE id IN :role_ids").bindparams(sa.bindparam("role_ids", expanding=True), role_ids=role_ids))
    op.execute(sa.text("DELETE FROM permissions WHERE id IN :permission_ids").bindparams(sa.bindparam("permission_ids", expanding=True), permission_ids=permission_ids))
    op.execute(sa.text("UPDATE roles SET name = 'Cajero' WHERE id = :role_id AND name = 'Cajero legacy'").bindparams(role_id=LEGACY_CAJERO_ROLE_ID))
    op.drop_table("profile_transition_mappings")
    op.drop_table("role_authority_grants")
