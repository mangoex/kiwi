from __future__ import annotations

import importlib.util
from datetime import datetime, timezone
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "apps/api/alembic/versions/202610152300_0095_branch_product_digital_visibility.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location(
        "branch_product_digital_visibility_migration", MIGRATION
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_digital_visibility_migration_is_separate_and_blocks_data_loss(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'digital-visibility.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("PRAGMA foreign_keys = ON"))
        connection.execute(sa.text("CREATE TABLE branches (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(sa.text("CREATE TABLE products (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(sa.text("INSERT INTO branches (id) VALUES ('branch-1')"))
        connection.execute(sa.text("INSERT INTO products (id) VALUES ('product-1')"))
        module = _migration()
        module.op = Operations(MigrationContext.configure(connection))

        module.upgrade()
        table = sa.Table(
            "branch_product_digital_visibility",
            sa.MetaData(),
            autoload_with=connection,
        )
        assert [column.name for column in table.primary_key.columns] == [
            "branch_id",
            "product_id",
        ]
        assert table.c.is_visible.nullable is False

        connection.execute(
            table.insert().values(
                branch_id="branch-1",
                product_id="product-1",
                is_visible=False,
                updated_at=datetime(2026, 10, 16, 5, 0, tzinfo=timezone.utc),
            )
        )
        with pytest.raises(RuntimeError, match="digital visibility exclusions exist"):
            module.downgrade()

        connection.execute(table.delete())
        module.downgrade()
        assert not sa.inspect(connection).has_table("branch_product_digital_visibility")
