"""AUD-CORE-001: observable regressions for scope and purchase invariants."""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models, operations
from restaurant_os.operations import _now
from sqlalchemy.exc import SQLAlchemyError
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _open_shift, _test_session_factory
from test_purchase_workspace import ITEM_ID, _effects, _presentation, _purchase_payload, _workspace


def purchase_fixture():
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    )
    assert presentation.status_code == 200, presentation.text
    payload = _purchase_payload(suppliers[0], presentation.json()["id"])
    return client, headers, suppliers, payload


def create_draft(client, headers, payload):
    response = client.post("/api/v1/purchases", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_corporate_purchase_list_includes_documents_without_branch_filter():
    client, headers, _, payload = purchase_fixture()
    purchase = create_draft(client, headers, payload)
    response = client.get("/api/v1/purchases", headers=headers)
    assert response.status_code == 200, response.text
    assert purchase["id"] in {row["id"] for row in response.json()}


def test_canonical_profile_supplies_organization_for_purchase_cache_scope():
    client, headers, _, _ = purchase_fixture()
    response = client.get("/api/v1/auth/session", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["organization_id"] == operations.ORGANIZATION_ID
    assert response.json()["user"]["id"] == ADMIN_USER_ID


@pytest.mark.parametrize("corporate_authority", [False, True])
def test_unrelated_organization_role_cannot_expand_branch_purchase_permission(corporate_authority):
    from test_cash_ledger import (
        BRANCH_A,
        BRANCH_B,
        CASHIER_ID,
        CASHIER_ROLE_ID,
        ORG_ID,
        _new_session,
    )
    from test_system_remediation_reports import purchase_row

    engine, session = _new_session()
    try:
        purchase_row(session)
        other = dict(session.execute(sa.select(models.purchase_documents)).mappings().one())
        other.update(
            id="aud-other-purchase",
            branch_id=BRANCH_B,
            folio="AUD-B",
            cash_movement_id=None,
            payment_method="transfer",
            paid_from_cash=False,
        )
        session.execute(models.purchase_documents.insert().values(**other))
        role_id, permission_id = str(uuid4()), str(uuid4())
        session.execute(
            models.roles.insert().values(
                id=role_id,
                organization_id=ORG_ID,
                name="Organización sin compras",
                scope="organization",
                created_at=_now(),
            )
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=CASHIER_ID,
                role_id=role_id,
                branch_id=None,
            )
        )
        session.execute(
            models.permissions.insert().values(
                id=permission_id,
                code="purchases.read",
                description="Read",
                created_at=_now(),
            )
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=CASHIER_ROLE_ID,
                permission_id=permission_id,
            )
        )
        if corporate_authority:
            session.execute(
                models.role_authority_grants.insert().values(
                    role_id=role_id,
                    authority_kind="organization_all_permissions",
                    created_at=_now(),
                )
            )
        session.commit()
        scope = operations.authorize_branch_scope(session, CASHIER_ID, "purchases.read")
        visible = operations.list_purchase_documents(session, scope)
        assert {row["branch_id"] for row in visible} == (
            {BRANCH_A, BRANCH_B} if corporate_authority else {BRANCH_A}
        )
        if corporate_authority:
            assert scope is None
            assert (
                operations.authorize_branch_scope(session, CASHIER_ID, "purchases.read", BRANCH_B)
                == BRANCH_B
            )
        else:
            with pytest.raises(operations.AuthorizationError):
                operations.authorize_branch_scope(session, CASHIER_ID, "purchases.read", BRANCH_B)
    finally:
        session.close()
        engine.dispose()


@pytest.mark.parametrize("path", ["/purchases", "/suppliers"])
def test_purchase_lists_return_forbidden_for_foreign_branch(path):
    client, headers, _, _ = purchase_fixture()
    response = client.get("/api/v1" + path, headers=headers, params={"branch_id": "foreign-branch"})
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "permission_denied"


