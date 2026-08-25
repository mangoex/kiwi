"""Add public order intents without granting public access by default.

Revision ID: 0051_public_order_intents
Revises: 0050_promote_recipes_to_global_scope
"""
from collections.abc import Sequence
from typing import Optional

import sqlalchemy as sa
from alembic import op

revision = "0051_public_order_intents"
down_revision = "0050_promote_recipes_to_global_scope"
branch_labels: Optional[Sequence[str]] = None
depends_on: Optional[Sequence[str]] = None


def upgrade() -> None:
    op.create_table("public_order_keys",
        sa.Column("public_key", sa.String(160), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True)), sa.Column("retired_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_public_order_keys_status"))
    op.create_index("uq_public_order_keys_one_active_branch", "public_order_keys", ["branch_id"], unique=True,
                    sqlite_where=sa.text("status = 'active'"), postgresql_where=sa.text("status = 'active'"))
    op.create_table("public_order_intents",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False), sa.Column("public_key", sa.String(160), sa.ForeignKey("public_order_keys.public_key"), nullable=False),
        sa.Column("public_reference", sa.String(64), nullable=False, unique=True), sa.Column("correlation_id", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(24), nullable=False, server_default="PENDING_REVIEW"),
        sa.Column("customer_snapshot", sa.JSON(), nullable=False), sa.Column("delivery_address_snapshot", sa.JSON()), sa.Column("order_type", sa.String(32), nullable=False), sa.Column("order_notes", sa.String(500)),
        sa.Column("total_cents", sa.Integer(), nullable=False), sa.Column("currency", sa.String(3), nullable=False, server_default="MXN"), sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("accepted_order_id", sa.String(36), sa.ForeignKey("orders.id"), unique=True), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("decided_at", sa.DateTime(timezone=True)), sa.Column("decision_reason", sa.String(500)), sa.Column("decided_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.CheckConstraint("status IN ('PENDING_REVIEW', 'ACCEPTED', 'REJECTED', 'EXPIRED')", name="ck_public_order_intents_status"), sa.CheckConstraint("total_cents >= 0 AND version > 0", name="ck_public_order_intents_amount_version"), sa.UniqueConstraint("id", "status", name="uq_public_order_intent_id_status"))
    op.create_index("ix_public_order_intents_branch_status", "public_order_intents", ["branch_id", "status"])
    op.create_table("public_order_intent_lines",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("intent_id", sa.String(36), sa.ForeignKey("public_order_intents.id"), nullable=False), sa.Column("product_id", sa.String(36), sa.ForeignKey("products.id"), nullable=False),
        sa.Column("product_name", sa.String(160), nullable=False), sa.Column("quantity", sa.Integer(), nullable=False), sa.Column("unit_price_cents", sa.Integer(), nullable=False), sa.Column("line_total_cents", sa.Integer(), nullable=False), sa.Column("station", sa.String(32), nullable=False),
        sa.Column("selected_modifiers", sa.JSON(), nullable=False, server_default="[]"), sa.Column("modifier_total_cents", sa.Integer(), nullable=False, server_default="0"), sa.Column("line_notes", sa.String(500)), sa.Column("family_id_snapshot", sa.String(36), nullable=False), sa.Column("family_name_snapshot", sa.String(160), nullable=False), sa.Column("consumption_snapshot", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("quantity > 0 AND unit_price_cents >= 0 AND line_total_cents >= 0", name="ck_public_order_intent_lines_amounts"))
    op.create_table("public_order_intent_commands",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False), sa.Column("intent_id", sa.String(36), sa.ForeignKey("public_order_intents.id")),
        sa.Column("command_type", sa.String(16), nullable=False), sa.Column("idempotency_key", sa.String(160), nullable=False), sa.Column("request_hash", sa.String(64), nullable=False), sa.Column("result", sa.JSON(), nullable=False), sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("command_type IN ('create', 'accept', 'reject')", name="ck_public_order_intent_commands_type"), sa.UniqueConstraint("organization_id", "command_type", "idempotency_key", name="uq_public_order_intent_commands_key"))
    op.create_table("order_outbox_events",
        sa.Column("id", sa.String(36), primary_key=True), sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False), sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False), sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False), sa.Column("event_type", sa.String(80), nullable=False), sa.Column("payload", sa.JSON(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)))
    op.create_index("ix_order_outbox_events_unpublished", "order_outbox_events", ["branch_id", "published_at"])
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("public_order_intent_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("public_order_intent_status", sa.String(24), nullable=True))
        batch.create_unique_constraint("uq_orders_public_order_intent_id", ["public_order_intent_id"])
        batch.create_foreign_key("fk_orders_public_order_intent_id", "public_order_intents", ["public_order_intent_id"], ["id"])
        batch.create_foreign_key("fk_orders_public_order_intent_accepted", "public_order_intents", ["public_order_intent_id", "public_order_intent_status"], ["id", "status"])
        batch.alter_column("cash_shift_id", existing_type=sa.String(36), nullable=True)
        batch.create_check_constraint("ck_orders_cash_shift_required_except_public_intent", "cash_shift_id IS NOT NULL OR (channel = 'PUBLIC_INTENT' AND public_order_intent_id IS NOT NULL AND public_order_intent_status = 'ACCEPTED')")


def downgrade() -> None:
    conn = op.get_bind()
    if conn.execute(sa.text("SELECT 1 FROM public_order_intents LIMIT 1")).first():
        raise RuntimeError("public_order_intent_history_prevents_downgrade")
    with op.batch_alter_table("orders") as batch:
        batch.drop_constraint("ck_orders_cash_shift_required_except_public_intent", type_="check")
        batch.drop_constraint("fk_orders_public_order_intent_accepted", type_="foreignkey")
        batch.drop_constraint("fk_orders_public_order_intent_id", type_="foreignkey")
        batch.drop_constraint("uq_orders_public_order_intent_id", type_="unique")
        batch.drop_column("public_order_intent_id")
        batch.drop_column("public_order_intent_status")
        batch.alter_column("cash_shift_id", existing_type=sa.String(36), nullable=False)
    op.drop_index("ix_order_outbox_events_unpublished", table_name="order_outbox_events")
    op.drop_table("order_outbox_events")
    op.drop_table("public_order_intent_commands")
    op.drop_table("public_order_intent_lines")
    op.drop_index("ix_public_order_intents_branch_status", table_name="public_order_intents")
    op.drop_table("public_order_intents")
    op.drop_index("uq_public_order_keys_one_active_branch", table_name="public_order_keys")
    op.drop_table("public_order_keys")
