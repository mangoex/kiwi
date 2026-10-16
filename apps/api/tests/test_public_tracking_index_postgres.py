"""Verify the tracking index is additive and reversible on PostgreSQL and SQLite."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.engine import make_url
from test_driver_cash_settlement_migration import _migrate


def _roundtrip(url: str) -> None:
    _migrate(url, "upgrade", "0096_driver_cash_settlements")
    engine = sa.create_engine(url)
    try:
        with engine.connect() as connection:
            before = connection.execute(sa.text("SELECT COUNT(*) FROM order_events")).scalar_one()
        _migrate(url, "upgrade", "0097_public_tracking_event_index")
        indexes = sa.inspect(engine).get_indexes("order_events")
        index = next(index for index in indexes if index["name"] == "ix_order_events_tracking")
        assert index["column_names"] == ["order_id", "created_at", "id"]
        with engine.connect() as connection:
            after = connection.execute(sa.text("SELECT COUNT(*) FROM order_events")).scalar_one()
            assert after == before
        _migrate(url, "downgrade", "0096_driver_cash_settlements")
        assert "ix_order_events_tracking" not in {
            index["name"] for index in sa.inspect(engine).get_indexes("order_events")
        }
        with engine.connect() as connection:
            after = connection.execute(sa.text("SELECT COUNT(*) FROM order_events")).scalar_one()
            assert after == before
    finally:
        engine.dispose()


def test_tracking_event_index_sqlite_roundtrip(tmp_path: Path) -> None:
    _roundtrip(f"sqlite+pysqlite:///{tmp_path / 'tracking-index.sqlite'}")


def test_tracking_event_index_postgres_roundtrip() -> None:
    raw = os.environ.get("TRACKING_TEST_POSTGRES_URL")
    if not raw:
        pytest.skip("TRACKING_TEST_POSTGRES_URL is required for the PostgreSQL gate")
    url = make_url(raw)
    if (not url.drivername.startswith("postgresql") or url.host not in {"127.0.0.1", "localhost"}
            or not (url.database or "").startswith("tracking_") or url.query):
        raise RuntimeError("Tracking tests require an isolated local tracking_* database")
    _roundtrip(raw)
