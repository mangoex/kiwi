"""0082 SQLite roundtrip and corporate purchase history guard."""

from __future__ import annotations

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0082_corporate_purchase_orders"
PREVIOUS = "0081_agent_cash_cut_compensation_index"


def test_corporate_purchase_migration_roundtrip_and_history_guard(tmp_path) -> None:
    path = tmp_path / "corporate-purchases.db"
    upgraded = _sqlite_alembic(path, "upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(path) as connection:
        table_names = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name LIKE 'corporate_purchase_%'"
            )
        }
        assert {
            "corporate_purchase_orders",
            "corporate_purchase_order_lines",
            "corporate_purchase_allocations",
            "corporate_purchase_receipts",
            "corporate_purchase_receipt_lines",
            "corporate_purchase_commands",
        } <= table_names
        price_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(supplier_price_history)")
        }
        assert {
            "organization_id",
            "branch_id",
            "warehouse_id",
            "source_type",
            "source_id",
        } <= price_columns
        permission_codes = {
            row[0]
            for row in connection.execute(
                "SELECT code FROM permissions WHERE code LIKE 'purchases.corporate.%'"
            )
        }
        assert permission_codes == {
            "purchases.corporate.read",
            "purchases.corporate.manage",
        }

    downgraded = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO corporate_purchase_commands "
            "(id,organization_id,actor_user_id,command_type,idempotency_key,request_hash,"
            "order_id,result,created_at) VALUES "
            "('command-1','org','actor','create','key','hash',NULL,'{}','2026-10-12')"
        )
        connection.commit()
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "Cannot downgrade 0082 while corporate purchase history exists" in (
        blocked.stdout + blocked.stderr
    )
