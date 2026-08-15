"""PCO-005B SQLite migration roundtrip and irreversible-history guard."""

from __future__ import annotations

import sqlite3

import pytest
from test_cash_ledger_migration import _sqlite_alembic

REVISION_0039 = "0039_order_reopen_requests"
REVISION_0040 = "0040_order_corrections"


def _seed_history(connection: sqlite3.Connection, table: str) -> None:
    """Insert the minimum append-only fact for each PCO-005B table.

    SQLite Alembic tests deliberately use this isolated database; a child fact
    is enough to make the downgrade unsafe even when foreign-key enforcement is
    disabled by a local SQLite driver.
    """
    if table == "order_corrections":
        connection.execute(
            """
            INSERT INTO order_corrections (
                id, organization_id, branch_id, order_id, request_id, folio,
                captured_order_version, resulting_order_version, before_snapshot,
                after_snapshot, currency, corrected_total_cents,
                settlement_delta_cents, actor_user_id, applied_at
            ) VALUES (
                'c1', 'o1', 'b1', 'order1', 'request1', 'COR-1', 1, 1, '{}', '{}',
                'MXN', 0, 0, 'u1', '2026-08-14T00:00:00+00:00'
            )
            """
        )
    elif table == "order_correction_lines":
        connection.execute(
            """
            INSERT INTO order_correction_lines (
                id, correction_id, source_line_id, operational_order_line_id, product_id,
                product_name_snapshot, family_name_snapshot, unit_price_cents, quantity,
                modifiers_snapshot, line_total_cents, classification
            ) VALUES ('cl1', 'c1', 'line1', NULL, 'product1', 'Producto', 'Familia',
                      0, 1, '[]', 0, 'RETAINED')
            """
        )
    elif table == "order_payment_adjustments":
        connection.execute(
            """
            INSERT INTO order_payment_adjustments (
                id, correction_id, original_payment_id, adjustment_type, amount_cents,
                method, currency, cash_shift_id, status, evidence_refs, cash_movement_id,
                created_at
            ) VALUES ('pa1', 'c1', 'payment1', 'CHARGE', 1, 'transfer', 'MXN', NULL,
                      'CONFIRMED', '[]', NULL, '2026-08-14T00:00:00+00:00')
            """
        )
    elif table == "order_production_adjustments":
        connection.execute(
            """
            INSERT INTO order_production_adjustments (
                id, correction_id, source_line_id, source_task_id, correction_line_id,
                adjustment_type, quantity, inventory_movement_id, production_task_id, created_at
            ) VALUES ('pr1', 'c1', NULL, NULL, 'cl1', 'ADDITION', 1, NULL, NULL,
                      '2026-08-14T00:00:00+00:00')
            """
        )
    else:  # pragma: no cover - guard for test maintenance
        raise AssertionError(f"Unknown PCO-005B table: {table}")


def test_sqlite_0039_to_0040_roundtrip_is_empty_and_repeatable(tmp_path) -> None:
    path = tmp_path / "pco005b-roundtrip.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0039).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION_0040).returncode == 0
    assert _sqlite_alembic(path, "downgrade", REVISION_0039).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION_0040).returncode == 0

    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT version_num FROM alembic_version").fetchone() == (
            REVISION_0040,
        )
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        assert table_names >= {
            "order_corrections",
            "order_correction_lines",
            "order_payment_adjustments",
            "order_production_adjustments",
        }
    finally:
        connection.close()


@pytest.mark.parametrize(
    "table",
    (
        "order_corrections",
        "order_correction_lines",
        "order_payment_adjustments",
        "order_production_adjustments",
    ),
)
def test_sqlite_0040_downgrade_is_blocked_by_history_in_each_pco005b_table(
    tmp_path, table: str
) -> None:
    path = tmp_path / f"pco005b-history-{table}.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0040).returncode == 0
    connection = sqlite3.connect(path)
    try:
        _seed_history(connection, table)
        connection.commit()
    finally:
        connection.close()

    blocked = _sqlite_alembic(path, "downgrade", REVISION_0039)
    assert blocked.returncode != 0
    assert "PCO-005B history blocks downgrade" in (blocked.stdout + blocked.stderr)
