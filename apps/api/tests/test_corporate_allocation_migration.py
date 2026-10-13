"""Additive target migration and downgrade history protection."""

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0083_corporate_allocation_targets"
PREVIOUS = "0082_corporate_purchase_orders"


def test_targets_migration_roundtrip_and_history_guard(tmp_path) -> None:
    path = tmp_path / "allocation-targets.db"
    upgraded = _sqlite_alembic(path, "upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute(
            "PRAGMA table_info(corporate_purchase_allocations)"
        )}
        assert {"inventory_cost_target", "allocation_sequence"} <= columns
    downgraded = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert downgraded.returncode == 0, downgraded.stdout + downgraded.stderr
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute(
            "INSERT INTO corporate_purchase_orders "
            "(id,organization_id,legal_entity_id,supplier_id,folio,order_date,currency,"
            "subtotal,discount_total,tax_total,total,status,version,created_by,"
            "created_at,updated_at,allocation_policy_version) VALUES "
            "('order','org','entity','supplier','folio','2026-10-13','MXN',"
            "1,0,0,1,'DRAFT',1,'actor','2026-10-13','2026-10-13',2)"
        )
        connection.commit()
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "Cannot downgrade 0083 while frozen allocation history exists" in (
        blocked.stdout + blocked.stderr
    )
