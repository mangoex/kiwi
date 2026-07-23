from __future__ import annotations

from decimal import Decimal

import pytest
from restaurant_os.operations import BusinessError, _variation_quantity, parse_order_comment_values
from test_platform_api import BRANCH_ID, _admin_headers, _client_with_seeded_database

BURGER_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
FRIES_ID = "018f6f73-2d0a-74f0-8f1c-000000000112"
SODA_ID = "018f6f73-2d0a-74f0-8f1c-000000000113"
BEEF_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"


def test_global_comment_parser_deduplicates_without_erasing_visible_text() -> None:
    assert parse_order_comment_values(
        " Sin azúcar,\nSIN AZUCAR  Sin cebolla, Muy caliente  Para llevar "
    ) == [
        "Sin azúcar",
        "Sin cebolla",
        "Muy caliente",
        "Para llevar",
    ]
    assert _variation_quantity("0.125000") == Decimal("0.125000")
    with pytest.raises(BusinessError, match="six decimal places"):
        _variation_quantity("0.0000005")


def test_global_comments_preview_bulk_relationships_and_product_filter() -> None:
    client = _client_with_seeded_database()
    preview = client.post(
        "/api/v1/catalog/order-comments/bulk/preview",
        headers=_admin_headers(),
        json={
            "comments": "Sin azúcar,\nSIN AZUCAR, Sin cebolla",
            "product_ids": [BURGER_ID, FRIES_ID],
        },
    )
    assert preview.status_code == 200
    assert len(preview.json()["created"]) == 2
    assert preview.json()["duplicates"] == ["SIN AZUCAR"]

    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={
            "comments": "Sin azúcar,\nSIN AZUCAR, Sin cebolla",
            "product_ids": [BURGER_ID, FRIES_ID],
        },
    )
    assert applied.status_code == 200
    assert applied.json()["relation_count"] == 4

    second = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "SIN AZUCAR", "product_ids": [BURGER_ID]},
    )
    assert second.status_code == 200
    assert second.json()["existing"]

    burger_names = {
        option["name"]
        for group in client.get(
            f"/api/v1/products/{BURGER_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    fries_names = {
        option["name"]
        for group in client.get(
            f"/api/v1/products/{FRIES_ID}/modifiers", headers=_admin_headers()
        ).json()
        for option in group["options"]
        if option.get("variation_kind") == "order_comment"
    }
    assert burger_names == {"Sin azúcar", "Sin cebolla"}
    assert fries_names == burger_names

    forbidden = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sucursal", "product_ids": [BURGER_ID], "branch_id": BRANCH_ID},
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "global_catalog_branch_override"


def test_global_comment_snapshot_is_frozen_without_inventory_or_price_effect() -> None:
    client = _client_with_seeded_database()
    applied = client.post(
        "/api/v1/catalog/order-comments/bulk",
        headers=_admin_headers(),
        json={"comments": "Sin azúcar", "product_ids": [BURGER_ID]},
    ).json()
    comment_id = applied["items"][0]["id"]
    assert (
        client.post(
            "/api/v1/cash-shifts/open",
            headers=_admin_headers(),
            json={"opening_cash_cents": 10000},
        ).status_code
        == 200
    )
    unrelated = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": SODA_ID,
                    "quantity": 1,
                    "comment_preset_ids": [comment_id],
                }
            ]
        },
    )
    assert unrelated.status_code == 409
    assert unrelated.json()["detail"]["code"] == "comment_preset_not_found"
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": BURGER_ID,
                    "quantity": 1,
                    "comment_preset_ids": [comment_id],
                }
            ]
        },
    )
    assert order.status_code == 200
    payload = order.json()
    snapshot = payload["consumption_snapshots"][0]
    comment = next(item for item in snapshot["modifiers"] if item["kind"] == "order_comment")
    assert comment["comment_preset_id"] == comment_id
    assert comment["kitchen_text"] == "Sin azúcar"
    assert comment["price_delta_cents"] == 0
    assert comment["inventory_effect"] is False
    assert payload["lines"][0]["modifier_total_cents"] == 0


