"""Real attendance DTO versus current role revocation in PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_access import FinancialAccessService
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, CASHIER_ID, CASHIER_ROLE_ID, OWNER_ID
from test_corte_ciego_f104_postgres import wait_until_blocked
from test_corte_ciego_f105_postgres import pg_cash
from test_corte_ciego_f106_postgres import pg_sales

__all__ = ["pg_cash", "pg_sales"]


def test_order_writer_holds_governance_before_branch_resource(
    pg_cash: tuple[sa.Engine, str, str],
) -> None:
    engine, _, _ = pg_cash
    with Session(engine) as session:
        ops._require_order_write_fence(session, BRANCH_A)
        assert (
            session.scalar(
                sa.text(
                    "SELECT count(*) FROM pg_locks WHERE pid=pg_backend_pid() "
                    "AND locktype='advisory' AND mode='ShareLock' AND granted"
                )
            )
            == 1
        )


@pytest.mark.parametrize("reader_first", [True, False])
def test_attended_read_and_role_revocation_serialize(
    pg_sales: tuple[sa.Engine, str],
    monkeypatch: pytest.MonkeyPatch,
    reader_first: bool,
) -> None:
    engine, grant = pg_sales
    order = ident("f106-order")
    with Session(engine) as session:
        FinancialAccessService(session, ops.ORGANIZATION_ID).revoke(
            OWNER_ID,
            grant,
            "remove-financial-fallback",
            {"reason": "Test operational context alone"},
        )
        for permission in ("orders.read", "orders.create"):
            grant_permission(session, CASHIER_ROLE_ID, permission)
        session.execute(
            models.orders.update().where(models.orders.c.id == order).values(status="ACCEPTED")
        )
        ops._audit(
            session,
            "order.accepted",
            "order",
            order,
            {"fixture": True},
            branch_id=BRANCH_A,
            actor_user_id=CASHIER_ID,
        )
        session.commit()
    arrived, release, contender_started = Event(), Event(), Event()
    pids: list[int] = []
    original_audit = ops._audit

    def pause_at_money(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if (
            reader_first
            and statement.lstrip().startswith("SELECT orders.id")
            and ("orders.total_cents" in statement)
        ):
            arrived.set()
            assert release.wait(10)

    def pause_at_writer(*args: Any, **kwargs: Any) -> None:
        original_audit(*args, **kwargs)
        if not reader_first and (kwargs.get("action") == "role.permissions_updated"):
            arrived.set()
            assert release.wait(10)

    monkeypatch.setattr(ops, "_audit", pause_at_writer)
    sa.event.listen(engine, "before_cursor_execute", pause_at_money)

    def read() -> bool:
        with Session(engine) as session:
            if not reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender_started.set()
            try:
                result = ops.get_order_detail(
                    session,
                    order,
                    CASHIER_ID,
                    expected_version=1,
                    projection_v2=True,
                )
                assert result["total_cents"] == 5678
                assert result["read_context"]["source_kind"] == "order_acceptance"
                session.commit()
                return True
            except ops.AuthorizationError:
                return False

    def revoke() -> None:
        with Session(engine) as session:
            if reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender_started.set()
            ops.update_role_permissions(session, CASHIER_ROLE_ID, [], OWNER_ID)

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            first = executor.submit(read if reader_first else revoke)
            second = None
            try:
                assert arrived.wait(10)
                second = executor.submit(revoke if reader_first else read)
                assert contender_started.wait(5)
                wait_until_blocked(engine, pids[0])
            finally:
                release.set()
            assert second is not None
            first_result, second_result = first.result(timeout=15), second.result(timeout=15)
            assert (first_result if reader_first else second_result) is reader_first
    finally:
        sa.event.remove(engine, "before_cursor_execute", pause_at_money)
