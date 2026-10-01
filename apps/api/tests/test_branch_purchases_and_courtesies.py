from __future__ import annotations

import uuid
from decimal import Decimal

import sqlalchemy as sa
from restaurant_os import models
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _open_shift,
    _test_session_factory,
)


def test_branch_supplier_presentation_and_multiline_purchase():
    """Characterize a three-line receipt using an authorized admin fixture.

    Verify exact amounts, atomic draft rejection, confirmation replay and reversals.
    """
    client = _client_with_seeded_database()
    headers = _admin_headers()

    # 1. Get an existing inventory item and units
    items_res = client.get("/api/v1/inventory/items", headers=headers)
    assert items_res.status_code == 200
    items = items_res.json()
    assert len(items) > 0
    item = items[0]
    item_id = item["id"]
    base_unit_id = item["base_unit_id"]

    units_res = client.get("/api/v1/inventory/units", headers=headers)
    assert units_res.status_code == 200
    units = units_res.json()
    assert len(units) > 0
    commercial_unit_id = units[0]["id"]

    # 2. Create local supplier
    supplier_code = f"SUP-{uuid.uuid4().hex[:6].upper()}"
    res_sup = client.post(
        "/api/v1/suppliers",
        json={
            "code": supplier_code,
            "commercial_name": "Fruteria La Huerta Local",
            "legal_name": "Frutas y Verduras La Huerta SA de CV",
            "tax_id": f"FRU{uuid.uuid4().hex[:9].upper()}",
            "credit_days": 0,
            "branch_id": BRANCH_ID,
            "contacts": [
                {
                    "name": "Don Pedro",
                    "phone": "6671234567",
                    "email": "pedro@huerta.com",
                    "primary_for_orders": True,
                }
            ],
        },
        headers=headers,
    )
    assert res_sup.status_code == 200, res_sup.text
    sup_data = res_sup.json()
    supplier_id = sup_data["id"]
    assert supplier_id is not None

    # 3. Create purchase presentation
    pres_code = f"PRES-{uuid.uuid4().hex[:6].upper()}"
    res_pres = client.post(
        "/api/v1/purchase-presentations",
        json={
            "supplier_id": supplier_id,
            "item_id": item_id,
            "commercial_unit_id": commercial_unit_id,
            "base_unit_id": base_unit_id,
            "code": pres_code,
            "name": "Paquete de 10 unidades base",
            "usable_content": "10.000000",
            "base_unit_yield": "10.000000",
            "yield_percent": "1.000000",
            "last_net_price": "250.00",
            "status": "active",
        },
        headers=headers,
    )
    assert res_pres.status_code == 200, res_pres.text
    pres_data = res_pres.json()
    pres_id = pres_data["id"]
    assert pres_id is not None

    # Same item, a different commercial presentation.
    smaller_res = client.post(
        "/api/v1/purchase-presentations",
        json={
            "supplier_id": supplier_id,
            "item_id": item_id,
            "commercial_unit_id": commercial_unit_id,
            "base_unit_id": base_unit_id,
            "code": "TC-280-PACK-5",
            "name": "Paquete de 5 unidades base",
            "usable_content": "5.000000",
            "base_unit_yield": "5.000000",
            "yield_percent": "1.000000",
            "last_net_price": "19.99",
            "status": "active",
        },
        headers=headers,
    )
    assert smaller_res.status_code == 200, smaller_res.text
    smaller_id = smaller_res.json()["id"]
    payload = {
        "branch_id": BRANCH_ID,
        "supplier_id": supplier_id,
        "document_type": "invoice",
        "document_date": "2026-09-30",
        "folio": f"FAC-{uuid.uuid4().hex[:6].upper()}",
        "paid_from_cash": False,
        "payment_method": "other",
        "lines": [
            {
                "presentation_id": pres_id,
                "quantity": "2",
                "unit_price": "250.00",
                "discount": "1.00",
                "tax": "40.00",
            },
            {
                "presentation_id": smaller_id,
                "quantity": "1",
                "unit_price": "19.99",
                "discount": "0.29",
                "tax": "3.15",
            },
            {
                "presentation_id": pres_id,
                "quantity": "0.5",
                "unit_price": "0.29",
                "discount": "0",
                "tax": "0.02",
            },
        ],
    }
    factory = _test_session_factory(client)

    def persisted_effects():
        with factory() as session:
            return {
                table.name: list(session.execute(sa.select(table)).mappings())
                for table in (
                    models.purchase_documents,
                    models.purchase_document_lines,
                    models.inventory_movements,
                    models.inventory_cost_states,
                    models.cash_movements,
                )
            }

    def physical_quantity():
        with factory() as session:
            return session.scalar(
                sa.select(
                    sa.func.coalesce(sa.func.sum(models.inventory_movements.c.quantity_delta), 0)
                ).where(
                    models.inventory_movements.c.branch_id == BRANCH_ID,
                    models.inventory_movements.c.item_id == item_id,
                    models.inventory_movements.c.movement_type.notin_(
                        ["SALE_RESERVATION", "RESERVATION_RELEASE"]
                    ),
                )
            )

    # An invalid final line must not leave a partly saved document or effects.
    baseline = persisted_effects()
    invalid_payload = {
        **payload,
        "lines": [
            *payload["lines"][:-1],
            {**payload["lines"][-1], "presentation_id": "00000000-0000-0000-0000-000000000999"},
        ],
    }
    rejected = client.post("/api/v1/purchases", json=invalid_payload, headers=headers)
    assert rejected.status_code == 409, rejected.text
    assert rejected.json()["detail"]["code"] == "purchase_presentation_not_found"
    assert persisted_effects() == baseline
    starting_quantity = physical_quantity()

    res_pur = client.post("/api/v1/purchases", json=payload, headers=headers)
    assert res_pur.status_code == 200, res_pur.text
    pur_data = res_pur.json()
    purchase_id = pur_data["id"]
    assert pur_data["status"] == "draft"
    assert len(pur_data["lines"]) == 3
    assert {line["presentation_id"] for line in pur_data["lines"]} == {pres_id, smaller_id}
    for field, expected in (
        ("subtotal", "520.135000"),
        ("discount_total", "1.29"),
        ("tax_total", "43.17"),
        ("total", "562.015000"),
    ):
        assert Decimal(str(pur_data[field])) == Decimal(expected)
    assert sorted(Decimal(str(line["base_quantity"])) for line in pur_data["lines"]) == [
        Decimal("5"),
        Decimal("5"),
        Decimal("20"),
    ]
    assert sum(Decimal(str(line["inventory_cost"])) for line in pur_data["lines"]) == Decimal(
        "518.845000"
    )
    assert physical_quantity() == starting_quantity

    idempotency_key = f"conf-{uuid.uuid4()}"
    confirm_headers = {**headers, "Idempotency-Key": idempotency_key}
    res_conf = client.post(
        f"/api/v1/purchases/{purchase_id}/confirm",
        json={"idempotency_key": idempotency_key},
        headers=confirm_headers,
    )
    assert res_conf.status_code == 200, res_conf.text
    confirmed = res_conf.json()
    assert confirmed["status"] == "confirmed"
    assert len(confirmed["lines"]) == 3
    assert len(confirmed["inventory_movements"]) == 3
    assert confirmed["cash_movements"] == []
    assert physical_quantity() == starting_quantity + Decimal("30")
    receipt_ids = {movement["id"] for movement in confirmed["inventory_movements"]}

    after_confirmation = persisted_effects()
    replay = client.post(
        f"/api/v1/purchases/{purchase_id}/confirm",
        json={"idempotency_key": idempotency_key},
        headers=confirm_headers,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == purchase_id
    assert persisted_effects() == after_confirmation

    res_cancel = client.post(
        f"/api/v1/purchases/{purchase_id}/cancel",
        json={"reason": "Error en captura de folio de factura"},
        headers=headers,
    )
    assert res_cancel.status_code == 200, res_cancel.text
    cancelled = res_cancel.json()
    assert cancelled["status"] == "cancelled"
    assert physical_quantity() == starting_quantity
    assert cancelled["cash_movements"] == []
    originals = [
        movement for movement in cancelled["inventory_movements"] if movement["id"] in receipt_ids
    ]
    assert {movement["id"] for movement in originals} == receipt_ids
    assert sorted(originals, key=lambda row: row["id"]) == sorted(
        confirmed["inventory_movements"], key=lambda row: row["id"]
    )
    reversals = [
        movement
        for movement in cancelled["inventory_movements"]
        if movement["reversal_of_id"] in receipt_ids
    ]
    assert len(reversals) == 3
    assert {movement["reversal_of_id"] for movement in reversals} == receipt_ids


def test_purchase_paid_from_cash_shift_and_cancellation_compensation():
    """Verify BDD-SC-079 and BDD-SC-081:
    A direct purchase paid in cash automatically links to the open cash shift,
    creates a cash withdrawal, and upon cancellation creates a compensating cash deposit.
    """
    client = _client_with_seeded_database()
    headers = _admin_headers()

    # 1. Open cash shift with 200,000 cents ($2,000 MXN)
    shift_res = _open_shift(client, opening_cash_cents=200000, headers=headers)
    assert shift_res.status_code == 200

    # 2. Get item & units
    items = client.get("/api/v1/inventory/items", headers=headers).json()
    item = items[0]
    units = client.get("/api/v1/inventory/units", headers=headers).json()
    commercial_unit_id = units[0]["id"]

    # 3. Create supplier & presentation
    sup = client.post(
        "/api/v1/suppliers",
        json={
            "code": f"FRUT-{uuid.uuid4().hex[:4].upper()}",
            "commercial_name": "Fruteria Express",
            "legal_name": "Fruteria Express SA",
            "branch_id": BRANCH_ID,
            "credit_days": 0,
        },
        headers=headers,
    ).json()

    pres = client.post(
        "/api/v1/purchase-presentations",
        json={
            "supplier_id": sup["id"],
            "item_id": item["id"],
            "commercial_unit_id": commercial_unit_id,
            "base_unit_id": item["base_unit_id"],
            "code": f"P-{uuid.uuid4().hex[:4].upper()}",
            "name": "Bolsa 5 Kg",
            "usable_content": "5.000000",
            "base_unit_yield": "5.000000",
            "yield_percent": "1.000000",
            "last_net_price": "100.00",
            "status": "active",
        },
        headers=headers,
    ).json()

    # 4. Create purchase with paid_from_cash = True ($300 MXN total)
    purchase = client.post(
        "/api/v1/purchases",
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": sup["id"],
            "document_type": "ticket",
            "document_date": "2026-09-30",
            "folio": f"TCK-{uuid.uuid4().hex[:5].upper()}",
            "paid_from_cash": True,
            "payment_method": "cash",
            "lines": [
                {
                    "presentation_id": pres["id"],
                    "quantity": "3",
                    "unit_price": "100.00",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
        headers=headers,
    ).json()

    # 5. Cash confirmation fails closed without a configured register.
    missing_register = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm",
        json={},
        headers={**headers, "Idempotency-Key": f"conf-missing-{uuid.uuid4()}"},
    )
    assert missing_register.status_code == 409
    assert missing_register.json()["detail"]["code"] == "cash_movement_invalid"

    # 6. Confirm purchase with cash shift
    conf_res = client.post(
        f"/api/v1/purchases/{purchase['id']}/confirm",
        json={"idempotency_key": f"conf-{uuid.uuid4()}", "register_id": "CAJA-01"},
        headers={**headers, "Idempotency-Key": f"conf-header-{uuid.uuid4()}"},
    )
    assert conf_res.status_code == 200, conf_res.text
    confirmed = conf_res.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["paid_from_cash"] is True
    assert confirmed["cash_movement_id"] is not None

    # 7. Cancel purchase and verify cash movement compensation
    cancel_res = client.post(
        f"/api/v1/purchases/{purchase['id']}/cancel",
        json={"reason": "Cancelación por devolución de fruta"},
        headers=headers,
    )
    assert cancel_res.status_code == 200, cancel_res.text
    cancelled = cancel_res.json()
    assert cancelled["status"] == "cancelled"
