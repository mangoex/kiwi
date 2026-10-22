"""TC-450/452: real cash endpoints, exact scopes, unchanged history and receipts."""

from __future__ import annotations

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, BRANCH_B, SHIFT_ID, CashWorld, cash_world
from restaurant_os import models
from restaurant_os.operations import UserCashCutService
from test_corte_ciego_f1_red import assert_blind

__all__ = ["cash_world"]


def get(world: CashWorld, path: str, actor: str = "cashier", **params: Any) -> Any:
    return world.client.get(f"/api/v2/{path}", params=params, headers=world.headers(actor))


@pytest.mark.parametrize(
    "path",
    [
        "cash/shifts",
        "cash/shifts/current",
        "cash/shifts/{shift}",
        "cash/user-cuts",
        "cash/user-cuts/{cut}",
    ],
)
def test_operational_reads_have_no_money_or_own_count(cash_world: CashWorld, path: str) -> None:
    path = path.format(shift=SHIFT_ID, cut=cash_world.cut_id)
    before = cash_world.snapshot()
    response = get(cash_world, path, branch_id=BRANCH_A, register_id="CAJA-01")
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert_blind(response.json())
    assert "counted_cash_cents" not in response.text
    assert "summary" not in response.text
    assert cash_world.snapshot() == before


@pytest.mark.parametrize("actor", ["cashier", "leader", "administrator", "accumulated", "revoked"])
@pytest.mark.parametrize("kind", ["shifts", "user-cuts"])
def test_no_financial_dataset_by_role_or_general_grant(
    cash_world: CashWorld,
    actor: str,
    kind: str,
) -> None:
    # Cashier has a specific prior cuts grant in this fixture; remove it explicitly.
    if actor == "cashier":
        cash_world.revoke("cashier", "cashier-prior-cuts-a")
    response = get(cash_world, f"financial/cash/{kind}", actor, branch_id=BRANCH_A)
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "financial_access_denied"
    assert_blind(response.json())


def test_delegate_scope_revocation_and_owner_real_snapshot(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        UserCashCutService(session).finalize(
            cash_world.cut_id, {"version": 2}, "f105-finalize", cash_world.actors["leader"]
        )
    route = f"financial/cash/user-cuts/{cash_world.cut_id}"
    for actor in ("owner", "delegate"):
        response = get(cash_world, route, actor)
        assert response.status_code == 200, response.text
        assert response.json()["cash_cut"]["expected_cash_cents"] == 16_500
        assert response.json()["cash_cut"]["difference_cents"] == -6_499
    assert (
        get(cash_world, "financial/cash/shifts", "delegate", branch_id=BRANCH_A).status_code == 403
    )
    assert get(cash_world, "financial/cash/user-cuts", "delegate").status_code == 403
    assert (
        get(cash_world, "financial/cash/user-cuts", "delegate", branch_id=BRANCH_B).status_code
        == 403
    )
    before = cash_world.snapshot()
    cash_world.revoke("delegate", "cuts-a")
    assert get(cash_world, route, "delegate").status_code == 403
    assert get(cash_world, route, "owner").status_code == 200
    assert cash_world.snapshot() == before


def test_unauthorized_financial_read_never_selects_money(cash_world: CashWorld) -> None:
    calls: list[str] = []

    def observe(conn: Any, cur: Any, statement: str, params: Any, ctx: Any, many: bool) -> None:
        if statement.lstrip().upper().startswith("SELECT") and (
            "user_cash_cuts.expected_cash_cents" in statement
            or "cash_shift_closures.summary_snapshot" in statement
        ):
            calls.append(statement)

    sa.event.listen(cash_world.engine, "before_cursor_execute", observe)
    try:
        response = get(cash_world, f"financial/cash/user-cuts/{cash_world.cut_id}", "leader")
        assert response.status_code == 403
        response = get(cash_world, f"financial/cash/shifts/{SHIFT_ID}", "leader")
        assert response.status_code == 403
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe)
    assert calls == []


def test_own_declaration_only_actual_capturer(cash_world: CashWorld) -> None:
    route = f"cash/user-cuts/{cash_world.cut_id}/own-declaration"
    own = get(cash_world, route)
    assert own.status_code == 200, own.text
    assert own.json()["counted_cash_cents"] == 10_001
    assert_blind(own.json())
    assert get(cash_world, route, "leader").status_code == 403
    assert get(cash_world, route, "owner").status_code == 403


def remove_permission(world: CashWorld, role: str, code: str) -> None:
    with world.sessions() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == code,
            )
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == world.roles[role],
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()


