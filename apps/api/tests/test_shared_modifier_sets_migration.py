"""SQLite roundtrip and downgrade guard for shared modifier sets."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0075_shared_modifier_sets"
PREVIOUS = "0074_dual_physical_counts"
MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "202610072130_0075_shared_modifier_sets.py"
)


def test_shared_modifier_migration_roundtrip_and_data_guard(tmp_path) -> None:
    path = tmp_path / "shared-modifier-sets.db"
    upgraded = _sqlite_alembic(path, "upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(path) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(modifier_groups)")}
        assert "modifier_set_id" in columns
        assert "modifier_sets" in {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
    assert _sqlite_alembic(path, "downgrade", PREVIOUS).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0

    with sqlite3.connect(path) as connection:
        organization_id = connection.execute("SELECT id FROM organizations LIMIT 1").fetchone()[0]
        user_id = connection.execute("SELECT id FROM users LIMIT 1").fetchone()[0]
        connection.execute(
            """
            INSERT INTO modifier_sets (
                id, organization_id, name, version, station, status, updated_by,
                created_at, updated_at
            ) VALUES (?, ?, 'Aderezos', 1, 'kitchen', 'active', ?, ?, ?)
            """,
            (
                "shared-set-1",
                organization_id,
                user_id,
                "2026-10-07T00:00:00+00:00",
                "2026-10-07T00:00:00+00:00",
            ),
        )
        connection.commit()

    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    assert "Cannot downgrade shared modifier sets while shared catalog data exists" in (
        blocked.stdout + blocked.stderr
    )


def test_shared_modifier_migration_locks_before_postgres_downgrade_guard() -> None:
    source = MIGRATION.read_text()
    assert source.index("LOCK TABLE modifier_sets IN ACCESS EXCLUSIVE MODE") < source.index(
        "SELECT 1 FROM modifier_sets LIMIT 1"
    )
