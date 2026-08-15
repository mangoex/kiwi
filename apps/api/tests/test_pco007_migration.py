"""TDD-TC-128 SQLite evidence for the PCO-007 append-only command table."""

from __future__ import annotations

import sqlite3

from test_cash_ledger_migration import _sqlite_alembic

REVISION_0041 = "0041_user_cash_cuts"
REVISION_0042 = "0042_recipe_reports"


def test_0041_to_0042_empty_roundtrip_is_reversible(tmp_path) -> None:
    path = tmp_path / "pco007-roundtrip.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0041).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION_0042).returncode == 0
    assert _sqlite_alembic(path, "downgrade", REVISION_0041).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION_0042).returncode == 0


def test_0042_downgrade_blocks_recipe_command_history_and_preserves_it(tmp_path) -> None:
    path = tmp_path / "pco007-history.db"
    assert _sqlite_alembic(path, "upgrade", REVISION_0042).returncode == 0
    connection = sqlite3.connect(path)
    try:
        connection.execute(
            "INSERT INTO recipe_version_commands (id, organization_id, actor_user_id, product_id, "
            "recipe_id, idempotency_key, request_hash, result, created_at) VALUES "
            "('command', 'o1', 'u1', 'p1', 'r1', 'key', ?, '{}', '2026-08-15T00:00:00+00:00')",
            ("0" * 64,),
        )
        connection.commit()
    finally:
        connection.close()
    blocked = _sqlite_alembic(path, "downgrade", REVISION_0041)
    assert blocked.returncode != 0
    connection = sqlite3.connect(path)
    try:
        assert connection.execute("SELECT COUNT(*) FROM recipe_version_commands").fetchone() == (1,)
    finally:
        connection.close()
