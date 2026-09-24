"""SQLite migration and protected downgrade for selectable compound products."""

from __future__ import annotations

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0069_selectable_compound_product"
PREVIOUS = "0068_admin_product_configuration"


def test_compound_product_0069_roundtrip_and_command_history_guard(tmp_path) -> None:
    path = tmp_path / "selectable-compound-products.db"
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    assert _sqlite_alembic(path, "downgrade", PREVIOUS).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0

    connection = sqlite3.connect(path)
    try:
        connection.execute(
            """
            INSERT INTO modifier_configuration_commands (
                id, organization_id, actor_user_id, product_id, idempotency_key,
                request_hash, result, created_at
            ) VALUES ('command-1', 'org-1', 'actor-1', 'product-1', 'key-1',
                      'hash-1', '{}', '2026-09-23T00:00:00+00:00')
            """
        )
        connection.commit()
    finally:
        connection.close()

    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "Cannot downgrade 0069 while compound-product configuration history exists" in (
        blocked.stdout + blocked.stderr
    )
