"""CORTE-CIEGO-001 Phases 2, 3, 4, 5, and 6 comprehensive verification suite."""

from __future__ import annotations

from datetime import UTC, timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from corte_ciego_fixtures import (
    BRANCH_A,
    CASHIER_ID,
    NOW,
    ORG_ID,
    OWNER_ID,
    SHIFT_ID,
    CashWorld,
    cash_world,
    grant_permission,
    ident,
)
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.owner_alerts import (
    record_discount_or_cancellation_alert,
    set_alert_channel_sender,
)
from test_corte_ciego_f1_red import assert_blind

__all__ = ["cash_world"]


def _new_closed_shift_and_draft_cut(
    world: CashWorld, register_code: str = "CAJA-P2"
) -> tuple[str, str]:
    """Open and operatively close a shift, then create a DRAFT user cash cut."""
    with world.sessions() as session:
        for code in ("cash.shift.open", "cash.shift.close"):
            grant_permission(session, world.roles["cashier"], code)
        session.commit()

    open_resp = world.client.post(
        "/api/v2/cash/shifts/open",
        json={"branch_id": BRANCH_A, "register_id": register_code, "opening_cash_cents": 50_000},
        headers=world.headers("cashier", key=f"open-{register_code}"),
    )
    assert open_resp.status_code == 200, open_resp.text
    shift_id = str(open_resp.json()["resource_id"])

    # Add a confirmed cash payment ($200.00 = 20_000c) and a debit payment ($150.00 = 15_000c)
    payment_time = ops._now()
    with world.sessions() as session:
        for idx, (method, amount) in enumerate((("cash", 20_000), ("debit", 15_000)), start=1):
            oid = ident(f"p2-order:{register_code}:{idx}")
            pid = ident(f"p2-payment:{register_code}:{idx}")
            session.execute(
                models.orders.insert().values(
                    id=oid,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    cash_shift_id=shift_id,
                    customer_id=ident("customer"),
                    folio=f"P2-{register_code}-{idx}",
                    channel="POS",
                    status="PAID",
                    total_cents=amount,
                    currency="MXN",
                    order_type="takeout",
                    created_at=payment_time,
                )
            )
            session.execute(
                models.payments.insert().values(
                    id=pid,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    order_id=oid,
                    cash_shift_id=shift_id,
                    method=method,
                    status="CONFIRMED",
                    amount_cents=amount,
                    currency="MXN",
                    confirmed_at=payment_time,
                    created_at=payment_time,
                )
            )
        session.commit()

    close_resp = world.client.post(
        f"/api/v2/cash/shifts/{shift_id}/close-operationally",
        json={},
        headers=world.headers("cashier", key=f"close-{register_code}"),
    )
    assert close_resp.status_code == 200, close_resp.text

    shift_detail = world.client.get(
        f"/api/v2/cash/shifts/{shift_id}",
        headers=world.headers("cashier"),
    ).json()

    with world.sessions() as session:
        closure_closed_at = session.scalar(
            sa.select(models.cash_shift_closures.c.closed_at).where(
                models.cash_shift_closures.c.cash_shift_id == shift_id
            )
        )
        cut_res = ops.UserCashCutService(session).create(
            {
                "branch_id": BRANCH_A,
                "register_id": register_code,
                "cash_shift_id": shift_id,
                "cashier_user_id": CASHIER_ID,
                "period_start": shift_detail["opened_at"],
                "period_end": (
                    closure_closed_at.replace(tzinfo=UTC)
                    if closure_closed_at.tzinfo is None
                    else closure_closed_at.astimezone(UTC)
                ).isoformat(),
            },
            f"create-cut-{register_code}",
            CASHIER_ID,
        )
        cut_id = str(
            cut_res["resource_id"] if "resource_id" in cut_res else cut_res["cash_cut"]["id"]
        )
    return shift_id, cut_id


# ==============================================================================
# PHASE 2 TESTS: Denominations, Drafts, Single Confirmation, Substitution,
# Per-Method Reconciliation, Custody Delivery, Error Reports, Transition Unblock
# ==============================================================================


def test_phase2_denomination_catalog_owner_only_and_transition_preflight(
    cash_world: CashWorld,
) -> None:
    # Non-owner cannot configure denominations
    denied = cash_world.client.put(
        "/api/v2/cash/denominations",
        json={"use_standard_mxn": True},
        headers=cash_world.headers("leader"),
    )
    assert denied.status_code == 403

    # Owner configures standard MXN denominations ($1,000 down to $0.50)
    ok = cash_world.client.put(
        "/api/v2/cash/denominations",
        json={"use_standard_mxn": True},
        headers=cash_world.headers("owner"),
    )
    assert ok.status_code == 200, ok.text
    denoms = ok.json()["items"]
    assert len(denoms) == 11
    assert denoms[0]["denomination_cents"] == 100_000
    assert denoms[-1]["denomination_cents"] == 50

    # Cashier can list active denominations for their branch
    listed = cash_world.client.get(
        "/api/v2/cash/denominations",
        params={"branch_id": BRANCH_A},
        headers=cash_world.headers("cashier"),
    )
    assert listed.status_code == 200, listed.text
    assert len(listed.json()["items"]) == 11


