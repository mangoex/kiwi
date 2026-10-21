import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from test_delivery_fee_catalog import create_tariff, enable_policy
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
    _test_session_factory,
)

PRODUCT = "018f6f73-2d0a-74f0-8f1c-000000000111"


def setup_delivery(client: TestClient | None = None) -> tuple[TestClient, dict, dict]:
    client = client or _client_with_seeded_database()
    tariff = create_tariff(client)
    enable_policy(client, tariff["id"])
    assert _open_shift(client, 50000).status_code == 200
    customer = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "name": "Entrega de prueba",
            "phones": [{"number": "6691239876", "is_primary": True}],
        },
    ).json()
    address = client.post(
        f"/api/v1/customers/{customer['id']}/addresses",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "alias": "Casa",
            "street": "Prueba",
            "exterior_number": "1",
            "neighborhood": "Centro",
            "postal_code": "80000",
            "city": "Culiacán",
            "municipality": "Culiacán",
            "state": "Sinaloa",
            "is_default": True,
        },
    ).json()
    payload = {
        "branch_id": BRANCH_ID,
        "register_id": "CAJA-01",
        "order_type": "delivery",
        "payment_method_intent": "cash",
        "customer_id": customer["id"],
        "delivery_address_id": address["id"],
        "lines": [{"product_id": PRODUCT, "quantity": 1}],
        "delivery_selection": {"mode": "AUTO"},
    }
    return client, payload, tariff


def quote(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/v1/orders/quote", headers=_admin_headers(), json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def test_quote_create_pay_and_ticket_include_fee_once_without_inventory_line() -> None:
    client, payload, _ = setup_delivery()
    priced = quote(client, payload)
    assert priced["total_cents"] == 12300
    assert priced["tax_cents"] is None
    assert priced["delivery_charge"]["charged_cents"] == 2800
    payload["delivery_quote_reference"] = priced["delivery_quote_reference"]
    response = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert response.status_code == 200, response.text
    order = response.json()
    assert len(order["lines"]) == 1
    assert len(order["production_tasks"]) == 1
    assert order["delivery_charge"]["charged_cents"] == 2800
    paid = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 12300, "method": "cash", "register_id": "CAJA-01"},
    )
    assert paid.status_code == 200, paid.text
    with _test_session_factory(client)() as session:
        tickets = (
            session.execute(
                sa.select(models.print_jobs.c.payload).where(
                    models.print_jobs.c.order_id == order["id"],
                    models.print_jobs.c.job_type == "ticket",
                )
            )
            .scalars()
            .all()
        )
        assert tickets[0]["delivery_charge"]["charged_cents"] == 2800
        snapshot = (
            session.execute(
                sa.select(models.sales_operation_snapshots).where(
                    models.sales_operation_snapshots.c.order_id == order["id"]
                )
            )
            .mappings()
            .one()
        )
        assert snapshot["net_cents"] == 12300
        assert snapshot["tax_cents"] is None


def test_remove_fee_only_preserves_production_and_replay_intention() -> None:
    client, payload, _ = setup_delivery()
    priced = quote(client, payload)
    payload["delivery_quote_reference"] = priced["delivery_quote_reference"]
    order_response = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert order_response.status_code == 200, order_response.text
    order = order_response.json()
    with _test_session_factory(client)() as session:
        inventory_before = [
            dict(row) for row in session.execute(sa.select(models.inventory_movements)).mappings()
        ]
    edit = {
        **payload,
        "order_id": order["id"],
        "expected_version": 1,
        "delivery_selection": {"mode": "REMOVED"},
    }
    edit.pop("delivery_quote_reference", None)
    priced = quote(client, edit)
    edit["delivery_quote_reference"] = priced["delivery_quote_reference"]
    headers = {**_admin_headers(), "Idempotency-Key": "delivery-remove-command-001"}
    response = client.post(f"/api/v1/orders/{order['id']}/amendments", headers=headers, json=edit)
    assert response.status_code == 200, response.text
    removed = response.json()
    with _test_session_factory(client)() as session:
        assert [
            dict(row) for row in session.execute(sa.select(models.inventory_movements)).mappings()
        ] == inventory_before
    assert removed["total_cents"] == 9500
    assert removed["delivery_charge"]["state"] == "REMOVED"
    assert [t["id"] for t in removed["production_tasks"]] == [
        t["id"] for t in order["production_tasks"]
    ]
    replay = client.post(f"/api/v1/orders/{order['id']}/amendments", headers=headers, json=edit)
    assert replay.status_code == 200
    restored_intention = {**edit, "expected_version": 2, "delivery_selection": {"mode": "AUTO"}}
    restored_intention["delivery_quote_reference"] = quote(client, restored_intention)[
        "delivery_quote_reference"
    ]
    restored = client.post(
        f"/api/v1/orders/{order['id']}/amendments",
        headers=_admin_headers(),
        json=restored_intention,
    )
    assert restored.status_code == 200, restored.text
    assert restored.json()["total_cents"] == 12300
    replay_after_restore = client.post(
        f"/api/v1/orders/{order['id']}/amendments", headers=headers, json=edit
    )
    assert replay_after_restore.json() == replay.json()
    changed = {**edit, "delivery_selection": {"mode": "AUTO"}}
    assert (
        client.post(
            f"/api/v1/orders/{order['id']}/amendments", headers=headers, json=changed
        ).status_code
        == 409
    )
    from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID

    with _test_session_factory(client)() as session:
        session.execute(
            models.roles.update().where(models.roles.c.id == ADMIN_ROLE_ID).values(scope="branch")
        )
        session.execute(
            models.user_roles.update()
            .where(models.user_roles.c.user_id == ADMIN_USER_ID)
            .values(branch_id=BRANCH_ID)
        )
        read_permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "orders.read")
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                models.role_permissions.c.permission_id == read_permission,
            )
        )
        session.commit()
    assert client.get(f"/api/v1/orders/{order['id']}", headers=_admin_headers()).status_code == 403
    denied_replay = client.post(
        f"/api/v1/orders/{order['id']}/amendments", headers=headers, json=edit
    )
    assert denied_replay.status_code == 403, denied_replay.text


