"""POS appearance additive migration and downgrade guard."""

import sqlite3
from pathlib import Path

from test_cash_ledger_migration import _sqlite_alembic

REVISION = "0073_pos_catalog_appearance"
PREVIOUS = "0072_purchase_create_commands"
MIGRATION = (
    Path(__file__).parents[1]
    / "alembic"
    / "versions"
    / "202610030900_0073_pos_catalog_appearance.py"
)


def test_pos_catalog_appearance_postgres_downgrade_excludes_concurrent_writers():
    source = MIGRATION.read_text()
    lock = source.index("LOCK TABLE branches IN ACCESS EXCLUSIVE MODE")
    guard = source.index("WHERE pos_catalog_visuals_enabled = false")
    drop = source.index('op.drop_column("branches", "pos_catalog_visuals_enabled")')
    assert lock < guard < drop


def test_pos_catalog_appearance_roundtrip_and_false_downgrade_guard(tmp_path):
    path = tmp_path / "pos-catalog-appearance.db"
    upgraded = _sqlite_alembic(path, "upgrade", REVISION)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    with sqlite3.connect(path) as connection:
        value = connection.execute(
            "SELECT pos_catalog_visuals_enabled FROM branches LIMIT 1"
        ).fetchone()[0]
        assert value == 1
    assert _sqlite_alembic(path, "downgrade", PREVIOUS).returncode == 0
    assert _sqlite_alembic(path, "upgrade", REVISION).returncode == 0
    with sqlite3.connect(path) as connection:
        connection.execute("UPDATE branches SET pos_catalog_visuals_enabled = 0")
    blocked = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert blocked.returncode != 0
    output = blocked.stdout + blocked.stderr
    assert "Cannot downgrade 0073 while hidden catalog visuals are configured" in output