def test_phase2_draft_confirmation_immutability_and_blind_receipt(cash_world: CashWorld) -> None:
    cash_world.client.put(
        "/api/v2/cash/denominations",
        json={"use_standard_mxn": True},
        headers=cash_world.headers("owner"),
    )
    _, cut_id = _new_closed_shift_and_draft_cut(cash_world, "CAJA-P2A")

    # 1. Client-calculated total is rejected
    bad_total = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
        json={
            "counted_cash_cents": 70_000,
            "denominations": [{"denomination_cents": 50_000, "piece_count": 1}],
            "version": 1,
        },
        headers=cash_world.headers("cashier", key="p2-bad-total"),
    )
    assert bad_total.status_code == 409, bad_total.text
    assert bad_total.json()["detail"]["code"] == "client_total_forbidden"

    # 2. Save editable drafts with revision history
    draft1 = cash_world.client.put(
        f"/api/v2/cash/user-cuts/{cut_id}/declaration-draft",
        json={
            "denominations": [{"denomination_cents": 50_000, "piece_count": 1}],
            "payment_methods": {
                "debit": {"declared_cents": 15_000, "voucher_count": 1, "references": ["V-01"]},
                "credit": {"declared_cents": 0, "voucher_count": 0},
                "transfer": {"declared_cents": None},
                "platform": {"declared_cents": None},
            },
        },
        headers=cash_world.headers("cashier"),
    )
    assert draft1.status_code == 200, draft1.text
    assert draft1.json()["revision"] == 1
    assert draft1.json()["counted_cash_cents"] == 50_000

    draft2 = cash_world.client.put(
        f"/api/v2/cash/user-cuts/{cut_id}/declaration-draft",
        json={
            "denominations": [
                {"denomination_cents": 50_000, "piece_count": 1},
                {"denomination_cents": 20_000, "piece_count": 1},
            ],
            "payment_methods": {
                "debit": {"declared_cents": 15_000, "voucher_count": 1, "references": ["V-01"]},
                "credit": {"declared_cents": 0, "voucher_count": 0},
                "transfer": {"declared_cents": None},
                "platform": {"declared_cents": None},
            },
        },
        headers=cash_world.headers("cashier"),
    )
    assert draft2.status_code == 200, draft2.text
    assert draft2.json()["revision"] == 2
    assert draft2.json()["counted_cash_cents"] == 70_000

    # 3. Confirm declaration once ($700.00 cash = 500 + 200, matching expected 500 opening + 200
    # sale)
    confirm_payload = {
        "denominations": [
            {"denomination_cents": 50_000, "piece_count": 1},
            {"denomination_cents": 20_000, "piece_count": 1},
        ],
        "payment_methods": {
            "debit": {"declared_cents": 15_000, "voucher_count": 1, "references": ["V-01"]},
            "credit": {"declared_cents": 0, "voucher_count": 0},
            "transfer": {"declared_cents": None},
            "platform": {"declared_cents": None},
        },
        "version": 1,
    }
    confirmed = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
        json=confirm_payload,
        headers=cash_world.headers("cashier", key="p2-confirm-1"),
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "COUNTED"
    assert_blind(confirmed.json())

    # 4. Idempotent replay with same key & payload returns replay=True
    replay = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
        json=confirm_payload,
        headers=cash_world.headers("cashier", key="p2-confirm-1"),
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["replay"] is True

    # 5. Editing draft or re-confirming with a new key after confirmation is rejected
    edit_after = cash_world.client.put(
        f"/api/v2/cash/user-cuts/{cut_id}/declaration-draft",
        json={"denominations": [{"denomination_cents": 50_000, "piece_count": 1}]},
        headers=cash_world.headers("cashier"),
    )
    assert edit_after.status_code == 409
    assert edit_after.json()["detail"]["code"] == "cash_cut_already_counted"

    reconfirm = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
        json=confirm_payload,
        headers=cash_world.headers("cashier", key="p2-confirm-2"),
    )
    assert reconfirm.status_code == 409
    assert reconfirm.json()["detail"]["code"] == "cash_cut_already_counted"

    # 6. Custody delivery & operator error report work without exposing expected or editing count
    custody = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/custody-delivery",
        json={"receiver_user_id": cash_world.actors["leader"], "notes": "Sobre sellado #12"},
        headers=cash_world.headers("cashier"),
    )
    assert custody.status_code == 200, custody.text
    assert custody.json()["custody_receiver_user_id"] == cash_world.actors["leader"]
    assert_blind(custody.json())

    err_rep = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/error-reports",
        json={"reason": "Olvidé incluir moneda de $10", "evidence_refs": ["foto-1"]},
        headers=cash_world.headers("cashier"),
    )
    assert err_rep.status_code == 200, err_rep.text
    assert_blind(err_rep.json())

    # 7. Finalize cut by Manager (leader) -> blind receipt, while Owner sees full reconciliation
    finalized = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/finalize",
        json={"version": 2, "external_pending_methods": {"platform": "uber_report_delayed"}},
        headers=cash_world.headers("leader", key="p2-finalize-1"),
    )
    assert finalized.status_code == 200, finalized.text
    assert finalized.json()["status"] == "FINALIZED"
    assert_blind(finalized.json())

    recon = cash_world.client.get(
        f"/api/v2/financial/cash/user-cuts/{cut_id}/reconciliation",
        headers=cash_world.headers("owner"),
    )
    assert recon.status_code == 200, recon.text
    recon_data = recon.json()
    assert len(recon_data["error_reports"]) == 1
    assert recon_data["declaration"]["custody_receiver_user_id"] == cash_world.actors["leader"]
    by_method = {m["payment_method"]: m for m in recon_data["method_reconciliations"]}
    assert by_method["cash"]["declared_cents"] == 70_000
    assert by_method["cash"]["expected_cents"] == 70_000
    assert by_method["cash"]["difference_cents"] == 0
    assert by_method["debit"]["declared_cents"] == 15_000
    assert by_method["debit"]["expected_cents"] == 15_000
    assert by_method["debit"]["difference_cents"] == 0
    # Credit was explicitly declared 0 vs transfer null (not counted) vs platform pending external
    assert by_method["credit"]["declared_cents"] == 0
    assert by_method["transfer"]["declared_cents"] is None
    assert by_method["platform"]["reconciliation_status"] == "PENDING_EXTERNAL"
    assert by_method["platform"]["pending_reason"] == "uber_report_delayed"
    assert by_method["platform"]["difference_cents"] is None


