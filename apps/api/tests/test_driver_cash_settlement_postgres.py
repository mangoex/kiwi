"""PostgreSQL concurrency gate for atomic driver cash settlements."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import BusinessError, settle_driver_cash_orders
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _admin_headers, _open_shift, _seed

TEST_URL_ENV = "DRIVER_CASH_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]


def _postgres_url() -> str:
    raw_url = os.environ.get(TEST_URL_ENV)
    if not raw_url:
        pytest.skip(f"{TEST_URL_ENV} is required for the PostgreSQL gate")
    url = make_url(raw_url)
    if url.query:
        raise RuntimeError("Driver-cash PostgreSQL URL must not contain query overrides")
    if not url.drivername.startswith("postgresql") or url.host not in {
        "127.0.0.1",
        "localhost",
    }:
        raise RuntimeError("Driver-cash tests require local PostgreSQL")
    if not (url.database or "").startswith("driver_cash_"):
        raise RuntimeError("Driver-cash tests require an isolated driver_cash_* database")
    return raw_url


def _session_factory() -> tuple[sa.Engine, sessionmaker[Session]]:
    url = _postgres_url()
    reset_engine = create_engine(url, future=True)
    try:
        with reset_engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        reset_engine.dispose()
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    environment.pop("DATABASE_URL", None)
    migration = subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "alembic.ini", "upgrade", "head"],
        cwd=API_DIR,
        env=environment,
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert migration.returncode == 0, migration.stdout + migration.stderr
    engine = create_engine(
        url,
        future=True,
        connect_args={"options": "-cstatement_timeout=15000 -clock_timeout=5000"},
    )
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        _seed(session)
    return engine, factory


def test_competing_driver_settlements_have_one_atomic_winner_on_postgresql() -> None:
    engine, factory = _session_factory()
    app = create_app()

    def scoped_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = scoped_session
    client = TestClient(app)
    try:
        driver_response = client.post(
            "/api/v1/drivers",
            headers=_admin_headers(),
            json={
                "employee_code": "DRPG01",
                "name": "Repartidor PostgreSQL",
                "license_number": "LIC-DRIVER-CASH-PG",
                "motorcycle_plate": "PG-001",
                "branch_id": BRANCH_ID,
                "phone": "6691000091",
                "address": "Base Centro",
                "emergency_contact_name": "Contacto",
            },
        )
        assert driver_response.status_code == 200
        driver = driver_response.json()
        customer_response = client.post(
            "/api/v1/customers",
            headers=_admin_headers(),
            json={
                "branch_id": BRANCH_ID,
                "name": "Cliente PostgreSQL",
                "phones": [{"number": "6691000092", "is_primary": True}],
            },
        )
        assert customer_response.status_code == 200
        customer = customer_response.json()
        address_response = client.post(
            f"/api/v1/customers/{customer['id']}/addresses",
            headers=_admin_headers(),
            json={
                "branch_id": BRANCH_ID,
                "alias": "Casa",
                "street": "Calle PostgreSQL",
                "exterior_number": "10",
                "neighborhood": "Centro",
                "postal_code": "82000",
                "city": "Mazatlán",
                "municipality": "Mazatlán",
                "state": "Sinaloa",
                "is_default": True,
            },
        )
        assert address_response.status_code == 200
        address = address_response.json()
        assert _open_shift(client, 50000).status_code == 200

        order_ids: list[str] = []
        for index in range(2):
            order_response = client.post(
                "/api/v1/orders",
                headers={
                    **_admin_headers(),
                    "Idempotency-Key": f"driver-cash-pg-order-{index:04d}",
                },
                json={
                    "branch_id": BRANCH_ID,
                    "order_type": "delivery",
                    "payment_method_intent": "cash",
                    "customer_id": customer["id"],
                    "delivery_address_id": address["id"],
                    "driver_id": driver["id"],
                    "lines": [
                        {
                            "product_id": "018f6f73-2d0a-74f0-8f1c-000000000111",
                            "quantity": index + 1,
                        }
                    ],
                },
            )
            assert order_response.status_code == 200
            order_ids.append(order_response.json()["id"])

        barrier = Barrier(2)

        def settle(key: str) -> tuple[str, str]:
            with factory() as session:
                barrier.wait(timeout=5)
                try:
                    result = settle_driver_cash_orders(
                        session,
                        branch_id=BRANCH_ID,
                        driver_id=driver["id"],
                        order_ids=order_ids,
                        register_id="CAJA-01",
                        idempotency_key=key,
                        actor_user_id=ADMIN_USER_ID,
                    )
                    return "confirmed", result["id"]
                except BusinessError as exc:
                    session.rollback()
                    return "rejected", exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [
                pool.submit(settle, "driver-cash-pg-settlement-0001"),
                pool.submit(settle, "driver-cash-pg-settlement-0002"),
            ]
            outcomes = [future.result(timeout=30) for future in futures]

        assert [status for status, _ in outcomes].count("confirmed") == 1
        assert ("rejected", "driver_settlement_order_ineligible") in outcomes
        with factory() as session:
            assert session.scalar(
                sa.select(sa.func.count()).select_from(models.driver_cash_settlements)
            ) == 1
            assert session.scalar(
                sa.select(sa.func.count()).select_from(models.driver_cash_settlement_items)
            ) == 2
            assert session.scalar(sa.select(sa.func.count()).select_from(models.payments)) == 2
            assert session.scalar(
                sa.select(sa.func.count()).select_from(models.driver_cash_settlement_commands)
            ) == 1
    finally:
        client.close()
        engine.dispose()
