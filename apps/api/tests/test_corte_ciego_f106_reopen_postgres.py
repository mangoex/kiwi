"""PostgreSQL correction receipts keep one immutable compensation and atomic audit."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from corte_ciego_storage import isolated_database
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session, sessionmaker
from test_cash_concepts import OWNER_ID, OWNER_ROLE_ID, _seed_cash_concept_scope
from test_cash_ledger import _insert_shift
from test_corte_ciego_f106_movements import activate
from test_order_corrections import _approved_simple_request, _plan
from test_order_reopen_workflow import _actors


@pytest.fixture
def reopen_pg() -> Iterator[tuple[sa.Engine, str]]:
    for engine in isolated_database("postgresql"):
        models.metadata.create_all(engine)
        with Session(engine) as session:
            _seed_cash_concept_scope(session)
            _insert_shift(session)
            _actors(session)
            _, request = _approved_simple_request(session, "f106-pg-1")
            grant_permission(session, OWNER_ROLE_ID, "orders.read")
            session.commit()
        activate(sessionmaker(bind=engine))
        yield engine, str(request["id"])


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_correction_receipts_preserve_one_compensation(
    reopen_pg: tuple[sa.Engine, str],
    same_key: bool,
) -> None:
    engine, request = reopen_pg
    barrier = Barrier(2)

    def apply(index: int) -> tuple[str, Any]:
        with Session(engine) as session:
            barrier.wait(10)
            try:
                value = ops.apply_order_reopen_request(
                    session,
                    request,
                    _plan([]),
                    f"f106-pg-reopen-{0 if same_key else index}",
                    OWNER_ID,
                )
                return "ok", value
            except ops.BusinessError as exc:
                session.rollback()
                return "denied", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(apply, index) for index in (0, 1)]
        results = [future.result(30) for future in futures]
    receipts = [value for status, value in results if status == "ok"]
    assert len(receipts) == (2 if same_key else 1)
    for value in receipts:
        assert value["projection"] == "operational" and "settlement_delta_cents" not in value
    if same_key:
        assert receipts[0] == receipts[1]
    else:
        assert ("denied", "order_reopen_transition_invalid") in results
    with Session(engine) as session:
        for table in (
            models.order_corrections,
            models.order_payment_adjustments,
            models.cash_movements,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 1
        assert session.scalar(sa.select(models.order_corrections.c.settlement_delta_cents)) == -500
        assert session.scalar(sa.select(models.payments.c.amount_cents)) == 500
        assert (
            session.scalar(
                sa.select(models.order_reopen_commands.c.response_snapshot).where(
                    models.order_reopen_commands.c.command_type == "apply",
                )
            )["settlement_delta_cents"]
            == -500
        )


def test_receipt_audit_and_compensation_rollback_together(
    reopen_pg: tuple[sa.Engine, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, request = reopen_pg
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "order.reopen.receipt_read":
            raise sa.exc.SQLAlchemyError("synthetic receipt failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with Session(engine) as session, pytest.raises(sa.exc.SQLAlchemyError):
        ops.apply_order_reopen_request(
            session, request, _plan([]), "f106-pg-reopen-failed", OWNER_ID
        )
    with Session(engine) as session:
        for table in (
            models.order_corrections,
            models.order_payment_adjustments,
            models.cash_movements,
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
        assert (
            session.scalar(
                sa.select(models.order_reopen_requests.c.status).where(
                    models.order_reopen_requests.c.id == request
                )
            )
            == "APPROVED"
        )