@pytest.mark.parametrize(
    "path,operation", [("/purchases", "list_purchase_documents"), ("/suppliers", "list_suppliers")]
)
def test_purchase_lists_redact_storage_failure(monkeypatch, caplog, path, operation):
    from restaurant_os import api

    client, headers, _, _ = purchase_fixture()
    marker = "AUDCORE-SENSITIVE-PARAMETERS"

    def fail(*args, **kwargs):
        raise SQLAlchemyError(marker)

    monkeypatch.setattr(api, operation, fail)
    response = client.get("/api/v1" + path, headers=headers, params={"branch_id": BRANCH_ID})
    assert response.status_code == 503, response.text
    assert marker not in response.text
    assert marker not in caplog.text
    assert response.json()["detail"]["code"] == "database_unavailable"


@pytest.mark.parametrize("transition", ["confirm", "cancel"])
def test_purchase_transition_requires_authentication(transition):
    client, _, _, _ = purchase_fixture()
    response = client.post(f"/api/v1/purchases/unknown/{transition}", json={})
    assert response.status_code == 401, response.text


@pytest.mark.parametrize("path", ["/purchases", "/purchases/preview"])
def test_purchase_capture_requires_authentication_before_domain_validation(path):
    client, _, _, payload = purchase_fixture()
    response = client.post(
        "/api/v1" + path, json=payload, headers={"Idempotency-Key": "aud-unauthenticated"}
    )
    assert response.status_code == 401, response.text


@pytest.mark.parametrize("transition", ["confirm", "cancel"])
def test_purchase_transition_redacts_storage_failure(monkeypatch, caplog, transition):
    from restaurant_os import api

    client, headers, _, payload = purchase_fixture()
    purchase = create_draft(client, headers, payload)
    marker = "AUDCORE-TRANSITION-SENSITIVE-PARAMETERS"

    def fail(*args, **kwargs):
        raise SQLAlchemyError(marker)

    operation = (
        "confirm_purchase_document" if transition == "confirm" else "cancel_purchase_document"
    )
    monkeypatch.setattr(api, operation, fail)
    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/{transition}", headers=headers, json={}
    )
    assert response.status_code == 503, response.text
    assert marker not in response.text
    assert marker not in caplog.text
    assert response.json()["detail"]["code"] == "database_unavailable"


def test_supplier_terms_reject_foreign_organization_without_persisting_relation():
    client, headers, suppliers, _ = purchase_fixture()
    foreign_id = str(uuid4())
    with _test_session_factory(client)() as session:
        session.execute(
            models.organizations.insert().values(
                id=foreign_id, name="Foreign", status="active", created_at=_now(), updated_at=_now()
            )
        )
        supplier = dict(
            session.execute(
                sa.select(models.suppliers).where(models.suppliers.c.id == suppliers[0])
            )
            .mappings()
            .one()
        )
        supplier.update(id=str(uuid4()), organization_id=foreign_id)
        session.execute(models.suppliers.insert().values(**supplier))
        before = list(session.execute(sa.select(models.supplier_branch_terms)).mappings())
        session.commit()
    response = client.put(
        f"/api/v1/suppliers/{supplier['id']}/branches/{BRANCH_ID}",
        headers=headers,
        json={"is_enabled": True},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "supplier_or_branch_not_found"
    with _test_session_factory(client)() as session:
        assert list(session.execute(sa.select(models.supplier_branch_terms)).mappings()) == before


@pytest.mark.parametrize("fault", ["auth", "storage"])
def test_supplier_terms_boundary_authenticates_and_redacts_storage(monkeypatch, caplog, fault):
    from restaurant_os import api

    client, headers, suppliers, _ = purchase_fixture()
    path = f"/api/v1/suppliers/{suppliers[0]}/branches/{BRANCH_ID}"
    if fault == "auth":
        assert client.put(path, json={"is_enabled": True}).status_code == 401
        return
    marker = "AUDCORE-TERMS-SENSITIVE"

    def fail(*args, **kwargs):
        raise SQLAlchemyError(marker)

    monkeypatch.setattr(api, "set_supplier_branch_terms", fail)
    response = client.put(path, headers=headers, json={"is_enabled": True})
    assert response.status_code == 503, response.text
    assert marker not in response.text
    assert marker not in caplog.text


@pytest.mark.parametrize("transition", ["confirm", "cancel"])
def test_purchase_transition_rejects_inactive_branch_before_effects(transition):
    client, headers, _, payload = purchase_fixture()
    purchase = create_draft(client, headers, payload)
    with _test_session_factory(client)() as session:
        session.execute(
            models.branches.update()
            .where(models.branches.c.id == BRANCH_ID)
            .values(status="inactive")
        )
        session.commit()
    before = _effects(client)
    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/{transition}",
        headers={**headers, "Idempotency-Key": "audcore-inactive-transition"},
        json={"reason": "Test cancellation"} if transition == "cancel" else {},
    )
    assert response.status_code == 403, response.text
    after = _effects(client)
    # Authorization denial is audited; documents and financial effects stay identical.
    before.pop("audit_events")
    after.pop("audit_events")
    assert after == before


