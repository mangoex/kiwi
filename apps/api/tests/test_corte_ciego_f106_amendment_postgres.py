"""Real PostgreSQL amendments: one effect, immutable history and atomic receipts."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_storage import isolated_database
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy.orm import Session, sessionmaker
from test_corte_ciego_f105_intents import activate
from test_corte_ciego_f106_amendments import AmendmentWorld
from test_corte_ciego_f106_settlement_postgres import session_dependency
from test_delivery_fee_commands import quote, setup_delivery
from test_platform_api import ADMIN_USER_ID, _admin_headers, _seed


@pytest.fixture
def amendment_pg(monkeypatch: pytest.MonkeyPatch) -> Iterator[AmendmentWorld]:
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "false")
    get_settings.cache_clear()
    try:
        for engine in isolated_database("postgresql"):
            models.metadata.create_all(engine)
            factory = sessionmaker(bind=engine, expire_on_commit=False)
            with factory() as session:
                _seed(session)
            app = create_app()
            app.dependency_overrides[get_session] = session_dependency(factory)
            app.state.test_session_factory = factory
            with TestClient(app) as client:
                _, body, _ = setup_delivery(client)
                body["delivery_quote_reference"] = quote(client, body)["delivery_quote_reference"]
                created = client.post("/api/v1/orders", headers=_admin_headers(), json=body)
                assert created.status_code == 200, created.text
                order = created.json()["id"]
                body.update(
                    order_id=order, expected_version=1, delivery_selection={"mode": "REMOVED"}
                )
                body.pop("delivery_quote_reference")
                body["delivery_quote_reference"] = quote(client, body)["delivery_quote_reference"]
                activate(factory)
                yield AmendmentWorld(client, factory, order, body)
    finally:
        get_settings.cache_clear()


def apply(
    world: AmendmentWorld, session: Session, key: str, *, commit: bool = True
) -> dict[str, Any]:
    return ops.amend_order(
        session,
        world.order,
        world.body["lines"],
        1,
        key,
        ADMIN_USER_ID,
        commit=commit,
        delivery_selection=world.body["delivery_selection"],
        delivery_quote_reference=world.body["delivery_quote_reference"],
    )


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_amendments_have_one_effect(
    amendment_pg: AmendmentWorld, same_key: bool
) -> None:
    world = amendment_pg
    barrier = Barrier(2)

    def amend(index: int) -> tuple[str, Any]:
        with world.factory() as session:
            barrier.wait(10)
            try:
                return "ok", apply(world, session, f"pg-amendment-{0 if same_key else index}")
            except ops.BusinessError as exc:
                session.rollback()
                return "denied", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(amend, (0, 1)))
    receipts = [value for status, value in results if status == "ok"]
    assert len(receipts) == (2 if same_key else 1)
    assert all("total_cents" not in receipt and receipt["version"] == 2 for receipt in receipts)
    if same_key:
        assert receipts[0] == receipts[1]
    else:
        assert ("denied", "order_version_conflict") in results
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 1
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == world.order)
            )
            == 9500
        )
        snapshot = session.scalar(sa.select(models.order_amendments.c.after_snapshot))
        assert (
            snapshot["total_cents"] == 9500 and snapshot["delivery_response"]["total_cents"] == 9500
        )


def test_outer_rollback_includes_amendment_and_receipt(amendment_pg: AmendmentWorld) -> None:
    world = amendment_pg
    with world.factory() as session:
        receipt = apply(world, session, "pg-amendment-rollback", commit=False)
        assert receipt["projection"] == "operational"
        session.rollback()
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 0
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == world.order)
            )
            == 12300
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "order.amendment.receipt_read")
            )
            == 0
        )


def test_audit_failure_reverts_amendment(
    amendment_pg: AmendmentWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = amendment_pg
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.amendment.receipt_read":
            raise sa.exc.SQLAlchemyError("receipt audit failed")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with world.factory() as session, pytest.raises(sa.exc.SQLAlchemyError):
        apply(world, session, "pg-amendment-audit")
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_amendments)) == 0
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == world.order)
            )
            == 12300
        )