def test_phase2_manager_substitution_requires_reason_and_preserves_responsible_cashier(
    cash_world: CashWorld,
) -> None:
    cash_world.client.put(
        "/api/v2/cash/denominations",
        json={"use_standard_mxn": True},
        headers=cash_world.headers("owner"),
    )
    _, cut_id = _new_closed_shift_and_draft_cut(cash_world, "CAJA-P2SUB")

    # Manager (leader) attempting substitution without reason is rejected
    no_reason = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
        json={
            "denominations": [{"denomination_cents": 50_000, "piece_count": 1}],
            "version": 1,
        },
        headers=cash_world.headers("leader", key="p2-sub-noreason"),
    )
    assert no_reason.status_code == 409, no_reason.text
    assert no_reason.json()["detail"]["code"] == "cash_substitution_reason_required"

    # Manager with reason succeeds and preserves original responsible_user_id = cashier
    with_reason = cash_world.client.post(
        f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
        json={
            "denominations": [{"denomination_cents": 50_000, "piece_count": 1}],
            "substitution_reason": "Cajero salió por emergencia médica",
            "version": 1,
        },
        headers=cash_world.headers("leader", key="p2-sub-ok"),
    )
    assert with_reason.status_code == 200, with_reason.text

    assert_blind(with_reason.json())
    with cash_world.sessions() as session:
        decl = (
            session.execute(
                sa.select(models.user_cash_cut_declarations).where(
                    models.user_cash_cut_declarations.c.cash_cut_id == cut_id
                )
            )
            .mappings()
            .one()
        )
        cut_cashier = session.scalar(
            sa.select(models.user_cash_cuts.c.cashier_user_id).where(
                models.user_cash_cuts.c.id == cut_id
            )
        )
    assert cut_cashier == CASHIER_ID
    assert decl["responsible_user_id"] == CASHIER_ID
    assert decl["capturer_user_id"] == cash_world.actors["leader"]
    assert bool(decl["is_substitution"]) is True
    assert decl["substitution_reason"] == "Cajero salió por emergencia médica"


# ==============================================================================
# PHASE 3 TESTS: Owner Alerts ($0.00 Tolerance, Discounts/Cancels, Delegate
# Recipient Scope & Revocation, Non-Blocking Channel Retry)
# ==============================================================================


