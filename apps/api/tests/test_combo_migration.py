"""SQLite migration roundtrip and irreversible combo-order history guard."""

from __future__ import annotations

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0066_combo_compositions"
PREVIOUS = "0065_admin_catalog"


def test_combo_0066_roundtrip_and_history_guard(tmp_path) -> None:
    path = tmp_path / "combo-compositions.db"
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    assert _sqlite_alembic(path, "downgrade", PREVIOUS).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0

    connection = sqlite3.connect(path)
    try:
        # Foreign keys are intentionally disabled in this isolated migration
        # fixture: the append-only snapshot itself is the downgrade boundary.
        connection.execute(
            """
            INSERT INTO order_line_component_snapshots (
                id, order_line_id, production_task_id, composition_id, composition_version,
                component_product_id, component_product_name, component_quantity,
                station, recipe_components, created_at
            ) VALUES ('snapshot-1', 'line-1', 'task-1', 'composition-1', 1, 'product-1',
                      'Componente', 1, 'kitchen', '[]', '2026-09-18T00:00:00+00:00')
            """
        )
        connection.commit()
    finally:
        connection.close()

    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "Cannot downgrade 0066 while combo order snapshots exist" in (
        blocked.stdout + blocked.stderr
    )
    connection = sqlite3.connect(path)
    try:
        assert connection.execute(
            "SELECT count(*) FROM order_line_component_snapshots"
        ).fetchone() == (1,)
    finally:
        connection.close()
