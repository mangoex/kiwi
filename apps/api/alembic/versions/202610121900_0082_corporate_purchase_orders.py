"""Corporate purchase orders with distributed branch receipts.

Revision ID: 0082_corporate_purchase_orders
Revises: 0081_agent_cash_cut_compensation_index
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0082_corporate_purchase_orders"
down_revision: str | None = "0081_agent_cash_cut_compensation_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PERMISSIONS = {
    "purchases.corporate.read": (
        "018f6f73-2d0a-74f0-8f1c-000000000982",
        "Consultar órdenes corporativas y sus recepciones.",
    ),
    "purchases.corporate.manage": (
        "018f6f73-2d0a-74f0-8f1c-000000000983",
        "Crear, aprobar, recibir y cancelar órdenes corporativas.",
    ),
}


def upgrade() -> None:
    with op.batch_alter_table("supplier_price_history") as batch:
        batch.add_column(sa.Column("organization_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("branch_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("warehouse_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("source_type", sa.String(48), nullable=True))
        batch.add_column(sa.Column("source_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("source_line_id", sa.String(36), nullable=True))
        batch.create_foreign_key(
            "fk_supplier_price_history_organization",
            "organizations",
            ["organization_id"],
            ["id"],
        )
        batch.create_foreign_key(
            "fk_supplier_price_history_branch", "branches", ["branch_id"], ["id"]
        )
        batch.create_foreign_key(
            "fk_supplier_price_history_warehouse", "warehouses", ["warehouse_id"], ["id"]
        )
    op.create_index(
        "ix_supplier_price_history_branch_effective",
        "supplier_price_history",
        ["organization_id", "branch_id", "presentation_id", "effective_at"],
    )

    op.create_table(
        "corporate_purchase_orders",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column(
            "legal_entity_id", sa.String(36), sa.ForeignKey("legal_entities.id"), nullable=False
        ),
        sa.Column("supplier_id", sa.String(36), sa.ForeignKey("suppliers.id"), nullable=False),
        sa.Column("folio", sa.String(80), nullable=False),
        sa.Column("order_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
        sa.Column("subtotal", sa.Numeric(18, 6), nullable=False),
        sa.Column("discount_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("tax_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("total", sa.Numeric(18, 6), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("approved_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancelled_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("cancellation_reason", sa.String(400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "legal_entity_id",
            "supplier_id",
            "folio",
            name="uq_corporate_purchase_order_identity",
        ),
        sa.CheckConstraint(
            "status IN ('DRAFT', 'APPROVED', 'PARTIALLY_RECEIVED', 'RECEIVED', 'CANCELLED')",
            name="ck_corporate_purchase_orders_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_corporate_purchase_orders_version"),
    )
    op.create_table(
        "corporate_purchase_order_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id", sa.String(36), sa.ForeignKey("corporate_purchase_orders.id"), nullable=False
        ),
        sa.Column(
            "presentation_id",
            sa.String(36),
            sa.ForeignKey("purchase_presentations.id"),
            nullable=False,
        ),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("presentation_snapshot", sa.JSON(), nullable=False),
        sa.Column("presentation_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("base_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 6), nullable=False),
        sa.Column("discount", sa.Numeric(18, 6), nullable=False),
        sa.Column("tax", sa.Numeric(18, 6), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("inventory_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column("cost_per_base_unit", sa.Numeric(18, 6), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "corporate_purchase_allocations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_line_id",
            sa.String(36),
            sa.ForeignKey("corporate_purchase_order_lines.id"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("presentation_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("base_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "received_presentation_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"
        ),
        sa.Column("received_base_quantity", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "order_line_id", "branch_id", "warehouse_id", name="uq_corporate_purchase_allocation"
        ),
        sa.CheckConstraint("presentation_quantity > 0", name="ck_corporate_allocation_quantity"),
        sa.CheckConstraint(
            "received_presentation_quantity >= 0 AND received_presentation_quantity <= presentation_quantity",
            name="ck_corporate_allocation_received",
        ),
    )
    op.create_table(
        "corporate_purchase_receipts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "order_id", sa.String(36), sa.ForeignKey("corporate_purchase_orders.id"), nullable=False
        ),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "corporate_purchase_receipt_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "receipt_id",
            sa.String(36),
            sa.ForeignKey("corporate_purchase_receipts.id"),
            nullable=False,
        ),
        sa.Column(
            "allocation_id",
            sa.String(36),
            sa.ForeignKey("corporate_purchase_allocations.id"),
            nullable=False,
        ),
        sa.Column("presentation_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("base_quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("inventory_cost", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "inventory_movement_id",
            sa.String(36),
            sa.ForeignKey("inventory_movements.id"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("receipt_id", "allocation_id", name="uq_corporate_receipt_allocation"),
    )
    op.create_table(
        "corporate_purchase_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("command_type", sa.String(24), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column(
            "order_id", sa.String(36), sa.ForeignKey("corporate_purchase_orders.id"), nullable=True
        ),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_corporate_purchase_command_org_key"
        ),
        sa.CheckConstraint(
            "command_type IN ('create', 'approve', 'receive', 'cancel')",
            name="ck_corporate_purchase_commands_type",
        ),
    )
    op.create_index(
        "ix_corporate_purchase_orders_org_status_updated",
        "corporate_purchase_orders",
        ["organization_id", "status", "updated_at"],
    )
    op.create_index(
        "ix_corporate_purchase_receipts_order_created",
        "corporate_purchase_receipts",
        ["order_id", "created_at"],
    )

    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    for code, (permission_id, description) in PERMISSIONS.items():
        if (
            bind.execute(
                sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}
            ).scalar_one_or_none()
            is None
        ):
            bind.execute(
                sa.text(
                    "INSERT INTO permissions (id, code, description, created_at) "
                    "VALUES (:id, :code, :description, :created_at)"
                ),
                {"id": permission_id, "code": code, "description": description, "created_at": now},
            )
    role_ids = [
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT id FROM roles WHERE scope = 'organization' AND lower(name) IN "
                "('dueño', 'dueno', 'administrador corporativo')"
            )
        )
    ]
    for role_id in role_ids:
        for code in PERMISSIONS:
            permission_id = bind.execute(
                sa.text("SELECT id FROM permissions WHERE code = :code"), {"code": code}
            ).scalar_one()
            if (
                bind.execute(
                    sa.text(
                        "SELECT 1 FROM role_permissions WHERE role_id = :role_id "
                        "AND permission_id = :permission_id"
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                ).first()
                is None
            ):
                bind.execute(
                    sa.text(
                        "INSERT INTO role_permissions (role_id, permission_id) "
                        "VALUES (:role_id, :permission_id)"
                    ),
                    {"role_id": role_id, "permission_id": permission_id},
                )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "corporate_purchase_commands",
        "corporate_purchase_receipt_lines",
        "corporate_purchase_receipts",
        "corporate_purchase_allocations",
        "corporate_purchase_order_lines",
        "corporate_purchase_orders",
    ):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Cannot downgrade 0082 while corporate purchase history exists")
    permission_ids = [
        str(row[0])
        for row in bind.execute(
            sa.text(
                "SELECT id FROM permissions WHERE code IN "
                "('purchases.corporate.read', 'purchases.corporate.manage')"
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
    op.drop_index(
        "ix_corporate_purchase_receipts_order_created", table_name="corporate_purchase_receipts"
    )
    op.drop_index(
        "ix_corporate_purchase_orders_org_status_updated", table_name="corporate_purchase_orders"
    )
    op.drop_table("corporate_purchase_commands")
    op.drop_table("corporate_purchase_receipt_lines")
    op.drop_table("corporate_purchase_receipts")
    op.drop_table("corporate_purchase_allocations")
    op.drop_table("corporate_purchase_order_lines")
    op.drop_table("corporate_purchase_orders")
    op.drop_index("ix_supplier_price_history_branch_effective", table_name="supplier_price_history")
    with op.batch_alter_table("supplier_price_history") as batch:
        batch.drop_constraint("fk_supplier_price_history_warehouse", type_="foreignkey")
        batch.drop_constraint("fk_supplier_price_history_branch", type_="foreignkey")
        batch.drop_constraint("fk_supplier_price_history_organization", type_="foreignkey")
        for column in (
            "source_line_id",
            "source_id",
            "source_type",
            "warehouse_id",
            "branch_id",
            "organization_id",
        ):
            batch.drop_column(column)
