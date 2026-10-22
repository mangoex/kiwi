"""SQL lock waits must not block ASGI's loop and prevent sibling sessions closing."""

import asyncio

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, CashWorld, cash_world

__all__ = ["cash_world"]


@pytest.mark.parametrize("path", ["/api/v1/payments", "/api/v1/cash/shifts"])
def test_governance_sql_runs_outside_asgi_event_loop(cash_world: CashWorld, path: str) -> None:
    observed = []

    def observe(_conn, _cursor, sql, *_args):
        if sql.strip().upper() != "BEGIN IMMEDIATE":
            return
        try:
            asyncio.get_running_loop()
            observed.append("event-loop")
        except RuntimeError:
            observed.append("worker")

    sa.event.listen(cash_world.engine, "before_cursor_execute", observe)
    try:
        result = cash_world.client.get(
            path, params={"branch_id": BRANCH_A}, headers=cash_world.headers("cashier")
        )
        assert result.status_code in (403, 409), result.text
        assert observed and set(observed) == {"worker"}
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe)
