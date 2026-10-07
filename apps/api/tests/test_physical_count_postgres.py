"""PostgreSQL concurrency gate for the physical-count inventory lock protocol."""

from __future__ import annotations

import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from restaurant_os.operations import _acquire_inventory_advisory_locks
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

TEST_URL_ENV = "PHYSICAL_COUNT_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]


def _postgres_url() -> str:
    raw_url = os.environ.get(TEST_URL_ENV)
    if not raw_url:
        pytest.skip(f"{TEST_URL_ENV} is required for opt-in PostgreSQL tests")
    parsed = urlparse(raw_url)
    url = make_url(raw_url)
    database = url.database or ""
    if parsed.query or url.query:
        raise RuntimeError("Physical-count PostgreSQL URL must not contain query overrides")
    if not url.drivername.startswith("postgresql") or url.host not in {
        "127.0.0.1",
        "localhost",
    }:
        raise RuntimeError("Physical-count tests require local PostgreSQL")
    if not database.startswith("physical_count_"):
        raise RuntimeError("Physical-count tests require an isolated physical_count_* database")
    return raw_url


def _engine() -> sa.Engine:
    url = _postgres_url()
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    return create_engine(url, future=True)


def test_inventory_advisory_lock_sets_serialize_without_deadlock() -> None:
    engine = _engine()
    barrier = Barrier(2)

    def run(item_ids: list[str]) -> tuple[float, float]:
        with Session(engine) as session:
            barrier.wait(timeout=5)
            _acquire_inventory_advisory_locks(
                session,
                "physical-count-branch",
                "physical-count-warehouse",
                item_ids,
            )
            acquired_at = time.monotonic()
            session.execute(sa.text("SELECT pg_sleep(0.2)"))
            session.commit()
            return acquired_at, time.monotonic()

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first = pool.submit(run, ["item-b", "item-a", "item-b"])
            second = pool.submit(run, ["item-a", "item-b"])
            intervals = [first.result(timeout=8), second.result(timeout=8)]
    finally:
        engine.dispose()

    earlier, later = sorted(intervals)
    assert later[0] - earlier[0] >= 0.15
