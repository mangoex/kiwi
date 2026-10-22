"""CC-D09: branch receiving uses quantities, never corporate management or prices."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission, ident
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.operations import ORGANIZATION_ID
from test_cash_ledger import NOW
from test_corporate_purchases import (
    BRANCH_ID,
    SECOND_BRANCH_ID,
    SECOND_WAREHOUSE_ID,
    _corporate_workspace,
    _effect_counts,
    _order_payload,
)
from test_corte_ciego_f105_intents import activate
from test_platform_api import _test_session_factory


@pytest.fixture
def receiving():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "f108-create"},
        json=_order_payload(supplier, presentation, warehouse),
    )
    assert created.status_code == 200, created.text
    order = created.json()
    result = client.post(
        f"/api/v1/corporate-purchases/{order['id']}/approve",
        headers={**headers, "Idempotency-Key": "f108-approve"},
        json={"expected_version": 1},
    )
    assert result.status_code == 200, result.text
    factory = _test_session_factory(client)
    activate(factory)
    user, role = ident("receiver-user"), ident("receiver-role")
    with factory() as session:
        session.execute(
            models.users.insert().values(
                id=user,
                organization_id=ORGANIZATION_ID,
                email="receiver@fixture.invalid",
                display_name="Receiver",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.roles.insert().values(
                id=role,
                organization_id=ORGANIZATION_ID,
                name="Receiving only",
                scope="branch",
                created_at=NOW,
            )
        )
        session.execute(
            models.user_roles.insert().values(user_id=user, role_id=role, branch_id=BRANCH_ID)
        )
        grant_permission(session, role, "purchases.receive")
        session.commit()
    receiver = {
        "Authorization": "Bearer " + create_session_token({"sub": user}, get_settings().secret_key),
        "Idempotency-Key": "f108-receive",
    }
    allocation = next(a for a in order["lines"][0]["allocations"] if a["branch_id"] == BRANCH_ID)
    payload = {
        "expected_version": 2,
        "branch_id": BRANCH_ID,
        "warehouse_id": warehouse,
        "discrepancy_reason": "Proveedor entrego parcialmente; pendiente en siguiente entrega",
        "lines": [{"allocation_id": allocation["id"], "quantity": "0.50"}],
    }
    try:
        yield client, receiver, order, payload
    finally:
        client.close()


def test_receive_without_corporate_management_or_monetary_response(receiving):
    client, headers, order, payload = receiving
    path = f"/api/v1/corporate-purchases/{order['id']}/receipts"
    before = _effect_counts(client)
    result = client.post(path, headers=headers, json=payload)
    assert result.status_code == 200, result.text
    assert result.json()["projection"] == "operational"
    for field in ("unit_price", "cost", "line_total", "subtotal", "tax_total"):
        assert field not in result.text
    assert result.json()["receipt"]["branch_id"] == BRANCH_ID
    assert result.json()["receipt"]["lines"][0]["presentation_quantity"] == "0.500000"
    after = _effect_counts(client)
    assert after["inventory"] == before["inventory"] + 1
    replay = client.post(path, headers=headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json() == result.json()
    assert _effect_counts(client) == after
    with _test_session_factory(client)() as session:
        event = session.execute(
            sa.select(models.audit_events.c.payload).where(
                models.audit_events.c.action == "corporate_purchase.received"
            )
        ).scalar_one()
        assert event["discrepancy_reason"] == payload["discrepancy_reason"]
        assert event["receipt_id"] == result.json()["receipt"]["id"]
        assert event["differences"][0]["pending_quantity"] == "0.500000"
    changed = client.post(
        path, headers=headers, json={**payload, "discrepancy_reason": "Otro motivo"}
    )
    assert changed.status_code == 409, changed.text
    denied = client.post(
        f"/api/v1/corporate-purchases/{order['id']}/approve",
        headers=headers,
        json={"expected_version": 3},
    )
    assert denied.status_code == 403, denied.text


def test_partial_receipt_requires_reason_before_any_effect(receiving):
    client, headers, order, payload = receiving
    before = _effect_counts(client)
    payload.pop("discrepancy_reason")
    result = client.post(
        f"/api/v1/corporate-purchases/{order['id']}/receipts", headers=headers, json=payload
    )
    assert result.status_code == 409, result.text
    assert result.json()["detail"]["code"] == "corporate_purchase_difference_reason_required"
    assert _effect_counts(client) == before


def test_receiving_is_limited_to_assigned_branch(receiving):
    client, headers, order, payload = receiving
    allocation = next(
        a for a in order["lines"][0]["allocations"] if a["branch_id"] == SECOND_BRANCH_ID
    )
    before = _effect_counts(client)
    result = client.post(
        f"/api/v1/corporate-purchases/{order['id']}/receipts",
        headers=headers,
        json={
            **payload,
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "lines": [{"allocation_id": allocation["id"], "quantity": "1"}],
        },
    )
    assert result.status_code == 403, result.text
    assert _effect_counts(client) == before


def test_receiving_list_returns_only_quantity_context(receiving):
    client, headers, order, payload = receiving
    result = client.get(
        "/api/v2/purchases/receiving", headers=headers, params={"branch_id": BRANCH_ID}
    )
    assert result.status_code == 200, result.text
    assert result.json()["items"][0]["id"] == order["id"]
    assert (
        result.json()["items"][0]["lines"][0]["allocation_id"]
        == payload["lines"][0]["allocation_id"]
    )
    for forbidden in ("cost", "price", "tax", "subtotal", SECOND_BRANCH_ID):
        assert forbidden not in result.text


def test_legacy_receipt_revalidates_after_commit(monkeypatch):
    from restaurant_os import purchase_receiving
    from test_platform_api import ADMIN_ROLE_ID

    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    try:
        created = client.post(
            "/api/v1/corporate-purchases",
            headers={**headers, "Idempotency-Key": "legacy-create"},
            json=_order_payload(supplier, presentation, warehouse),
        ).json()
        approved = client.post(
            f"/api/v1/corporate-purchases/{created['id']}/approve",
            headers={**headers, "Idempotency-Key": "legacy-approve"},
            json={"expected_version": 1},
        )
        assert approved.status_code == 200, approved.text
        original = purchase_receiving.authority
        calls = 0

        def revoke_after_commit(session, actor, branch, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 2:
                permission = session.scalar(
                    sa.select(models.permissions.c.id).where(
                        models.permissions.c.code == "purchases.corporate.manage"
                    )
                )
                session.execute(
                    models.role_permissions.delete().where(
                        models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                        models.role_permissions.c.permission_id == permission,
                    )
                )
                session.commit()
            return original(session, actor, branch, **kwargs)

        monkeypatch.setattr(purchase_receiving, "authority", revoke_after_commit)
        allocation = next(
            row for row in created["lines"][0]["allocations"] if row["branch_id"] == BRANCH_ID
        )
        response = client.post(
            f"/api/v1/corporate-purchases/{created['id']}/receipts",
            headers={**headers, "Idempotency-Key": "legacy-receive"},
            json={
                "expected_version": 2,
                "branch_id": BRANCH_ID,
                "warehouse_id": warehouse,
                "lines": [{"allocation_id": allocation["id"], "quantity": "1"}],
            },
        )
        assert response.status_code == 403, response.text
        assert "unit_price" not in response.text
        assert _effect_counts(client)["inventory"] > 0
    finally:
        client.close()
