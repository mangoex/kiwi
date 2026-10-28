"""Real PostgreSQL acceptance/assignment race and caller transaction boundaries."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_storage import isolated_database
from fastapi.testclient import TestClient
from fixture_metadata import create_fixture_tables
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy.orm import Session, sessionmaker
from test_corte_ciego_f105_intents import activate
from test_corte_ciego_f106_acceptance import AcceptanceWorld, create_pending, setup_acceptance
from test_corte_ciego_f106_settlement_postgres import session_dependency
from test_platform_api import ADMIN_USER_ID, _seed


@pytest.fixture
def acceptance_pg(monkeypatch: pytest.MonkeyPatch) -> Iterator[AcceptanceWorld]:
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "false")
    get_settings.cache_clear()
    try:
        for engine in isolated_database("postgresql"):
            create_fixture_tables(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory() as session:
                _seed(session)
            app = create_app()
            app.dependency_overrides[get_session] = session_dependency(factory)
            app.state.test_session_factory = factory
            with TestClient(app) as client:
                yield setup_acceptance(client)
    finally:
        get_settings.cache_clear()


def prepare(world: AcceptanceWorld, action: str) -> str:
    if action == "pending":
        order = create_pending(world)
    elif action == "assignment":
        order = world.accept().json()["id"]
    else:
        order = ""
    activate(world.factory)
    return order


def execute(
    world: AcceptanceWorld, session: Session, action: str, order: str, *, commit: bool = True
) -> dict[str, Any]:
    if action == "public":
        return ops.accept_public_order_intent(
            session,
            world.intent,
            1,
            "f106-pg-acceptance",
            ADMIN_USER_ID,
            world.driver,
            commit=commit,
        )[0]
    if action == "pending":
        return ops.accept_pending_order(session, order, ADMIN_USER_ID, commit=commit)
    return ops.assign_delivery_driver(session, order, world.driver, ADMIN_USER_ID, commit=commit)


@pytest.mark.parametrize("action", ["public", "pending", "assignment"])
def test_concurrent_same_actor_has_one_effect(acceptance_pg: AcceptanceWorld, action: str) -> None:
    world = acceptance_pg
    order = prepare(world, action)
    barrier = Barrier(2)

    def apply() -> dict[str, Any]:
        with world.factory() as session:
            barrier.wait(10)
            return execute(world, session, action, order)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply) for _ in range(2)]
        receipts = [future.result(30) for future in futures]
    assert receipts[0] == receipts[1] and receipts[0]["projection"] == "operational"
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "order.accepted",
                )
            )
            == 1
        )
        if action != "pending":
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.delivery_assignments))
                == 1
            )
        amounts = list(
            session.scalars(
                sa.select(models.inventory_movements.c.quantity_delta).where(
                    models.inventory_movements.c.movement_type == "SALE_RESERVATION",
                )
            )
        )
        assert amounts and len(amounts) == len(
            set(
                session.scalars(
                    sa.select(
                        models.inventory_movements.c.item_id,
                    ).where(models.inventory_movements.c.movement_type == "SALE_RESERVATION")
                )
            )
        )


@pytest.mark.parametrize("action", ["public", "pending", "assignment"])
def test_caller_can_rollback_complete_operation(
    acceptance_pg: AcceptanceWorld, action: str
) -> None:
    world = acceptance_pg
    order = prepare(world, action)
    tables = [
        models.orders,
        models.order_lines,
        models.inventory_movements,
        models.delivery_assignments,
        models.public_order_intent_commands,
        models.audit_events,
    ]
    with world.factory() as session:
        before = {
            table.name: list(session.execute(sa.select(table)).mappings()) for table in tables
        }
    with world.factory() as session:
        result = execute(world, session, action, order, commit=False)
        assert result["projection"] == "operational"
        session.rollback()
    with world.factory() as session:
        after = {table.name: list(session.execute(sa.select(table)).mappings()) for table in tables}
        assert before == after


def test_competing_public_keys_cannot_accept_twice(acceptance_pg: AcceptanceWorld) -> None:
    world = acceptance_pg
    activate(world.factory)
    barrier = Barrier(2)

    def accept(index: int) -> str:
        with world.factory() as session:
            barrier.wait(10)
            try:
                ops.accept_public_order_intent(
                    session,
                    world.intent,
                    1,
                    f"f106-accept-competing-{index}",
                    ADMIN_USER_ID,
                )
                return "ok"
            except ops.BusinessError as exc:
                session.rollback()
                return exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(accept, index) for index in range(2)]
        results = [future.result(30) for future in futures]
    assert sorted(results) == ["ok", "public_order_transition_invalid"]
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
