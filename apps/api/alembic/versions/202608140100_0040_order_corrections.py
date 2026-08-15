"""PCO-005B append-only compensating order corrections."""

from alembic import op
import sqlalchemy as sa

revision = "0040_order_corrections"
down_revision = "0039_order_reopen_requests"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "order_corrections",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("request_id", sa.String(36), sa.ForeignKey("order_reopen_requests.id"), nullable=False, unique=True),
        sa.Column("folio", sa.String(80), nullable=False, unique=True),
        sa.Column("captured_order_version", sa.Integer(), nullable=False),
        sa.Column("resulting_order_version", sa.Integer(), nullable=False),
        sa.Column("before_snapshot", sa.JSON(), nullable=False),
        sa.Column("after_snapshot", sa.JSON(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("corrected_total_cents", sa.Integer(), nullable=False),
        sa.Column("settlement_delta_cents", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="APPLIED"),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("captured_order_version > 0 AND resulting_order_version >= captured_order_version", name="ck_order_corrections_versions"),
        sa.CheckConstraint("length(trim(currency)) = 3 AND currency = upper(currency)", name="ck_order_corrections_currency"),
        sa.CheckConstraint("corrected_total_cents >= 0", name="ck_order_corrections_total"),
        sa.CheckConstraint("status = 'APPLIED'", name="ck_order_corrections_status"),
    )
    op.create_table(
        "order_correction_lines",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correction_id", sa.String(36), sa.ForeignKey("order_corrections.id"), nullable=False),
        sa.Column("source_line_id", sa.String(36), sa.ForeignKey("order_lines.id")),
        sa.Column("operational_order_line_id", sa.String(36), sa.ForeignKey("order_lines.id")),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("product_name_snapshot", sa.String(160), nullable=False),
        sa.Column("family_name_snapshot", sa.String(160), nullable=False),
        sa.Column("unit_price_cents", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("modifiers_snapshot", sa.JSON(), nullable=False),
        sa.Column("line_total_cents", sa.Integer(), nullable=False),
        sa.Column("classification", sa.String(16), nullable=False),
        sa.CheckConstraint("quantity > 0 AND unit_price_cents >= 0 AND line_total_cents >= 0", name="ck_order_correction_lines_amounts"),
        sa.CheckConstraint("classification IN ('RETAINED','ADDITION')", name="ck_order_correction_lines_classification"),
        sa.CheckConstraint("(classification = 'RETAINED' AND source_line_id IS NOT NULL) OR (classification = 'ADDITION' AND source_line_id IS NULL)", name="ck_order_correction_lines_source"),
    )
    op.create_index("ix_order_correction_lines_operational", "order_correction_lines", ["operational_order_line_id"])
    op.create_table(
        "order_payment_adjustments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correction_id", sa.String(36), sa.ForeignKey("order_corrections.id"), nullable=False, unique=True),
        sa.Column("original_payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("adjustment_type", sa.String(12), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("method", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id")),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("evidence_refs", sa.JSON(), nullable=False),
        sa.Column("cash_movement_id", sa.String(36), sa.ForeignKey("cash_movements.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("adjustment_type IN ('CHARGE','REFUND') AND amount_cents > 0", name="ck_order_payment_adjustments_amount"),
        sa.CheckConstraint("status = 'CONFIRMED'", name="ck_order_payment_adjustments_status"),
        sa.CheckConstraint("method IN ('cash','debit_card','credit_card','transfer')", name="ck_order_payment_adjustments_method"),
        sa.CheckConstraint("length(trim(currency)) = 3 AND currency = upper(currency)", name="ck_order_payment_adjustments_currency"),
        sa.CheckConstraint("(method = 'cash' AND cash_shift_id IS NOT NULL AND cash_movement_id IS NOT NULL) OR (method != 'cash' AND cash_shift_id IS NULL AND cash_movement_id IS NULL)", name="ck_order_payment_adjustments_cash_link"),
    )
    op.create_table(
        "order_production_adjustments",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("correction_id", sa.String(36), sa.ForeignKey("order_corrections.id"), nullable=False),
        sa.Column("source_line_id", sa.String(36), sa.ForeignKey("order_lines.id")),
        sa.Column("source_task_id", sa.String(36), sa.ForeignKey("production_tasks.id")),
        sa.Column("correction_line_id", sa.String(36), sa.ForeignKey("order_correction_lines.id")),
        sa.Column("adjustment_type", sa.String(16), nullable=False),
        sa.Column("quantity", sa.Numeric(18, 6), nullable=False),
        sa.Column("inventory_movement_id", sa.String(36), sa.ForeignKey("inventory_movements.id")),
        sa.Column("production_task_id", sa.String(36), sa.ForeignKey("production_tasks.id")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("adjustment_type IN ('RELEASE','WASTE','RECOVERY','ADDITION') AND quantity > 0", name="ck_order_production_adjustments_value"),
        sa.CheckConstraint("(adjustment_type = 'ADDITION' AND source_line_id IS NULL AND source_task_id IS NULL AND correction_line_id IS NOT NULL) OR (adjustment_type != 'ADDITION' AND source_line_id IS NOT NULL AND source_task_id IS NOT NULL)", name="ck_order_production_adjustments_links"),
    )
    op.create_index("ix_order_corrections_org_branch_applied", "order_corrections", ["organization_id", "branch_id", "applied_at"])
    op.create_index("ix_order_correction_lines_correction", "order_correction_lines", ["correction_id"])
    op.create_index("ix_order_payment_adjustments_correction", "order_payment_adjustments", ["correction_id"])
    op.create_index("ix_order_production_adjustments_correction", "order_production_adjustments", ["correction_id"])


def downgrade() -> None:
    connection = op.get_bind()
    for table in (
        "order_corrections",
        "order_correction_lines",
        "order_payment_adjustments",
        "order_production_adjustments",
    ):
        if connection.execute(sa.text(f"SELECT 1 FROM {table} LIMIT 1")).first():
            raise RuntimeError("PCO-005B history blocks downgrade; corrections are append-only")
    op.drop_index("ix_order_production_adjustments_correction", table_name="order_production_adjustments")
    op.drop_index("ix_order_corrections_org_branch_applied", table_name="order_corrections")
    op.drop_table("order_production_adjustments")
    op.drop_index("ix_order_payment_adjustments_correction", table_name="order_payment_adjustments")
    op.drop_table("order_payment_adjustments")
    op.drop_index("ix_order_correction_lines_operational", table_name="order_correction_lines")
    op.drop_index("ix_order_correction_lines_correction", table_name="order_correction_lines")
    op.drop_table("order_correction_lines")
    op.drop_table("order_corrections")