@pytest.mark.parametrize(
    "method,paid,code",
    [
        ("cash", False, "cash_purchase_payment_mismatch"),
        ("transfer", True, "cash_purchase_payment_mismatch"),
        ("credit", False, "workspace_payload_invalid"),
        ("unrecognized", False, "workspace_payload_invalid"),
    ],
)
@pytest.mark.parametrize("path", ["/purchases/preview", "/purchases"])
def test_purchase_capture_rejects_incoherent_payment_without_effects(method, paid, code, path):
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method=method, paid_from_cash=paid)
    before = _effects(client)
    response = client.post("/api/v1" + path, headers=headers, json=payload)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == code
    assert _effects(client) == before


def test_historical_incoherent_draft_cannot_be_confirmed_silently():
    client, headers, _, payload = purchase_fixture()
    purchase = create_draft(client, headers, payload)
    with _test_session_factory(client)() as session:
        session.execute(
            models.purchase_documents.update()
            .where(models.purchase_documents.c.id == purchase["id"])
            .values(payment_method="cash", paid_from_cash=False)
        )
        session.commit()
    before = _effects(client)
    response = client.post(f"/api/v1/purchases/{purchase['id']}/confirm", headers=headers, json={})
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "cash_purchase_payment_mismatch"
    assert _effects(client) == before


