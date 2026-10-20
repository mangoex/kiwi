"""PostgreSQL concurrency gate for immutable first driver assignment."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeoutError
from pathlib import Path
from threading import Barrier, Event

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BusinessError,
    accept_public_order_intent,
    assign_delivery_driver,
    create_driver,
    create_public_order_intent,
    fulfill_order,
)
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _seed

TEST_URL_ENV = "DELIVERY_ASSIGNMENT_TEST_POSTGRES_URL"
API_DIR = Path(__file__).resolve().parents[1]
PUBLIC_KEY = "pk_delivery_assignment_postgres"
PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"


def _postgres_factory() -> tuple[sa.Engine, sessionmaker[Session]]:
    raw_url = os.environ.get(TEST_URL_ENV)
    if not raw_url:
        pytest.skip(f"{TEST_URL_ENV} is required for the PostgreSQL gate")
    url = make_url(raw_url)
    if url.query:
        raise RuntimeError("Delivery-assignment PostgreSQL URL must not contain query overrides")
    if not url.drivername.startswith("postgresql") or url.host not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Delivery-assignment tests require local PostgreSQL")
    if not (url.database or "").startswith("delivery_assignment_"):
        raise RuntimeError(
            "Delivery-assignment tests require an isolated delivery_assignment_* database"
        )
    reset_engine = create_engine(raw_url, future=True)
    try:
        with reset_engine.begin() as connection:
            connection.execute(sa.text("DROP SCHEMA public CASCADE"))
            connection.execute(sa.text("CREATE SCHEMA public"))
    finally:
        reset_engine.dispose()
    environment = {**os.environ, "RESTAURANTOS_DATABASE_URL": raw_url}
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
        raw_url,
        future=True,
        connect_args={"options": "-cstatement_timeout=15000 -clock_timeout=5000"},
    )
    # Migrations bootstrap organization and permission rows. The deterministic
    # fixture must start empty, while keeping Alembic's schema revision intact.
    with engine.begin() as connection:
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        _seed(session)
    return engine, factory


def _driver_values(code: str, name: str) -> dict[str, str]:
    return {
        "employee_code": code,
        "name": name,
        "license_number": f"LIC-{code}",
        "motorcycle_plate": f"PG-{code}",
        "phone": "6691234567",
        "address": "Base PostgreSQL",
        "emergency_contact_name": "Contacto PostgreSQL",
    }


def test_competing_first_assignments_have_one_winner_on_postgresql() -> None:
    engine, factory = _postgres_factory()
    try:
        with factory() as session:
            first = create_driver(
                session,
                BRANCH_ID,
                _driver_values("DAP001", "Repartidor PostgreSQL Uno"),
                ADMIN_USER_ID,
            )
            second = create_driver(
                session,
                BRANCH_ID,
                _driver_values("DAP002", "Repartidor PostgreSQL Dos"),
                ADMIN_USER_ID,
            )
            session.execute(
                models.public_order_keys.insert().values(
                    public_key=PUBLIC_KEY,
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    branch_id=BRANCH_ID,
                    status="active",
                )
            )
            session.commit()
            captured, _ = create_public_order_intent(
                session,
                PUBLIC_KEY,
                {
                    "customer_name": "Cliente PostgreSQL",
                    "customer_phone": "+526691234567",
                    "order_type": "delivery",
                    "delivery_address": {"address_text": "Calle PostgreSQL 10"},
                    "lines": [{"product_id": PRODUCT_ID, "quantity": 1}],
                },
                "delivery-assignment-pg-create-001",
            )
            intent_id = str(
                session.execute(
                    sa.select(models.public_order_intents.c.id).where(
                        models.public_order_intents.c.public_reference
                        == captured["public_reference"]
                    )
                ).scalar_one()
            )
            accepted, _ = accept_public_order_intent(
                session,
                intent_id,
                1,
                "delivery-assignment-pg-accept-001",
                ADMIN_USER_ID,
            )
            order_id = accepted["id"]

        barrier = Barrier(2)

        def assign(driver_id: str) -> tuple[str, str]:
            with factory() as session:
                barrier.wait(timeout=5)
                try:
                    result = assign_delivery_driver(
                        session,
                        order_id,
                        driver_id,
                        ADMIN_USER_ID,
                    )
                    return "assigned", str(result["driver_id"])
                except BusinessError as exc:
                    session.rollback()
                    return "rejected", exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = [
                future.result(timeout=30)
                for future in (
                    pool.submit(assign, first["id"]),
                    pool.submit(assign, second["id"]),
                )
            ]

        assert [status for status, _ in outcomes].count("assigned") == 1
        assert ("rejected", "delivery_assignment_conflict") in outcomes
        with factory() as session:
            assert session.scalar(
                sa.select(sa.func.count()).select_from(models.delivery_assignments)
            ) == 1
            assert session.scalar(
                sa.select(sa.func.count())
                .select_from(models.order_events)
                .where(models.order_events.c.event_type == "DRIVER_ASSIGNED")
            ) == 1
            assert session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "delivery.driver_assigned")
            ) == 1
    finally:
        engine.dispose()


def test_assignment_rechecks_driver_after_concurrent_deactivation() -> None:
    engine, factory = _postgres_factory()
    try:
        with factory() as session:
            driver = create_driver(
                session,
                BRANCH_ID,
                _driver_values("DAP003", "Repartidor PostgreSQL Bloqueado"),
                ADMIN_USER_ID,
            )
            session.execute(
                models.public_order_keys.insert().values(
                    public_key=PUBLIC_KEY,
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    branch_id=BRANCH_ID,
                    status="active",
                )
            )
            session.commit()
            captured, _ = create_public_order_intent(
                session,
                PUBLIC_KEY,
                {
                    "customer_name": "Cliente PostgreSQL Bloqueo",
                    "customer_phone": "+526691234568",
                    "order_type": "delivery",
                    "delivery_address": {"address_text": "Calle PostgreSQL 11"},
                    "lines": [{"product_id": PRODUCT_ID, "quantity": 1}],
                },
                "delivery-assignment-pg-lock-create-001",
            )
            intent_id = str(
                session.execute(
                    sa.select(models.public_order_intents.c.id).where(
                        models.public_order_intents.c.public_reference
                        == captured["public_reference"]
                    )
                ).scalar_one()
            )
            accepted, _ = accept_public_order_intent(
                session,
                intent_id,
                1,
                "delivery-assignment-pg-lock-accept-001",
                ADMIN_USER_ID,
            )
            order_id = accepted["id"]

        started = Event()

        def assign_while_deactivation_is_uncommitted() -> tuple[str, str]:
            with factory() as session:
                started.set()
                try:
                    result = assign_delivery_driver(
                        session,
                        order_id,
                        driver["id"],
                        ADMIN_USER_ID,
                    )
                    return "assigned", str(result["driver_id"])
                except BusinessError as exc:
                    session.rollback()
                    return "rejected", exc.code

        with factory() as deactivation_session:
            deactivation_session.execute(
                models.drivers.update()
                .where(models.drivers.c.id == driver["id"])
                .values(status="inactive")
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(assign_while_deactivation_is_uncommitted)
                assert started.wait(timeout=5)
                with pytest.raises(FutureTimeoutError):
                    future.result(timeout=1)
                deactivation_session.commit()
                outcome = future.result(timeout=15)

        assert outcome == ("rejected", "delivery_driver_unavailable")
        with factory() as session:
            assert session.scalar(
                sa.select(sa.func.count()).select_from(models.delivery_assignments)
            ) == 0
            assert session.scalar(
                sa.select(sa.func.count())
                .select_from(models.order_events)
                .where(models.order_events.c.event_type == "DRIVER_ASSIGNED")
            ) == 0
            assert session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "delivery.driver_assigned")
            ) == 0
    finally:
        engine.dispose()


def test_assignment_and_dispatch_use_a_consistent_postgresql_lock_order() -> None:
    engine, factory = _postgres_factory()
    try:
        with factory() as session:
            driver = create_driver(
                session,
                BRANCH_ID,
                _driver_values("DAP004", "Repartidor PostgreSQL Despacho"),
                ADMIN_USER_ID,
            )
            session.execute(
                models.public_order_keys.insert().values(
                    public_key=PUBLIC_KEY,
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    branch_id=BRANCH_ID,
                    status="active",
                )
            )
            session.commit()
            captured, _ = create_public_order_intent(
                session,
                PUBLIC_KEY,
                {
                    "customer_name": "Cliente PostgreSQL Despacho",
                    "customer_phone": "+526691234569",
                    "order_type": "delivery",
                    "delivery_address": {"address_text": "Calle PostgreSQL 12"},
                    "lines": [{"product_id": PRODUCT_ID, "quantity": 1}],
                },
                "delivery-assignment-pg-dispatch-create-001",
            )
            intent_id = str(
                session.execute(
                    sa.select(models.public_order_intents.c.id).where(
                        models.public_order_intents.c.public_reference
                        == captured["public_reference"]
                    )
                ).scalar_one()
            )
            accepted, _ = accept_public_order_intent(
                session,
                intent_id,
                1,
                "delivery-assignment-pg-dispatch-accept-001",
                ADMIN_USER_ID,
            )
            order_id = accepted["id"]
            session.execute(
                models.orders.update()
                .where(models.orders.c.id == order_id)
                .values(status="READY")
            )
            session.commit()

        started = Event()

        def assign_during_dispatch() -> tuple[str, str]:
            with factory() as session:
                started.set()
                try:
                    result = assign_delivery_driver(
                        session,
                        order_id,
                        driver["id"],
                        ADMIN_USER_ID,
                    )
                    return "assigned", str(result["driver_id"])
                except BusinessError as exc:
                    session.rollback()
                    return "rejected", exc.code

        with factory() as dispatch_session:
            dispatch_session.scalar(
                sa.select(models.branches.c.id)
                .where(models.branches.c.id == BRANCH_ID)
                .with_for_update()
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(assign_during_dispatch)
                assert started.wait(timeout=5)
                with pytest.raises(FutureTimeoutError):
                    future.result(timeout=1)
                dispatched = fulfill_order(
                    dispatch_session,
                    order_id,
                    "start_delivery",
                    "delivery-assignment-pg-dispatch-001",
                    ADMIN_USER_ID,
                    commit=False,
                )
                assert dispatched["status"] == "IN_DELIVERY"
                dispatch_session.commit()
                outcome = future.result(timeout=15)

        assert outcome == ("rejected", "delivery_assignment_state_invalid")
        with factory() as session:
            assert session.scalar(
                sa.select(sa.func.count()).select_from(models.delivery_assignments)
            ) == 0
    finally:
        engine.dispose()
