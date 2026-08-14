"""PCO-005A governed reopen requests; historical orders remain immutable."""

from alembic import op
import sqlalchemy as sa

revision = "0039_order_reopen_requests"
down_revision = "0038_cash_shift_closures_sales_monitor"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_reopen_requests",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("order_version_snapshot", sa.Integer(), nullable=False),
        sa.Column("order_status_snapshot", sa.String(32), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("requested_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("decided_at", sa.DateTime(timezone=True)),
        sa.Column("decision_reason", sa.String(500)),
        sa.Column("applied_by_user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("applied_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('REQUESTED','APPROVED','REJECTED','EXPIRED','APPLIED')",
            name="ck_order_reopen_status",
        ),
        sa.CheckConstraint("order_version_snapshot > 0", name="ck_order_reopen_version"),
        sa.CheckConstraint("trim(reason) != ''", name="ck_order_reopen_reason"),
        sa.CheckConstraint(
            "length(trim(CAST(evidence_refs AS TEXT))) > 2",
            name="ck_order_reopen_evidence_nonempty",
        ),
        sa.CheckConstraint(
            "(status = 'REQUESTED' AND decided_by_user_id IS NULL AND decided_at IS NULL AND decision_reason IS NULL AND applied_by_user_id IS NULL AND applied_at IS NULL) OR (status IN ('APPROVED','REJECTED') AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL AND trim(decision_reason) != '' AND applied_by_user_id IS NULL AND applied_at IS NULL) OR (status = 'EXPIRED' AND decided_by_user_id IS NULL AND decided_at IS NULL AND decision_reason IS NULL AND applied_by_user_id IS NULL AND applied_at IS NULL) OR (status = 'APPLIED' AND decided_by_user_id IS NOT NULL AND decided_at IS NOT NULL AND trim(decision_reason) != '' AND applied_by_user_id IS NOT NULL AND applied_at IS NOT NULL)",
            name="ck_order_reopen_state_coherence",
        ),
    )
    op.create_index(
        "uq_order_reopen_active",
        "order_reopen_requests",
        ["order_id"],
        unique=True,
        sqlite_where=sa.text("status IN ('REQUESTED','APPROVED')"),
        postgresql_where=sa.text("status IN ('REQUESTED','APPROVED')"),
    )
    op.create_index(
        "ix_order_reopen_org_branch_requested",
        "order_reopen_requests",
        ["organization_id", "branch_id", "requested_at", "id"],
    )
    op.create_index(
        "ix_order_reopen_order_created", "order_reopen_requests", ["order_id", "created_at"]
    )
    op.create_table(
        "order_reopen_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("order_reopen_requests.id")),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("command_type", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(160), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="completed"),
        sa.Column("response_snapshot", sa.JSON(), nullable=False),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "command_type IN ('request','approve','reject','apply')",
            name="ck_order_reopen_command_type",
        ),
        sa.CheckConstraint("status = 'completed'", name="ck_order_reopen_command_status"),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_order_reopen_command_org_key"
        ),
    )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("order_reopen_commands", "order_reopen_requests"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("Cannot downgrade 0039 while PCO-005A history exists")
    op.drop_table("order_reopen_commands")
    op.drop_index("ix_order_reopen_order_created", table_name="order_reopen_requests")
    op.drop_index("ix_order_reopen_org_branch_requested", table_name="order_reopen_requests")
    op.drop_index("uq_order_reopen_active", table_name="order_reopen_requests")
    op.drop_table("order_reopen_requests")