def test_universal_extra_uses_canonical_backend_values_without_product_assignment() -> None:
    client = _client_with_seeded_database()
    forbidden = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID, "branch_id": BRANCH_ID},
    )
    assert forbidden.status_code == 409
    assert forbidden.json()["detail"]["code"] == "global_catalog_branch_override"
    incomplete = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={"inventory_item_id": BEEF_ID},
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "ingredient_extra_configuration_required"
    extra = client.post(
        "/api/v1/catalog/ingredient-variations",
        headers=_admin_headers(),
        json={
            "inventory_item_id": BEEF_ID,
            "add_label": "Aguacate extra",
            "portion_quantity": "10.500000",
            "sale_price_cents": 250,
            "station": "kitchen",
            "display_order": 2,
        },
    )
    assert extra.status_code == 200
    extra_payload = extra.json()
    assert extra_payload["sale_price_cents"] == 250
    assert str(extra_payload["portion_quantity"]) == "10.500000"
    assert (
        client.get(
            "/api/v1/catalog/ingredient-extras/available",
            headers=_admin_headers(),
        ).json()[0]["extra_id"]
        == extra_payload["id"]
    )
    orphan = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "ingredient_extras": [{"extra_id": extra_payload["id"], "portions": 1}],
            "lines": [],
        },
    )
    assert orphan.status_code == 409
    assert orphan.json()["detail"]["code"] == "order_line_modifiers_required"

    assert (
        client.post(
            "/api/v1/cash-shifts/open",
            headers=_admin_headers(),
            json={"opening_cash_cents": 10000},
        ).status_code
        == 200
    )
    invalid_portions = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 1,
                    "ingredient_extras": [{"extra_id": extra_payload["id"], "portions": 1.5}],
                }
            ],
        },
    )
    assert invalid_portions.status_code == 409
    assert invalid_portions.json()["detail"]["code"] == "invalid_ingredient_extra_portions"
    for portions in (0, -1, 100):
        rejected = client.post(
            "/api/v1/orders",
            headers=_admin_headers(),
            json={
                "lines": [
                    {
                        "product_id": FRIES_ID,
                        "quantity": 1,
                        "ingredient_extras": [
                            {"extra_id": extra_payload["id"], "portions": portions}
                        ],
                    }
                ]
            },
        )
        assert rejected.status_code == 409
        assert rejected.json()["detail"]["code"] == "invalid_ingredient_extra_portions"
    duplicate = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 1,
                    "ingredient_extras": [
                        {"extra_id": extra_payload["id"], "portions": 1},
                        {"extra_id": extra_payload["id"], "portions": 1},
                    ],
                }
            ]
        },
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"]["code"] == "duplicate_modifier_option"
    order = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 1,
                    "ingredient_extras": [
                        {
                            "extra_id": extra_payload["id"],
                            "portions": 2,
                            "price_cents": 999999,
                        }
                    ],
                }
            ]
        },
    )
    assert order.status_code == 200
    payload = order.json()
    assert payload["total_cents"] == 4500 + 500
    extra_snapshot = next(
        item
        for item in payload["consumption_snapshots"][0]["modifiers"]
        if item["kind"] == "ingredient_extra"
    )
    assert extra_snapshot["extra_id"] == extra_payload["id"]
    assert extra_snapshot["portion_count"] == 2
    assert str(extra_snapshot["add_quantity"]) == "21.000000"
    assert extra_snapshot["price_delta_cents"] == 500
    assert any(
        component["item_id"] == BEEF_ID and str(component["gross_quantity"]) == "21.000000"
        for component in payload["consumption_snapshots"][0]["components"]
    )

    quantity_two = client.post(
        "/api/v1/orders",
        headers=_admin_headers(),
        json={
            "lines": [
                {
                    "product_id": FRIES_ID,
                    "quantity": 2,
                    "ingredient_extras": [
                        {"extra_id": extra_payload["id"], "portions": 2, "price_cents": 1}
                    ],
                }
            ]
        },
    )
    assert quantity_two.status_code == 200
    quantity_two_payload = quantity_two.json()
    assert quantity_two_payload["total_cents"] == (4500 * 2) + (250 * 2 * 2)
    assert quantity_two_payload["lines"][0]["modifier_total_cents"] == 1000
    quantity_two_snapshot = quantity_two_payload["consumption_snapshots"][0]
    quantity_two_extra = next(
        modifier
        for modifier in quantity_two_snapshot["modifiers"]
        if modifier["kind"] == "ingredient_extra"
    )
    assert quantity_two_extra["portion_count"] == 2
    assert str(quantity_two_extra["add_quantity"]) == "42.000000"
    quantity_two_component = next(
        component
        for component in quantity_two_snapshot["components"]
        if component["item_id"] == BEEF_ID
    )
    assert str(quantity_two_component["gross_quantity"]) == "42.000000"
    assert Decimal(str(quantity_two_component["total_cost"])) == (
        Decimal(str(quantity_two_component["unit_cost"])) * Decimal("42.000000")
    )
    reservation = client.get(
        f"/api/v1/inventory/kardex?item_id={BEEF_ID}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_RESERVATION"
        and Decimal(str(row["quantity_delta"])) == Decimal("-42.000000")
        for row in reservation
    )
    task_id = quantity_two_payload["production_tasks"][0]["id"]
    kds_task = next(
        task for task in client.get("/api/v1/kds/tasks").json() if task["id"] == task_id
    )
    assert any(
        modifier.get("extra_id") == extra_payload["id"]
        and str(modifier.get("add_quantity")) == "42.000000"
        for modifier in kds_task["selected_modifiers"]
    )
    paid = client.post(
        f"/api/v1/orders/{quantity_two_payload['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": quantity_two_payload["total_cents"], "method": "cash"},
    )
    assert paid.status_code == 200
    kitchen_print = next(
        job for job in client.get("/api/v1/print-jobs").json()
        if job["order_id"] == quantity_two_payload["id"] and job["job_type"] == "kitchen"
    )
    assert any(
        modifier.get("extra_id") == extra_payload["id"]
        and str(modifier.get("add_quantity")) == "42.000000"
        for modifier in kitchen_print["payload"]["lines"][0]["selected_modifiers"]
    )
    assert client.post(
        f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "IN_PROGRESS"}
    ).status_code == 200
    assert client.post(
        f"/api/v1/kds/tasks/{task_id}/transition", json={"status": "COMPLETED"}
    ).status_code == 200
    consumption = client.get(
        f"/api/v1/inventory/kardex?item_id={BEEF_ID}", headers=_admin_headers()
    ).json()
    assert any(
        row["movement_type"] == "SALE_CONSUMPTION"
        and Decimal(str(row["quantity_delta"])) == Decimal("-42.000000")
        for row in consumption
    )

    for status in ("needs_review", "archived"):
        if status == "archived":
            assert client.put(
                f"/api/v1/catalog/ingredient-variations/{extra_payload['id']}",
                headers=_admin_headers(),
                json={"status": "active"},
            ).status_code == 200
        assert client.put(
            f"/api/v1/catalog/ingredient-variations/{extra_payload['id']}",
            headers=_admin_headers(),
            json={"status": status},
        ).status_code == 200
        available = client.get(
            "/api/v1/catalog/ingredient-extras/available", headers=_admin_headers()
        ).json()
        assert extra_payload["id"] not in {row["extra_id"] for row in available}
        unavailable = client.post(
            "/api/v1/orders",
            headers=_admin_headers(),
            json={
                "lines": [
                    {
                        "product_id": FRIES_ID,
                        "quantity": 1,
                        "ingredient_extras": [{"extra_id": extra_payload["id"], "portions": 1}],
                    }
                ]
            },
        )
        assert unavailable.status_code == 409
        assert unavailable.json()["detail"]["code"] == "ingredient_extra_not_found"
