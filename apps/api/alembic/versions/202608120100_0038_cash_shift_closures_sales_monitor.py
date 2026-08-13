"""add PCO-004 operational closures and historical sales snapshots

Revision ID: 0038_cash_shift_closures_sales_monitor
Revises: 0037_cash_movement_ledger
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision: str = "0038_cash_shift_closures_sales_monitor"
down_revision: str | None = "0037_cash_movement_ledger"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ACTIVE_LINE_STATUS = "active"
_CONFIRMED_PAYMENT_STATUS = "CONFIRMED"


def _id() -> str:
    return str(uuid4())


def _fail_if_legacy_data_is_ambiguous(bind: sa.Connection) -> None:
    duplicate = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM cash_shifts
            WHERE upper(status) IN ('OPEN', 'CLOSING')
            GROUP BY branch_id, register_code
            HAVING count(*) > 1
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if duplicate:
        raise RuntimeError("Cash shift preflight failed: duplicate active shifts")

    invalid_line = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM order_lines line
            LEFT JOIN products product ON product.id = line.product_id
            LEFT JOIN product_categories category ON category.id = product.category_id
            LEFT JOIN orders order_row ON order_row.id = line.order_id
            WHERE product.id IS NULL
               OR category.id IS NULL
               OR order_row.id IS NULL
               OR trim(category.name) = ''
               OR product.organization_id != category.organization_id
               OR order_row.organization_id != product.organization_id
            LIMIT 1
            """
        )
    ).scalar_one_or_none()
    if invalid_line:
        raise RuntimeError(
            "Family snapshot preflight failed: missing, empty or incoherent catalog relation"
        )

    invalid_payment = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM payments payment
            LEFT JOIN orders order_row ON order_row.id = payment.order_id
            LEFT JOIN cash_shifts shift_row ON shift_row.id = payment.cash_shift_id
            WHERE upper(payment.status) = :confirmed
              AND (
                    order_row.id IS NULL
                 OR shift_row.id IS NULL
                 OR payment.organization_id != order_row.organization_id
                 OR payment.organization_id != shift_row.organization_id
                 OR payment.branch_id != order_row.branch_id
                 OR payment.branch_id != shift_row.branch_id
                 OR payment.amount_cents < 0
                 OR length(trim(payment.currency)) != 3
                 OR upper(trim(payment.currency)) != upper(trim(order_row.currency))
                 OR trim(shift_row.register_code) = ''
                 OR trim(order_row.folio) = ''
                 OR order_row.order_type NOT IN ('dine-in', 'takeout', 'delivery', 'takeaway')
                 OR length(trim(order_row.currency)) != 3
              )
            LIMIT 1
            """
        ),
        {"confirmed": _CONFIRMED_PAYMENT_STATUS},
    ).scalar_one_or_none()
    if invalid_payment:
        raise RuntimeError(
            "Sales snapshot preflight failed: incoherent confirmed payment history"
        )

    invalid_active_line = bind.execute(
        sa.text(
            """
            SELECT 1
            FROM order_lines line
            JOIN payments payment ON payment.order_id = line.order_id
            WHERE upper(payment.status) = :confirmed
              AND lower(line.status) = :active
              AND (
                    line.quantity <= 0
                 OR line.line_total_cents < 0
                 OR trim(line.product_name) = ''
              )
            LIMIT 1
            """
        ),
        {"confirmed": _CONFIRMED_PAYMENT_STATUS, "active": _ACTIVE_LINE_STATUS},
    ).scalar_one_or_none()
    if invalid_active_line:
        raise RuntimeError(
            "Sales snapshot preflight failed: invalid confirmed payment line history"
        )


def _create_history_tables() -> None:
    op.create_table(
        "cash_shift_closures",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column(
            "cash_shift_id",
            sa.String(36),
            sa.ForeignKey("cash_shifts.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("register_code_snapshot", sa.String(32), nullable=False),
        sa.Column("closed_by_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("summary_snapshot", sa.JSON(), nullable=False),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "trim(register_code_snapshot) != ''", name="ck_cash_shift_closures_register"
        ),
    )
    op.create_index(
        "ix_cash_shift_closures_org_branch_closed",
        "cash_shift_closures",
        ["organization_id", "branch_id", "closed_at"],
    )
    op.create_table(
        "cash_shift_commands",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("actor_user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=True),
        sa.Column("command_type", sa.String(16), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="completed"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "command_type IN ('open', 'close')", name="ck_cash_shift_commands_type"
        ),
        sa.CheckConstraint("status = 'completed'", name="ck_cash_shift_commands_status"),
        sa.CheckConstraint(
            "trim(idempotency_key) != ''", name="ck_cash_shift_commands_idempotency_key"
        ),
        sa.CheckConstraint(
            "length(request_hash) = 64", name="ck_cash_shift_commands_request_hash"
        ),
        sa.UniqueConstraint(
            "organization_id", "idempotency_key", name="uq_cash_shift_commands_org_key"
        ),
    )
    op.create_table(
        "sales_operation_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "organization_id", sa.String(36), sa.ForeignKey("organizations.id"), nullable=False
        ),
        sa.Column("branch_id", sa.String(36), sa.ForeignKey("branches.id"), nullable=False),
        sa.Column(
            "payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False, unique=True
        ),
        sa.Column("order_id", sa.String(36), sa.ForeignKey("orders.id"), nullable=False),
        sa.Column("cash_shift_id", sa.String(36), sa.ForeignKey("cash_shifts.id"), nullable=False),
        sa.Column("register_code_snapshot", sa.String(32), nullable=False),
        sa.Column("folio_snapshot", sa.String(64), nullable=False),
        sa.Column("service_type_snapshot", sa.String(32), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("net_cents", sa.Integer(), nullable=False),
        sa.Column("discount_cents", sa.Integer(), nullable=True),
        sa.Column("courtesy_cents", sa.Integer(), nullable=True),
        sa.Column("tax_cents", sa.Integer(), nullable=True),
        sa.Column("quality_status", sa.String(32), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "quality_status IN ('captured', 'legacy_backfill', 'incomplete')",
            name="ck_sales_snapshot_quality",
        ),
        sa.CheckConstraint(
            "service_type_snapshot IN ('dine-in', 'takeout', 'delivery')",
            name="ck_sales_snapshot_service_type",
        ),
        sa.CheckConstraint("length(trim(currency)) = 3", name="ck_sales_snapshot_currency"),
        sa.CheckConstraint(
            "trim(register_code_snapshot) != '' AND trim(folio_snapshot) != ''",
            name="ck_sales_snapshot_identifiers",
        ),
        sa.CheckConstraint(
            "gross_cents >= 0 AND net_cents >= 0",
            name="ck_sales_snapshot_known_cents_nonnegative",
        ),
        sa.CheckConstraint(
            "(discount_cents IS NULL OR discount_cents >= 0) "
            "AND (courtesy_cents IS NULL OR courtesy_cents >= 0) "
            "AND (tax_cents IS NULL OR tax_cents >= 0)",
            name="ck_sales_snapshot_optional_cents_nonnegative",
        ),
    )
    op.create_table(
        "sales_operation_line_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "sales_operation_snapshot_id",
            sa.String(36),
            sa.ForeignKey("sales_operation_snapshots.id"),
            nullable=False,
        ),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("payments.id"), nullable=False),
        sa.Column("order_line_id", sa.String(36), sa.ForeignKey("order_lines.id"), nullable=False),
        sa.Column("product_id", sa.String(36), nullable=False),
        sa.Column("product_name_snapshot", sa.String(160), nullable=False),
        sa.Column("family_id_snapshot", sa.String(36), nullable=False),
        sa.Column("family_name_snapshot", sa.String(160), nullable=False),
        sa.Column("family_snapshot_source", sa.String(32), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("gross_cents", sa.Integer(), nullable=False),
        sa.Column("net_cents", sa.Integer(), nullable=True),
        sa.Column("discount_cents", sa.Integer(), nullable=True),
        sa.Column("courtesy_cents", sa.Integer(), nullable=True),
        sa.Column("tax_cents", sa.Integer(), nullable=True),
        sa.UniqueConstraint(
            "sales_operation_snapshot_id", "order_line_id", name="uq_sales_snapshot_line"
        ),
        sa.CheckConstraint(
            "family_snapshot_source IN ('captured', 'legacy_catalog_backfill')",
            name="ck_sales_line_family_source",
        ),
        sa.CheckConstraint(
            "trim(product_name_snapshot) != '' AND trim(family_name_snapshot) != ''",
            name="ck_sales_line_names",
        ),
        sa.CheckConstraint(
            "quantity > 0 AND gross_cents >= 0", name="ck_sales_line_quantity_gross"
        ),
        sa.CheckConstraint(
            "(net_cents IS NULL OR net_cents >= 0) "
            "AND (discount_cents IS NULL OR discount_cents >= 0) "
            "AND (courtesy_cents IS NULL OR courtesy_cents >= 0) "
            "AND (tax_cents IS NULL OR tax_cents >= 0)",
            name="ck_sales_line_optional_cents_nonnegative",
        ),
    )
    op.create_index(
        "ix_sales_snapshots_org_period_branch",
        "sales_operation_snapshots",
        ["organization_id", "confirmed_at", "branch_id"],
    )
    op.create_index(
        "ix_sales_snapshots_org_shift_register_service",
        "sales_operation_snapshots",
        ["organization_id", "cash_shift_id", "register_code_snapshot", "service_type_snapshot"],
    )
    op.create_index(
        "ix_sales_line_snapshots_family",
        "sales_operation_line_snapshots",
        ["family_id_snapshot", "sales_operation_snapshot_id"],
    )
    op.create_index(
        "ix_sales_line_snapshots_payment",
        "sales_operation_line_snapshots",
        ["payment_id"],
    )


def _backfill_sales_history(bind: sa.Connection) -> None:
    payments = bind.execute(
        sa.text(
            """
            SELECT payment.id AS payment_id,
                   payment.organization_id,
                   payment.branch_id,
                   payment.order_id,
                   payment.cash_shift_id,
                   payment.amount_cents,
                   payment.confirmed_at,
                   order_row.folio,
                   order_row.order_type,
                   order_row.currency,
                   shift_row.register_code
            FROM payments payment
            JOIN orders order_row ON order_row.id = payment.order_id
            JOIN cash_shifts shift_row ON shift_row.id = payment.cash_shift_id
            WHERE upper(payment.status) = :confirmed
            ORDER BY payment.confirmed_at, payment.id
            """
        ),
        {"confirmed": _CONFIRMED_PAYMENT_STATUS},
    ).mappings()

    for payment in payments:
        lines = list(
            bind.execute(
                sa.text(
                    """
                    SELECT line.id AS order_line_id,
                           line.product_id,
                           line.product_name,
                           line.quantity,
                           line.line_total_cents,
                           line.family_id_snapshot,
                           line.family_name_snapshot,
                           line.family_snapshot_source
                    FROM order_lines line
                    WHERE line.order_id = :order_id AND lower(line.status) = :active
                    ORDER BY line.id
                    """
                ),
                {"order_id": payment["order_id"], "active": _ACTIVE_LINE_STATUS},
            ).mappings()
        )
        gross_cents = sum(int(line["line_total_cents"]) for line in lines)
        reconciled = gross_cents == int(payment["amount_cents"])
        snapshot_id = _id()
        bind.execute(
            sa.text(
                """
                INSERT INTO sales_operation_snapshots (
                    id, organization_id, branch_id, payment_id, order_id, cash_shift_id,
                    register_code_snapshot, folio_snapshot, service_type_snapshot, currency,
                    gross_cents, net_cents, discount_cents, courtesy_cents, tax_cents,
                    quality_status, confirmed_at, created_at
                ) VALUES (
                    :id, :organization_id, :branch_id, :payment_id, :order_id, :cash_shift_id,
                    :register_code, :folio, :service_type, :currency,
                    :gross_cents, :net_cents, :discount_cents, :courtesy_cents, :tax_cents,
                    :quality_status, :confirmed_at, :created_at
                )
                """
            ),
            {
                "id": snapshot_id,
                "organization_id": payment["organization_id"],
                "branch_id": payment["branch_id"],
                "payment_id": payment["payment_id"],
                "order_id": payment["order_id"],
                "cash_shift_id": payment["cash_shift_id"],
                "register_code": payment["register_code"],
                "folio": payment["folio"],
                "service_type": (
                    "takeout" if payment["order_type"] == "takeaway" else payment["order_type"]
                ),
                "currency": payment["currency"],
                "gross_cents": gross_cents,
                "net_cents": int(payment["amount_cents"]),
                "discount_cents": 0 if reconciled else None,
                "courtesy_cents": 0 if reconciled else None,
                "tax_cents": 0 if reconciled else None,
                "quality_status": "legacy_backfill" if reconciled else "incomplete",
                "confirmed_at": payment["confirmed_at"],
                "created_at": payment["confirmed_at"],
            },
        )
        for line in lines:
            _insert_backfilled_line(bind, snapshot_id, payment, line, reconciled)


def _insert_backfilled_line(
    bind: sa.Connection,
    snapshot_id: str,
    payment: Mapping[str, object],
    line: Mapping[str, object],
    reconciled: bool,
) -> None:
    line_gross = int(line["line_total_cents"])
    bind.execute(
        sa.text(
            """
            INSERT INTO sales_operation_line_snapshots (
                id, sales_operation_snapshot_id, payment_id, order_line_id,
                product_id, product_name_snapshot, family_id_snapshot,
                family_name_snapshot, family_snapshot_source, quantity,
                gross_cents, net_cents, discount_cents, courtesy_cents, tax_cents
            ) VALUES (
                :id, :snapshot_id, :payment_id, :order_line_id,
                :product_id, :product_name, :family_id, :family_name, :family_source, :quantity,
                :gross_cents, :net_cents, :discount_cents, :courtesy_cents, :tax_cents
            )
            """
        ),
        {
            "id": _id(),
            "snapshot_id": snapshot_id,
            "payment_id": payment["payment_id"],
            "order_line_id": line["order_line_id"],
            "product_id": line["product_id"],
            "product_name": line["product_name"],
            "family_id": line["family_id_snapshot"],
            "family_name": line["family_name_snapshot"],
            "family_source": line["family_snapshot_source"],
            "quantity": int(line["quantity"]),
            "gross_cents": line_gross,
            "net_cents": line_gross if reconciled else None,
            "discount_cents": 0 if reconciled else None,
            "courtesy_cents": 0 if reconciled else None,
            "tax_cents": 0 if reconciled else None,
        },
    )


def upgrade() -> None:
    bind = op.get_bind()
    _fail_if_legacy_data_is_ambiguous(bind)

    op.drop_index("uq_cash_shifts_open_register", table_name="cash_shifts")
    op.create_index(
        "uq_cash_shifts_open_register",
        "cash_shifts",
        ["branch_id", "register_code"],
        unique=True,
        sqlite_where=sa.text("upper(status) IN ('OPEN', 'CLOSING')"),
        postgresql_where=sa.text("upper(status) IN ('OPEN', 'CLOSING')"),
    )
    with op.batch_alter_table("order_lines") as batch:
        batch.add_column(sa.Column("family_id_snapshot", sa.String(36), nullable=True))
        batch.add_column(sa.Column("family_name_snapshot", sa.String(160), nullable=True))
        batch.add_column(sa.Column("family_snapshot_source", sa.String(32), nullable=True))
    bind.execute(
        sa.text(
            """
            UPDATE order_lines
            SET family_id_snapshot = (
                    SELECT category.id
                    FROM products product
                    JOIN product_categories category ON category.id = product.category_id
                    WHERE product.id = order_lines.product_id
                ),
                family_name_snapshot = (
                    SELECT category.name
                    FROM products product
                    JOIN product_categories category ON category.id = product.category_id
                    WHERE product.id = order_lines.product_id
                ),
                family_snapshot_source = 'legacy_catalog_backfill'
            """
        )
    )
    with op.batch_alter_table("order_lines") as batch:
        batch.alter_column("family_id_snapshot", existing_type=sa.String(36), nullable=False)
        batch.alter_column("family_name_snapshot", existing_type=sa.String(160), nullable=False)
        batch.alter_column("family_snapshot_source", existing_type=sa.String(32), nullable=False)
        batch.create_check_constraint(
            "ck_order_lines_family_snapshot_source",
            "family_snapshot_source IN ('captured', 'legacy_catalog_backfill')",
        )
        batch.create_check_constraint(
            "ck_order_lines_family_snapshot_complete",
            "trim(family_id_snapshot) != '' AND trim(family_name_snapshot) != ''",
        )

    _create_history_tables()
    _backfill_sales_history(bind)


def downgrade() -> None:
    bind = op.get_bind()
    protected = bind.execute(
        sa.text(
            """
            SELECT
                (SELECT count(*) FROM cash_shift_closures)
              + (SELECT count(*) FROM cash_shift_commands)
              + (SELECT count(*) FROM sales_operation_snapshots WHERE quality_status = 'captured')
              + (SELECT count(*) FROM sales_operation_line_snapshots
                   WHERE family_snapshot_source = 'captured')
              + (SELECT count(*) FROM order_lines WHERE family_snapshot_source = 'captured')
            """
        )
    ).scalar_one()
    if protected:
        raise RuntimeError("Safe downgrade blocked: PCO-004 captured history exists")

    bind.execute(
        sa.text(
            """
            DELETE FROM sales_operation_line_snapshots
            WHERE sales_operation_snapshot_id IN (
                SELECT id FROM sales_operation_snapshots
                WHERE quality_status IN ('legacy_backfill', 'incomplete')
            )
            """
        )
    )
    bind.execute(
        sa.text(
            """
            DELETE FROM sales_operation_snapshots
            WHERE quality_status IN ('legacy_backfill', 'incomplete')
            """
        )
    )
    remaining_snapshots = bind.execute(
        sa.text("SELECT count(*) FROM sales_operation_snapshots")
    ).scalar_one()
    if remaining_snapshots:
        raise RuntimeError("Safe downgrade blocked: PCO-004 non-regenerable history exists")

    op.drop_index("ix_sales_line_snapshots_payment", table_name="sales_operation_line_snapshots")
    op.drop_index("ix_sales_line_snapshots_family", table_name="sales_operation_line_snapshots")
    op.drop_index(
        "ix_sales_snapshots_org_shift_register_service", table_name="sales_operation_snapshots"
    )
    op.drop_index("ix_sales_snapshots_org_period_branch", table_name="sales_operation_snapshots")
    op.drop_index("ix_cash_shift_closures_org_branch_closed", table_name="cash_shift_closures")
    op.drop_table("sales_operation_line_snapshots")
    op.drop_table("sales_operation_snapshots")
    op.drop_table("cash_shift_commands")
    op.drop_table("cash_shift_closures")
    op.drop_index("uq_cash_shifts_open_register", table_name="cash_shifts")
    op.create_index(
        "uq_cash_shifts_open_register",
        "cash_shifts",
        ["branch_id", "register_code"],
        unique=True,
        sqlite_where=sa.text("upper(status) = 'OPEN'"),
        postgresql_where=sa.text("upper(status) = 'OPEN'"),
    )
    with op.batch_alter_table("order_lines") as batch:
        batch.drop_constraint("ck_order_lines_family_snapshot_complete", type_="check")
        batch.drop_constraint("ck_order_lines_family_snapshot_source", type_="check")
        batch.drop_column("family_snapshot_source")
        batch.drop_column("family_name_snapshot")
        batch.drop_column("family_id_snapshot")
