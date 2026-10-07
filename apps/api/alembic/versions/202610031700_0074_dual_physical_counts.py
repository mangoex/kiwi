"""Dual-role physical counts with presentation snapshots.

Revision ID: 0074_dual_physical_counts
Revises: 0073_pos_catalog_appearance
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import sqlalchemy as sa
from alembic import op

revision: str = "0074_dual_physical_counts"
down_revision: str | None = "0073_pos_catalog_appearance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "inventory.count.capture": (
        "018f6f73-2d0a-74f0-8f1c-000000000974",
        "Abrir, capturar y enviar conteos físicos ciegos.",
    ),
    "inventory.count.review": (
        "018f6f73-2d0a-74f0-8f1c-000000000975",
        "Consultar fotografía, costos y diferencias de conteos físicos.",
    ),
    "inventory.count.approve": (
        "018f6f73-2d0a-74f0-8f1c-000000000976",
        "Aprobar ajustes, cerrar y cancelar conteos físicos.",
    ),
}


def upgrade() -> None:
    bind = op.get_bind()
    duplicate_active = bind.execute(
        sa.text(
            "SELECT branch_id FROM physical_count_sessions "
            "WHERE status IN ('counting', 'submitted', 'approved') "
            "GROUP BY branch_id HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate_active:
        raise RuntimeError(
            "Cannot enforce one active physical count while duplicate branch sessions exist"
        )
    op.create_index(
        "uq_physical_count_active_branch",
        "physical_count_sessions",
        ["branch_id"],
        unique=True,
        postgresql_where=sa.text("status IN ('counting', 'submitted', 'approved')"),
        sqlite_where=sa.text("status IN ('counting', 'submitted', 'approved')"),
    )
    op.add_column(
        "physical_count_sessions",
        sa.Column("scope_definition", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.add_column(
        "physical_count_lines",
        sa.Column("capture_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "physical_count_line_entries",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "line_id",
            sa.String(36),
            sa.ForeignKey("physical_count_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "presentation_id",
            sa.String(36),
            sa.ForeignKey("purchase_presentations.id"),
            nullable=True,
        ),
        sa.Column("presentation_code_snapshot", sa.String(64), nullable=True),
        sa.Column("presentation_name_snapshot", sa.String(180), nullable=True),
        sa.Column("commercial_unit_code_snapshot", sa.String(24), nullable=True),
        sa.Column("base_unit_yield_snapshot", sa.Numeric(18, 6), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("converted_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("captured_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint("line_id", "sort_order", name="uq_physical_count_entry_order"),
    )

    now = datetime.now(timezone.utc)
    for code, (permission_id, description) in PERMISSIONS.items():
        exists = bind.execute(
            sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}
        ).scalar_one_or_none()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, description, created_at) "
                    "VALUES (:id, :code, :description, :created_at)"
                ),
                {
                    "id": permission_id,
                    "code": code,
                    "description": description,
                    "created_at": now,
                },
            )

    legacy_roles = {
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT rp.role_id FROM role_permissions rp "
                "JOIN permissions p ON p.id = rp.permission_id "
                "WHERE p.code = 'inventory.count'"
            )
        )
    }
    cashier_roles = {
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT id FROM roles "
                "WHERE lower(name) IN ('cajero', 'caja', 'cajero jefe')"
            )
        )
    }
    administrative_roles = {
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT id FROM roles WHERE lower(name) IN "
                "('líder', 'lider', 'supervisor', 'supervisor de sucursal', "
                "'administrador', 'administrador corporativo', 'dueño', 'dueno')"
            )
        )
    }
    grants = {
        "inventory.count.capture": legacy_roles | cashier_roles | administrative_roles,
        "inventory.count.review": legacy_roles | administrative_roles,
        "inventory.count.approve": legacy_roles | administrative_roles,
    }
    for code, role_ids in grants.items():
        permission_id = bind.execute(
            sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}
        ).scalar_one()
        for role_id in sorted(role_ids):
            exists = bind.execute(
                sa.text(
                    "SELECT 1 FROM role_permissions "
                    "WHERE role_id = :role_id AND permission_id = :permission_id"
                ),
                {"role_id": role_id, "permission_id": permission_id},
            ).first()
            if not exists:
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :permission_id)"
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        bind.execute(sa.text("LOCK TABLE physical_count_line_entries IN ACCESS EXCLUSIVE MODE"))
        bind.execute(sa.text("LOCK TABLE physical_count_lines IN ACCESS EXCLUSIVE MODE"))
        bind.execute(sa.text("LOCK TABLE physical_count_sessions IN ACCESS EXCLUSIVE MODE"))
    has_entries = bind.execute(
        sa.text("SELECT 1 FROM physical_count_line_entries LIMIT 1")
    ).first()
    has_scoped_sessions = bind.execute(
        sa.text(
            "SELECT 1 FROM physical_count_sessions "
            "WHERE scope_definition IS NOT NULL "
            "AND CAST(scope_definition AS TEXT) NOT IN ('{}', 'null') LIMIT 1"
        )
    ).first()
    if has_entries or has_scoped_sessions:
        raise RuntimeError(
            "Cannot downgrade 0074 while presentation captures or frozen scopes exist"
        )

    permission_ids = [
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT id FROM permissions WHERE code IN "
                "('inventory.count.capture', 'inventory.count.review', 'inventory.count.approve')"
            )
        )
    ]
    if permission_ids:
        bind.execute(
            sa.text("DELETE FROM role_permissions WHERE permission_id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": permission_ids},
        )
        bind.execute(
            sa.text("DELETE FROM permissions WHERE id IN :ids").bindparams(
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": permission_ids},
        )
    op.drop_table("physical_count_line_entries")
    op.drop_column("physical_count_lines", "capture_version")
    op.drop_column("physical_count_sessions", "scope_definition")
    op.drop_index("uq_physical_count_active_branch", table_name="physical_count_sessions")
