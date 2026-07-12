"""customer directory and order snapshots

Revision ID: 0016_customer_directory_snapshots
Revises: 0015_business_units_operational_roles
Create Date: 2026-07-11 02:00:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0016_customer_directory_snapshots"
down_revision: str | None = "0015_business_units_operational_roles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "customer_phones",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("captured_number", sa.String(32), nullable=False),
        sa.Column("normalized_number", sa.String(20), nullable=False),
        sa.Column("phone_type", sa.String(24), nullable=False, server_default="mobile"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("whatsapp_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_customer_phones_normalized", "customer_phones", ["normalized_number"])
    bind = op.get_bind()
    now = datetime.now(timezone.utc)
    legacy_phones = bind.execute(
        sa.text("SELECT id, phone FROM customers WHERE phone IS NOT NULL AND phone <> ''")
    ).mappings()
    for row in legacy_phones:
        captured = str(row["phone"])
        bind.execute(
            sa.text("""
                INSERT INTO customer_phones
                    (id, customer_id, captured_number, normalized_number, phone_type,
                     is_primary, whatsapp_enabled, is_verified, status, created_at, updated_at)
                VALUES
                    (:id, :customer_id, :captured, :normalized, 'mobile',
                     :is_primary, :whatsapp, :verified, 'active', :created_at, :updated_at)
            """),
            {
                "id": str(uuid4()),
                "customer_id": row["id"],
                "captured": captured,
                "normalized": _normalize_phone(captured),
                "is_primary": True,
                "whatsapp": False,
                "verified": False,
                "created_at": now,
                "updated_at": now,
            },
        )

    with op.batch_alter_table("customers") as batch:
        batch.drop_column("phone")
        batch.add_column(sa.Column("customer_type", sa.String(24), nullable=False, server_default="person"))
        batch.add_column(sa.Column("customer_segment", sa.String(48), nullable=True))
        batch.add_column(sa.Column("notes", sa.String(600), nullable=True))
        batch.add_column(sa.Column("status", sa.String(32), nullable=False, server_default="active"))
        batch.add_column(sa.Column("origin_branch_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key("fk_customers_origin_branch_id", "branches", ["origin_branch_id"], ["id"])
    op.execute(sa.text("UPDATE customers SET updated_at = created_at WHERE updated_at IS NULL"))
    with op.batch_alter_table("customers") as batch:
        batch.alter_column("updated_at", existing_type=sa.DateTime(timezone=True), nullable=False)
    op.create_table(
        "customer_addresses",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("alias", sa.String(60), nullable=False),
        sa.Column("street", sa.String(180), nullable=False),
        sa.Column("exterior_number", sa.String(32), nullable=False),
        sa.Column("interior_number", sa.String(32), nullable=True),
        sa.Column("neighborhood", sa.String(120), nullable=False),
        sa.Column("postal_code", sa.String(12), nullable=False),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("municipality", sa.String(100), nullable=False),
        sa.Column("state", sa.String(100), nullable=False),
        sa.Column("country", sa.String(2), nullable=False, server_default="MX"),
        sa.Column("cross_streets", sa.String(240), nullable=True),
        sa.Column("references", sa.String(600), nullable=True),
        sa.Column("delivery_instructions", sa.String(600), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("delivery_zone_id", sa.String(36), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "customer_tax_profiles",
        sa.Column("customer_id", sa.String(36), sa.ForeignKey("customers.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("legal_name", sa.String(180), nullable=False),
        sa.Column("tax_id", sa.String(16), nullable=False),
        sa.Column("tax_regime", sa.String(12), nullable=False),
        sa.Column("fiscal_postal_code", sa.String(12), nullable=False),
        sa.Column("cfdi_use", sa.String(12), nullable=True),
        sa.Column("billing_email", sa.String(180), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("customer_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("customer_snapshot", sa.JSON(), nullable=True))
        batch.add_column(sa.Column("delivery_address_snapshot", sa.JSON(), nullable=True))
        batch.create_foreign_key("fk_orders_customer_id", "customers", ["customer_id"], ["id"])


def downgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("fk_orders_customer_id", type_="foreignkey")
        batch.drop_column("delivery_address_snapshot")
        batch.drop_column("customer_snapshot")
        batch.drop_column("customer_id")
    with op.batch_alter_table("customers") as batch:
        batch.drop_constraint("fk_customers_origin_branch_id", type_="foreignkey")
        batch.add_column(sa.Column("phone", sa.String(32), nullable=True))
        batch.drop_column("updated_at")
        batch.drop_column("origin_branch_id")
        batch.drop_column("status")
        batch.drop_column("notes")
        batch.drop_column("customer_segment")
        batch.drop_column("customer_type")
    op.execute(sa.text("""
        UPDATE customers
        SET phone = (
            SELECT captured_number FROM customer_phones
            WHERE customer_phones.customer_id = customers.id
            ORDER BY is_primary DESC, created_at ASC
            LIMIT 1
        )
    """))
    op.drop_table("customer_tax_profiles")
    op.drop_table("customer_addresses")
    op.drop_index("ix_customer_phones_normalized", table_name="customer_phones")
    op.drop_table("customer_phones")


def _normalize_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 10:
        return f"+52{digits}"
    if len(digits) == 12 and digits.startswith("52"):
        return f"+{digits}"
    return f"+{digits}" if digits else value
