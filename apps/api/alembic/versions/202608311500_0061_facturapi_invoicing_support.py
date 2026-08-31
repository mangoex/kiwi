"""Add Facturapi and CFDI 4.0 invoicing tables.

Revision ID: 0061_facturapi_invoicing_support
Revises: 0060_update_orders_channel_check_constraint
"""

from __future__ import annotations

from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "0061_facturapi_invoicing_support"
down_revision: str | None = "0060_update_orders_channel_check_constraint"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "facturapi_config",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("environment", sa.String(24), nullable=False, server_default="sandbox"),
        sa.Column("api_key", sa.String(256), nullable=True),
        sa.Column("organization_legal_name", sa.String(200), nullable=True),
        sa.Column("organization_rfc", sa.String(13), nullable=True),
        sa.Column("organization_tax_system", sa.String(10), nullable=True),
        sa.Column("organization_zip", sa.String(10), nullable=True),
        sa.Column("default_product_sat_key", sa.String(16), nullable=False, server_default="90101501"),
        sa.Column("default_unit_sat_key", sa.String(16), nullable=False, server_default="E48"),
        sa.Column("series", sa.String(10), nullable=False, server_default="F"),
        sa.Column("enable_self_invoicing", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("self_invoicing_domain", sa.String(120), nullable=True, server_default="demo"),
        sa.Column("self_invoicing_days_valid", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("print_qr_on_ticket", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_facturapi_config_org"),
    )

    op.create_table(
        "cfdi_invoices",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("facturapi_invoice_id", sa.String(128), nullable=True, unique=True),
        sa.Column("facturapi_receipt_id", sa.String(128), nullable=True),
        sa.Column("uuid_sat", sa.String(64), nullable=True),
        sa.Column("folio_number", sa.String(64), nullable=False),
        sa.Column("rfc_emisor", sa.String(13), nullable=False),
        sa.Column("rfc_receptor", sa.String(13), nullable=False),
        sa.Column("nombre_receptor", sa.String(200), nullable=False),
        sa.Column("codigo_postal_receptor", sa.String(10), nullable=False),
        sa.Column("regimen_fiscal_receptor", sa.String(10), nullable=False),
        sa.Column("uso_cfdi", sa.String(10), nullable=False, server_default="G03"),
        sa.Column("forma_pago_sat", sa.String(10), nullable=False, server_default="01"),
        sa.Column("metodo_pago_sat", sa.String(10), nullable=False, server_default="PUE"),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"),
        sa.Column("status", sa.String(32), nullable=False, server_default="issued"),
        sa.Column("verification_url", sa.String(500), nullable=True),
        sa.Column("self_invoice_url", sa.String(500), nullable=True),
        sa.Column("pdf_url", sa.String(500), nullable=True),
        sa.Column("xml_url", sa.String(500), nullable=True),
        sa.Column("cancellation_reason", sa.String(10), nullable=True),
        sa.Column("raw_sat_response", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("cfdi_invoices")
    op.drop_table("facturapi_config")
