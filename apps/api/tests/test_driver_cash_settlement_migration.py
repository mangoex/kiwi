"""Forward and empty rollback evidence for driver cash settlement storage."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import sqlalchemy as sa

API_DIR = Path(__file__).resolve().parents[1]
REVISION = "0096_driver_cash_settlements"
PREVIOUS_REVISION = "0095_branch_product_digital_visibility"
TABLES = {
    "driver_cash_settlements",
    "driver_cash_settlement_items",
    "driver_cash_settlement_commands",
}


def _migrate(database_url: str, *arguments: str) -> None:
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": database_url}
    environment.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", *arguments],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_driver_cash_settlement_migration_empty_roundtrip(tmp_path: Path) -> None:
    database_url = f"sqlite+pysqlite:///{tmp_path / 'driver-cash-migration.sqlite'}"
    _migrate(database_url, "upgrade", PREVIOUS_REVISION)
    _migrate(database_url, "upgrade", REVISION)
    engine = sa.create_engine(database_url)
    try:
        assert TABLES <= set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()

    _migrate(database_url, "downgrade", PREVIOUS_REVISION)
    engine = sa.create_engine(database_url)
    try:
        assert not TABLES & set(sa.inspect(engine).get_table_names())
    finally:
        engine.dispose()

    _migrate(database_url, "upgrade", REVISION)
