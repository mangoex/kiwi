"""order amendments and deferred payments

Revision ID: 0029_order_amendments_deferred
Revises: 0028_global_order_comments_extras
Create Date: 2026-07-22 22:30:00
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision: str = "0029_order_amendments_deferred"
down_revision: str | None = "0028_global_order_comments_extras"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

UTC = timezone.utc
PERMISSION_ID = "018f6f73-2d0a-74f0-8f1c-000000000627"


def upgrade() -> None:
    with op.batch_alter_table("orders") as batch:
        batch.add_column(sa.Column("payment_method_intent", sa.String(32), nullable=True))
        batch.add_column(
            sa.Column("version", sa.Integer(), nullable=False, server_default="1")
        )

    with op.batch_alter_table("order_lines") as batch:
        batch.add_column(
            sa.Column("status", sa.String(32), nullable=False, server_default="active")
        )
        batch.add_column(
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1")
        )
        batch.add_column(sa.Column("supersedes_line_id", sa.String(36), nullable=True))
        batch.add_column(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("removed_at", sa.DateTime(timezone=True), nullable=True))
        batch.create_foreign_key(
            "fk_order_lines_supersedes_line_id",
            "order_lines",
            ["supersedes_line_id"],
            ["id"],
        )

    op.create_table(
        "order_amendments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("expected_version", sa.Integer(), nullable=False),
        sa.Column("resulting_version", sa.Integer(), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("order_id", "sequence", name="uq_order_amendment_sequence"),
        sa.UniqueConstraint(
            "order_id", "idempotency_key", name="uq_order_amendment_idempotency"
        ),
    )

    now = datetime(2026, 7, 22, 22, 30, tzinfo=UTC)
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """
            INSERT INTO permissions (id, code, description, created_at)
            VALUES (:id, 'orders.amend', 'Editar pedidos no pagados antes de producción.', :now)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {"id": PERMISSION_ID, "now": now},
    )
    connection.execute(
        sa.text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            SELECT roles.id, permissions.id
            FROM roles CROSS JOIN permissions
            WHERE lower(roles.name) IN (
                'administrador corporativo',
                'supervisor de sucursal',
                'cajero',
                'caja'
            )
              AND permissions.code = 'orders.amend'
            ON CONFLICT DO NOTHING
            """
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    amendment_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM order_amendments")
    ).scalar_one()
    deferred_count = connection.execute(
        sa.text(
            """
            SELECT COUNT(*) FROM orders
            WHERE version <> 1 OR payment_method_intent IS NOT NULL
            """
        )
    ).scalar_one()
    if amendment_count or deferred_count:
        raise RuntimeError(
            "Cannot downgrade 0029 while amended or deferred-payment orders exist"
        )
    connection.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code = 'orders.amend'
            )
            """
        )
    )
    connection.execute(sa.text("DELETE FROM permissions WHERE code = 'orders.amend'"))
    op.drop_table("order_amendments")
    with op.batch_alter_table("order_lines") as batch:
        batch.drop_constraint("fk_order_lines_supersedes_line_id", type_="foreignkey")
        batch.drop_column("removed_at")
        batch.drop_column("updated_at")
        batch.drop_column("supersedes_line_id")
        batch.drop_column("revision")
        batch.drop_column("status")
    with op.batch_alter_table("orders") as batch:
        batch.drop_column("version")
        batch.drop_column("payment_method_intent")