def test_replay_keeps_own_receipt_without_action_but_requires_read(cash_world: CashWorld) -> None:
    remove_permission(cash_world, "cashier", "cash.user_cut.capture")
    remove_permission(cash_world, "cashier", "cash.user_cut.create")
    before = cash_world.snapshot()
    route = f"/api/v2/cash/user-cuts/{cash_world.cut_id}/counted-cash"
    payload = {"counted_cash_cents": 10_001, "version": 1}
    headers = cash_world.headers("cashier", key="f103-setup-count")
    response = cash_world.client.post(route, json=payload, headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["replay"] is True
    assert_blind(response.json())
    remove_permission(cash_world, "cashier", "cash.user_cut.operational.read")
    response = cash_world.client.post(route, json=payload, headers=headers)
    assert response.status_code == 403, response.text
    assert cash_world.snapshot() == before


def test_phase2_write_gate_and_historical_receipt_hash(cash_world: CashWorld) -> None:
    before = cash_world.snapshot()
    response = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cash_world.cut_id}/finalize",
        json={"version": 2},
        headers=cash_world.headers("leader", key="f105-phase2"),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "cash_capture_not_ready"
    response = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cash_world.cut_id}/counted-cash",
        json={"version": 1, "counted_cash_cents": 99},
        headers=cash_world.headers("cashier", key="f103-setup-count"),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "idempotency_conflict"
    assert cash_world.snapshot() == before


def test_shift_open_close_replay_and_snapshot(cash_world: CashWorld) -> None:
    headers = cash_world.headers("owner", key="f105-open")
    body = {"branch_id": BRANCH_A, "register_id": "F105", "opening_cash_cents": 777}
    opened = cash_world.client.post("/api/v2/cash/shifts/open", json=body, headers=headers)
    assert opened.status_code == 200, opened.text
    assert_blind(opened.json())
    shift = opened.json()["resource_id"]
    closed = cash_world.client.post(
        f"/api/v2/cash/shifts/{shift}/close-operationally",
        json={},
        headers=cash_world.headers("owner", key="f105-close"),
    )
    assert closed.status_code == 200, closed.text
    assert_blind(closed.json())
    assert closed.json()["status"] == "OPERATIVELY_CLOSED"
    before = cash_world.snapshot()
    replay = cash_world.client.post("/api/v2/cash/shifts/open", json=body, headers=headers)
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "OPEN"  # The original ack, not today's state.
    assert replay.json()["replay"] is True
    assert replay.json()["command_id"] == opened.json()["command_id"]
    financial = get(cash_world, f"financial/cash/shifts/{shift}", "owner")
    assert financial.status_code == 200, financial.text
    assert financial.json()["closure"]["summary_snapshot"]["expected_cash_cents"] == 777
    assert financial.json()["current_summary"]["expected_cash_cents"] == 777
    assert cash_world.snapshot() == before


