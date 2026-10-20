"""CORP-PUR-001 corporate order and distributed receipt regressions."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.operations import ORGANIZATION_ID
from test_platform_api import (
    ADMIN_ROLE_ID,
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)

UTC = timezone.utc
LEGAL_ENTITY_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
SECOND_BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000008201"
SECOND_WAREHOUSE_ID = "018f6f73-2d0a-74f0-8f1c-000000008202"
ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
BASE_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
PACKAGE_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000303"


def _corporate_workspace():
    client = _client_with_seeded_database()
    headers = _admin_headers()
    now = datetime(2026, 10, 12, tzinfo=UTC)
    with _test_session_factory(client)() as session:
        corporate_permissions = {
            "purchases.corporate.read": "018f6f73-2d0a-74f0-8f1c-000000000982",
            "purchases.corporate.manage": "018f6f73-2d0a-74f0-8f1c-000000000983",
        }
        for code, permission_id in corporate_permissions.items():
            session.execute(
                models.permissions.insert().values(
                    id=permission_id,
                    code=code,
                    description=code,
                    created_at=now,
                )
            )
            session.execute(
                models.role_permissions.insert().values(
                    role_id=ADMIN_ROLE_ID, permission_id=permission_id
                )
            )
        business_unit_id = session.scalar(
            sa.select(models.business_units.c.id).where(
                models.business_units.c.legal_entity_id == LEGAL_ENTITY_ID
            )
        )
        session.execute(
            models.branches.insert().values(
                id=SECOND_BRANCH_ID,
                organization_id=ORGANIZATION_ID,
                legal_entity_id=LEGAL_ENTITY_ID,
                business_unit_id=business_unit_id,
                name="Sucursal Norte",
                code="NORTE-CORP",
                timezone="America/Mazatlan",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.warehouses.insert().values(
                id=SECOND_WAREHOUSE_ID,
                organization_id=ORGANIZATION_ID,
                branch_id=SECOND_BRANCH_ID,
                name="Almacén Norte",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    supplier = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={"code": "CORP-SUP", "commercial_name": "Proveedor corporativo"},
    ).json()
    presentation_response = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json={
            "supplier_id": supplier["id"],
            "item_id": ITEM_ID,
            "code": "CORP-PRES",
            "name": "Paquete corporativo",
            "commercial_quantity": "1",
            "commercial_unit_id": PACKAGE_UNIT_ID,
            "base_unit_id": BASE_UNIT_ID,
            "base_unit_yield": "5",
            "usable_content": "5",
            "yield_percent": "1",
            "last_net_price": "100",
            "tax_rate": "0",
        },
    )
    assert presentation_response.status_code == 200, presentation_response.text
    with _test_session_factory(client)() as session:
        primary_warehouse_id = session.scalar(
            sa.select(models.warehouses.c.id).where(models.warehouses.c.branch_id == BRANCH_ID)
        )
    return client, headers, supplier["id"], presentation_response.json()["id"], primary_warehouse_id


def _order_payload(supplier_id: str, presentation_id: str, primary_warehouse_id: str):
    return {
        "legal_entity_id": LEGAL_ENTITY_ID,
        "supplier_id": supplier_id,
        "folio": "OC-CORP-001",
        "order_date": "2026-10-12",
        "currency": "MXN",
        "notes": "Distribución inicial",
        "lines": [
            {
                "presentation_id": presentation_id,
                "quantity": "3",
                "unit_price": "100",
                "discount": "0",
                "tax": "48",
                "allocations": [
                    {
                        "branch_id": BRANCH_ID,
                        "warehouse_id": primary_warehouse_id,
                        "quantity": "1",
                    },
                    {
                        "branch_id": SECOND_BRANCH_ID,
                        "warehouse_id": SECOND_WAREHOUSE_ID,
                        "quantity": "2",
                    },
                ],
            }
        ],
    }


def _effect_counts(client) -> dict[str, int]:
    with _test_session_factory(client)() as session:
        return {
            "inventory": session.scalar(
                sa.select(sa.func.count()).select_from(models.inventory_movements)
            ),
            "costs": session.scalar(
                sa.select(sa.func.count()).select_from(models.inventory_cost_states)
            ),
            "cash": session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)),
            "prices": session.scalar(
                sa.select(sa.func.count()).select_from(models.supplier_price_history)
            ),
        }


def test_corporate_order_create_approve_and_replay_have_no_operational_effects():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    session = client.get("/api/v1/auth/session", headers=headers)
    assert session.status_code == 200, session.text
    assert session.json()["admin_capabilities"]["purchases.corporate.read"] is True
    assert session.json()["admin_capabilities"]["purchases.corporate.manage"] is True
    options = client.get("/api/v1/corporate-purchases/options", headers=headers)
    assert options.status_code == 200, options.text
    assert options.json()["suppliers"][0]["id"] == supplier_id
    assert options.json()["presentations"][0]["id"] == presentation_id
    payload = _order_payload(supplier_id, presentation_id, warehouse_id)
    before = _effect_counts(client)

    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-001"},
        json=payload,
    )
    assert created.status_code == 200, created.text
    assert created.json()["status"] == "DRAFT"
    assert created.json()["currency"] == "MXN"
    assert created.json()["total"] == "348.000000"
    assert sum(
        Decimal(item["quantity"]) for item in created.json()["lines"][0]["allocations"]
    ) == Decimal("3")

    replay = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-001"},
        json=payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == created.json()

    conflict = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-001"},
        json={**payload, "folio": "OC-CORP-OTHER"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "corporate_purchase_idempotency_conflict"

    approved = client.post(
        f"/api/v1/corporate-purchases/{created.json()['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-approve-001"},
        json={"expected_version": 1},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "APPROVED"
    assert approved.json()["version"] == 2
    assert _effect_counts(client) == before
    second_payload = _order_payload(supplier_id, presentation_id, warehouse_id)
    second_payload["folio"] = "OC-CORP-PAGE-002"
    second = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-page-002"},
        json=second_payload,
    )
    assert second.status_code == 200, second.text
    first_page = client.get(
        "/api/v1/corporate-purchases?limit=1&offset=0", headers=headers
    )
    assert first_page.status_code == 200, first_page.text
    assert "lines" not in first_page.json()[0]
    second_page = client.get(
        "/api/v1/corporate-purchases?limit=1&offset=1", headers=headers
    )
    assert second_page.status_code == 200, second_page.text
    assert len(second_page.json()) == 1
    assert "lines" not in second_page.json()[0]
    page_ids = {first_page.json()[0]["id"], second_page.json()[0]["id"]}
    assert page_ids == {created.json()["id"], second.json()["id"]}
    invalid_page = client.get(
        "/api/v1/corporate-purchases?limit=101&offset=0", headers=headers
    )
    assert invalid_page.status_code == 409, invalid_page.text
    assert invalid_page.json()["detail"]["code"] == "corporate_purchase_pagination_invalid"


def test_corporate_receipt_preserves_snapshot_after_catalog_supplier_and_unit_correction():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    created = client.post(
        "/api/v1/corporate-purchases", headers={**headers, "Idempotency-Key": "correction-create"},
        json=_order_payload(supplier_id, presentation_id, warehouse_id),
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "correction-approve"},
        json={"expected_version": 1},
    ).json()
    other = client.post("/api/v1/suppliers", headers=headers,
                        json={"code": "NEW-SUP", "commercial_name": "Proveedor nuevo"}).json()
    presentation = next(row for row in client.get(
        "/api/v1/purchase-presentations", headers=headers).json() if row["id"] == presentation_id)
    corrected = client.put(
        f"/api/v1/purchase-presentations/{presentation_id}", headers=headers,
        json={"supplier_id": other["id"], "commercial_unit_id": BASE_UNIT_ID,
              "usable_content": "0.45", "base_unit_yield": "0.45",
              "expected_updated_at": presentation["updated_at"]},
    )
    assert corrected.status_code == 200, corrected.text
    north = next(row for row in approved["lines"][0]["allocations"]
                 if row["branch_id"] == SECOND_BRANCH_ID)
    received = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "correction-receive"},
        json={"expected_version": 2, "branch_id": SECOND_BRANCH_ID,
              "warehouse_id": SECOND_WAREHOUSE_ID, "received_at": "2026-10-12",
              "lines": [{"allocation_id": north["id"], "quantity": "1"}]},
    )
    assert received.status_code == 200, received.text
    assert received.json()["order"]["supplier_id"] == supplier_id
    assert received.json()["order"]["lines"][0]["presentation_snapshot"] == (
        approved["lines"][0]["presentation_snapshot"])
    with _test_session_factory(client)() as session:
        movement = session.execute(sa.select(models.inventory_movements).where(
            models.inventory_movements.c.source_type == "corporate_purchase_receipt"
        )).mappings().one()
        assert movement["quantity_delta"] == Decimal("5")
        history = session.execute(sa.select(models.supplier_price_history).where(
            models.supplier_price_history.c.branch_id == SECOND_BRANCH_ID
        )).mappings().one()
        assert history["supplier_id"] == supplier_id
        catalog = session.execute(sa.select(models.purchase_presentations).where(
            models.purchase_presentations.c.id == presentation_id
        )).mappings().one()
        assert catalog["supplier_id"] == other["id"]
        assert catalog["usable_content"] == Decimal("0.45")


def test_corporate_receipts_are_partial_idempotent_and_destination_scoped():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-002"},
        json=_order_payload(supplier_id, presentation_id, warehouse_id),
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-approve-002"},
        json={"expected_version": 1},
    ).json()
    north = next(
        allocation
        for allocation in approved["lines"][0]["allocations"]
        if allocation["branch_id"] == SECOND_BRANCH_ID
    )
    before_cash = _effect_counts(client)["cash"]
    receipt_payload = {
        "expected_version": 2,
        "branch_id": SECOND_BRANCH_ID,
        "warehouse_id": SECOND_WAREHOUSE_ID,
        "received_at": "2026-10-12",
        "lines": [{"allocation_id": north["id"], "quantity": "1"}],
    }
    received = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-receive-001"},
        json=receipt_payload,
    )
    assert received.status_code == 200, received.text
    assert received.json()["order"]["status"] == "PARTIALLY_RECEIVED"
    assert received.json()["receipt"]["branch_id"] == SECOND_BRANCH_ID
    assert received.json()["receipt"]["warehouse_id"] == SECOND_WAREHOUSE_ID
    assert _effect_counts(client)["cash"] == before_cash

    replay = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-receive-001"},
        json=receipt_payload,
    )
    assert replay.status_code == 200, replay.text
    assert replay.json() == received.json()

    over_receipt = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-receive-over"},
        json={
            **receipt_payload,
            "expected_version": 3,
            "lines": [{"allocation_id": north["id"], "quantity": "2"}],
        },
    )
    assert over_receipt.status_code == 409
    assert over_receipt.json()["detail"]["code"] == "corporate_purchase_over_receipt"

    with _test_session_factory(client)() as session:
        movements = list(
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.source_type == "corporate_purchase_receipt"
                )
            ).mappings()
        )
        assert len(movements) == 1
        assert movements[0]["branch_id"] == SECOND_BRANCH_ID
        assert movements[0]["warehouse_id"] == SECOND_WAREHOUSE_ID
        assert Decimal(str(movements[0]["quantity_delta"])) == Decimal("5")
        state = (
            session.execute(
                sa.select(models.inventory_cost_states).where(
                    models.inventory_cost_states.c.branch_id == SECOND_BRANCH_ID,
                    models.inventory_cost_states.c.item_id == ITEM_ID,
                )
            )
            .mappings()
            .one()
        )
        assert Decimal(str(state["quantity_on_hand"])) == Decimal("5")
        assert Decimal(str(state["average_unit_cost"])) == Decimal("20")
        price = (
            session.execute(
                sa.select(models.supplier_price_history).where(
                    models.supplier_price_history.c.source_type == "corporate_purchase_receipt"
                )
            )
            .mappings()
            .one()
        )
        assert price["branch_id"] == SECOND_BRANCH_ID
        assert price["warehouse_id"] == SECOND_WAREHOUSE_ID
        assert price["source_id"] == received.json()["receipt"]["id"]
        received_audit = (
            session.execute(
                sa.select(models.audit_events).where(
                    models.audit_events.c.action == "corporate_purchase.received",
                    models.audit_events.c.entity_id == created["id"],
                )
            )
            .mappings()
            .one()
        )
        assert received_audit["payload"] == {
            "status": "PARTIALLY_RECEIVED",
            "version": 3,
            "receipt_id": received.json()["receipt"]["id"],
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "line_count": 1,
            "presentation_quantity": "1.000000",
            "base_quantity": "5.000000",
            "movement_ids": [movements[0]["id"]],
        }

    north_completed = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-receive-north-complete"},
        json={
            **receipt_payload,
            "expected_version": 3,
            "lines": [{"allocation_id": north["id"], "quantity": "1"}],
        },
    )
    assert north_completed.status_code == 200, north_completed.text
    assert north_completed.json()["order"]["status"] == "PARTIALLY_RECEIVED"
    center = next(
        allocation
        for allocation in north_completed.json()["order"]["lines"][0]["allocations"]
        if allocation["branch_id"] == BRANCH_ID
    )
    completed = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-receive-center-complete"},
        json={
            "expected_version": 4,
            "branch_id": BRANCH_ID,
            "warehouse_id": warehouse_id,
            "received_at": "2026-10-12",
            "lines": [{"allocation_id": center["id"], "quantity": "1"}],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["order"]["status"] == "RECEIVED"


def test_branch_purchase_history_does_not_expose_another_branch_corporate_receipt():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    payload = _order_payload(supplier_id, presentation_id, warehouse_id)
    payload["folio"] = "OC-CORP-SCOPED-HISTORY"
    payload["lines"][0]["quantity"] = "1"
    payload["lines"][0]["tax"] = "0"
    payload["lines"][0]["allocations"] = [
        {
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "quantity": "1",
        }
    ]
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-scoped-history-create"},
        json=payload,
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-scoped-history-approve"},
        json={"expected_version": 1},
    ).json()
    allocation = approved["lines"][0]["allocations"][0]
    receipt = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-scoped-history-receive"},
        json={
            "expected_version": 2,
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "received_at": "2026-10-12",
            "lines": [{"allocation_id": allocation["id"], "quantity": "1"}],
        },
    )
    assert receipt.status_code == 200, receipt.text
    receipt_id = receipt.json()["receipt"]["id"]

    branch_actor_id = "018f6f73-2d0a-74f0-8f1c-000000008221"
    branch_role_id = "018f6f73-2d0a-74f0-8f1c-000000008222"
    now = datetime(2026, 10, 12, tzinfo=UTC)
    with _test_session_factory(client)() as session:
        permission_id = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "purchases.read"
            )
        )
        session.execute(
            models.roles.insert().values(
                id=branch_role_id,
                organization_id=ORGANIZATION_ID,
                name="Consulta de compras Centro",
                scope="branch",
                created_at=now,
            )
        )
        session.execute(
            models.users.insert().values(
                id=branch_actor_id,
                organization_id=ORGANIZATION_ID,
                email="branch-purchases@example.test",
                display_name="Consulta Centro",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=branch_role_id, permission_id=permission_id
            )
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=branch_actor_id,
                role_id=branch_role_id,
                branch_id=BRANCH_ID,
            )
        )
        session.commit()
    branch_token = create_session_token({"sub": branch_actor_id}, get_settings().secret_key)
    branch_response = client.get(
        f"/api/v1/purchase-presentations?branch_id={BRANCH_ID}",
        headers={"Authorization": f"Bearer {branch_token}"},
    )
    assert branch_response.status_code == 200, branch_response.text
    branch_presentation = next(
        row for row in branch_response.json() if row["id"] == presentation_id
    )
    assert receipt_id not in {
        row["source_id"] for row in branch_presentation["price_history"]
    }
    assert all(
        row["branch_id"] in {None, BRANCH_ID}
        for row in branch_presentation["price_history"]
    )

    corporate_response = client.get("/api/v1/purchase-presentations", headers=headers)
    assert corporate_response.status_code == 200, corporate_response.text
    corporate_presentation = next(
        row for row in corporate_response.json() if row["id"] == presentation_id
    )
    assert receipt_id in {
        row["source_id"] for row in corporate_presentation["price_history"]
    }


def test_corporate_order_rejects_wrong_warehouse_and_branch_only_authority_without_effects():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    payload = _order_payload(supplier_id, presentation_id, warehouse_id)
    payload["lines"][0]["allocations"][1]["warehouse_id"] = warehouse_id
    before = _effect_counts(client)
    rejected = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-invalid-destination"},
        json=payload,
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "corporate_purchase_destination_invalid"
    assert _effect_counts(client) == before

    with _test_session_factory(client)() as session:
        corporate_permission_ids = dict(
            session.execute(
                sa.select(models.permissions.c.code, models.permissions.c.id).where(
                    models.permissions.c.code.in_(
                        {"purchases.corporate.read", "purchases.corporate.manage"}
                    )
                )
            ).all()
        )
        assert corporate_permission_ids
        branch_role_has_corporate = session.scalar(
            sa.select(models.role_permissions.c.role_id).where(
                models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                models.role_permissions.c.permission_id.in_(corporate_permission_ids.values()),
            )
        )
        # The seeded role is organization-scoped; this guards against accidentally granting by name.
        assert branch_role_has_corporate is not None

        branch_actor_id = "018f6f73-2d0a-74f0-8f1c-000000008211"
        branch_role_id = "018f6f73-2d0a-74f0-8f1c-000000008212"
        now = datetime(2026, 10, 12, tzinfo=UTC)
        session.execute(
            models.roles.insert().values(
                id=branch_role_id,
                organization_id=ORGANIZATION_ID,
                name="Comprador local con código corporativo",
                scope="branch",
                created_at=now,
            )
        )
        session.execute(
            models.users.insert().values(
                id=branch_actor_id,
                organization_id=ORGANIZATION_ID,
                email="local-corporate@example.test",
                display_name="Comprador local",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert(),
            [
                {"role_id": branch_role_id, "permission_id": permission_id}
                for permission_id in corporate_permission_ids.values()
            ],
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=branch_actor_id, role_id=branch_role_id, branch_id=BRANCH_ID
            )
        )
        session.commit()
    branch_token = create_session_token({"sub": branch_actor_id}, get_settings().secret_key)
    branch_denied = client.post(
        "/api/v1/corporate-purchases",
        headers={
            "Authorization": f"Bearer {branch_token}",
            "Idempotency-Key": "branch-cannot-create-corporate",
        },
        json=_order_payload(supplier_id, presentation_id, warehouse_id),
    )
    assert branch_denied.status_code == 403
    assert branch_denied.json()["detail"]["code"] == "permission_denied"

    read_actor_id = "018f6f73-2d0a-74f0-8f1c-000000008213"
    read_role_id = "018f6f73-2d0a-74f0-8f1c-000000008214"
    with _test_session_factory(client)() as session:
        read_permission_id = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "purchases.corporate.read"
            )
        )
        session.execute(
            models.roles.insert().values(
                id=read_role_id,
                organization_id=ORGANIZATION_ID,
                name="Consulta corporativa",
                scope="organization",
                created_at=now,
            )
        )
        session.execute(
            models.users.insert().values(
                id=read_actor_id,
                organization_id=ORGANIZATION_ID,
                email="corporate-read@example.test",
                display_name="Consulta corporativa",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=read_role_id, permission_id=read_permission_id
            )
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=read_actor_id, role_id=read_role_id, branch_id=None
            )
        )
        session.commit()
    read_token = create_session_token({"sub": read_actor_id}, get_settings().secret_key)
    read_headers = {"Authorization": f"Bearer {read_token}"}
    readable_options = client.get("/api/v1/corporate-purchases/options", headers=read_headers)
    assert readable_options.status_code == 200, readable_options.text
    assert readable_options.json()["suppliers"][0]["id"] == supplier_id
    read_only_denied = client.post(
        "/api/v1/corporate-purchases",
        headers={**read_headers, "Idempotency-Key": "read-only-cannot-create"},
        json=_order_payload(supplier_id, presentation_id, warehouse_id),
    )
    assert read_only_denied.status_code == 403
    assert read_only_denied.json()["detail"]["code"] == "permission_denied"


def test_partial_receipt_cost_rounding_absorbs_the_final_remainder():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    payload = _order_payload(supplier_id, presentation_id, warehouse_id)
    payload["folio"] = "OC-CORP-ROUNDING"
    payload["lines"][0]["discount"] = "200"
    payload["lines"][0]["tax"] = "0"
    payload["lines"][0]["allocations"] = [
        {
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "quantity": "3",
        }
    ]
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-rounding-create"},
        json=payload,
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-rounding-approve"},
        json={"expected_version": 1},
    ).json()
    allocation = approved["lines"][0]["allocations"][0]
    for index, version in enumerate((2, 3, 4), start=1):
        received = client.post(
            f"/api/v1/corporate-purchases/{created['id']}/receipts",
            headers={**headers, "Idempotency-Key": f"corp-rounding-receive-{index}"},
            json={
                "expected_version": version,
                "branch_id": SECOND_BRANCH_ID,
                "warehouse_id": SECOND_WAREHOUSE_ID,
                "received_at": "2026-10-12",
                "lines": [{"allocation_id": allocation["id"], "quantity": "1"}],
            },
        )
        assert received.status_code == 200, received.text
    with _test_session_factory(client)() as session:
        received_cost = session.scalar(
            sa.select(sa.func.sum(models.corporate_purchase_receipt_lines.c.inventory_cost))
        )
        movement_cost = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.total_cost)).where(
                models.inventory_movements.c.source_type == "corporate_purchase_receipt"
            )
        )
    assert Decimal(str(received_cost)) == Decimal("100")
    assert Decimal(str(movement_cost)) == Decimal("100")


def test_partial_receipt_base_quantity_absorbs_the_final_remainder():
    client, headers, supplier_id, _, warehouse_id = _corporate_workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "item_id": ITEM_ID,
            "code": "CORP-FRACTIONAL-BASE",
            "name": "Presentación base fraccionaria",
            "commercial_quantity": "1",
            "commercial_unit_id": PACKAGE_UNIT_ID,
            "base_unit_id": BASE_UNIT_ID,
            "base_unit_yield": "0.333333",
            "usable_content": "0.333333",
            "yield_percent": "1",
            "last_net_price": "100",
            "tax_rate": "0",
        },
    )
    assert presentation.status_code == 200, presentation.text
    payload = _order_payload(supplier_id, presentation.json()["id"], warehouse_id)
    payload["folio"] = "OC-CORP-FRACTIONAL-BASE"
    payload["lines"][0]["quantity"] = "1"
    payload["lines"][0]["tax"] = "0"
    payload["lines"][0]["allocations"] = [
        {
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "quantity": "1",
        }
    ]
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-base-create"},
        json=payload,
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-base-approve"},
        json={"expected_version": 1},
    ).json()
    allocation = approved["lines"][0]["allocations"][0]
    for index, version in enumerate((2, 3), start=1):
        received = client.post(
            f"/api/v1/corporate-purchases/{created['id']}/receipts",
            headers={**headers, "Idempotency-Key": f"corp-base-receive-{index}"},
            json={
                "expected_version": version,
                "branch_id": SECOND_BRANCH_ID,
                "warehouse_id": SECOND_WAREHOUSE_ID,
                "received_at": "2026-10-12",
                "lines": [{"allocation_id": allocation["id"], "quantity": "0.5"}],
            },
        )
        assert received.status_code == 200, received.text
    with _test_session_factory(client)() as session:
        received_base = session.scalar(
            sa.select(sa.func.sum(models.corporate_purchase_receipt_lines.c.base_quantity))
        )
        movement_quantity = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.source_type == "corporate_purchase_receipt"
            )
        )
        stored_allocation = session.execute(
            sa.select(models.corporate_purchase_allocations).where(
                models.corporate_purchase_allocations.c.id == allocation["id"]
            )
        ).mappings().one()
    assert Decimal(str(received_base)) == Decimal("0.333333")
    assert Decimal(str(movement_quantity)) == Decimal("0.333333")
    assert Decimal(str(stored_allocation["received_base_quantity"])) == Decimal("0.333333")


def test_partial_receipt_below_base_precision_is_rejected_before_effects():
    client, headers, supplier_id, _, warehouse_id = _corporate_workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json={
            "supplier_id": supplier_id,
            "item_id": ITEM_ID,
            "code": "CORP-MIN-BASE",
            "name": "Presentación base mínima",
            "commercial_quantity": "1",
            "commercial_unit_id": PACKAGE_UNIT_ID,
            "base_unit_id": BASE_UNIT_ID,
            "base_unit_yield": "0.000001",
            "usable_content": "0.000001",
            "yield_percent": "1",
            "last_net_price": "100",
            "tax_rate": "0",
        },
    )
    assert presentation.status_code == 200, presentation.text
    payload = _order_payload(supplier_id, presentation.json()["id"], warehouse_id)
    payload["folio"] = "OC-CORP-MIN-BASE"
    payload["lines"][0]["quantity"] = "1"
    payload["lines"][0]["tax"] = "0"
    payload["lines"][0]["allocations"] = [
        {
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "quantity": "1",
        }
    ]
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-min-base-create"},
        json=payload,
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-min-base-approve"},
        json={"expected_version": 1},
    ).json()
    allocation = approved["lines"][0]["allocations"][0]
    before = _effect_counts(client)
    rejected = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-min-base-partial"},
        json={
            "expected_version": 2,
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "received_at": "2026-10-12",
            "lines": [{"allocation_id": allocation["id"], "quantity": "0.5"}],
        },
    )
    assert rejected.status_code == 409, rejected.text
    assert (
        rejected.json()["detail"]["code"]
        == "corporate_purchase_quantity_below_base_precision"
    )
    assert _effect_counts(client) == before
    stored = client.get(f"/api/v1/corporate-purchases/{created['id']}", headers=headers)
    assert stored.status_code == 200, stored.text
    assert stored.json()["status"] == "APPROVED"
    assert stored.json()["version"] == 2

    completed = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/receipts",
        headers={**headers, "Idempotency-Key": "corp-min-base-complete"},
        json={
            "expected_version": 2,
            "branch_id": SECOND_BRANCH_ID,
            "warehouse_id": SECOND_WAREHOUSE_ID,
            "received_at": "2026-10-12",
            "lines": [{"allocation_id": allocation["id"], "quantity": "1"}],
        },
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["order"]["status"] == "RECEIVED"


def test_corporate_order_can_cancel_only_draft_and_keeps_history():
    client, headers, supplier_id, presentation_id, warehouse_id = _corporate_workspace()
    created = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-cancel"},
        json=_order_payload(supplier_id, presentation_id, warehouse_id),
    ).json()
    cancelled = client.post(
        f"/api/v1/corporate-purchases/{created['id']}/cancel",
        headers={**headers, "Idempotency-Key": "corp-cancel-001"},
        json={"expected_version": 1, "reason": "Proveedor sin disponibilidad"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    assert len(cancelled.json()["lines"]) == 1
    assert len(cancelled.json()["lines"][0]["allocations"]) == 2

    approved_source = _order_payload(supplier_id, presentation_id, warehouse_id)
    approved_source["folio"] = "OC-CORP-002"
    approved = client.post(
        "/api/v1/corporate-purchases",
        headers={**headers, "Idempotency-Key": "corp-create-approved"},
        json=approved_source,
    ).json()
    approved = client.post(
        f"/api/v1/corporate-purchases/{approved['id']}/approve",
        headers={**headers, "Idempotency-Key": "corp-approve-cancel"},
        json={"expected_version": 1},
    ).json()
    rejected = client.post(
        f"/api/v1/corporate-purchases/{approved['id']}/cancel",
        headers={**headers, "Idempotency-Key": "corp-cancel-approved"},
        json={"expected_version": 2, "reason": "No debe borrar compromiso aprobado"},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "corporate_purchase_not_cancellable"
