from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = (
    ROOT
    / "apps/api/alembic/versions/202610151030_0094_purchase_delivery_details.py"
)


def _migration():
    spec = importlib.util.spec_from_file_location("purchase_delivery_details_migration", MIGRATION)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_delivery_name_migration_is_additive_and_blocks_destructive_downgrade(tmp_path):
    engine = sa.create_engine(f"sqlite+pysqlite:///{tmp_path / 'delivery.db'}")
    with engine.begin() as connection:
        connection.execute(sa.text("CREATE TABLE purchase_documents (id VARCHAR(36) PRIMARY KEY)"))
        module = _migration()
        module.op = Operations(MigrationContext.configure(connection))

        module.upgrade()
        columns = {
            column["name"]: column
            for column in sa.inspect(connection).get_columns("purchase_documents")
        }
        assert columns["delivered_by_name"]["type"].length == 160
        assert columns["delivered_by_name"]["nullable"] is True

        connection.execute(
            sa.text(
                "INSERT INTO purchase_documents (id, delivered_by_name) "
                "VALUES ('purchase-1', 'Ana López')"
            )
        )
        with pytest.raises(RuntimeError, match="delivery names exist"):
            module.downgrade()

        connection.execute(
            sa.text("UPDATE purchase_documents SET delivered_by_name = NULL")
        )
        module.downgrade()
        assert "delivered_by_name" not in {
            column["name"] for column in sa.inspect(connection).get_columns("purchase_documents")
        }
