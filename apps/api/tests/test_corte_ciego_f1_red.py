"""Executable F1-03 RED: real v1 handlers/domain, no missing-v2-route failures.

TC-450/451/452/462. Failures are intentional until F1-04..08 are authorized.
No xfail, skip, production changes or authorization/projection stubs.
"""

from __future__ import annotations

import importlib
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_contracts import RECEIPT_SCHEMA
from corte_ciego_fixtures import (
    BRANCH_A,
    BRANCH_B,
    OTHER_BRANCH,
    SHIFT_ID,
    CashWorld,
    cash_world,
    ident,
)
from restaurant_os import executive_ai, models
from restaurant_os.operations import AuthorizationError, UserCashCutService

# Re-export fixture explicitly for pytest; no root conftest/global test changes.
__all__ = ["cash_world"]
jsonschema = importlib.import_module("jsonschema")

FINANCIAL_KEYS = frozenset({
    "opening_cash_cents", "cash_payment_cents", "deposit_cents", "withdrawal_cents",
    "expected_cash_cents", "difference_cents", "tolerance_cents", "total_revenue_cents",
    "average_ticket_cents", "total_sales_cents", "summary_at_commit", "current_summary",
    "is_balanced", "has_financial_alert", "total_spend_cents",
})


def financial_paths(value: Any, path: str = "$") -> list[str]:
    if isinstance(value, dict):
        return [f"{path}.{key}" for key in value if key in FINANCIAL_KEYS] + [
            found for key, nested in value.items()
            for found in financial_paths(nested, f"{path}.{key}")
        ]
    if isinstance(value, list):
        return [found for i, nested in enumerate(value)
                for found in financial_paths(nested, f"{path}[{i}]")]
    return []


def assert_blind(value: Any) -> None:
    paths = financial_paths(value)
    assert not paths, f"CC-F1 financial fields escaped the operational boundary: {paths}"


@pytest.mark.parametrize("actor", ["cashier", "leader"])
@pytest.mark.parametrize("resource", [
    "cash/shifts/current", "cash-shifts/current", "cash-shifts/summary",
    "cash/shifts", "cash/shifts/{shift}", "cash/user-cuts", "cash/user-cuts/{cut}",
])
def test_tc450_active_policy_rejects_legacy_aliases(
    cash_world: CashWorld, actor: str, resource: str,
) -> None:
    route = resource.format(shift=SHIFT_ID, cut=cash_world.cut_id)
    before = cash_world.snapshot()
    response = cash_world.client.get(
        f"/api/v1/{route}", params={"branch_id": BRANCH_A, "register_id": "CAJA-01"},
        headers=cash_world.headers(actor),
    )
    assert cash_world.snapshot() == before
    # A 404/422/500 is a fixture/transport error, never accepted as a security RED.
    assert response.status_code in (200, 409), response.text
    assert response.status_code == 409, (
        f"CC-F1 legacy {route} ignored activated policy; status={response.status_code}, "
        f"financial_paths={financial_paths(response.json())}"
    )
    assert response.json()["detail"]["code"] == "cash_contract_upgrade_required"
    assert_blind(response.json())


@pytest.mark.parametrize("actor", [
    "cashier", "leader", "chief_cashier", "administrator", "supervisor", "accumulated",
    "delegate", "revoked",
])
def test_tc451_roles_and_wrong_or_revoked_grants_do_not_authorize_sales(
    cash_world: CashWorld, actor: str,
) -> None:
    # Delegate has cash.cuts in A and sales in B, NOT sales in A (no Cartesian product).
    response = cash_world.client.get(
        "/api/v1/dashboard/overview", params={"branch_id": BRANCH_A},
        headers=cash_world.headers(actor),
    )
    assert response.status_code in (200, 403), response.text
    assert response.status_code == 403, (
        f"CC-F1 actor={actor} obtained sales without a live (branch A, sales) grant"
    )
    assert response.json()["detail"]["code"] == "financial_access_denied"
    assert_blind(response.json())


@pytest.mark.parametrize("route", ["payments", "cash-movements", "cash/movements"])
def test_tc450_global_money_lists_require_financial_authority(
    cash_world: CashWorld, route: str,
) -> None:
    response = cash_world.client.get(
        f"/api/v1/{route}", params={"branch_id": BRANCH_A},
        headers=cash_world.headers("cashier"),
    )
    assert response.status_code in (200, 403), response.text
    assert response.status_code == 403, f"CC-F1 {route} allows monetary browsing"
    assert response.json()["detail"]["code"] == "financial_access_denied"


