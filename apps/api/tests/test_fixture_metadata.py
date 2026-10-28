"""Cross-dialect DDL must preserve the accepted-intent foreign key in SQLite."""

import sqlalchemy as sa
from fixture_metadata import create_fixture_tables
from restaurant_os import models
from sqlalchemy.dialects import sqlite


def test_postgres_fixture_preserves_shared_sqlite_constraints() -> None:
    before = str(sa.schema.CreateTable(models.orders).compile(dialect=sqlite.dialect()))
    create_fixture_tables(sa.create_mock_engine("postgresql://", lambda *a, **kw: None))
    after = str(sa.schema.CreateTable(models.orders).compile(dialect=sqlite.dialect()))
    assert "fk_orders_public_order_intent_accepted" in before
    assert after == before
