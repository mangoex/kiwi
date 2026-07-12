"""business units and operational roles

Revision ID: 0015_business_units_operational_roles
Revises: 0014_legacy_caja_role_permissions
Create Date: 2026-07-11 01:00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0015_business_units_operational_roles"
down_revision: str | None = "0014_legacy_caja_role_permissions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UTC = timezone.utc
ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
LEGAL_ENTITY_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
BUSINESS_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000015"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"
SUPERVISOR_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000016"
TRANSFER_RECEIVER_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000017"
AUDITOR_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000018"

PERMISSIONS = [
    ("018f6f73-2d0a-74f0-8f1c-000000000614", "purchases.read", "Consultar compras de la sucursal."),
    ("018f6f73-2d0a-74f0-8f1c-000000000615", "purchases.manage", "Registrar y confirmar compras directas."),
    ("018f6f73-2d0a-74f0-8f1c-000000000616", "cash.withdraw", "Registrar retiros autorizados de efectivo."),
    ("018f6f73-2d0a-74f0-8f1c-000000000617", "inventory.read", "Consultar existencias y kardex."),
    ("018f6f73-2d0a-74f0-8f1c-000000000618", "inventory.waste", "Registrar mermas reales autorizadas."),
    ("018f6f73-2d0a-74f0-8f1c-000000000619", "inventory.transfer.send", "Iniciar y confirmar traspasos enviados."),
    ("018f6f73-2d0a-74f0-8f1c-000000000620", "inventory.transfer.receive", "Confirmar recepciones y diferencias de traspaso."),
    ("018f6f73-2d0a-74f0-8f1c-000000000621", "inventory.count", "Iniciar y capturar conteos fisicos."),
    ("018f6f73-2d0a-74f0-8f1c-000000000622", "audit.read", "Consultar auditoria sin modificar operaciones."),
]

SUPERVISOR_CODES = [
    "pos.operate", "cash.shift.read", "cash.shift.open", "cash.shift.close", "cash.withdraw",
    "orders.read", "orders.create", "orders.cancel", "payments.read", "payments.confirm",
    "dashboard.read", "inventory.read", "inventory.waste", "inventory.transfer.send",
    "inventory.count", "purchases.read", "purchases.manage",
]
RECEIVER_CODES = ["inventory.read", "inventory.transfer.receive"]
AUDITOR_CODES = [
    "dashboard.read", "orders.read", "payments.read", "cash.shift.read", "inventory.read",
    "purchases.read", "audit.read",
]


def upgrade() -> None:
    now = datetime(2026, 7, 11, 1, 0, tzinfo=UTC)
    op.create_table(
        "business_units",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("legal_entity_id", sa.String(36), sa.ForeignKey("legal_entities.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("unit_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_business_units_organization_code"),
    )
    with op.batch_alter_table("branches") as batch:
        batch.add_column(sa.Column("business_unit_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_branches_business_unit_id", "business_units", ["business_unit_id"], ["id"], ondelete="RESTRICT"
        )

    op.execute(sa.text("""
        INSERT INTO business_units
            (id, organization_id, legal_entity_id, name, code, unit_type, status, created_at, updated_at)
        VALUES
            (:id, :organization_id, :legal_entity_id, 'Operaciones Kiwi', 'KIWI', 'restaurant', 'active', :now, :now)
    """).bindparams(id=BUSINESS_UNIT_ID, organization_id=ORGANIZATION_ID, legal_entity_id=LEGAL_ENTITY_ID, now=now))
    op.execute(sa.text("""
        UPDATE branches SET business_unit_id = :business_unit_id
        WHERE organization_id = :organization_id AND business_unit_id IS NULL
    """).bindparams(business_unit_id=BUSINESS_UNIT_ID, organization_id=ORGANIZATION_ID))
    with op.batch_alter_table("branches") as batch:
        batch.alter_column("business_unit_id", existing_type=sa.String(36), nullable=False)

    for permission_id, code, description in PERMISSIONS:
        op.execute(sa.text("""
            INSERT INTO permissions (id, code, description, created_at)
            VALUES (:id, :code, :description, :created_at)
            ON CONFLICT (code) DO NOTHING
        """).bindparams(id=permission_id, code=code, description=description, created_at=now))

    roles = [
        (SUPERVISOR_ROLE_ID, "Supervisor de sucursal", "branch"),
        (TRANSFER_RECEIVER_ROLE_ID, "Receptor de traspaso", "branch"),
        (AUDITOR_ROLE_ID, "Auditor", "organization"),
    ]
    for role_id, name, scope in roles:
        op.execute(sa.text("""
            INSERT INTO roles (id, organization_id, name, scope, created_at)
            VALUES (:id, :organization_id, :name, :scope, :created_at)
            ON CONFLICT (id) DO NOTHING
        """).bindparams(id=role_id, organization_id=ORGANIZATION_ID, name=name, scope=scope, created_at=now))

    _assign_permissions(ADMIN_ROLE_ID, [code for _, code, _ in PERMISSIONS])
    _assign_permissions(SUPERVISOR_ROLE_ID, SUPERVISOR_CODES)
    _assign_permissions(TRANSFER_RECEIVER_ROLE_ID, RECEIVER_CODES)
    _assign_permissions(AUDITOR_ROLE_ID, AUDITOR_CODES)


def _assign_permissions(role_id: str, codes: list[str]) -> None:
    op.execute(sa.text("""
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT :role_id, permissions.id FROM permissions
        WHERE permissions.code IN :codes
        ON CONFLICT DO NOTHING
    """).bindparams(sa.bindparam("codes", expanding=True), role_id=role_id, codes=codes))


def downgrade() -> None:
    role_ids = [SUPERVISOR_ROLE_ID, TRANSFER_RECEIVER_ROLE_ID, AUDITOR_ROLE_ID]
    permission_codes = [code for _, code, _ in PERMISSIONS]
    op.execute(sa.text("DELETE FROM role_permissions WHERE role_id IN :role_ids").bindparams(
        sa.bindparam("role_ids", expanding=True), role_ids=role_ids
    ))
    op.execute(sa.text("""
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code IN :codes)
    """).bindparams(sa.bindparam("codes", expanding=True), codes=permission_codes))
    op.execute(sa.text("DELETE FROM roles WHERE id IN :role_ids").bindparams(
        sa.bindparam("role_ids", expanding=True), role_ids=role_ids
    ))
    op.execute(sa.text("DELETE FROM permissions WHERE code IN :codes").bindparams(
        sa.bindparam("codes", expanding=True), codes=permission_codes
    ))
    with op.batch_alter_table("branches") as batch:
        batch.drop_constraint("fk_branches_business_unit_id", type_="foreignkey")
        batch.drop_column("business_unit_id")
    op.drop_table("business_units")
