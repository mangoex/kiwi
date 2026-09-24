"""Opt-in PostgreSQL concurrency evidence for selectable compound products."""

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
from restaurant_os.modifier_configuration import save_modifier_configuration
from restaurant_os.operations import BusinessError
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_platform_api import ADMIN_USER_ID, _seed

TEST_URL_ENV = "COMPOUND_PRODUCTS_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]
REVISION = "0069_selectable_compound_product"
PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"


def _postgres_url() -> str:
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        pytest.skip(f"{TEST_URL_ENV} is required for opt-in PostgreSQL tests")
    parsed = urlparse(url)
    sqlalchemy_url = make_url(url)
    if parsed.query or sqlalchemy_url.query:
        raise RuntimeError("Compound-product PostgreSQL URL must not contain query overrides")
    if not sqlalchemy_url.drivername.startswith("postgresql") or sqlalchemy_url.host not in {
        "localhost",
        "127.0.0.1",
    }:
        raise RuntimeError("Compound-product PostgreSQL requires a local PostgreSQL URL")
    if not (sqlalchemy_url.database or "").startswith("compound_products_test"):
        raise RuntimeError(
            "Compound-product PostgreSQL requires an isolated compound_products_test* database"
        )
    return url


def _engine() -> sa.Engine:
    url = _postgres_url()
    reset = create_engine(url, future=True)
    try:
        with reset.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        reset.dispose()
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", REVISION],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )
    assert migration.returncode == 0, migration.stdout + migration.stderr
    engine = create_engine(url, future=True)
    with Session(engine) as session:
        _seed(session)
    return engine


def _payload() -> dict[str, object]:
    return {
        "expected_version": 0,
        "groups": [
            {
                "name": "Preparación",
                "minimum_selections": 0,
                "maximum_selections": 1,
                "included_selections": 0,
                "options": [
                    {
                        "name": "Sin cebolla",
                        "effect_type": "instruction",
                        "price_delta_cents": 0,
                        "kitchen_text": "SIN CEBOLLA",
                    }
                ],
            }
        ],
    }


def test_same_key_replays_concurrently_on_postgresql() -> None:
    engine = _engine()
    try:
        barrier = Barrier(2)

        def writer() -> dict[str, object]:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                return save_modifier_configuration(
                    session,
                    ADMIN_USER_ID,
                    PRODUCT_ID,
                    _payload(),
                    "compound-products-postgres-same",
                )

        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(lambda _: writer(), range(2)))
        assert {str(first["result"]), str(second["result"])} == {"applied", "replay"}
        assert first["version"] == second["version"] == 1
        with Session(engine) as session:
            assert (
                session.scalar(
                    sa.select(sa.func.count()).select_from(models.modifier_configuration_commands)
                )
                == 1
            )
    finally:
        engine.dispose()


def test_different_keys_have_one_version_winner_on_postgresql() -> None:
    engine = _engine()
    try:
        barrier = Barrier(2)

        def writer(index: int) -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    save_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        PRODUCT_ID,
                        _payload(),
                        f"compound-products-postgres-race-{index}",
                    )
                    return "applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = sorted(pool.map(writer, range(2)))
        assert outcomes == ["applied", "modifier_configuration_version_conflict"]
        with Session(engine) as session:
            assert (
                session.scalar(
                    sa.select(models.product_modifier_configurations.c.version).where(
                        models.product_modifier_configurations.c.product_id == PRODUCT_ID
                    )
                )
                == 1
            )
    finally:
        engine.dispose()


def test_fixed_and_selectable_writers_cannot_both_win_on_postgresql() -> None:
    engine = _engine()
    try:
        barrier = Barrier(2)

        def selectable_writer() -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    save_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        PRODUCT_ID,
                        _payload(),
                        "compound-products-postgres-mode-selectable",
                    )
                    return "selectable-applied"
                except BusinessError as error:
                    return error.code

        def fixed_writer() -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    save_composition(
                        session,
                        ADMIN_USER_ID,
                        PRODUCT_ID,
                        None,
                        expected_version=0,
                        idempotency_key="compound-products-postgres-mode-fixed",
                        components=[
                            {
                                "product_id": "018f6f73-2d0a-74f0-8f1c-000000000112",
                                "quantity": "1",
                            }
                        ],
                    )
                    return "fixed-applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            selectable_future = pool.submit(selectable_writer)
            fixed_future = pool.submit(fixed_writer)
            outcomes = {selectable_future.result(), fixed_future.result()}
        assert outcomes in (
            {"selectable-applied", "combo_selectable_configuration_conflict"},
            {"fixed-applied", "modifier_component_nested"},
        )
        with Session(engine) as session:
            has_selectable = bool(
                session.scalar(
                    sa.select(models.modifier_groups.c.id).where(
                        models.modifier_groups.c.product_id == PRODUCT_ID,
                        models.modifier_groups.c.status == "active",
                    )
                )
            )
            has_fixed = bool(
                session.scalar(
                    sa.select(models.product_compositions.c.id).where(
                        models.product_compositions.c.combo_product_id == PRODUCT_ID,
                        models.product_compositions.c.status == "active",
                    )
                )
            )
            assert has_selectable != has_fixed
    finally:
        engine.dispose()


def test_referenced_component_and_its_fixed_composition_cannot_both_win() -> None:
    engine = _engine()
    fries_id = "018f6f73-2d0a-74f0-8f1c-000000000112"
    soda_id = "018f6f73-2d0a-74f0-8f1c-000000000113"
    try:
        barrier = Barrier(2)
        selectable_payload = {
            "expected_version": 0,
            "groups": [
                {
                    "name": "Acompañamiento",
                    "minimum_selections": 1,
                    "maximum_selections": 1,
                    "included_selections": 1,
                    "options": [
                        {
                            "name": "Papas",
                            "effect_type": "product_component",
                            "component_product_id": fries_id,
                            "component_quantity": "1",
                            "price_delta_cents": 0,
                        }
                    ],
                }
            ],
        }

        def parent_writer() -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    save_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        PRODUCT_ID,
                        selectable_payload,
                        "compound-products-postgres-reference-component",
                    )
                    return "selectable-applied"
                except BusinessError as error:
                    return error.code

        def component_writer() -> str:
            with Session(engine) as session:
                barrier.wait(timeout=10)
                try:
                    save_composition(
                        session,
                        ADMIN_USER_ID,
                        fries_id,
                        None,
                        expected_version=0,
                        idempotency_key="compound-products-postgres-component-fixed",
                        components=[{"product_id": soda_id, "quantity": "1"}],
                    )
                    return "fixed-applied"
                except BusinessError as error:
                    return error.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            parent_future = pool.submit(parent_writer)
            component_future = pool.submit(component_writer)
            outcomes = {parent_future.result(), component_future.result()}
        assert outcomes in (
            {"selectable-applied", "combo_component_nested"},
            {"fixed-applied", "modifier_component_nested"},
        )
        with Session(engine) as session:
            has_reference = bool(
                session.scalar(
                    sa.select(models.modifier_options.c.id).where(
                        models.modifier_options.c.component_product_id == fries_id,
                        models.modifier_options.c.status == "active",
                    )
                )
            )
            has_fixed = bool(
                session.scalar(
                    sa.select(models.product_compositions.c.id).where(
                        models.product_compositions.c.combo_product_id == fries_id,
                        models.product_compositions.c.status == "active",
                    )
                )
            )
            assert has_reference != has_fixed
    finally:
        engine.dispose()