@pytest.mark.parametrize(
    "price,remaining,mode,error",
    [
        ("0", "5", "single", "purchase_reversal_insufficient_stock"),
        ("2.50", "5", "single", "purchase_reversal_insufficient_stock"),
        ("0", "10", "single", None),
        ("2.50", "10", "single", None),
        ("0", "1.5", "fractional_multi", "purchase_reversal_insufficient_stock"),
        ("2.50", "3", "fractional_multi", None),
        ("2.50", "4", "fractional_value", "purchase_reversal_cost_conflict"),
        ("0", "4", "fractional_multi", None),
    ],
)
def test_cancellation_validates_aggregate_duplicate_item_quantity(price, remaining, mode, error):
    client, headers, suppliers, payload = purchase_fixture()
    line = {
        **payload["lines"][0],
        "quantity": "1",
        "unit_price": price,
        "discount": "0",
        "tax": "0",
    }
    payload["lines"] = [line, dict(line)]
    removed = Decimal("10")
    if mode.startswith("fractional"):
        second = client.post(
            "/api/v1/purchase-presentations",
            headers=headers,
            json={
                **_presentation(suppliers[0]),
                "code": "AUD-SECOND",
                "usable_content": "10",
                "base_unit_yield": "10",
            },
        )
        assert second.status_code == 200, second.text
        payload["lines"][0]["quantity"] = "0.1"
        payload["lines"][1].update(quantity="0.25", presentation_id=second.json()["id"])
        removed = Decimal("3")  # 0.1*5 + 0.25*10, independently of the writer.
    purchase = create_draft(client, headers, payload)
    with _test_session_factory(client)() as session:
        initial = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.item_id == ITEM_ID
            )
        )
        initial_row = dict(
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.item_id == ITEM_ID
                )
            )
            .mappings()
            .first()
        )
        initial_row.update(
            id=str(uuid4()),
            movement_type="SALE_CONSUMPTION",
            quantity_delta=-Decimal(str(initial)),
            total_cost=Decimal("0"),
            source_type="test_consumption",
            source_id=str(uuid4()),
            idempotency_key=str(uuid4()),
        )
        session.execute(models.inventory_movements.insert().values(**initial_row))
        session.commit()
    confirmed = client.post(f"/api/v1/purchases/{purchase['id']}/confirm", headers=headers, json={})
    assert confirmed.status_code == 200, confirmed.text
    with _test_session_factory(client)() as session:
        current = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.item_id == ITEM_ID
            )
        )
        receipt = dict(
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.source_id == purchase["id"]
                )
            )
            .mappings()
            .first()
        )
        # Fixture consumption leaves the requested physical balance, preserving receipt history.
        receipt.update(
            id=str(uuid4()),
            movement_type="SALE_CONSUMPTION",
            quantity_delta=Decimal(remaining) - Decimal(str(current)),
            total_cost=Decimal("0"),
            source_type="test_consumption",
            source_id=str(uuid4()),
            idempotency_key=str(uuid4()),
        )
        session.execute(models.inventory_movements.insert().values(**receipt))
        if mode == "fractional_value":
            session.execute(
                models.inventory_cost_states.update()
                .where(models.inventory_cost_states.c.item_id == ITEM_ID)
                .values(average_unit_cost=Decimal("0"))
            )
        session.commit()
    before = _effects(client)
    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=headers,
        json={"reason": "Duplicate item regression"},
    )
    if error:
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == error
        assert _effects(client) == before
    else:
        assert response.status_code == 200, response.text
        with _test_session_factory(client)() as session:
            assert (
                session.scalar(
                    sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                        models.inventory_movements.c.item_id == ITEM_ID
                    )
                )
                == Decimal(remaining) - removed
            )
            reversals = (
                session.execute(
                    sa.select(models.inventory_movements).where(
                        models.inventory_movements.c.source_id == purchase["id"],
                        models.inventory_movements.c.movement_type == "PURCHASE_REVERSAL",
                    )
                )
                .mappings()
                .all()
            )
            assert len(reversals) == 2
            assert len({r["reversal_of_id"] for r in reversals}) == 2


def test_purchase_cash_context_exposes_only_authorized_open_register_metadata():
    client, headers, _, _ = purchase_fixture()
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200, shift.text
    response = client.get(
        "/api/v1/purchases/cash-context", headers=headers, params={"branch_id": BRANCH_ID}
    )
    assert response.status_code == 200, response.text
    returned = response.json()
    opened_at = returned["open_registers"][0].pop("opened_at")
    assert datetime.fromisoformat(opened_at.replace("Z", "+00:00")) == datetime.fromisoformat(
        shift.json()["opened_at"].replace("Z", "+00:00")
    )
    assert returned == {
        "branch_id": BRANCH_ID,
        "open_registers": [
            {
                "register_id": "CAJA-01",
                "cash_shift_id": shift.json()["id"],
            }
        ],
    }
    denied = client.get(
        "/api/v1/purchases/cash-context", headers=headers, params={"branch_id": "foreign-branch"}
    )
    assert denied.status_code == 403, denied.text