@pytest.mark.parametrize("actor", ["cashier", "delegate", "administrator"])
def test_tc452_legacy_create_cannot_finalize_without_separate_authority(
    cash_world: CashWorld, actor: str,
) -> None:
    before = cash_world.snapshot()
    denied = False
    with cash_world.sessions() as session:
        try:
            UserCashCutService(session).finalize(
                cash_world.cut_id, {"version": 2}, "f103-forbidden-finalize",
                cash_world.actors[actor],
            )
        except AuthorizationError:
            denied = True
    after = cash_world.snapshot()
    assert denied and after == before, (
        f"CC-F1 actor={actor} finalized via legacy create; "
        f"denied={denied}, business_state_unchanged={after == before}"
    )


def test_tc452_leader_finalize_uses_new_capability_without_legacy_create(
    cash_world: CashWorld,
) -> None:
    with cash_world.sessions() as session:
        legacy_id = session.scalar(sa.select(models.permissions.c.id).where(
            models.permissions.c.code == "cash.user_cut.create"
        ))
        session.execute(models.role_permissions.delete().where(
            models.role_permissions.c.role_id == cash_world.roles["leader"],
            models.role_permissions.c.permission_id == legacy_id,
        ))
        session.commit()
        try:
            result = UserCashCutService(session).finalize(
                cash_world.cut_id, {"version": 2}, "f103-leader-finalize",
                cash_world.actors["leader"],
            )
        except AuthorizationError as exc:
            pytest.fail(f"CC-F1 authorized finalizer still depends on legacy create: {exc.code}")
        state = session.scalar(sa.select(models.user_cash_cuts.c.status).where(
            models.user_cash_cuts.c.id == cash_world.cut_id
        ))
        assert state == "FINALIZED"
        assert_blind(result)


def test_tc450_count_replay_reprojects_stored_financial_body(cash_world: CashWorld) -> None:
    before = cash_world.snapshot()
    with cash_world.sessions() as session:
        result = UserCashCutService(session).counted_cash(
            cash_world.cut_id, {"counted_cash_cents": 10_001, "version": 1},
            "f103-setup-count", cash_world.actors["cashier"],
        )
    assert cash_world.snapshot() == before, "Replay must not execute the count again"
    assert_blind(result)
    jsonschema.validate(result, RECEIPT_SCHEMA)


