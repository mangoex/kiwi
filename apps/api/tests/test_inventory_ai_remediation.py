"""Permanent acceptance regressions for scoped procurement assistance."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.inventory_ai import (
    audit_inventory_yield_and_waste,
    calculate_suggested_purchases,
    parse_supplier_invoice_data,
)
from restaurant_os.operations import ORGANIZATION_ID
from test_inventory_ai import USER_ID, _grant_procurement_actor
from test_inventory_ai import client as client
from test_inventory_ai import sample_inventory_data as sample_inventory_data
from test_inventory_ai import test_db as test_db


def test_ocr_must_not_invent_a_line_for_empty_input():
    parsed = parse_supplier_invoice_data("")
    assert parsed["lines"] == [], parsed


def test_ocr_preserves_exact_cent_amount():
    parsed = parse_supplier_invoice_data("Producto | 1 | $19.99")
    assert parsed["lines"][0]["unit_price_cents"] == 1999, parsed


@pytest.mark.parametrize(
    "text",
    [
        "Producto | -1 | $19.99",
        "Producto | 1 | -19.99",
        "Producto | desconocido | $19.99",
        "Producto | 1 | sin precio",
        "Producto | 1 | $1,99",
        "Producto | 0 | $19.99",
        "Producto | 1 | 1000000000000",
        "Producto | 0.0000001 | 1",
    ],
)
def test_ocr_invalid_amounts_are_not_replaced_by_defaults(text):
    parsed = parse_supplier_invoice_data(text)
    assert parsed["lines"] == []
    assert parsed["status"] == "insufficient_data"
    assert parsed["warnings"]
    assert parsed["supplier_name"] is None and parsed["folio"] is None


def test_ocr_rounds_half_cent_and_preserves_decimal_quantity():
    parsed = parse_supplier_invoice_data("Producto | 0.125 | $0.29\nOtro | 1 | $19.995")
    assert Decimal(parsed["lines"][0]["quantity"]) == Decimal("0.125")
    assert parsed["lines"][0]["line_total_cents"] == 4
    assert parsed["lines"][1]["unit_price_cents"] == 2000


def test_suggestions_do_not_use_other_branch_history(test_db, sample_inventory_data):
    known = calculate_suggested_purchases(test_db, sample_inventory_data["branch_id"], 7)
    foreign = calculate_suggested_purchases(test_db, "018f6f73-2d0a-74f0-8f1c-999999999999", 7)
    assert foreign == [], {"known": known, "foreign": foreign}


def test_suggestion_endpoint_denies_ungranted_actor(client, sample_inventory_data):
    token = create_session_token(
        {"user_id": USER_ID, "organization_id": ORGANIZATION_ID}, get_settings().secret_key
    )
    response = client.post(
        "/api/v1/admin-ai/suggested-purchases",
        headers={"Authorization": "Bearer " + token},
        json={"branch_id": "018f6f73-2d0a-74f0-8f1c-999999999999", "days_ahead": 7},
    )
    assert response.status_code in (401, 403, 404), response.text


@pytest.mark.parametrize("inactive", [False, True])
def test_routes_check_persisted_actor_permissions_and_state(
    client, test_db, sample_inventory_data, inactive
):
    _grant_procurement_actor(test_db)
    if inactive:
        test_db.execute(
            sa.update(models.users).where(models.users.c.id == USER_ID).values(status="inactive")
        )
    else:
        test_db.execute(models.role_permissions.delete())
    test_db.commit()
    token = create_session_token(
        {"user_id": USER_ID, "organization_id": ORGANIZATION_ID}, get_settings().secret_key
    )
    headers = {"Authorization": "Bearer " + token}
    branch_id = sample_inventory_data["branch_id"]
    requests = [
        client.post(
            "/api/v1/admin-ai/suggested-purchases",
            headers=headers,
            json={"branch_id": branch_id, "days_ahead": 7},
        ),
        client.get(
            "/api/v1/admin-ai/inventory-yield-audit",
            headers=headers,
            params={"branch_id": branch_id},
        ),
        client.post(
            "/api/v1/admin-ai/parse-invoice-ocr",
            headers=headers,
            json={"invoice_text": "Producto | 1 | $19.99"},
        ),
    ]
    assert all(response.status_code == 403 for response in requests), [
        response.text for response in requests
    ]


def test_reader_cannot_request_another_existing_branch(client, test_db, sample_inventory_data):
    _grant_procurement_actor(test_db)
    branch_id = sample_inventory_data["branch_id"]
    other_id = "018f6f73-2d0a-74f0-8f1c-000000000099"
    existing = dict(
        test_db.execute(sa.select(models.branches).where(models.branches.c.id == branch_id))
        .mappings()
        .one()
    )
    test_db.execute(
        models.branches.insert().values(
            **{**existing, "id": other_id, "code": "OTHER", "name": "Otra sucursal"}
        )
    )
    test_db.commit()
    token = create_session_token(
        {"user_id": USER_ID, "organization_id": ORGANIZATION_ID}, get_settings().secret_key
    )
    response = client.post(
        "/api/v1/admin-ai/suggested-purchases",
        headers={"Authorization": "Bearer " + token},
        json={"branch_id": other_id, "days_ahead": 7},
    )
    assert response.status_code == 403, response.text


def test_real_other_branch_history_and_local_catalog_do_not_leak(test_db, sample_inventory_data):
    branch_a = sample_inventory_data["branch_id"]
    branch_b = "018f6f73-2d0a-74f0-8f1c-000000000098"
    item_b = "018f6f73-2d0a-74f0-8f1c-000000000097"
    supplier_b = "018f6f73-2d0a-74f0-8f1c-000000000096"
    document_b = "018f6f73-2d0a-74f0-8f1c-000000000095"
    for table, where, patch in [
        (
            models.branches,
            models.branches.c.id == branch_a,
            {"id": branch_b, "code": "B", "name": "Sucursal B"},
        ),
        (
            models.inventory_items,
            models.inventory_items.c.id == sample_inventory_data["item_id"],
            {
                "id": item_b,
                "sku": "LOCAL-B",
                "name": "Insumo exclusivo B",
                "catalog_scope": "branch",
                "source_branch_id": branch_b,
            },
        ),
        (
            models.suppliers,
            models.suppliers.c.id == sample_inventory_data["supplier_id"],
            {"id": supplier_b, "code": "SUP-B", "commercial_name": "Proveedor exclusivo B"},
        ),
        (
            models.purchase_documents,
            sa.true(),
            {
                "id": document_b,
                "branch_id": branch_b,
                "supplier_id": supplier_b,
                "folio": "B-RECENT",
                "created_at": datetime.now(timezone.utc) + timedelta(days=1),
            },
        ),
        (
            models.purchase_document_lines,
            sa.true(),
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000094",
                "purchase_document_id": document_b,
                "unit_price": Decimal("999.99"),
            },
        ),
    ]:
        original = dict(test_db.execute(sa.select(table).where(where)).mappings().first())
        test_db.execute(table.insert().values(**{**original, **patch}))
    test_db.commit()
    suggestions = calculate_suggested_purchases(test_db, branch_a, 7)
    assert suggestions, "A must retain its own positive proposal"
    assert all(group["supplier_id"] != supplier_b for group in suggestions)
    assert all(line["item_id"] != item_b for group in suggestions for line in group["lines"])
    assert suggestions[0]["supplier_id"] == sample_inventory_data["supplier_id"]


def test_waste_from_existing_other_branch_is_never_returned(client, test_db, sample_inventory_data):
    _grant_procurement_actor(test_db)
    branch_a = sample_inventory_data["branch_id"]
    branch_b = "018f6f73-2d0a-74f0-8f1c-000000000099"
    original = dict(test_db.execute(sa.select(models.branches)).mappings().one())
    test_db.execute(models.branches.insert().values(**{**original, "id": branch_b, "code": "B"}))
    test_db.execute(
        models.waste_records.insert().values(
            id="waste-b",
            organization_id=ORGANIZATION_ID,
            branch_id=branch_b,
            warehouse_id="warehouse-b",
            item_id=sample_inventory_data["item_id"],
            unit_id="unit-b",
            reason_id="reason-b",
            stage="storage",
            quantity=Decimal("500"),
            total_cost=Decimal("999"),
            effective_at=datetime.now(timezone.utc),
            created_at=datetime.now(timezone.utc),
            created_by=USER_ID,
            status="confirmed",
        )
    )
    test_db.commit()
    assert audit_inventory_yield_and_waste(test_db, branch_a, 30) == []
    assert audit_inventory_yield_and_waste(test_db, branch_b, 30)
    token = create_session_token(
        {"user_id": USER_ID, "organization_id": ORGANIZATION_ID}, get_settings().secret_key
    )
    response = client.get(
        "/api/v1/admin-ai/inventory-yield-audit",
        headers={"Authorization": "Bearer " + token},
        params={"branch_id": branch_b},
    )
    assert response.status_code == 403, response.text