@pytest.mark.parametrize(
    "grants,allowed",
    [
        (("purchases.manage", "cash.movement.withdraw"), "purchase"),
        (("expenses.manage", "cash.movement.withdraw"), "expense"),
        (("cash.movement.withdraw",), None),
        (("dashboard.read",), "reconciliation"),
        (("reports.expenses.read",), None),
        (("purchases.read", "expenses.read"), "documents"),
    ],
)
def test_domain_grants_do_not_imply_other_documents_cash_or_reports(grants, allowed):
    from test_platform_api import ADMIN_ROLE_ID

    client, headers, _, _ = purchase_fixture()
    with _test_session_factory(client)() as session:
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == ADMIN_ROLE_ID
            )
        )
        for code in grants:
            pid = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            if pid is None:
                pid = str(uuid4())
                session.execute(
                    models.permissions.insert().values(
                        id=pid, code=code, description="Fixture", created_at=_now()
                    )
                )
            session.execute(
                models.role_permissions.insert().values(role_id=ADMIN_ROLE_ID, permission_id=pid)
            )
        session.commit()
    date = "2026-10-09"
    routes = [
        (f"/purchases/cash-context?branch_id={BRANCH_ID}", "purchase"),
        (f"/expenses/cash-context?branch_id={BRANCH_ID}", "expense"),
        (f"/purchases?branch_id={BRANCH_ID}", "purchase_documents"),
        (f"/expenses?branch_id={BRANCH_ID}", "expense_documents"),
        (
            f"/reports/branch-reconciliation/daily?branch_id={BRANCH_ID}&date={date}",
            "reconciliation",
        ),
        (
            f"/reports/branch-reconciliation/consolidated?branch_id={BRANCH_ID}&date_from={date}&date_to={date}",
            "reconciliation",
        ),
        (
            f"/reports/branch-reconciliation/export?branch_id={BRANCH_ID}&month=10&year=2026",
            "reconciliation",
        ),
    ]
    for path, capability in routes:
        version = "/api/v2" if capability == "reconciliation" else "/api/v1"
        response = client.get(version + path, headers=headers)
        permitted = (
            allowed == capability
            or (allowed == "purchase" and capability == "purchase_documents")
            or (
                allowed == "documents" and capability in {"purchase_documents", "expense_documents"}
            )
        )
        assert response.status_code == (200 if permitted else 403), (
            path,
            response.status_code,
            response.text[:400],
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("branch_id", "foreign-branch"),
        ("expected_cash_shift_id", "reopened-shift"),
    ],
)
def test_cash_confirmation_rejects_changed_reviewed_context(field, value):
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200, shift.text
    body = {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "expected_cash_shift_id": shift.json()["id"],
        field: value,
    }
    before = _effects(client)
    response = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm", headers=headers, json=body
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "purchase_cash_context_changed"
    assert _effects(client) == before


