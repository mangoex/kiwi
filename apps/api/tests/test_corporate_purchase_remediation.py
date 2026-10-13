from decimal import Decimal

import pytest
import sqlalchemy as sa
from restaurant_os import models
from test_corporate_purchases import (
    BRANCH_ID,
    ITEM_ID,
    SECOND_BRANCH_ID,
    SECOND_WAREHOUSE_ID,
    _corporate_workspace,
    _order_payload,
    _test_session_factory,
)


def _create(client, headers, payload, key):
    response = client.post(
        "/api/v1/corporate-purchases", headers={**headers, "Idempotency-Key": key}, json=payload
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_allocations_preserve_frozen_line_base_quantity():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    with _test_session_factory(client)() as session:
        session.execute(
            sa.update(models.purchase_presentations)
            .where(models.purchase_presentations.c.id == presentation)
            .values(base_unit_yield=Decimal("0.333333"))
        )
        session.commit()
    payload = _order_payload(supplier, presentation, warehouse)
    line = payload["lines"][0]
    line["quantity"] = "1"
    for allocation in line["allocations"]:
        allocation["quantity"] = "0.5"
    created = _create(client, headers, payload, "audit-rounding")
    actual = sum(Decimal(a["base_quantity"]) for a in created["lines"][0]["allocations"])
    expected = Decimal(created["lines"][0]["base_quantity"])
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "audit-rounding-approve"},
        json={"expected_version": 1},
    ).json()
    version = approved["version"]
    for index, allocation in enumerate(approved["lines"][0]["allocations"]):
        receipt = client.post(
            f"/api/v1/corporate-purchases/{created['id']}/receipts",
            headers={**headers, "Idempotency-Key": f"audit-rounding-receipt-{index}"},
            json={
                "expected_version": version,
                "branch_id": allocation["branch_id"],
                "warehouse_id": allocation["warehouse_id"],
                "lines": [{"allocation_id": allocation["id"], "quantity": "0.5"}],
            },
        )
        assert receipt.status_code == 200, receipt.text
        version = receipt.json()["order"]["version"]
    assert receipt.json()["order"]["status"] == "RECEIVED"
    with _test_session_factory(client)() as session:
        received = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.document_id == created["id"]
            )
        )
    assert received == expected, (
        f"RECEIVED ledger quantity {received} != frozen line base {expected}"
    )
    assert actual == expected, f"allocation base sum {actual} != frozen line base {expected}"


def test_frozen_receipt_identity_survives_catalog_rename():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    created = _create(
        client, headers, _order_payload(supplier, presentation, warehouse), "identity-create"
    )
    snapshot = created["lines"][0]["presentation_snapshot"]
    assert all(
        snapshot[field]
        for field in ("item_name", "item_sku", "name", "base_unit_code", "commercial_unit_code")
    )
    with _test_session_factory(client)() as session:
        session.execute(
            sa.update(models.inventory_items)
            .where(models.inventory_items.c.id == ITEM_ID)
            .values(name="Nombre posterior", sku="SKU-POSTERIOR")
        )
        session.execute(
            sa.update(models.purchase_presentations)
            .where(models.purchase_presentations.c.id == presentation)
            .values(name="Presentación posterior")
        )
        session.commit()
    detail = client.get(f"/api/v1/corporate-purchases/{created['id']}", headers=headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["lines"][0]["presentation_snapshot"] == snapshot


def test_branch_catalog_item_cannot_be_allocated_to_other_branch():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    with _test_session_factory(client)() as session:
        session.execute(
            sa.update(models.inventory_items)
            .where(models.inventory_items.c.id == ITEM_ID)
            .values(catalog_scope="branch", source_branch_id=BRANCH_ID)
        )
        session.commit()
    response = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "audit-scope"},
        json=_order_payload(supplier, presentation, warehouse),
    )
    assert response.status_code != 200, response.text


def test_inactive_item_cannot_be_ordered():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    with _test_session_factory(client)() as session:
        session.execute(
            sa.update(models.inventory_items)
            .where(models.inventory_items.c.id == ITEM_ID)
            .values(status="inactive")
        )
        session.commit()
    response = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "audit-inactive"},
        json=_order_payload(supplier, presentation, warehouse),
    )
    assert response.status_code != 200, response.text


def test_approve_replay_cannot_change_url_order():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    payload = _order_payload(supplier, presentation, warehouse)
    first = _create(client, headers, payload, "audit-create-first")
    payload["folio"] = "AUDIT-SECOND"
    second = _create(client, headers, payload, "audit-create-second")
    body = {"expected_version": 1}
    first_approval = client.post(
        f"/api/v1/corporate-purchases/{first['id']}/approve",
        headers={**headers, "Idempotency-Key": "audit-approve"},
        json=body,
    )
    assert first_approval.status_code == 200, first_approval.text
    replay = client.post(
        f"/api/v1/corporate-purchases/{second['id']}/approve",
        headers={**headers, "Idempotency-Key": "audit-approve"},
        json=body,
    )
    assert replay.status_code == 409, replay.text


@pytest.mark.parametrize(
    "body",
    [
        {"expected_version": 1, "order_id": "another-order"},
        {"expected_version": True},
    ],
)
def test_approval_rejects_identity_injection_and_boolean_version(body):
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    created = _create(
        client, headers, _order_payload(supplier, presentation, warehouse), "strict-create"
    )
    response = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "strict-approve"},
        json=body,
    )
    assert response.status_code in {400, 409, 422}, response.text
    with _test_session_factory(client)() as session:
        assert (
            session.scalar(
                sa.select(models.corporate_purchase_orders.c.status).where(
                    models.corporate_purchase_orders.c.id == created["id"]
                )
            )
            == "DRAFT"
        )


