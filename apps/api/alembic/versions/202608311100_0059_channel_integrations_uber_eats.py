"""Add channel integrations, store mappings, webhook logs, and Uber Eats support.

Revision ID: 0059_channel_integrations_uber_eats
Revises: 0058_verify_0049_la_primavera_seed
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import sqlalchemy as sa
from alembic import op

revision: str = "0059_channel_integrations_uber_eats"
down_revision: str | None = "0058_verify_0049_la_primavera_seed"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "channel_integrations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("environment", sa.String(24), nullable=False, server_default="sandbox"),
        sa.Column("client_id", sa.String(128), nullable=True),
        sa.Column("client_secret", sa.String(256), nullable=True),
        sa.Column("webhook_secret", sa.String(256), nullable=True),
        sa.Column("auto_accept", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("default_prep_time_minutes", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "provider", name="uq_channel_integrations_org_provider"),
    )

    op.create_table(
        "channel_store_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_store_id", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "provider", "external_store_id", name="uq_channel_store_mappings_org_provider_store"),
        sa.UniqueConstraint("branch_id", "provider", name="uq_channel_store_mappings_branch_provider"),
    )

    op.create_table(
        "channel_product_mappings",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_item_id", sa.String(128), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "provider", "external_item_id", name="uq_channel_product_mappings_org_provider_item"),
    )

    op.create_table(
        "integration_webhook_logs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("event_id", sa.String(128), nullable=True),
        sa.Column("signature", sa.String(256), nullable=True),
        sa.Column("payload_raw", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="received"),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "channel_orders_meta",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False, unique=True),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_order_id", sa.String(128), nullable=False),
        sa.Column("display_code", sa.String(32), nullable=False),
        sa.Column("customer_name", sa.String(160), nullable=True),
        sa.Column("driver_name", sa.String(160), nullable=True),
        sa.Column("driver_phone", sa.String(32), nullable=True),
        sa.Column("external_status", sa.String(48), nullable=False, server_default="CREATED"),
        sa.Column("estimated_ready_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("channel_orders_meta")
    op.drop_table("integration_webhook_logs")
    op.drop_table("channel_product_mappings")
    op.drop_table("channel_store_mappings")
    op.drop_table("channel_integrations")