def test_phase3_zero_tolerance_alert_delegate_scope_and_channel_retry(
    cash_world: CashWorld,
) -> None:
    cash_world.client.put(
        "/api/v2/cash/denominations",
        json={"use_standard_mxn": True},
        headers=cash_world.headers("owner"),
    )
    _, cut_id = _new_closed_shift_and_draft_cut(cash_world, "CAJA-P3")

    # Simulate external channel failure on first emission
    delivered_events: list[dict[str, Any]] = []
    should_fail = True

    def flaky_sender(event: dict[str, Any]) -> None:
        if should_fail:
            raise RuntimeError("whatsapp_gateway_timeout")
        delivered_events.append(event)

    set_alert_channel_sender(flaky_sender)
    try:
        # Declare $699.50 (69_950c) vs expected $700.00 (70_000c) -> -$0.50 (-50c) difference
        cash_world.client.post(
            f"/api/v2/cash/user-cuts/{cut_id}/counted-cash",
            json={
                "denominations": [
                    {"denomination_cents": 50_000, "piece_count": 1},
                    {"denomination_cents": 10_000, "piece_count": 1},
                    {"denomination_cents": 5_000, "piece_count": 1},
                    {"denomination_cents": 2_000, "piece_count": 2},
                    {"denomination_cents": 500, "piece_count": 1},
                    {"denomination_cents": 200, "piece_count": 2},
                    {"denomination_cents": 50, "piece_count": 1},
                ],
                "payment_methods": {
                    "debit": {
                        "declared_cents": 15_050
                    },  # +50c on debit must NOT offset -50c on cash!
                },
                "version": 1,
            },
            headers=cash_world.headers("cashier", key="p3-count"),
        )
        # Finalize succeeds even though external channel threw an exception!
        fin = cash_world.client.post(
            f"/api/v2/cash/user-cuts/{cut_id}/finalize",
            json={"version": 2},
            headers=cash_world.headers("leader", key="p3-finalize"),
        )
        assert fin.status_code == 200, fin.text

        # Also emit an order discount/cancellation alert
        with cash_world.sessions() as session:
            record_discount_or_cancellation_alert(
                session,
                branch_id=BRANCH_A,
                order_id=ident("order:1"),
                event_kind="discount",
                actor_user_id=CASHIER_ID,
                supervisor_user_id=cash_world.actors["leader"],
                reason="Promoción autorizada",
                amount_cents=500,
            )
            session.commit()

        # Owner sees both alerts in FAILED_RETRYING state
        owner_alerts = cash_world.client.get(
            "/api/v2/financial/owner-alerts",
            params={"branch_id": BRANCH_A},
            headers=cash_world.headers("owner"),
        )
        assert owner_alerts.status_code == 200, owner_alerts.text
        items = owner_alerts.json()["items"]
        types = {a["alert_type"]: a for a in items}
        assert "cash_cut_difference" in types
        assert "order_discount_courtesy_cancellation" in types
        diff_alert = types["cash_cut_difference"]
        assert diff_alert["delivery_status"] == "FAILED_RETRYING"
        # Both cash (-50) and debit (+50) are reported without netting
        diff_methods = {
            d["payment_method"]: d["difference_cents"] for d in diff_alert["payload"]["differences"]
        }
        assert diff_methods == {"cash": -50, "debit": 50}

        # Delegate has financial grant for cash.cuts in BRANCH_A, but is NOT yet designated as alert
        # recipient
        undesignated = cash_world.client.get(
            "/api/v2/financial/owner-alerts",
            params={"branch_id": BRANCH_A},
            headers=cash_world.headers("delegate"),
        )
        assert undesignated.status_code == 403

        # Owner designates delegate for cash_cut_difference in BRANCH_A
        desig = cash_world.client.post(
            "/api/v2/financial/owner-alerts/recipients",
            json={
                "branch_id": BRANCH_A,
                "user_id": cash_world.actors["delegate"],
                "alert_type": "cash_cut_difference",
                "channel": "in_app",
                "is_active": True,
            },
            headers=cash_world.headers("owner"),
        )
        assert desig.status_code == 200, desig.text

        # Now delegate can read cash_cut_difference in BRANCH_A, but NOT
        # order_discount_courtesy_cancellation
        del_alerts = cash_world.client.get(
            "/api/v2/financial/owner-alerts",
            params={"branch_id": BRANCH_A},
            headers=cash_world.headers("delegate"),
        )
        assert del_alerts.status_code == 200, del_alerts.text
        assert [a["alert_type"] for a in del_alerts.json()["items"]] == ["cash_cut_difference"]

        # Revoking delegate's financial grant immediately blocks alert access
        cash_world.revoke("delegate", "cuts-a")
        after_revoke = cash_world.client.get(
            "/api/v2/financial/owner-alerts",
            params={"branch_id": BRANCH_A},
            headers=cash_world.headers("delegate"),
        )
        assert after_revoke.status_code == 403

        # Channel recovers -> retry sends pending alerts without duplicating rows
        should_fail = False
        retried = cash_world.client.post(
            "/api/v2/financial/owner-alerts/retry",
            json={"branch_id": BRANCH_A},
            headers=cash_world.headers("owner"),
        )
        assert retried.status_code == 200, retried.text
        assert retried.json()["sent_count"] >= 2
        assert len(delivered_events) >= 2

        ack = cash_world.client.post(
            f"/api/v2/financial/owner-alerts/{diff_alert['id']}/acknowledge",
            headers=cash_world.headers("owner"),
        )
        assert ack.status_code == 200, ack.text
        assert ack.json()["delivery_status"] == "ACKNOWLEDGED"
    finally:
        set_alert_channel_sender(None)


# ==============================================================================
# PHASE 4 TESTS: Suggested Purchases by Presentation Factor & Low-Stock Alerts
# ==============================================================================