def test_tc450_finalize_response_does_not_disclose_snapshot(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        result = UserCashCutService(session).finalize(
            cash_world.cut_id, {"version": 2}, "f103-leader-ack", cash_world.actors["leader"],
        )
        state = session.scalar(sa.select(models.user_cash_cuts.c.status).where(
            models.user_cash_cuts.c.id == cash_world.cut_id
        ))
        assert state == "FINALIZED", "Must exercise a valid finalization, not a rejected command"
    assert_blind(result)
    jsonschema.validate(result, RECEIPT_SCHEMA)


def test_tc450_replay_after_financial_revocation_preserves_only_own_ack(
    cash_world: CashWorld,
) -> None:
    # The actor keeps own operational-read/capture; only financial access is revoked.
    cash_world.revoke("cashier", "cashier-prior-cuts-a")
    before = cash_world.snapshot()
    with cash_world.sessions() as session:
        result = UserCashCutService(session).counted_cash(
            cash_world.cut_id, {"counted_cash_cents": 10_001, "version": 1},
            "f103-setup-count", cash_world.actors["cashier"],
        )
    assert cash_world.snapshot() == before
    assert_blind(result)


def test_tc450_omitted_branch_cannot_expand_financial_scope(cash_world: CashWorld) -> None:
    response = cash_world.client.get(
        "/api/v1/dashboard/overview", headers=cash_world.headers("delegate"),
    )
    assert response.status_code in (200, 403), response.text
    assert response.status_code == 403, "CC-F1 omitted branch expands sales beyond grant in B"
    assert response.json()["detail"]["code"] == "financial_access_denied"


@pytest.mark.parametrize("command", ["counted-cash", "finalize"])
def test_tc450_legacy_mutation_or_replay_cannot_bypass_upgrade(
    cash_world: CashWorld, command: str,
) -> None:
    is_replay = command == "counted-cash"
    before = cash_world.snapshot()
    response = cash_world.client.post(
        f"/api/v1/cash/user-cuts/{cash_world.cut_id}/{command}",
        json={"counted_cash_cents": 10_001, "version": 1} if is_replay else {"version": 2},
        headers=cash_world.headers(
            "cashier" if is_replay else "leader",
            key="f103-setup-count" if is_replay else "f103-legacy-finalize",
        ),
    )
    assert response.status_code in (200, 409), response.text
    unchanged = cash_world.snapshot() == before
    assert response.status_code == 409 and unchanged, (
        f"CC-F1 legacy {command} accepted; status={response.status_code}, unchanged={unchanged}"
    )
    assert response.json()["detail"]["code"] == "cash_contract_upgrade_required"


def test_tc450_revocation_revalidates_next_read(cash_world: CashWorld) -> None:
    # Live positive control on a real financial endpoint before persisted revocation.
    before = cash_world.client.get(
        "/api/v1/dashboard/overview", params={"branch_id": BRANCH_B, "month": "2026-08"},
        headers=cash_world.headers("delegate"),
    )
    assert before.status_code == 200, before.text
    assert before.json()["total_revenue_cents"] == 5_000
    cash_world.revoke("delegate", "sales-b")
    after = cash_world.client.get(
        "/api/v1/dashboard/overview", params={"branch_id": BRANCH_B, "month": "2026-08"},
        headers=cash_world.headers("delegate"),
    )
    assert after.status_code in (200, 403), after.text
    assert after.status_code == 403, "CC-F1 revoked grant still reads financial data"


def test_tc450_ai_authorizes_before_building_context(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    provider_calls: list[str] = []

    def observe_sql(
        connection: Any, cursor: Any, statement: str, parameters: Any,
        context: Any, executemany: bool,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "orders.total_cents" in statement:
            calls.append("financial-query")

    def provider_sink(*args: Any, **kwargs: Any) -> str:
        provider_calls.append("provider")
        return "Synthetic offline provider"

    # Actual service and SQL remain. Only external I/O is stubbed; no fixture goes online.
    monkeypatch.setattr(executive_ai, "_call_external_provider", provider_sink)
    sa.event.listen(cash_world.engine, "before_cursor_execute", observe_sql)
    try:
        response = cash_world.client.post(
            "/api/v1/admin-ai/executive-insights",
            json={"prompt": "Venta de la sucursal", "branch_id": BRANCH_A},
            headers=cash_world.headers("cashier"),
        )
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe_sql)
    assert response.status_code in (200, 403), response.text
    assert calls == [], "CC-F1 financial context was reached before authorization"
    assert provider_calls == []
    assert response.status_code == 403


@pytest.mark.parametrize("route,params", [
    ("customers", {"limit": 1, "offset": 0}),
    ("customers", {"q": "Synthetic", "limit": 1}),
    ("orders/accounts", {"limit": 1}),
    ("orders/accounts", {"q": "F103", "limit": 1}),
])
def test_tc462_legacy_search_and_pagination_cannot_reconstruct_money(
    cash_world: CashWorld, route: str, params: dict[str, Any],
) -> None:
    response = cash_world.client.get(
        f"/api/v1/{route}", params={"branch_id": BRANCH_A, **params},
        headers=cash_world.headers("cashier"),
    )
    assert response.status_code in (200, 403), response.text
    assert response.status_code == 403, (
        f"CC-F1 legacy {route} exposes monetary history through filtered/paged access"
    )
    assert response.json()["detail"]["code"] == "financial_access_denied"


def test_tc462_exact_order_id_is_not_an_authorized_service_context(cash_world: CashWorld) -> None:
    # Seeded historical order has no actor-bound attendance/follow-up authorization.
    response = cash_world.client.get(
        f"/api/v1/orders/{ident('order:2')}", headers=cash_world.headers("cashier"),
    )
    assert response.status_code in (200, 403), response.text
    assert response.status_code == 403, "CC-F1 knowing an order ID disclosed historical money"


@pytest.mark.parametrize("branch", [BRANCH_B, OTHER_BRANCH])
def test_tc450_individual_cut_not_owned_by_cashier_is_denied(
    cash_world: CashWorld, branch: str,
) -> None:
    before = cash_world.snapshot()
    response = cash_world.client.get(
        f"/api/v1/cash/user-cuts/{ident(f'cut:{branch}')}",
        headers=cash_world.headers("cashier"),
    )
    assert response.status_code in (403, 404, 409), response.text
    assert_blind(response.json())
    assert cash_world.snapshot() == before
