"""Opt-in PostgreSQL concurrency and irreversible-history evidence for combos."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.combo import save_composition
from restaurant_os.operations import BusinessError
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_cash_concepts import _seed_cash_concept_scope
from test_cash_ledger import _insert_shift
from test_combo_compositions import (
    ACTOR,
    BURGER,
    COMBO,
    DRINK,
    _seed,
    _seed_combo_recipes_and_order_scope,
)

TEST_URL_ENV = "COMBOS_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]
REVISION = "0066_combo_compositions"
CURRENT_TEST_REVISION = "0067_offline_orders"
PREVIOUS = "0065_admin_catalog"


def _postgres_url() -> str:
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        pytest.skip(f"{TEST_URL_ENV} is required for opt-in PostgreSQL tests")
    parsed = urlparse(url)
    sqlalchemy_url = make_url(url)
    if parsed.query or sqlalchemy_url.query:
        raise RuntimeError("Combo PostgreSQL URL must not contain query overrides")
    if not sqlalchemy_url.drivername.startswith("postgresql") or sqlalchemy_url.host not in {
        "localhost",
        "127.0.0.1",
    }:
        raise RuntimeError("Combo PostgreSQL requires a local PostgreSQL URL")
    database = sqlalchemy_url.database or ""
    if not database.startswith("combo_test"):
        raise RuntimeError("Combo PostgreSQL requires an isolated combo_test* database")
    return url


def _alembic(url: str, command: str, revision: str) -> subprocess.CompletedProcess[str]:
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", command, revision],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )


def _engine() -> sa.Engine:
    url = _postgres_url()
    reset = create_engine(url, future=True)
    try:
        with reset.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        reset.dispose()
    result = _alembic(url, "upgrade", CURRENT_TEST_REVISION)
    assert result.returncode == 0, result.stdout + result.stderr
    engine = create_engine(url, future=True)
    with engine.begin() as connection:
        tables = (
            connection.execute(
                sa.text(
                    "SELECT tablename FROM pg_tables "
                    "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
                )
            )
            .scalars()
            .all()
        )
        preparer = connection.dialect.identifier_preparer
        quoted_tables = ", ".join(preparer.quote(table) for table in tables)
        connection.execute(sa.text(f"TRUNCATE TABLE {quoted_tables} RESTART IDENTITY CASCADE"))
    return engine


def _seed_scope(engine: sa.Engine, *, recipes: bool = False) -> None:
    with Session(engine) as session:
        _seed_cash_concept_scope(session)
        _insert_shift(session)
        _seed(session)
        if recipes:
            _seed_combo_recipes_and_order_scope(session)


def test_combo_same_key_replays_concurrently_on_postgresql() -> None:
    engine = _engine()
    try:
        _seed_scope(engine)
        barrier = Barrier(2)

        def writer() -> dict[str, object]:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                return save_composition(
                    session,
                    ACTOR,
                    COMBO,
                    None,
                    expected_version=0,
                    idempotency_key="combo-postgres-concurrent",
                    components=[{"product_id": BURGER, "quantity": "1"}],
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: writer(), range(2)))
        assert first["id"] == second["id"]
        with Session(engine) as session:
            assert (
                session.execute(
                    sa.select(sa.func.count()).select_from(models.product_composition_commands)
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_combo_different_keys_have_one_version_winner_on_postgresql() -> None:
    engine = _engine()
    try:
        _seed_scope(engine)
        barrier = Barrier(2)

        def writer(index: int) -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    save_composition(
                        session,
                        ACTOR,
                        COMBO,
                        None,
                        expected_version=0,
                        idempotency_key=f"combo-postgres-race-{index}",
                        components=[{"product_id": BURGER, "quantity": "1"}],
                    )
                    return "applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(writer, range(2)))
        assert outcomes == ["applied", "combo_composition_version_conflict"]
        with Session(engine) as session:
            assert (
                session.execute(
                    sa.select(sa.func.count()).select_from(models.product_compositions)
                ).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_combo_postgres_downgrade_blocks_accepted_snapshot_history() -> None:
    from restaurant_os.operations import create_local_order

    url = _postgres_url()
    engine = _engine()
    try:
        _seed_scope(engine, recipes=True)
        with Session(engine) as session:
            save_composition(
                session,
                ACTOR,
                COMBO,
                None,
                expected_version=0,
                idempotency_key="combo-postgres-history",
                components=[
                    {"product_id": BURGER, "quantity": "1"},
                    {"product_id": DRINK, "quantity": "1"},
                ],
            )
            create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="combo-postgres-order",
            )
        # Alembic needs an exclusive DDL lock while proving the downgrade
        # guard; dispose the pool so this test does not block its own command.
        engine.dispose()
        blocked = _alembic(url, "downgrade", PREVIOUS)
        assert blocked.returncode != 0
        assert "Cannot downgrade 0066 while combo order snapshots exist" in (
            blocked.stdout + blocked.stderr
        )
        check = create_engine(url, future=True)
        try:
            with check.connect() as connection:
                assert (
                    connection.execute(
                        sa.text("SELECT count(*) FROM order_line_component_snapshots")
                    ).scalar_one()
                    == 2
                )
        finally:
            check.dispose()
    finally:
        engine.dispose()
