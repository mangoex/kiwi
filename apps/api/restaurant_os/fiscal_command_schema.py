"""Additive fiscal preparation, private snapshot and unresolved-order reservations."""

from __future__ import annotations

import sqlalchemy as sa

ORDER_SCOPE_INDEX = "uq_orders_fiscal_scope_identity"


def tables(metadata: sa.MetaData) -> tuple[sa.Table, sa.Table, sa.Table, sa.Table]:
    commands = sa.Table(
        "fiscal_commands",
        metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("legal_entity_id", sa.String(36), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(32), nullable=False),
        sa.Column("external_key", sa.String(64), nullable=False, unique=True),
        sa.Column("emitter_configuration_id", sa.String(36), nullable=False),
        sa.Column("emitter_configuration_version", sa.Integer(), nullable=False),
        sa.Column("snapshot_ciphertext", sa.Text(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("dispatch_ready", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "branch_id"],
            ["branches.organization_id", "branches.id"],
            name="fk_fiscal_command_branch_scope",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "legal_entity_id"],
            ["legal_entities.organization_id", "legal_entities.id"],
            name="fk_fiscal_command_emitter_scope",
        ),
        sa.ForeignKeyConstraint(
            ["emitter_configuration_id", "emitter_configuration_version"],
            [
                "fiscal_emitter_configuration_versions.configuration_id",
                "fiscal_emitter_configuration_versions.version",
            ],
            name="fk_fiscal_command_configuration_revision",
        ),
        sa.UniqueConstraint(
            "organization_id",
            "actor_user_id",
            "operation",
            "idempotency_key",
            name="uq_fiscal_command_intention",
        ),
        sa.UniqueConstraint("id", "organization_id", "branch_id", name="uq_fiscal_command_scope"),
        sa.CheckConstraint("operation = 'issue'", name="ck_fiscal_command_operation"),
        sa.CheckConstraint("dispatch_ready = false", name="ck_fiscal_payment_not_dispatchable"),
        sa.CheckConstraint("provider = 'facturapi'", name="ck_fiscal_command_provider"),
        sa.CheckConstraint(
            "state IN ('pending','processing','unknown','succeeded','rejected','needs_review')",
            name="ck_fiscal_command_state",
        ),
        sa.CheckConstraint("total_cents >= 0", name="ck_fiscal_command_total"),
        sa.CheckConstraint("emitter_configuration_version > 0", name="ck_fiscal_command_revision"),
        sa.CheckConstraint("length(request_hash) = 64", name="ck_fiscal_command_hash"),
        sa.CheckConstraint(
            "length(idempotency_key) BETWEEN 1 AND 128", name="ck_fiscal_command_key"
        ),
        sa.CheckConstraint(
            "length(currency) = 3 AND currency = upper(currency)",
            name="ck_fiscal_command_currency",
        ),
    )
    links = sa.Table(
        "fiscal_command_orders",
        metadata,
        sa.Column("command_id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("order_version", sa.Integer(), nullable=False),
        sa.Column("total_cents", sa.Integer(), nullable=False),
        sa.Column("paid_cents", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.ForeignKeyConstraint(
            ["command_id", "organization_id", "branch_id"],
            ["fiscal_commands.id", "fiscal_commands.organization_id", "fiscal_commands.branch_id"],
            name="fk_fiscal_command_order_command_scope",
        ),
        sa.ForeignKeyConstraint(
            ["order_id", "organization_id", "branch_id"],
            ["orders.id", "orders.organization_id", "orders.branch_id"],
            name="fk_fiscal_command_order_source_scope",
        ),
        sa.CheckConstraint("order_version > 0", name="ck_fiscal_command_order_version"),
        sa.CheckConstraint(
            "total_cents >= 0 AND paid_cents >= total_cents", name="ck_fiscal_order_payment"
        ),
    )
    reservations = sa.Table(
        "fiscal_order_reservations",
        metadata,
        sa.Column("order_id", sa.String(36), primary_key=True),
        sa.Column("command_id", sa.String(36), nullable=False),
        sa.ForeignKeyConstraint(
            ["command_id", "order_id"],
            ["fiscal_command_orders.command_id", "fiscal_command_orders.order_id"],
            name="fk_fiscal_order_reservation_link",
        ),
    )
    outbox = sa.Table(
        "fiscal_command_outbox",
        metadata,
        sa.Column(
            "command_id", sa.String(36), sa.ForeignKey("fiscal_commands.id"), primary_key=True
        ),
        sa.Column("event_type", sa.String(48), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "event_type = 'fiscal.issue.prepare'", name="ck_fiscal_preparation_outbox"
        ),
    )
    return commands, links, reservations, outbox
