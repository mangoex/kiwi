"""Additive delivery accounting; services never enter product/recipe tables."""

from __future__ import annotations

import sqlalchemy as sa


def tables(metadata: sa.MetaData) -> tuple[sa.Table, ...]:
    tariffs = sa.Table(
        "delivery_tariffs",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_delivery_tariff_code"),
    )
    versions = sa.Table(
        "delivery_tariff_versions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("tariff_id", sa.String(36), sa.ForeignKey("delivery_tariffs.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("fiscal_mapping", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("tariff_id", "version", name="uq_delivery_tariff_version"),
        sa.CheckConstraint("amount_cents >= 0 AND version > 0", name="ck_delivery_tariff_price"),
    )
    policies = sa.Table(
        "delivery_policies",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("scope_key", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("eligible_tariff_ids", sa.JSON(), nullable=False),
        sa.Column("default_tariff_id", sa.String(36), nullable=True),
        sa.Column("free_threshold_cents", sa.Integer(), nullable=True),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "scope_key", "version", name="uq_delivery_policy"),
        sa.CheckConstraint(
            "version > 0 AND (free_threshold_cents IS NULL OR free_threshold_cents > 0)",
            name="ck_delivery_threshold",
        ),
    )
    charges = sa.Table(
        "delivery_charge_revisions",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("order_version", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_id", "order_version", name="uq_delivery_charge_revision"),
    )
    sales = sa.Table(
        "delivery_sale_snapshots",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False, unique=True
        ),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    commands = sa.Table(
        "delivery_catalog_commands",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("response", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_delivery_command"),
    )
    return tariffs, versions, policies, charges, sales, commands
