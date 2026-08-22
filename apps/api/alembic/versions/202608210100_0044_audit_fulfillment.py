"""add audited fulfillment commands and granular print permissions

Revision ID: 0044_audit_fulfillment
Revises: 0043_reconciliation_audit_log
"""

from alembic import op
import sqlalchemy as sa

revision = "0044_audit_fulfillment"
down_revision = "0043_reconciliation_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    for permission_id, code, description in (
        (
            "018f6f73-2d0a-74f0-8f1c-000000000929",
            "print.jobs.read",
            "Consultar trabajos de impresion de la sucursal.",
        ),
        (
            "018f6f73-2d0a-74f0-8f1c-000000000930",
            "print.jobs.retry",
            "Reintentar trabajos de impresion fallidos.",
        ),
        (
            "018f6f73-2d0a-74f0-8f1c-000000000931",
            "orders.fulfill",
            "Ejecutar transiciones terminales de entrega y cierre.",
        ),
    ):
        op.execute(
            sa.text(
                "INSERT INTO permissions (id, code, description, created_at) "
                "VALUES (:id, :code, :description, CURRENT_TIMESTAMP) "
                "ON CONFLICT (code) DO NOTHING"
            ).bindparams(id=permission_id, code=code, description=description)
        )

    op.create_table(
        "order_fulfillment_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(36),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("command", sa.String(32), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "order_id",
            "idempotency_key",
            name="uq_order_fulfillment_command_key",
        ),
        sa.CheckConstraint(
            "command IN ('start_delivery', 'deliver', 'close')",
            name="ck_order_fulfillment_command",
        ),
    )
    op.create_index(
        "ix_order_fulfillment_commands_scope_created",
        "order_fulfillment_commands",
        ["organization_id", "branch_id", "created_at"],
    )
    op.create_table(
        "order_adjustment_authorizations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("requesting_actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("supervisor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cart_hash", sa.String(64), nullable=False),
        sa.Column("adjustment_type", sa.String(16), nullable=False),
        sa.Column("adjustment_value", sa.String(40), nullable=False),
        sa.Column("subtotal_cents", sa.Integer(), nullable=False),
        sa.Column("adjustment_cents", sa.Integer(), nullable=False),
        sa.Column("resulting_total_cents", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(240), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=True),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "adjustment_type IN ('percent', 'fixed', 'courtesy')",
            name="ck_order_adjustment_authorization_type",
        ),
        sa.CheckConstraint(
            "status IN ('AUTHORIZED', 'CONSUMED')",
            name="ck_order_adjustment_authorization_status",
        ),
        sa.CheckConstraint(
            "adjustment_cents >= 0",
            name="ck_order_adjustment_authorization_cents",
        ),
        sa.CheckConstraint(
            "subtotal_cents >= adjustment_cents AND resulting_total_cents = subtotal_cents - adjustment_cents",
            name="ck_order_adjustment_authorization_totals",
        ),
    )
    op.create_index(
        "ix_order_adjustment_authorizations_scope_status",
        "order_adjustment_authorizations",
        ["organization_id", "branch_id", "status", "expires_at"],
    )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.execute(sa.text("SELECT 1 FROM order_fulfillment_commands LIMIT 1")).first() or bind.execute(
        sa.text("SELECT 1 FROM order_adjustment_authorizations LIMIT 1")
    ).first():
        raise RuntimeError("Order fulfillment or adjustment history blocks downgrade")
    op.drop_index(
        "ix_order_adjustment_authorizations_scope_status",
        table_name="order_adjustment_authorizations",
    )
    op.drop_table("order_adjustment_authorizations")
    op.drop_index(
        "ix_order_fulfillment_commands_scope_created",
        table_name="order_fulfillment_commands",
    )
    op.drop_table("order_fulfillment_commands")
    op.execute(
        sa.text(
            "DELETE FROM permissions WHERE code IN "
            "('print.jobs.read', 'print.jobs.retry', 'orders.fulfill')"
        )
    )