def test_inconsistent_legacy_allocation_is_blocked_without_history_rewrite():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    created = _create(
        client, headers, _order_payload(supplier, presentation, warehouse), "legacy-create"
    )
    with _test_session_factory(client)() as session:
        session.execute(
            sa.update(models.corporate_purchase_orders)
            .where(models.corporate_purchase_orders.c.id == created["id"])
            .values(allocation_policy_version=1)
        )
        for line in created["lines"]:
            session.execute(
                sa.update(models.corporate_purchase_allocations)
                .where(models.corporate_purchase_allocations.c.order_line_id == line["id"])
                .values(allocation_sequence=None, inventory_cost_target=None)
            )
        allocation_id = created["lines"][0]["allocations"][0]["id"]
        session.execute(
            sa.update(models.corporate_purchase_allocations)
            .where(models.corporate_purchase_allocations.c.id == allocation_id)
            .values(base_quantity=Decimal("0.000001"))
        )
        session.commit()
    response = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "legacy-approve"},
        json={"expected_version": 1},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "corporate_purchase_legacy_allocation_invalid"
    with _test_session_factory(client)() as session:
        assert session.scalar(
            sa.select(models.corporate_purchase_allocations.c.base_quantity).where(
                models.corporate_purchase_allocations.c.id == allocation_id
            )
        ) == Decimal("0.000001")


def test_prorated_cost_never_becomes_negative_at_last_destination():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    with _test_session_factory(client)() as session:
        session.execute(
            sa.update(models.purchase_presentations)
            .where(models.purchase_presentations.c.id == presentation)
            .values(base_unit_yield=Decimal("0.000001"))
        )
        source = dict(
            session.execute(
                sa.select(models.branches).where(models.branches.c.id == SECOND_BRANCH_ID)
            )
            .mappings()
            .one()
        )
        source_warehouse = dict(
            session.execute(
                sa.select(models.warehouses).where(models.warehouses.c.id == SECOND_WAREHOUSE_ID)
            )
            .mappings()
            .one()
        )
        destinations = [(BRANCH_ID, warehouse), (SECOND_BRANCH_ID, SECOND_WAREHOUSE_ID)]
        for index in range(2):
            branch = f"018f6f73-2d0a-74f0-8f1c-00000000821{index}"
            new_warehouse = f"018f6f73-2d0a-74f0-8f1c-00000000822{index}"
            session.execute(
                models.branches.insert().values(
                    **{**source, "id": branch, "code": f"AUDIT-{index}", "name": f"Audit {index}"}
                )
            )
            session.execute(
                models.warehouses.insert().values(
                    **{**source_warehouse, "id": new_warehouse, "branch_id": branch}
                )
            )
            destinations.append((branch, new_warehouse))
        session.commit()
    payload = _order_payload(supplier, presentation, warehouse)
    line = payload["lines"][0]
    line.update(quantity="4", unit_price="0.000001", discount="0.000002", tax="0")
    line["allocations"] = [
        {"branch_id": b, "warehouse_id": w, "quantity": "1"} for b, w in destinations
    ]
    created = _create(client, headers, payload, "audit-negative-create")
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "audit-negative-approve"},
        json={"expected_version": 1},
    ).json()
    costs = []
    from restaurant_os.corporate_purchases import _allocation_cost_target

    with _test_session_factory(client)() as session:
        for allocation in approved["lines"][0]["allocations"]:
            costs.append(
                _allocation_cost_target(
                    session,
                    {
                        **allocation,
                        "line_inventory_cost": Decimal(approved["lines"][0]["inventory_cost"]),
                        "line_presentation_quantity": Decimal("4"),
                    },
                )
            )
    allocation = approved["lines"][0]["allocations"][costs.index(min(costs))]
    receipt = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "audit-negative-receipt"},
        json={
            "expected_version": 2,
            "branch_id": allocation["branch_id"],
            "warehouse_id": allocation["warehouse_id"],
            "lines": [{"allocation_id": allocation["id"], "quantity": "1"}],
        },
    )
    assert receipt.status_code == 200, receipt.text
    with _test_session_factory(client)() as session:
        average = session.scalar(
            sa.select(models.inventory_cost_states.c.average_unit_cost).where(
                models.inventory_cost_states.c.branch_id == allocation["branch_id"],
                models.inventory_cost_states.c.item_id == ITEM_ID,
            )
        )
    assert average >= 0, (
        f"negative average after valid receipt: {average}; allocation costs {costs}"
    )
    assert min(costs) >= 0, f"allocation costs: {costs}"


def test_header_totals_cannot_exceed_database_decimal_range():
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    payload = _order_payload(supplier, presentation, warehouse)
    line = payload["lines"][0]
    line.update(quantity="1", unit_price="600000000000", discount="0", tax="0")
    line["allocations"] = [{"branch_id": BRANCH_ID, "warehouse_id": warehouse, "quantity": "1"}]
    payload["lines"].append(dict(line))
    response = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "audit-aggregate"},
        json=payload,
    )
    assert response.status_code != 200, response.text


@pytest.mark.parametrize("price", ["10000000000.000003", "999999999999.999999"])
def test_sqlite_refuses_lossy_numeric_storage_before_creating_order(price):
    client, headers, supplier, presentation, warehouse = _corporate_workspace()
    payload = _order_payload(supplier, presentation, warehouse)
    payload["lines"][0].update(quantity="1", unit_price=price, discount="0", tax="0")
    for allocation in payload["lines"][0]["allocations"]:
        allocation["quantity"] = "0.5"
    response = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "lossy-create"},
        json=payload,
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "corporate_purchase_storage_precision_unsupported"
    with _test_session_factory(client)() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.corporate_purchase_orders))
            == 0
        )