def test_confirmation_replay_keeps_identity_after_cancellation():
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200, shift.text
    body = {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "expected_cash_shift_id": shift.json()["id"],
    }
    path = f"/api/v1/purchases/{purchase['id']}/confirm"
    confirmed = client.post(path, headers=headers, json=body)
    assert confirmed.status_code == 200, confirmed.text
    different = client.post(path, headers=headers, json={**body, "register_id": "CAJA-02"})
    assert different.status_code == 409, different.text
    cancelled = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=headers,
        json={"reason": "Return purchase"},
    )
    assert cancelled.status_code == 200, cancelled.text
    before = _effects(client)
    replay = client.post(path, headers=headers, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json()["status"] == "cancelled"
    assert _effects(client) == before


@pytest.mark.parametrize(
    "fault,status",
    [("actor", 409), ("revoked", 403), ("inactive_branch", 403), ("closed_reopened", 200)],
)
def test_confirmed_replay_revalidates_authority_without_replacing_original_turn(fault, status):
    from test_platform_api import ADMIN_ROLE_ID

    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200
    body = {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "expected_cash_shift_id": shift.json()["id"],
    }
    path = f"/api/v1/purchases/{purchase['id']}/confirm"
    response = client.post(path, headers=headers, json=body)
    assert response.status_code == 200, response.text
    replay_headers = dict(headers)
    with _test_session_factory(client)() as session:
        if fault == "actor":
            actor = dict(
                session.execute(sa.select(models.users).where(models.users.c.id == ADMIN_USER_ID))
                .mappings()
                .one()
            )
            actor.update(id=str(uuid4()), email="other-authorized@example.invalid")
            session.execute(models.users.insert().values(**actor))
            session.execute(
                models.user_roles.insert().values(
                    user_id=actor["id"], role_id=ADMIN_ROLE_ID, branch_id=None
                )
            )
            from test_platform_api import create_session_token, get_settings

            replay_headers["Authorization"] = "Bearer " + create_session_token(
                {"sub": actor["id"]}, get_settings().secret_key
            )
        elif fault == "revoked":
            session.execute(
                models.user_roles.delete().where(models.user_roles.c.user_id == ADMIN_USER_ID)
            )
        elif fault == "inactive_branch":
            session.execute(
                models.branches.update()
                .where(models.branches.c.id == BRANCH_ID)
                .values(status="inactive")
            )
        session.commit()
    if fault == "closed_reopened":
        closed = client.post(
            f"/api/v1/cash/shifts/{shift.json()['id']}/close-operationally",
            headers={**headers, "Idempotency-Key": "aud-replay-close"},
            json={},
        )
        assert closed.status_code == 200, closed.text
        reopened = _open_shift(client, 200000, {**headers, "Idempotency-Key": "aud-replay-reopen"})
        assert reopened.status_code == 200, reopened.text
        assert reopened.json()["id"] != body["expected_cash_shift_id"]
    before = _effects(client)
    replay = client.post(path, headers=replay_headers, json=body)
    assert replay.status_code == status, replay.text[:300]
    if status == 200:
        assert replay.json()["cash_movement_id"] == response.json()["cash_movement_id"]
    after = _effects(client)
    before.pop("audit_events")
    after.pop("audit_events")
    assert after == before


@pytest.mark.parametrize("transition", ["replay", "cancel"])
@pytest.mark.parametrize(
    "fault",
    [
        "cash_source",
        "cash_extra",
        "cash_amount",
        "cash_status",
        "cash_reversal",
        "receipt_document",
        "receipt_scope",
        "receipt_unit",
        "receipt_missing",
    ],
)
def test_purchase_commands_reject_foreign_original_effect_identity(transition, fault):
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200
    body = {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "expected_cash_shift_id": shift.json()["id"],
    }
    path = f"/api/v1/purchases/{purchase['id']}/confirm"
    confirmed = client.post(path, headers=headers, json=body)
    assert confirmed.status_code == 200, confirmed.text
    with _test_session_factory(client)() as session:
        if fault == "cash_extra":
            extra = dict(
                session.execute(
                    sa.select(models.cash_movements).where(
                        models.cash_movements.c.id == confirmed.json()["cash_movement_id"]
                    )
                )
                .mappings()
                .one()
            )
            extra.update(id=str(uuid4()), idempotency_key=str(uuid4()))
            session.execute(models.cash_movements.insert().values(**extra))
        elif fault.startswith("cash_"):
            patch = {
                "cash_source": {"source_id": "other-purchase"},
                "cash_amount": {"amount_cents": 1},
                "cash_status": {"status": "pending"},
                "cash_reversal": {"reversal_of_id": confirmed.json()["cash_movement_id"]},
            }[fault]
            session.execute(
                models.cash_movements.update()
                .where(models.cash_movements.c.id == confirmed.json()["cash_movement_id"])
                .values(**patch)
            )
        elif fault == "receipt_missing":
            receipt_id = session.scalar(
                sa.select(models.inventory_movements.c.id).where(
                    models.inventory_movements.c.source_id == purchase["id"]
                )
            )
            session.execute(
                models.inventory_movements.delete().where(
                    models.inventory_movements.c.id == receipt_id
                )
            )
        else:
            patch = {
                "receipt_document": {"document_id": "other-purchase"},
                "receipt_scope": {"branch_id": "other-branch"},
                "receipt_unit": {"unit_id": "other-unit"},
            }[fault]
            session.execute(
                models.inventory_movements.update()
                .where(models.inventory_movements.c.source_id == purchase["id"])
                .values(**patch)
            )
        session.commit()
    before = _effects(client)
    response = client.post(
        path if transition == "replay" else f"/api/v1/purchases/{purchase['id']}/cancel",
        headers=headers,
        json=body if transition == "replay" else {"reason": "Return"},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "purchase_effect_integrity_conflict"
    assert _effects(client) == before


@pytest.mark.parametrize(
    "table_name,field",
    [
        ("cash_movements", "branch_id"),
        ("cash_movements", "organization_id"),
        ("inventory_movements", "branch_id"),
        ("inventory_movements", "organization_id"),
    ],
)
def test_purchase_reader_does_not_expose_foreign_scope_children(table_name, field):
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    assert _open_shift(client, 200000, headers).status_code == 200
    confirmed = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm",
        headers=headers,
        json={"register_id": "CAJA-01"},
    )
    assert confirmed.status_code == 200, confirmed.text
    with _test_session_factory(client)() as session:
        table = models.metadata.tables[table_name]
        session.execute(
            table.update()
            .where(table.c.source_id == purchase["id"])
            .values(**{field: "foreign-scope", "reason": "PRIVATE-FROM-OTHER-SCOPE"})
        )
        session.commit()
    before = _effects(client)
    response = client.get(f"/api/v1/purchases?branch_id={BRANCH_ID}", headers=headers)
    assert response.status_code == 409, response.text[:300]
    assert response.json()["detail"]["code"] == "purchase_effect_integrity_conflict"
    assert "PRIVATE-FROM-OTHER-SCOPE" not in response.text
    assert _effects(client) == before


@pytest.mark.parametrize("transition", ["confirm", "cancel"])
def test_purchase_domain_rolls_back_all_effects_after_audit_failure(monkeypatch, transition):
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200, shift.text
    if transition == "cancel":
        confirmed = client.post(
            f"/api/v1/purchases/{purchase['id']}/confirm",
            headers=headers,
            json={"register_id": "CAJA-01"},
        )
        assert confirmed.status_code == 200, confirmed.text
    before = _effects(client)
    original_audit = operations._audit

    def fail(session, action, *args, **kwargs):
        if action == ("purchase.confirmed" if transition == "confirm" else "purchase.cancelled"):
            raise RuntimeError("Injected audit failure")
        return original_audit(session, action, *args, **kwargs)

    monkeypatch.setattr(operations, "_audit", fail)
    with _test_session_factory(client)() as session:
        with pytest.raises(RuntimeError, match="Injected audit failure"):
            if transition == "confirm":
                operations.confirm_purchase_document(
                    session, purchase["id"], "audcore-fault", "CAJA-01", ADMIN_USER_ID
                )
            else:
                operations.cancel_purchase_document(session, purchase["id"], "Fault", ADMIN_USER_ID)
        # A caller reusing the session cannot accidentally commit partial domain effects.
        session.commit()
    assert _effects(client) == before


@pytest.mark.parametrize(
    "transition,table_name",
    [
        ("confirm", "cash_movements"),
        ("confirm", "inventory_movements"),
        ("confirm", "inventory_cost_states"),
        ("confirm", "supplier_price_history"),
        ("confirm", "purchase_presentations"),
        ("confirm", "purchase_documents"),
        ("cancel", "inventory_movements"),
        ("cancel", "inventory_cost_states"),
        ("cancel", "cash_movements"),
        ("cancel", "purchase_documents"),
    ],
)
def test_purchase_domain_rolls_back_after_each_effect_write(monkeypatch, transition, table_name):
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    purchase = create_draft(client, headers, payload)
    assert _open_shift(client, 200000, headers).status_code == 200
    if transition == "cancel":
        response = client.post(
            f"/api/v1/purchases/{purchase['id']}/confirm",
            headers=headers,
            json={"register_id": "CAJA-01"},
        )
        assert response.status_code == 200, response.text
    before = _effects(client)
    with _test_session_factory(client)() as session:
        original_execute = session.execute
        reached = False

        def injected(statement, *args, **kwargs):
            nonlocal reached
            result = original_execute(statement, *args, **kwargs)
            if (
                isinstance(statement, (sa.sql.dml.Insert, sa.sql.dml.Update))
                and statement.table.name == table_name
            ):
                reached = True
                raise RuntimeError("Injected after persisted effect")
            return result

        monkeypatch.setattr(session, "execute", injected)
        with pytest.raises(RuntimeError, match="Injected after persisted effect"):
            if transition == "confirm":
                operations.confirm_purchase_document(
                    session, purchase["id"], "aud-write-fault", "CAJA-01", ADMIN_USER_ID
                )
            else:
                operations.cancel_purchase_document(
                    session, purchase["id"], "Return", ADMIN_USER_ID
                )
        assert reached, "The selected write must actually occur before the injected failure"
        session.commit()
    assert _effects(client) == before


def test_purchase_and_expenses_share_cash_without_inventory_dependencies():
    client, headers, _, payload = purchase_fixture()
    payload.update(payment_method="cash", paid_from_cash=True)
    payload["lines"] = [
        {**payload["lines"][0], "quantity": "1", "unit_price": "300", "discount": "0", "tax": "0"}
    ]
    purchase = create_draft(client, headers, payload)
    shift = _open_shift(client, 200000, headers)
    assert shift.status_code == 200, shift.text
    confirmed = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm",
        headers=headers,
        json={"register_id": "CAJA-01"},
    )
    assert confirmed.status_code == 200, confirmed.text
    with _test_session_factory(client)() as session:
        from test_platform_api import ADMIN_ROLE_ID

        for code in (
            "expense.concept.manage",
            "expense.concept.read",
            "expenses.manage",
            "expenses.read",
            "reports.expenses.read",
        ):
            pid = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            if pid is None:
                pid = str(uuid4())
                session.execute(
                    models.permissions.insert().values(
                        id=pid, code=code, description="Fixture", created_at=_now()
                    )
                )
            session.execute(
                models.role_permissions.insert().values(role_id=ADMIN_ROLE_ID, permission_id=pid)
            )
        session.commit()
    before = _effects(client)
    concept = client.post(
        "/api/v1/expense-concepts",
        headers={**headers, "Idempotency-Key": "aud-integrated-concept"},
        json={"code": "AUD-LUZ", "name": "Luz", "description": "Servicio"},
    )
    assert concept.status_code == 200, concept.text
    for method, total in (("cash", 30000), ("transfer", 100000)):
        created = client.post(
            "/api/v1/expenses",
            headers={**headers, "Idempotency-Key": f"aud-integrated-{method}"},
            json={
                "branch_id": BRANCH_ID,
                "concept_id": concept.json()["id"],
                "document_date": "2026-10-09",
                "total_cents": total,
                "tax_cents": None,
                "payment_method": method,
                "reference": "Test",
                "notes": "",
                "evidence_refs": ["archivo:integracion"],
            },
        )
        assert created.status_code == 200, created.text
        body = {"branch_id": BRANCH_ID, "version": 1}
        if method == "cash":
            body.update(register_id="CAJA-01", expected_cash_shift_id=shift.json()["id"])
        response = client.post(
            f"/api/v1/expenses/{created.json()['id']}/confirm",
            headers={**headers, "Idempotency-Key": f"aud-integrated-confirm-{method}"},
            json=body,
        )
        assert response.status_code == 200, response.text
    after = _effects(client)
    for table in (
        "inventory_movements",
        "inventory_cost_states",
        "purchase_presentations",
        "supplier_price_history",
        "purchase_documents",
        "purchase_document_lines",
    ):
        assert after[table] == before[table], table
    with _test_session_factory(client)() as session:
        assert (
            operations.calculate_expected_cash(session, shift.json()["id"])["expected_cash_cents"]
            == 140000
        )
        totals = session.scalars(
            sa.select(models.expense_documents.c.total_cents).where(
                models.expense_documents.c.status == "confirmed"
            )
        ).all()
        assert sum(totals) == 130000
