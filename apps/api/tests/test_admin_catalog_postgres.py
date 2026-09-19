"""Opt-in PostgreSQL persistence and concurrency coverage for ADMIN-RETRO-001."""

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
from restaurant_os.admin_catalog import (
    apply_bulk_recipe,
    preview_bulk_recipe,
    set_category_priorities,
    set_stock_threshold,
)
from restaurant_os.operations import AuthorizationError, BusinessError
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_admin_catalog import PRODUCT_B, _recipe_payload, _seed_admin_catalog_scope
from test_cash_concepts import OWNER_ID
from test_cash_ledger import BRANCH_A, CASHIER_ID, CASHIER_ROLE_ID
from test_pco007_recipe_reports import ITEM_ID

TEST_URL_ENV = "ADMINRETRO_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]


def _postgres_url() -> str:
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        pytest.skip(f"{TEST_URL_ENV} is required for opt-in PostgreSQL tests")
    parsed = urlparse(url)
    sqlalchemy_url = make_url(url)
    database = sqlalchemy_url.database or ""
    # Query parameters can override host/service details for a PostgreSQL driver;
    # reject them before this fixture drops a schema.
    if parsed.query or sqlalchemy_url.query:
        raise RuntimeError("ADMIN-RETRO PostgreSQL URL must not contain query overrides")
    if not sqlalchemy_url.drivername.startswith("postgresql") or sqlalchemy_url.host not in {
        "localhost",
        "127.0.0.1",
    }:
        raise RuntimeError("ADMIN-RETRO requires a local PostgreSQL URL")
    if not database.startswith("adminretro_test"):
        raise RuntimeError("ADMIN-RETRO requires an isolated adminretro_test* database")
    return url


def _alembic(url: str, revision: str) -> None:
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", revision],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _downgrade(url: str, revision: str) -> None:
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "downgrade", revision],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=40,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def _engine() -> sa.Engine:
    url = _postgres_url()
    reset = create_engine(url, future=True)
    try:
        with reset.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        reset.dispose()
    _alembic(url, "0065_admin_catalog")
    engine = create_engine(url, future=True)
    with engine.begin() as connection:
        tables = connection.execute(
            sa.text(
                "SELECT tablename FROM pg_tables "
                "WHERE schemaname = 'public' AND tablename <> 'alembic_version'"
            )
        ).scalars().all()
        preparer = connection.dialect.identifier_preparer
        quoted = ", ".join(preparer.quote(table) for table in tables)
        connection.execute(sa.text(f"TRUNCATE TABLE {quoted} RESTART IDENTITY CASCADE"))
    return engine


def _seed(engine: sa.Engine) -> None:
    with Session(engine) as session:
        from test_cash_concepts import _seed_cash_concept_scope

        _seed_cash_concept_scope(session)
        _seed_admin_catalog_scope(session)


def test_postgres_url_guard_rejects_driver_query_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        TEST_URL_ENV,
        "postgresql+psycopg://adminretro@127.0.0.1:55432/adminretro_tests?host=remote.example",
    )
    with pytest.raises(RuntimeError, match="query overrides"):
        _postgres_url()


def test_admin_catalog_migration_downgrade_preserves_canonical_recipes() -> None:
    url = _postgres_url()
    engine = _engine()
    try:
        _seed(engine)
        with Session(engine) as session:
            preview = preview_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_B],
                payload=_recipe_payload(),
            )
            expected = {
                row["product_id"]: row["expected_active_recipe_id"]
                for row in preview["destinations"]
            }
            apply_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_B],
                payload=_recipe_payload(),
                preview_fingerprint=preview["fingerprint"],
                expected_active_recipe_ids=expected,
                idempotency_key="adminretro-migration",
            )
        _downgrade(url, "0064_add_branches_google_review_url")
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT count(*) FROM recipes")).scalar_one() == 1
            assert (
                connection.execute(
                    sa.text("SELECT to_regclass('public.admin_recipe_bulk_commands')")
                ).scalar_one()
                is None
            )
        _alembic(url, "0065_admin_catalog")
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT count(*) FROM recipes")).scalar_one() == 1
    finally:
        engine.dispose()


def test_bulk_recipe_same_key_replays_concurrently_on_postgresql() -> None:
    engine = _engine()
    try:
        _seed(engine)
        with Session(engine) as session:
            preview = preview_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_B],
                payload=_recipe_payload(),
            )
        expected = {
            row["product_id"]: row["expected_active_recipe_id"] for row in preview["destinations"]
        }
        barrier = Barrier(2)

        def writer() -> dict[str, object]:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                return apply_bulk_recipe(
                    session,
                    CASHIER_ID,
                    branch_id=BRANCH_A,
                    destination_product_ids=[PRODUCT_B],
                    payload=_recipe_payload(),
                    preview_fingerprint=preview["fingerprint"],
                    expected_active_recipe_ids=expected,
                    idempotency_key="adminretro-concurrent",
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: writer(), range(2)))
        assert first["command_id"] == second["command_id"]
        with Session(engine) as session:
            assert (
                session.execute(
                    sa.select(sa.func.count()).select_from(models.admin_recipe_bulk_commands)
                ).scalar_one()
                == 1
            )
            assert (
                session.execute(sa.select(sa.func.count()).select_from(models.recipes)).scalar_one()
                == 1
            )
    finally:
        engine.dispose()