def test_phase4_suggested_purchases_ceiling_formula_and_low_stock_alert(
    cash_world: CashWorld,
) -> None:
    unit_id = ident("p4-unit-kg")
    pack_unit_id = ident("p4-unit-pack")
    supplier_id = ident("p4-supplier")
    item_low_id = ident("p4-item-low")
    item_ok_id = ident("p4-item-ok")
    warehouse_id = ident("p4-warehouse-a")

    with cash_world.sessions() as session:
        existing_wh = session.scalar(
            sa.select(models.warehouses.c.id).where(models.warehouses.c.branch_id == BRANCH_A)
        )
        if existing_wh is None:
            session.execute(
                models.warehouses.insert().values(
                    id=warehouse_id,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    name="Almacén A",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        else:
            warehouse_id = str(existing_wh)

        session.execute(
            models.inventory_units.insert().values(
                [
                    {
                        "id": unit_id,
                        "organization_id": ORG_ID,
                        "code": "KG",
                        "name": "Kilogramo",
                        "dimension": "mass",
                        "precision_scale": 3,
                        "created_at": NOW,
                    },
                    {
                        "id": pack_unit_id,
                        "organization_id": ORG_ID,
                        "code": "CAJA",
                        "name": "Caja",
                        "dimension": "discrete",
                        "precision_scale": 0,
                        "created_at": NOW,
                    },
                ]
            )
        )
        session.execute(
            models.suppliers.insert().values(
                id=supplier_id,
                organization_id=ORG_ID,
                code="PROV-P4",
                commercial_name="Proveedor P4",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.inventory_items.insert().values(
                [
                    {
                        "id": item_low_id,
                        "organization_id": ORG_ID,
                        "name": "Carne Pastor",
                        "sku": "INS-PASTOR",
                        "base_unit_id": unit_id,
                        "status": "active",
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                    {
                        "id": item_ok_id,
                        "organization_id": ORG_ID,
                        "name": "Queso Gouda",
                        "sku": "INS-QUESO",
                        "base_unit_id": unit_id,
                        "status": "active",
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                ]
            )
        )
        # Presentation: 1 CAJA = 6 KG (base_unit_yield = 6)
        session.execute(
            models.purchase_presentations.insert().values(
                id=ident("p4-pres-pastor"),
                organization_id=ORG_ID,
                supplier_id=supplier_id,
                item_id=item_low_id,
                code="CAJA-6KG",
                name="Caja 6 kg",
                package_type="box",
                commercial_quantity=Decimal("1"),
                commercial_unit_id=pack_unit_id,
                base_unit_id=unit_id,
                base_unit_yield=Decimal("6.000000"),
                usable_content=Decimal("6.000000"),
                yield_percent=Decimal("100.000000"),
                last_net_price=Decimal("600.000000"),
                cost_per_base_unit=Decimal("100.000000"),
                is_preferred=True,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        # Thresholds: Carne Pastor min=10, max=25; current stock=7 -> shortage=18 -> ceil(18/6)=3
        # Let's test non-exact division: current stock=6 -> shortage=19 -> ceil(19/6)=4 boxes!
        session.execute(
            models.inventory_stock_thresholds.insert().values(
                [
                    {
                        "id": ident("p4-thresh-low"),
                        "organization_id": ORG_ID,
                        "branch_id": BRANCH_A,
                        "warehouse_id": warehouse_id,
                        "item_id": item_low_id,
                        "minimum_quantity": Decimal("10.000000"),
                        "maximum_quantity": Decimal("25.000000"),
                        "version": 1,
                        "created_by": OWNER_ID,
                        "updated_by": OWNER_ID,
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                    {
                        "id": ident("p4-thresh-ok"),
                        "organization_id": ORG_ID,
                        "branch_id": BRANCH_A,
                        "warehouse_id": warehouse_id,
                        "item_id": item_ok_id,
                        "minimum_quantity": Decimal("5.000000"),
                        "maximum_quantity": Decimal("20.000000"),
                        "version": 1,
                        "created_by": OWNER_ID,
                        "updated_by": OWNER_ID,
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                ]
            )
        )
        session.execute(
            models.inventory_movements.insert().values(
                [
                    {
                        "id": ident("p4-mov-low"),
                        "organization_id": ORG_ID,
                        "branch_id": BRANCH_A,
                        "warehouse_id": warehouse_id,
                        "item_id": item_low_id,
                        "movement_type": "PURCHASE_RECEIPT",
                        "quantity_delta": Decimal("6.000000"),
                        "unit_id": unit_id,
                        "unit_cost": Decimal("100.000000"),
                        "total_cost": Decimal("600.000000"),
                        "effective_at": NOW,
                        "actor_user_id": OWNER_ID,
                        "reason": "Stock inicial",
                        "status": "confirmed",
                        "created_at": NOW,
                    },
                    {
                        "id": ident("p4-mov-ok"),
                        "organization_id": ORG_ID,
                        "branch_id": BRANCH_A,
                        "warehouse_id": warehouse_id,
                        "item_id": item_ok_id,
                        "movement_type": "PURCHASE_RECEIPT",
                        "quantity_delta": Decimal("12.000000"),
                        "unit_id": unit_id,
                        "unit_cost": Decimal("80.000000"),
                        "total_cost": Decimal("960.000000"),
                        "effective_at": NOW,
                        "actor_user_id": OWNER_ID,
                        "reason": "Stock inicial",
                        "status": "confirmed",
                        "created_at": NOW,
                    },
                ]
            )
        )
        session.commit()

    resp = cash_world.client.get(
        "/api/v2/inventory/suggested-purchases",
        params={"branch_id": BRANCH_A},
        headers=cash_world.headers("owner"),
    )
    assert resp.status_code == 200, resp.text
    items = resp.json()["items"]
    assert len(items) == 1
    pastor = items[0]
    assert pastor["item_id"] == item_low_id
    assert pastor["current_stock"] == "6.00"
    assert pastor["maximum_quantity"] == "25.00"
    assert pastor["presentation_factor"] == "6.00"
    # ceil((25 - 6) / 6) = ceil(19 / 6) = 4
    assert pastor["suggested_presentation_units"] == 4
    assert pastor["suggested_base_quantity"] == "24.00"

    # Verify inventory_below_minimum alert was emitted for Owner
    alerts = cash_world.client.get(
        "/api/v2/financial/owner-alerts",
        params={"branch_id": BRANCH_A, "alert_type": "inventory_below_minimum"},
        headers=cash_world.headers("owner"),
    )
    assert alerts.status_code == 200
    assert len(alerts.json()["items"]) == 1
    assert alerts.json()["items"][0]["resource_id"] == item_low_id


# ==============================================================================
# PHASE 5 TESTS: Product Margins ((price - cost) / price), Incomplete Cost Guard,
# and <50% Owner Alert
# ==============================================================================


def test_phase5_product_margins_incomplete_guard_and_below_50_alert(
    cash_world: CashWorld,
) -> None:
    cat_id = ident("p5-cat")
    unit_id = ident("p5-unit")
    wh_id = ident("p5-wh")
    item_costed = ident("p5-item-costed")
    item_uncosted = ident("p5-item-uncosted")
    prod_low_margin = ident("p5-prod-low")
    prod_high_margin = ident("p5-prod-high")
    prod_incomplete = ident("p5-prod-inc")

    with cash_world.sessions() as session:
        existing_wh = session.scalar(
            sa.select(models.warehouses.c.id).where(models.warehouses.c.branch_id == BRANCH_A)
        )
        if existing_wh is None:
            session.execute(
                models.warehouses.insert().values(
                    id=wh_id,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    name="Almacén P5",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        else:
            wh_id = str(existing_wh)

        session.execute(
            models.product_categories.insert().values(
                id=cat_id,
                organization_id=ORG_ID,
                name="Tacos P5",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.inventory_units.insert().values(
                id=unit_id,
                organization_id=ORG_ID,
                code="PZA",
                name="Pieza",
                dimension="discrete",
                precision_scale=0,
                created_at=NOW,
            )
        )
        session.execute(
            models.inventory_items.insert().values(
                [
                    {
                        "id": item_costed,
                        "organization_id": ORG_ID,
                        "name": "Insumo Con Costo",
                        "sku": "P5-COSTED",
                        "base_unit_id": unit_id,
                        "status": "active",
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                    {
                        "id": item_uncosted,
                        "organization_id": ORG_ID,
                        "name": "Insumo Sin Costo",
                        "sku": "P5-UNCOSTED",
                        "base_unit_id": unit_id,
                        "status": "active",
                        "created_at": NOW,
                        "updated_at": NOW,
                    },
                ]
            )
        )
        # Costed item has average_unit_cost = $60.00 MXN
        session.execute(
            models.inventory_cost_states.insert().values(
                branch_id=BRANCH_A,
                warehouse_id=wh_id,
                item_id=item_costed,
                quantity_on_hand=Decimal("10"),
                average_unit_cost=Decimal("60.000000"),
                last_unit_cost=Decimal("60.000000"),
                updated_at=NOW,
            )
        )

        for pid, name, sku, price_cents, comp_item in (
            (
                prod_low_margin,
                "Combo Margen Bajo",
                "P5-LOW",
                10_000,
                item_costed,
            ),  # Price $100, Cost $60 -> 40% (<50%)
            (
                prod_high_margin,
                "Combo Margen Alto",
                "P5-HIGH",
                20_000,
                item_costed,
            ),  # Price $200, Cost $60 -> 70% (>=50%)
            (
                prod_incomplete,
                "Combo Incompleto",
                "P5-INC",
                10_000,
                item_uncosted,
            ),  # Missing component cost
        ):
            session.execute(
                models.products.insert().values(
                    id=pid,
                    organization_id=ORG_ID,
                    category_id=cat_id,
                    name=name,
                    sku=sku,
                    station="kitchen",
                    status="active",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.execute(
                models.price_versions.insert().values(
                    id=ident(f"price:{pid}"),
                    organization_id=ORG_ID,
                    product_id=pid,
                    price_cents=price_cents,
                    currency="MXN",
                    valid_from=NOW,
                    valid_to=None,
                    created_at=NOW,
                )
            )
            rid = ident(f"recipe:{pid}")
            session.execute(
                models.recipes.insert().values(
                    id=rid,
                    organization_id=ORG_ID,
                    product_id=pid,
                    branch_id=BRANCH_A,
                    recipe_type="sale",
                    version=1,
                    status="active",
                    yield_quantity=Decimal("1.000000"),
                    yield_unit_id=unit_id,
                    valid_from=NOW,
                    valid_to=None,
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
            session.execute(
                models.recipe_components.insert().values(
                    recipe_id=rid,
                    item_id=comp_item,
                    quantity_base_units=Decimal("1.000000"),
                    unit_id=unit_id,
                    net_quantity=Decimal("1.000000"),
                    waste_rate=Decimal("0"),
                    gross_quantity=Decimal("1.000000"),
                    sort_order=1,
                )
            )
        session.commit()

    # Non-financial operator cannot read margins
    denied = cash_world.client.get(
        "/api/v2/financial/products/margins",
        params={"branch_id": BRANCH_A},
        headers=cash_world.headers("cashier"),
    )
    assert denied.status_code == 403

    # Owner reads margins
    resp = cash_world.client.get(
        "/api/v2/financial/products/margins",
        params={"branch_id": BRANCH_A},
        headers=cash_world.headers("owner"),
    )
    assert resp.status_code == 200, resp.text
    by_id = {p["product_id"]: p for p in resp.json()["products"]}

    low = by_id[prod_low_margin]
    assert low["cost_complete"] is True
    assert low["margin_reliable"] is True
    assert low["margin_pct"] == "40.00"
    assert low["below_threshold"] is True

    high = by_id[prod_high_margin]
    assert high["cost_complete"] is True
    assert high["margin_reliable"] is True
    assert high["margin_pct"] == "70.00"
    assert high["below_threshold"] is False

    inc = by_id[prod_incomplete]
    assert inc["cost_complete"] is False
    assert inc["margin_reliable"] is False
    assert inc["margin_pct"] is None
    assert inc["incomplete_reason"] == "missing_component_cost"

    # Only the reliable low-margin product emitted a product_margin_below_threshold alert
    alerts = cash_world.client.get(
        "/api/v2/financial/owner-alerts",
        params={"branch_id": BRANCH_A, "alert_type": "product_margin_below_threshold"},
        headers=cash_world.headers("owner"),
    )
    assert alerts.status_code == 200
    items = alerts.json()["items"]
    assert len(items) == 1
    assert items[0]["resource_id"] == prod_low_margin


# ==============================================================================
# PHASE 6 TESTS: High Waste, Consumption Variance, FEFO Expiring Lots (<=3d),
# Delayed Orders, Ticket Reprint (Count + Step-Up + No Extra Sale), and
# Cash Drawer Open Without Sale (Step-Up + Reason + Audit)
# ==============================================================================


def test_phase6_operational_controls_reprint_drawer_and_remaining_alerts(
    cash_world: CashWorld,
) -> None:
    unit_id = ident("p6-unit")
    wh_id = ident("p6-wh")
    item_id = ident("p6-item")
    reason_id = ident("p6-waste-reason")
    delayed_order_id = ident("p6-order-delayed")

    with cash_world.sessions() as session:
        # Configure leader credentials for step-up authorization under protected policy
        salt = "0123456789abcdef0123456789abcdef"
        secret = "LeaderSecret#2026"
        session.execute(
            models.user_credentials.insert().values(
                user_id=cash_world.actors["leader"],
                password_hash=ops.hash_password(secret, salt),
                password_salt=salt,
                password_algorithm=ops.PASSWORD_ALGORITHM,
                updated_at=NOW,
            )
        )
        grant_permission(session, cash_world.roles["leader"], "orders.exceptions.authorize")
        grant_permission(session, cash_world.roles["leader"], "cash.user_cut.finalize")

        existing_wh = session.scalar(
            sa.select(models.warehouses.c.id).where(models.warehouses.c.branch_id == BRANCH_A)
        )
        if existing_wh is None:
            session.execute(
                models.warehouses.insert().values(
                    id=wh_id,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    name="Almacén P6",
                    created_at=NOW,
                    updated_at=NOW,
                )
            )
        else:
            wh_id = str(existing_wh)

        session.execute(
            models.inventory_units.insert().values(
                id=unit_id,
                organization_id=ORG_ID,
                code="L",
                name="Litro",
                dimension="volume",
                precision_scale=2,
                created_at=NOW,
            )
        )
        session.execute(
            models.inventory_items.insert().values(
                id=item_id,
                organization_id=ORG_ID,
                name="Aceite Vegetal",
                sku="P6-ACEITE",
                base_unit_id=unit_id,
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.waste_reasons.insert().values(
                id=reason_id,
                organization_id=ORG_ID,
                code="DERRAME",
                name="Derrame accidental",
                classification="operational",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        # 1. Confirmed high waste record ($650.00 MXN >= $500.00 threshold)
        session.execute(
            models.waste_records.insert().values(
                id=ident("p6-waste-1"),
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                warehouse_id=wh_id,
                item_id=item_id,
                unit_id=unit_id,
                reason_id=reason_id,
                stage="kitchen",
                quantity=Decimal("10.000000"),
                unit_cost=Decimal("65.000000"),
                total_cost=Decimal("650.000000"),
                effective_at=NOW,
                status="confirmed",
                created_by=CASHIER_ID,
                confirmed_by=cash_world.actors["leader"],
                created_at=NOW,
                confirmed_at=NOW,
            )
        )
        # 2. Consumption variance: theoretical = 10 L, real consumption movement = -15 L (50%
        # variance)
        cat_id = ident("p6-cat")
        prod_id = ident("p6-prod")
        rec_id = ident("p6-rec")
        line_id = ident("p6-line")
        session.execute(
            models.product_categories.insert().values(
                id=cat_id,
                organization_id=ORG_ID,
                name="Fritos P6",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.products.insert().values(
                id=prod_id,
                organization_id=ORG_ID,
                category_id=cat_id,
                name="Papas P6",
                sku="P6-PAPAS",
                station="kitchen",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.recipes.insert().values(
                id=rec_id,
                organization_id=ORG_ID,
                product_id=prod_id,
                branch_id=BRANCH_A,
                recipe_type="sale",
                version=1,
                status="active",
                yield_quantity=Decimal("1.000000"),
                yield_unit_id=unit_id,
                valid_from=NOW,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.order_lines.insert().values(
                id=line_id,
                order_id=ident("order:1"),
                product_id=prod_id,
                product_name="Papas P6",
                quantity=1,
                unit_price_cents=5_000,
                line_total_cents=5_000,
                station="kitchen",
                family_id_snapshot=cat_id,
                family_name_snapshot="Fritos P6",
                family_snapshot_source="captured",
                created_at=NOW,
            )
        )
        session.execute(
            models.order_line_consumption_snapshots.insert().values(
                order_line_id=line_id,
                order_id=ident("order:1"),
                recipe_id=rec_id,
                recipe_version=1,
                branch_id=BRANCH_A,
                components=[{"item_id": item_id, "gross_quantity": "10.000000"}],
                total_theoretical_cost=Decimal("650.000000"),
                created_at=NOW,
            )
        )
        session.execute(
            models.inventory_movements.insert().values(
                id=ident("p6-mov-real"),
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                warehouse_id=wh_id,
                item_id=item_id,
                movement_type="SALE_CONSUMPTION",
                quantity_delta=Decimal("-15.000000"),
                unit_id=unit_id,
                unit_cost=Decimal("65.000000"),
                total_cost=Decimal("975.000000"),
                effective_at=NOW,
                actor_user_id=CASHIER_ID,
                reason="Consumo real",
                status="confirmed",
                created_at=NOW,
            )
        )
        # 3. Delayed order in preparation for 45 minutes
        session.execute(
            models.orders.insert().values(
                id=delayed_order_id,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                cash_shift_id=SHIFT_ID,
                customer_id=ident("customer"),
                folio="P6-DELAY-01",
                channel="POS",
                status="IN_PREPARATION",
                total_cents=8_000,
                currency="MXN",
                order_type="dine-in",
                created_at=ops._now() - timedelta(minutes=45),
                accepted_at=ops._now() - timedelta(minutes=45),
            )
        )
        session.commit()

    # Evaluate operational controls (high waste, consumption variance, FEFO lots, delayed orders)
    soon_exp = (ops._now() + timedelta(days=2)).isoformat()
    later_exp = (ops._now() + timedelta(days=10)).isoformat()
    eval_resp = cash_world.client.post(
        "/api/v2/operational-controls/evaluate",
        json={
            "branch_id": BRANCH_A,
            "delay_threshold_minutes": 25,
            "lots": [
                {
                    "lot_code": "LOTE-LEJANO",
                    "item_id": item_id,
                    "item_name": "Aceite Vegetal",
                    "available_quantity": "5.00",
                    "expires_at": later_exp,
                },
                {
                    "lot_code": "LOTE-PROXIMO",
                    "item_id": item_id,
                    "item_name": "Aceite Vegetal",
                    "available_quantity": "3.00",
                    "expires_at": soon_exp,
                },
            ],
        },
        headers=cash_world.headers("owner"),
    )
    assert eval_resp.status_code == 200, eval_resp.text
    eval_data = eval_resp.json()
    assert len(eval_data["high_waste_alerts"]) == 1
    assert len(eval_data["consumption_variance_alerts"]) == 1
    assert len(eval_data["delayed_order_alerts"]) >= 1
    # FEFO order places LOTE-PROXIMO first and alerts only on <=3 days lot
    assert [lot["lot_code"] for lot in eval_data["fefo_lots"]] == ["LOTE-PROXIMO", "LOTE-LEJANO"]
    assert len(eval_data["expiring_lot_alerts"]) == 1
    assert eval_data["expiring_lot_alerts"][0]["resource_id"] == "LOTE-PROXIMO"

    # 4. Ticket reprint requires supervisor step-up, increments reprint_number, and does NOT add
    # sales/orders
    with cash_world.sessions() as session:
        orders_before = session.scalar(sa.select(sa.func.count()).select_from(models.orders))
        payments_before = session.scalar(sa.select(sa.func.count()).select_from(models.payments))
        sales_before = session.scalar(
            sa.select(sa.func.count()).select_from(models.sales_operation_snapshots)
        )

    reprint1 = cash_world.client.post(
        f"/api/v2/orders/{ident('order:1')}/reprint-ticket",
        json={
            "reason": "Impresora atascó papel térmico",
            "supervisor_identity": "leader@fixture.invalid",
            "supervisor_code_or_password": "LeaderSecret#2026",
        },
        headers=cash_world.headers("cashier"),
    )
    assert reprint1.status_code == 200, reprint1.text
    assert reprint1.json()["reprint_number"] == 1
    assert reprint1.json()["duplicates_sale"] is False

    reprint2 = cash_world.client.post(
        f"/api/v2/orders/{ident('order:1')}/reprint-ticket",
        json={
            "reason": "Cliente solicitó copia legible",
            "supervisor_identity": "leader@fixture.invalid",
            "supervisor_code_or_password": "LeaderSecret#2026",
        },
        headers=cash_world.headers("cashier"),
    )
    assert reprint2.status_code == 200, reprint2.text
    assert reprint2.json()["reprint_number"] == 2

    with cash_world.sessions() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == orders_before
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.payments))
            == payments_before
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.sales_operation_snapshots))
            == sales_before
        )

    # 5. Open cash drawer without sale requires supervisor step-up + reason and emits Owner alert
    drawer_open = cash_world.client.post(
        f"/api/v2/cash/shifts/{SHIFT_ID}/open-drawer-no-sale",
        json={
            "reason": "Cambio de billete de $500 por denominaciones menores",
            "supervisor_identity": "leader@fixture.invalid",
            "supervisor_code_or_password": "LeaderSecret#2026",
        },
        headers=cash_world.headers("cashier"),
    )
    assert drawer_open.status_code == 200, drawer_open.text
    assert drawer_open.json()["sequence_number"] == 1
    assert drawer_open.json()["authorized_by_user_id"] == cash_world.actors["leader"]

    owner_alerts = cash_world.client.get(
        "/api/v2/financial/owner-alerts",
        params={"branch_id": BRANCH_A},
        headers=cash_world.headers("owner"),
    )
    assert owner_alerts.status_code == 200
    alert_types = {a["alert_type"] for a in owner_alerts.json()["items"]}
    assert {
        "high_waste",
        "consumption_variance",
        "lot_expiring_soon",
        "order_delayed",
        "ticket_reprint",
        "cash_drawer_no_sale_open",
    }.issubset(alert_types)
