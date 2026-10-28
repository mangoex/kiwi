"""Real PostgreSQL batch locks, idempotency and audit rollback under the blind policy."""

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
from test_corte_ciego_f106_settlements import SettlementWorld, seed_deliveries
from test_platform_api import ADMIN_USER_ID, _seed


def session_dependency(factory: sessionmaker[Session]) -> Any:
    def scoped_session() -> Iterator[Session]:
        with factory() as session:
            yield session

    return scoped_session


@pytest.fixture
def settlement_pg(monkeypatch: pytest.MonkeyPatch) -> Iterator[SettlementWorld]:
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
            with TestClient(app) as client:
                body = seed_deliveries(client)
                activate(factory)
                yield SettlementWorld(client, factory, body)
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_batches_collect_once(settlement_pg: SettlementWorld, same_key: bool) -> None:
    world = settlement_pg
    barrier = Barrier(2)

    def collect(index: int) -> tuple[str, dict[str, Any] | str]:
        key = f"f106-pg-settlement-{0 if same_key else index}"
        with world.factory() as session:
            barrier.wait(timeout=10)
            try:
                return "confirmed", ops.settle_driver_cash_orders(
                    session,
                    **world.body,
                    idempotency_key=key,
                    actor_user_id=ADMIN_USER_ID,
                )
            except ops.BusinessError as exc:
                session.rollback()
                return "rejected", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(collect, (0, 1)))
    receipts = [value for status, value in results if status == "confirmed"]
    assert len(receipts) == (2 if same_key else 1)
    for value in receipts:
        assert isinstance(value, dict)
        assert value["projection"] == "operational" and "total_cents" not in value
    if same_key:
        assert receipts[0] == receipts[1]
    else:
        assert ("rejected", "driver_settlement_order_ineligible") in results
    with world.factory() as session:
        for table, count in (
            (models.payments, 2),
            (models.payment_commands, 2),
            (models.driver_cash_settlements, 1),
            (models.driver_cash_settlement_items, 2),
            (models.driver_cash_settlement_commands, 1),
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == count
        assert session.scalar(sa.select(sa.func.sum(models.payments.c.amount_cents))) == 28500
        stored = session.scalar(
            sa.select(models.driver_cash_settlement_commands.c.response_snapshot)
        )
        assert stored["total_cents"] == 28500 and len(stored["items"]) == 2


def test_failed_receipt_audit_leaves_no_batch_or_payments(
    settlement_pg: SettlementWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    world = settlement_pg
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "driver.cash_settlement.receipt_read":
            raise sa.exc.SQLAlchemyError("synthetic audit failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with world.factory() as session, pytest.raises(sa.exc.SQLAlchemyError):
        ops.settle_driver_cash_orders(
            session,
            **world.body,
            idempotency_key="f106-pg-audit-failure",
            actor_user_id=ADMIN_USER_ID,
        )
    with world.factory() as session:
        for table in (
            models.payments,
            models.payment_commands,
            models.driver_cash_settlements,
            models.driver_cash_settlement_items,
            models.driver_cash_settlement_commands,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