def test_bulk_recipe_different_keys_have_one_version_winner_on_postgresql() -> None:
    engine = _engine()
    try:
        _seed(engine)
        with Session(engine) as session:
            preview = preview_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_B],
                payload=_recipe_payload(),
            )
        expected = {
            row["product_id"]: row["expected_active_recipe_id"] for row in preview["destinations"]
        }
        barrier = Barrier(2)

        def writer(index: int) -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    apply_bulk_recipe(
                        session,
                        CASHIER_ID,
                        branch_id=BRANCH_A,
                        destination_product_ids=[PRODUCT_B],
                        payload=_recipe_payload(),
                        preview_fingerprint=preview["fingerprint"],
                        expected_active_recipe_ids=expected,
                        idempotency_key=f"adminretro-race-{index}",
                    )
                    return "applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(writer, range(2)))
        assert outcomes == ["applied", "bulk_recipe_version_conflict"]
        with Session(engine) as session:
            recipe_count = session.execute(
                sa.select(sa.func.count()).select_from(models.recipes)
            ).scalar_one()
            assert recipe_count == 1
    finally:
        engine.dispose()


def test_priority_first_write_and_threshold_stale_writer_are_serialized_on_postgresql() -> None:
    engine = _engine()
    try:
        _seed(engine)
        with Session(engine) as session:
            category_ids = [
                str(category_id)
                for category_id in session.execute(
                    sa.select(models.product_categories.c.id).order_by(
                        models.product_categories.c.display_order, models.product_categories.c.id
                    )
                ).scalars()
            ]
            initial = set_stock_threshold(
                session,
                CASHIER_ID,
                BRANCH_A,
                ITEM_ID,
                minimum_quantity="1",
                maximum_quantity="2",
                expected_version=None,
            )
        barrier = Barrier(2)

        def priority_writer() -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    set_category_priorities(
                        session,
                        OWNER_ID,
                        view_category_ids=category_ids,
                        print_category_ids=category_ids,
                        expected_version=0,
                    )
                    return "applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            priority_outcomes = sorted(pool.map(lambda _: priority_writer(), range(2)))
        assert priority_outcomes == ["applied", "category_priorities_version_conflict"]

        barrier = Barrier(2)

        def threshold_writer(index: int) -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    set_stock_threshold(
                        session,
                        CASHIER_ID,
                        BRANCH_A,
                        ITEM_ID,
                        minimum_quantity=str(index + 2),
                        maximum_quantity="5",
                        expected_version=initial["version"],
                    )
                    return "applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            threshold_outcomes = sorted(pool.map(threshold_writer, range(2)))
        assert threshold_outcomes == ["applied", "stock_threshold_version_conflict"]
    finally:
        engine.dispose()


def test_bulk_recipe_replay_requires_current_permission_on_postgresql() -> None:
    engine = _engine()
    try:
        _seed(engine)
        with Session(engine) as session:
            preview = preview_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_B],
                payload=_recipe_payload(),
            )
            expected = {
                row["product_id"]: row["expected_active_recipe_id"]
                for row in preview["destinations"]
            }
            apply_bulk_recipe(
                session,
                CASHIER_ID,
                branch_id=BRANCH_A,
                destination_product_ids=[PRODUCT_B],
                payload=_recipe_payload(),
                preview_fingerprint=preview["fingerprint"],
                expected_active_recipe_ids=expected,
                idempotency_key="adminretro-revoked",
            )
            permission_id = session.execute(
                sa.select(models.permissions.c.id).where(
                    models.permissions.c.code == "recipes.manage"
                )
            ).scalar_one()
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == CASHIER_ROLE_ID,
                    models.role_permissions.c.permission_id == permission_id,
                )
            )
            session.commit()
        with Session(engine) as session:
            with pytest.raises(AuthorizationError):
                apply_bulk_recipe(
                    session,
                    CASHIER_ID,
                    branch_id=BRANCH_A,
                    destination_product_ids=[PRODUCT_B],
                    payload=_recipe_payload(),
                    preview_fingerprint=preview["fingerprint"],
                    expected_active_recipe_ids=expected,
                    idempotency_key="adminretro-revoked",
                )
    finally:
        engine.dispose()
