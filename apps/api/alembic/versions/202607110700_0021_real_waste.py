"""real waste documents, reasons and immutable compensation

Revision ID: 0021_real_waste
Revises: 0020_product_modifiers
Create Date: 2026-07-11 07:00:00
"""

from __future__ import annotations
from collections.abc import Sequence
from datetime import datetime, timezone
import sqlalchemy as sa
from alembic import op

revision: str = "0021_real_waste"
down_revision: str | None = "0020_product_modifiers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
UTC = timezone.utc
REASONS = [
    ("018f6f73-2d0a-74f0-8f1c-000000000701", "EXPIRATION", "Caducidad", "quality"),
    ("018f6f73-2d0a-74f0-8f1c-000000000702", "SPOILAGE", "Descomposición", "quality"),
    ("018f6f73-2d0a-74f0-8f1c-000000000703", "PREPARATION_ERROR", "Error de preparación", "production"),
    ("018f6f73-2d0a-74f0-8f1c-000000000704", "SPILL", "Derrame", "operation"),
    ("018f6f73-2d0a-74f0-8f1c-000000000705", "BURNED", "Producto quemado", "production"),
    ("018f6f73-2d0a-74f0-8f1c-000000000706", "PACKAGING_DAMAGE", "Daño de empaque", "operation"),
    ("018f6f73-2d0a-74f0-8f1c-000000000707", "NON_REUSABLE_SURPLUS", "Sobrante no reutilizable", "production"),
    ("018f6f73-2d0a-74f0-8f1c-000000000708", "THEFT_OR_SHORTAGE", "Robo o faltante", "security"),
    ("018f6f73-2d0a-74f0-8f1c-000000000709", "OTHER_AUTHORIZED", "Otro motivo autorizado", "other"),
]


def upgrade() -> None:
    op.create_table(
        "waste_reasons",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("classification", sa.String(40), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_waste_reason_organization_code"),
    )
    op.create_table(
        "waste_records",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("warehouse_id", sa.String(36), sa.ForeignKey("warehouses.id"), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_items.id"), nullable=False),
        sa.Column("unit_id", sa.String(36), sa.ForeignKey("inventory_units.id"), nullable=False),
        sa.Column("reason_id", sa.String(36), sa.ForeignKey("waste_reasons.id"), nullable=False),
        sa.Column("stage", sa.String(48), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("unit_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("total_cost", sa.Numeric(18, 6), nullable=False, server_default="0"),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("notes", sa.String(600), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="draft"),
        sa.Column("created_by", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("confirmed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("reversed_by", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True),
        sa.Column("reversal_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id"), nullable=True),
        sa.Column("confirmation_idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("reversal_idempotency_key", sa.String(180), nullable=True, unique=True),
        sa.Column("reversal_reason", sa.String(400), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
    )
    now = datetime(2026, 7, 11, 7, 0, tzinfo=UTC)
    reason_table = sa.table(
        "waste_reasons",
        sa.column("id"), sa.column("organization_id"), sa.column("code"), sa.column("name"),
        sa.column("classification"), sa.column("display_order"), sa.column("status"),
        sa.column("created_at"), sa.column("updated_at"),
    )
    op.bulk_insert(reason_table, [
        {"id": reason_id, "organization_id": ORGANIZATION_ID, "code": code, "name": name,
         "classification": classification, "display_order": index * 10, "status": "active",
         "created_at": now, "updated_at": now}
        for index, (reason_id, code, name, classification) in enumerate(REASONS, start=1)
    ])


def downgrade() -> None:
    op.drop_table("waste_records")
    op.drop_table("waste_reasons")
