"""ORD-OFF001 retained bundles, grants, lease and central inbox."""

from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = "0067_offline_orders"
down_revision = "0066_combo_compositions"
branch_labels = depends_on = None


def upgrade() -> None:
    op.create_table(
        "offline_order_bundles",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("bundle_hash", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("catalog", sa.JSON(), nullable=False),
        sa.Column("operational_seed", sa.JSON(), nullable=False),
        sa.Column("kid", sa.String(128), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("id", "bundle_hash", name="uq_offline_order_bundle_identity"),
    )
    op.create_table(
        "offline_order_gateway_leases",
        sa.Column("branch_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("fencing_token", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "offline_order_handoffs",
        sa.Column("handoff_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("public_key", sa.Text(), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("watermark", sa.Integer(), nullable=False),
        sa.Column("manifest_hash", sa.String(64), nullable=False),
        sa.Column("manifest", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "organization_id",
            "branch_id",
            "device_id",
            "lease_epoch",
            "manifest_hash",
            name="uq_offline_order_handoff_manifest",
        ),
        sa.CheckConstraint("lease_epoch > 0", name="ck_offline_order_handoff_epoch"),
        sa.CheckConstraint("watermark >= 0", name="ck_offline_order_handoff_watermark"),
        sa.CheckConstraint("status = 'RELEASED'", name="ck_offline_order_handoff_status"),
    )
    op.create_table(
        "offline_order_grants",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("bundle_id", sa.String(36), nullable=False),
        sa.Column("bundle_hash", sa.String(64), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("capabilities", sa.JSON(), nullable=False),
        sa.Column("token", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "offline_order_inbox",
        sa.Column("command_id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), nullable=False),
        sa.Column("branch_id", sa.String(36), nullable=False),
        sa.Column("device_id", sa.String(36), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("bundle_id", sa.String(36), nullable=False),
        sa.Column("lease_epoch", sa.Integer(), nullable=False),
        sa.Column("checkpoint", sa.Integer(), nullable=False),
        sa.Column("aggregate_id", sa.String(36), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("command_hash", sa.String(64), nullable=False),
        sa.Column("intention_hash", sa.String(64), nullable=False),
        sa.Column("envelope", sa.JSON(), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("aggregate_id", "sequence", name="uq_offline_order_inbox_sequence"),
        sa.UniqueConstraint("checkpoint", name="uq_offline_order_inbox_checkpoint"),
        sa.CheckConstraint("checkpoint > 0", name="ck_offline_order_inbox_checkpoint"),
        sa.CheckConstraint("sequence > 0", name="ck_offline_order_inbox_sequence"),
        sa.CheckConstraint("lease_epoch > 0", name="ck_offline_order_inbox_epoch"),
        sa.CheckConstraint("status IN ('CONFIRMED', 'CONFLICT')", name="ck_offline_order_inbox_status"),
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in (
        "offline_order_handoffs",
        "offline_order_inbox",
        "offline_order_grants",
        "offline_order_gateway_leases",
        "offline_order_bundles",
    ):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first() is not None:
            raise RuntimeError("Cannot downgrade 0067 while offline order history exists")
    op.drop_table("offline_order_handoffs")
    op.drop_table("offline_order_inbox")
    op.drop_table("offline_order_grants")
    op.drop_table("offline_order_gateway_leases")
    op.drop_table("offline_order_bundles")
