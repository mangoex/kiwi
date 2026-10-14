"""0087 additive SQLite migration and history guard with a real prepared intention."""

import importlib.util
import shutil
import sqlite3
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from restaurant_os import models
from test_fiscal_command_preparation import _prepare, _ready
from test_fiscal_command_preparation import fiscal_data as fiscal_data
from test_fiscal_command_preparation import test_db as test_db
from test_fiscal_emitter_migration import _sqlite_alembic
from test_fiscal_emitter_migration import baseline as baseline

REVISION = "0087_fiscal_commands"
PREVIOUS = "0086_fiscal_emitters"


def test_additive_migration_preserves_legacy_and_empty_downgrade(baseline, tmp_path):
    path = tmp_path / "fiscal-command.db"
    shutil.copyfile(baseline, path)
    with sqlite3.connect(path) as connection:
        original = connection.execute("SELECT * FROM cfdi_invoices").fetchall()
        legacy = connection.execute("SELECT * FROM facturapi_config").fetchall()
    for target in (PREVIOUS, REVISION):
        result = _sqlite_alembic(path, "upgrade", target)
        assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        # 0086 adds nullable origin fields; 0087 does not rewrite the legacy portion.
        current = connection.execute("SELECT * FROM cfdi_invoices").fetchall()
        assert [row[: len(original[0])] for row in current] == original
        assert connection.execute("SELECT * FROM facturapi_config").fetchall() == legacy
        for table in (
            models.fiscal_commands,
            models.fiscal_command_orders,
            models.fiscal_order_reservations,
            models.fiscal_command_outbox,
        ):
            names = {row[1] for row in connection.execute(f"PRAGMA table_info({table.name})")}
            assert names == set(table.c.keys())
        assert connection.execute("SELECT count(*) FROM fiscal_commands").fetchone()[0] == 0
    result = _sqlite_alembic(path, "downgrade", PREVIOUS)
    assert result.returncode == 0, result.stdout + result.stderr
    with sqlite3.connect(path) as connection:
        assert (
            connection.execute("SELECT version_num FROM alembic_version").fetchone()[0] == PREVIOUS
        )
        assert connection.execute("SELECT * FROM facturapi_config").fetchall() == legacy


def test_history_blocks_downgrade_before_any_table_change(fiscal_data, monkeypatch):
    session, _, _ = _ready(fiscal_data)
    _prepare(session)
    session.rollback()
    path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/202610140300_0087_fiscal_commands.py"
    )
    spec = importlib.util.spec_from_file_location("fiscal_commands_migration", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with session.get_bind().begin() as connection:
        before = dict(connection.execute(sa.select(models.fiscal_commands)).mappings().one())
        monkeypatch.setattr(module, "op", Operations(MigrationContext.configure(connection)))
        with pytest.raises(RuntimeError, match="0087 downgrade blocked"):
            module.downgrade()
        assert (
            dict(connection.execute(sa.select(models.fiscal_commands)).mappings().one()) == before
        )
        assert (
            connection.scalar(sa.select(sa.func.count()).select_from(models.fiscal_command_outbox))
            == 1
        )
