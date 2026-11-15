"""Regressions for inventory cost reservation consistency and cash-close ACCEPTED order alerts."""

from __future__ import annotations

import sqlalchemy as sa
from restaurant_os import models
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
    _test_session_factory,
)


def test_inventory_costs_subtracts_open_reservations_and_matches_stock() -> None:
    client = _client_with_seeded_database()
    assert _open_shift(client, 100_000).status_code == 200

    unit_res = client.post(
        "/api/v1/inventory/units",
        headers=_admin_headers(),
        json={"code": "KGT", "name": "Kilogramo Test", "precision_scale": 3, "dimension": "mass"},
    )
    assert unit_res.status_code == 200, unit_res.text
    unit = unit_res.json()

    item_res = client.post(
        "/api/v1/inventory/items",
        headers=_admin_headers(),
        json={
            "name": "ACEITUNA TEST",
            "sku": "99101",
            "item_type": "ingredient",
            "base_unit_id": unit["id"],
        },
    )
    assert item_res.status_code == 200, item_res.text
    item = item_res.json()

    supplier = client.post(
        "/api/v1/suppliers",
        headers=_admin_headers(),
        json={
            "code": "PROV-RES",
            "commercial_name": "Proveedor Test",
            "delivery_days": [],
            "payment_methods": ["transfer"],
        },
    ).json()
    assert (
        client.put(
            f"/api/v1/suppliers/{supplier['id']}/branches/{BRANCH_ID}",
            headers=_admin_headers(),
            json={"is_enabled": True},
        ).status_code
        == 200
    )
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=_admin_headers(),
        json={
            "supplier_id": supplier["id"],
            "item_id": item["id"],
            "code": "ACE-1",
            "name": "Bolsa 1kg",
            "package_type": "bag",
            "commercial_quantity": "1",
            "commercial_unit_id": unit["id"],
            "base_unit_id": unit["id"],
            "base_unit_yield": "1",
            "usable_content": "1",
            "yield_percent": "1",
            "last_net_price": "100",
            "tax_rate": "0",
        },
    ).json()
    purchase = client.post(
        "/api/v1/purchases",
        headers=_admin_headers(),
        json={
            "document_date": "2026-11-14",
            "branch_id": BRANCH_ID,
            "supplier_id": supplier["id"],
            "document_type": "invoice",
            "folio": "FAC-RES-001",
            "payment_method": "transfer",
            "paid_from_cash": False,
            "lines": [
                {
                    "presentation_id": presentation["id"],
                    "quantity": "10",
                    "unit_price": "100",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
    ).json()
    confirm = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm",
        headers={**_admin_headers(), "Idempotency-Key": "confirm-res-001"},
        json={},
    )
    assert confirm.status_code == 200

    product_id = "018f6f73-2d0a-74f0-8f1c-000000000111"
    recipe = client.put(
        f"/api/v1/products/{product_id}/recipe",
        headers={**_admin_headers(), "Idempotency-Key": "recipe-res-001"},
        json={
            "branch_id": BRANCH_ID,
            "expected_active_recipe_id": None,
            "yield_quantity": "1",
            "yield_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000303",
            "components": [
                {
                    "item_id": item["id"],
                    "unit_id": unit["id"],
                    "net_quantity": "2.0",
                    "waste_rate": "0",
                }
            ],
        },
    )
    assert recipe.status_code == 200, recipe.text

    order_res = client.post(
        "/api/v1/orders",
        headers={**_admin_headers(), "Idempotency-Key": "order-res-001"},
        json={"lines": [{"product_id": product_id, "quantity": 1}]},
    )
    assert order_res.status_code == 200, order_res.text
    order = order_res.json()
    assert order["status"] == "ACCEPTED"

    stock_rows = client.get(
        f"/api/v1/inventory/stock?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    cost_rows = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    stock_item = next(r for r in stock_rows if r["id"] == item["id"])
    cost_item = next(r for r in cost_rows if r["item_id"] == item["id"])

    assert float(stock_item["quantity_on_hand"]) == 8.0
    assert float(cost_item["quantity_on_hand"]) == 8.0

    for task in order["production_tasks"]:
        assert (
            client.post(
                f"/api/v1/kds/tasks/{task['id']}/transition",
                headers=_admin_headers(),
                json={"status": "IN_PROGRESS", "branch_id": BRANCH_ID},
            ).status_code
            == 200
        )
        assert (
            client.post(
                f"/api/v1/kds/tasks/{task['id']}/transition",
                headers=_admin_headers(),
                json={"status": "COMPLETED", "branch_id": BRANCH_ID},
            ).status_code
            == 200
        )

    cost_rows_after = client.get(
        f"/api/v1/inventory/costs?branch_id={BRANCH_ID}", headers=_admin_headers()
    ).json()
    cost_item_after = next(r for r in cost_rows_after if r["item_id"] == item["id"])
    assert float(cost_item_after["quantity_on_hand"]) == 8.0


def test_operational_close_emits_owner_alert_when_accepted_orders_remain() -> None:
    client = _client_with_seeded_database()
    shift_res = _open_shift(client, 100_000)
    assert shift_res.status_code == 200
    shift_id = shift_res.json()["id"]

    order_res = client.post(
        "/api/v1/orders",
        headers={**_admin_headers(), "Idempotency-Key": "order-alert-001"},
        json={"lines": [{"product_id": "018f6f73-2d0a-74f0-8f1c-000000000111", "quantity": 1}]},
    )
    assert order_res.status_code == 200, order_res.text
    order = order_res.json()
    assert order["status"] == "ACCEPTED"

    close_res = client.post(
        f"/api/v1/cash/shifts/{shift_id}/close-operationally",
        headers={**_admin_headers(), "Idempotency-Key": "close-alert-001"},
        json={},
    )
    assert close_res.status_code == 200, close_res.text
    assert close_res.json()["cash_shift"]["status"] == "OPERATIVELY_CLOSED"

    with _test_session_factory(client)() as session:
        alerts = (
            session.execute(
                sa.select(models.owner_alerts).where(
                    models.owner_alerts.c.branch_id == BRANCH_ID,
                    models.owner_alerts.c.alert_type == "orders_accepted_after_cash_close",
                )
            )
            .mappings()
            .all()
        )
        assert len(alerts) == 1
        assert alerts[0]["payload"]["count"] == 1
        assert order["folio"] in alerts[0]["payload"]["order_folios"]