def test_stale_quote_and_legacy_client_cannot_silently_change_amount() -> None:
    client, payload, tariff = setup_delivery()
    priced = quote(client, payload)
    missing = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "delivery_contract_upgrade_required"
    revised = client.post(
        f"/api/v1/delivery-tariffs/{tariff['id']}/revisions",
        headers=_admin_headers(),
        json={"expected_version": 1, "name": "Nuevo", "amount_cents": 3000, "active": True},
    )
    assert revised.status_code == 200
    payload["delivery_quote_reference"] = priced["delivery_quote_reference"]
    stale = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "delivery_quote_stale"


def test_legacy_delivery_stays_without_fee_after_branch_activation() -> None:
    client, payload, tariff = setup_delivery()
    policy = {
        "branch_id": BRANCH_ID,
        "expected_version": 1,
        "enabled": False,
        "eligible_tariff_ids": [tariff["id"]],
        "default_tariff_id": tariff["id"],
        "free_threshold_cents": None,
    }
    assert (
        client.post("/api/v1/delivery-policies", headers=_admin_headers(), json=policy).status_code
        == 200
    )
    response = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert response.status_code == 200, response.text
    order = response.json()
    assert order["total_cents"] == 9500
    assert (
        client.post(
            "/api/v1/delivery-policies",
            headers=_admin_headers(),
            json={**policy, "enabled": True, "expected_version": 2},
        ).status_code
        == 200
    )
    edit = {**payload, "order_id": order["id"], "expected_version": 1}
    assert quote(client, edit)["total_cents"] == 9500
    response = client.post(
        f"/api/v1/orders/{order['id']}/amendments", headers=_admin_headers(), json=edit
    )
    assert response.status_code == 200, response.text
    assert response.json()["total_cents"] == 9500
    assert response.json()["delivery_charge"] is None


def test_discounted_products_drive_threshold_and_payment_line_totals_reconcile() -> None:
    client, payload, tariff = setup_delivery()
    policy = {
        "branch_id": BRANCH_ID,
        "expected_version": 1,
        "enabled": True,
        "eligible_tariff_ids": [tariff["id"]],
        "default_tariff_id": tariff["id"],
        "free_threshold_cents": 9000,
    }
    assert (
        client.post("/api/v1/delivery-policies", headers=_admin_headers(), json=policy).status_code
        == 200
    )
    authorization = client.post(
        "/api/v1/orders/adjustments/authorize",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "supervisor_pin": "superadmin-test-password",
            "lines": payload["lines"],
            "adjustment": {"type": "percent", "value": "10", "reason": "Descuento de prueba"},
        },
    )
    assert authorization.status_code == 200, authorization.text
    payload["adjustment_authorization_id"] = authorization.json()["authorization_id"]
    priced = quote(client, payload)
    assert priced["delivery_charge"]["eligible_subtotal_cents"] == 8550
    assert priced["total_cents"] == 11350
    payload["delivery_quote_reference"] = priced["delivery_quote_reference"]
    response = client.post("/api/v1/orders", headers=_admin_headers(), json=payload)
    assert response.status_code == 200, response.text
    order = response.json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 11350, "method": "cash", "register_id": "CAJA-01"},
    )
    assert paid.status_code == 200, paid.text
    with _test_session_factory(client)() as session:
        line = (
            session.execute(
                sa.select(models.sales_operation_line_snapshots).where(
                    models.sales_operation_line_snapshots.c.payment_id == paid.json()["id"]
                )
            )
            .mappings()
            .one()
        )
        assert line["gross_cents"] == 9500
        assert line["discount_cents"] == 950
        assert line["net_cents"] + 2800 == 11350
