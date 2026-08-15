"""add PCO-006 immutable user cash cuts

Revision ID: 0041_user_cash_cuts
Revises: 0040_order_corrections
"""

from alembic import op
import sqlalchemy as sa

revision = "0041_user_cash_cuts"
down_revision = "0040_order_corrections"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # SQLite requires batch mode when adding the foreign-key constraint.
    with op.batch_alter_table("cash_shifts") as batch:
        batch.add_column(sa.Column("cashier_user_id", sa.String(36), nullable=True))
        batch.create_foreign_key("fk_cash_shifts_cashier_user", "users", ["cashier_user_id"], ["id"])
    op.create_index("ix_cash_shifts_cashier", "cash_shifts", ["cashier_user_id"])
    # Only a single persisted historical open command is authoritative.  Missing
    # or conflicting command history deliberately remains NULL and is ineligible.
    op.execute(
        sa.text(
            """
            UPDATE cash_shifts
               SET cashier_user_id = (
                   SELECT MIN(command_row.actor_user_id)
                     FROM cash_shift_commands AS command_row
                    WHERE command_row.cash_shift_id = cash_shifts.id
                      AND command_row.command_type = 'open'
               )
             WHERE cashier_user_id IS NULL
               AND (
                   SELECT COUNT(DISTINCT command_row.actor_user_id)
                     FROM cash_shift_commands AS command_row
                    WHERE command_row.cash_shift_id = cash_shifts.id
                      AND command_row.command_type = 'open'
               ) = 1
            """
        )
    )
    op.create_table("user_cash_cuts", sa.Column("id",sa.String(36),primary_key=True), sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False), sa.Column("branch_id",sa.String(36),sa.ForeignKey("branches.id"),nullable=False), sa.Column("cash_shift_id",sa.String(36),sa.ForeignKey("cash_shifts.id"),nullable=False,unique=True), sa.Column("register_code_snapshot",sa.String(32),nullable=False), sa.Column("cashier_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False), sa.Column("timezone",sa.String(64),nullable=False), sa.Column("period_start",sa.DateTime(timezone=True),nullable=False), sa.Column("period_end",sa.DateTime(timezone=True),nullable=False), sa.Column("status",sa.String(16),nullable=False), sa.Column("opening_cash_cents",sa.Integer(),nullable=False), sa.Column("cash_payment_cents",sa.Integer()), sa.Column("deposit_cents",sa.Integer()), sa.Column("withdrawal_cents",sa.Integer()), sa.Column("expected_cash_cents",sa.Integer()), sa.Column("counted_cash_cents",sa.Integer()), sa.Column("difference_cents",sa.Integer()), sa.Column("tolerance_cents",sa.Integer(),nullable=False,server_default="0"), sa.Column("created_by_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False), sa.Column("finalized_by_user_id",sa.String(36),sa.ForeignKey("users.id")), sa.Column("version",sa.Integer(),nullable=False,server_default="1"), sa.Column("created_at",sa.DateTime(timezone=True),nullable=False), sa.Column("counted_at",sa.DateTime(timezone=True)), sa.Column("finalized_at",sa.DateTime(timezone=True)), sa.CheckConstraint("status IN ('DRAFT','COUNTED','FINALIZED')",name="ck_user_cash_cuts_status"), sa.CheckConstraint("period_start < period_end",name="ck_user_cash_cuts_period"), sa.CheckConstraint("tolerance_cents = 0",name="ck_user_cash_cuts_tolerance"))
    op.create_index("ix_user_cash_cuts_org_branch_period","user_cash_cuts",["organization_id","branch_id","period_start"])
    op.create_table("user_cash_cut_operations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("cash_cut_id",sa.String(36),sa.ForeignKey("user_cash_cuts.id"),nullable=False),sa.Column("operation_type",sa.String(16),nullable=False),sa.Column("operation_id",sa.String(36),nullable=False),sa.Column("signed_amount_cents",sa.Integer(),nullable=False),sa.Column("occurred_at",sa.DateTime(timezone=True),nullable=False),sa.CheckConstraint("operation_type IN ('PAYMENT','MOVEMENT')",name="ck_user_cash_cut_operations_type"),sa.UniqueConstraint("organization_id","operation_type","operation_id",name="uq_user_cash_cut_operation_global"))
    op.create_table("user_cash_cut_commands",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("actor_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("cash_cut_id",sa.String(36),sa.ForeignKey("user_cash_cuts.id")),sa.Column("command_type",sa.String(24),nullable=False),sa.Column("idempotency_key",sa.String(180),nullable=False),sa.Column("request_hash",sa.String(64),nullable=False),sa.Column("result",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.UniqueConstraint("organization_id","idempotency_key",name="uq_user_cash_cut_commands_key"))
    op.create_table("user_cash_cut_reopen_requests",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("cash_cut_id",sa.String(36),sa.ForeignKey("user_cash_cuts.id"),nullable=False),sa.Column("proposed_counted_cash_cents",sa.Integer(),nullable=False),sa.Column("reason",sa.String(600),nullable=False),sa.Column("evidence_refs",sa.JSON(),nullable=False),sa.Column("status",sa.String(16),nullable=False),sa.Column("requested_by_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("decided_by_user_id",sa.String(36),sa.ForeignKey("users.id")),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False),sa.Column("decided_at",sa.DateTime(timezone=True)),sa.CheckConstraint("status IN ('REQUESTED','APPROVED','REJECTED','COMPENSATED')",name="ck_user_cash_cut_reopen_status"))
    op.create_index("uq_user_cash_cut_reopen_active","user_cash_cut_reopen_requests",["cash_cut_id"],unique=True,sqlite_where=sa.text("status IN ('REQUESTED', 'APPROVED')"),postgresql_where=sa.text("status IN ('REQUESTED', 'APPROVED')"))
    op.create_table("user_cash_cut_compensations",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("cash_cut_id",sa.String(36),sa.ForeignKey("user_cash_cuts.id"),nullable=False),sa.Column("reopen_request_id",sa.String(36),sa.ForeignKey("user_cash_cut_reopen_requests.id"),nullable=False,unique=True),sa.Column("corrected_counted_cash_cents",sa.Integer(),nullable=False),sa.Column("expected_cash_cents",sa.Integer(),nullable=False),sa.Column("tolerance_cents",sa.Integer(),nullable=False),sa.Column("corrected_difference_cents",sa.Integer(),nullable=False),sa.Column("difference_delta_cents",sa.Integer(),nullable=False),sa.Column("created_by_user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    with op.batch_alter_table("user_cash_cuts") as batch:
        batch.create_check_constraint("ck_user_cash_cuts_amounts", "opening_cash_cents >= 0 AND (cash_payment_cents IS NULL OR cash_payment_cents >= 0) AND (deposit_cents IS NULL OR deposit_cents >= 0) AND (withdrawal_cents IS NULL OR withdrawal_cents >= 0) AND (counted_cash_cents IS NULL OR counted_cash_cents >= 0) AND version > 0")
    with op.batch_alter_table("user_cash_cut_commands") as batch:
        batch.create_check_constraint("ck_user_cash_cut_commands_type", "command_type IN ('create','count','finalize','reopen_request','reopen_approved','reopen_rejected','reopen_compensate')")
        batch.create_check_constraint("ck_user_cash_cut_commands_key", "trim(idempotency_key) != ''")
        batch.create_check_constraint("ck_user_cash_cut_commands_hash", "length(request_hash) = 64")
    with op.batch_alter_table("user_cash_cut_reopen_requests") as batch:
        batch.create_check_constraint("ck_user_cash_cut_reopen_amount", "proposed_counted_cash_cents >= 0")
    with op.batch_alter_table("user_cash_cut_compensations") as batch:
        batch.create_check_constraint("ck_user_cash_cut_compensation_amounts", "corrected_counted_cash_cents >= 0 AND tolerance_cents >= 0")


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("user_cash_cuts", "user_cash_cut_operations", "user_cash_cut_commands", "user_cash_cut_reopen_requests", "user_cash_cut_compensations"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("PCO-006 history blocks downgrade; user cash cuts are append-only")
    if bind.execute(
        sa.text("SELECT 1 FROM cash_shifts WHERE cashier_user_id IS NOT NULL LIMIT 1")
    ).first():
        raise RuntimeError("PCO-006 cashier history blocks downgrade")
    op.drop_table("user_cash_cut_compensations")
    op.drop_index("uq_user_cash_cut_reopen_active", table_name="user_cash_cut_reopen_requests")
    op.drop_table("user_cash_cut_reopen_requests")
    op.drop_table("user_cash_cut_commands")
    op.drop_table("user_cash_cut_operations")
    op.drop_index("ix_user_cash_cuts_org_branch_period", table_name="user_cash_cuts")
    op.drop_table("user_cash_cuts")
    op.drop_index("ix_cash_shifts_cashier", table_name="cash_shifts")
    with op.batch_alter_table("cash_shifts") as batch:
        batch.drop_constraint("fk_cash_shifts_cashier_user", type_="foreignkey")
        batch.drop_column("cashier_user_id")