def test_owner_correction_receipts_preserve_original(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        UserCashCutService(session).finalize(
            cash_world.cut_id, {"version": 2}, "f105-correction-final", cash_world.actors["owner"]
        )
    original = get(cash_world, f"financial/cash/user-cuts/{cash_world.cut_id}", "owner").json()
    body = {
        "counted_cash_cents": 16_500,
        "reason": "Synthetic correction",
        "evidence_refs": ["test"],
    }
    route = f"/api/v2/cash/user-cuts/{cash_world.cut_id}/reopen-requests"
    denied = cash_world.client.post(
        route, json=body, headers=cash_world.headers("administrator", key="bad")
    )
    assert denied.status_code == 403, denied.text
    result = cash_world.client.post(
        route, json=body, headers=cash_world.headers("owner", key="f105-corr")
    )
    assert result.status_code == 200, result.text
    assert_blind(result.json())
    request_id = result.json()["resource_id"]
    assert result.json()["status"] == "REQUESTED"
    for action in ("approve", "compensate"):
        result = cash_world.client.post(
            f"/api/v2/cash/user-cuts/reopen-requests/{request_id}/{action}",
            json={},
            headers=cash_world.headers("owner", key=f"f105-{action}"),
        )
        assert result.status_code == 200, result.text
        assert_blind(result.json())
    after = get(cash_world, f"financial/cash/user-cuts/{cash_world.cut_id}", "owner").json()
    assert after["cash_cut"] == original["cash_cut"]
    assert after["compensations"][0]["corrected_difference_cents"] == 0


def test_no_effect_when_finalizer_loses_receipt_read(cash_world: CashWorld) -> None:
    remove_permission(cash_world, "leader", "cash.user_cut.operational.read")
    before = cash_world.snapshot()
    with cash_world.sessions() as session:
        from restaurant_os.operations import AuthorizationError

        with pytest.raises(AuthorizationError):
            UserCashCutService(session).finalize(
                cash_world.cut_id,
                {"version": 2},
                "f105-no-receipt",
                cash_world.actors["leader"],
            )
    assert cash_world.snapshot() == before


@pytest.mark.parametrize(
    "route,body",
    [
        (
            "cash/shifts/open",
            {"branch_id": BRANCH_A, "register_id": "NEW", "opening_cash_cents": 1},
        ),
        (
            "cash-shifts/open",
            {"branch_id": BRANCH_A, "register_id": "NEW", "opening_cash_cents": 1},
        ),
        ("cash-shifts/close", {"branch_id": BRANCH_A, "register_id": "CAJA-01"}),
        ("cash/shifts/{shift}/close-operationally", {}),
        ("cash/user-cuts/{cut}/reopen-requests", {}),
    ],
)
def test_all_legacy_mutations_block_before_effect(
    cash_world: CashWorld,
    route: str,
    body: dict[str, Any],
) -> None:
    before = cash_world.snapshot()
    route = route.format(shift=SHIFT_ID, cut=cash_world.cut_id)
    response = cash_world.client.post(
        f"/api/v1/{route}", json=body, headers=cash_world.headers("owner", key="blocked")
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "cash_contract_upgrade_required"
    assert cash_world.snapshot() == before


def test_legacy_omitted_branch_does_not_hide_policy(cash_world: CashWorld) -> None:
    response = cash_world.client.get(
        "/api/v1/cash-shifts/summary", headers=cash_world.headers("owner")
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "cash_contract_upgrade_required"


def test_nested_financial_contract_rejects_extra_fields(cash_world: CashWorld) -> None:
    from pydantic import ValidationError
    from restaurant_os.cash_financial_schemas import UserCashCutFinancialV2

    result = get(cash_world, f"financial/cash/user-cuts/{cash_world.cut_id}", "owner").json()
    result["cash_cut"]["unexpected"] = "private"
    with pytest.raises(ValidationError):
        UserCashCutFinancialV2.model_validate(result)


def test_summary_has_its_own_contract(cash_world: CashWorld) -> None:
    result = get(cash_world, f"financial/cash/shifts/{SHIFT_ID}/summary", "owner")
    assert result.status_code == 200, result.text
    assert result.json()["current_summary"]["expected_cash_cents"] == 16_500
    assert "cash_shift" not in result.json()
    assert result.json()["resource_id"] == SHIFT_ID


def test_policy_change_after_commit_returns_retry_without_reexecuting(
    cash_world: CashWorld,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from restaurant_os import cash_command_views
    from restaurant_os.operations import BusinessError

    original = cash_command_views._execute

    def interleaved(*args: Any, **kwargs: Any) -> dict[str, Any]:
        result = original(*args, **kwargs)
        with cash_world.sessions() as session:
            table = models.blind_cash_policy_revisions
            row = dict(
                session.execute(
                    sa.select(table).where(
                        table.c.branch_id == BRANCH_A,
                        table.c.revision == 1,
                    )
                )
                .mappings()
                .one()
            )
            row["revision"] = 2
            session.execute(table.insert().values(**row))
            session.commit()
        return result

    monkeypatch.setattr(cash_command_views, "_execute", interleaved)
    with cash_world.sessions() as session:
        with pytest.raises(BusinessError) as error:
            UserCashCutService(session).finalize(
                cash_world.cut_id,
                {"version": 2},
                "policy-race",
                cash_world.actors["leader"],
            )
        assert error.value.code == "cash_authorization_changed"
    before = cash_world.snapshot()
    with cash_world.sessions() as session:
        replay = UserCashCutService(session).finalize(
            cash_world.cut_id,
            {"version": 2},
            "policy-race",
            cash_world.actors["leader"],
        )
    assert replay["policy_version"] == 2 and replay["replay"] is True
    assert cash_world.snapshot() == before


def test_openapi_separates_operational_and_financial_page_contracts(cash_world: CashWorld) -> None:
    response = cash_world.client.get("/openapi.json")
    assert response.status_code == 200
    spec = response.json()
    schemas = spec["components"]["schemas"]
    for route, item_type in (
        ("/api/v2/cash/shifts", "CashShiftOperationalV2"),
        ("/api/v2/cash/user-cuts", "UserCashCutOperationalV2"),
        ("/api/v2/financial/cash/shifts", "CashShiftFinancialV2"),
        ("/api/v2/financial/cash/user-cuts", "UserCashCutFinancialV2"),
    ):
        reference = spec["paths"][route]["get"]["responses"]["200"]["content"]["application/json"][
            "schema"
        ]["$ref"]
        page = schemas[reference.rsplit("/", 1)[-1]]
        assert page["additionalProperties"] is False
        assert page["properties"]["items"]["items"]["$ref"].endswith("/" + item_type)
        assert schemas[item_type]["additionalProperties"] is False
