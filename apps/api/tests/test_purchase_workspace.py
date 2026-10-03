"""SR-WORKSPACE-001 presentation relation and precision regressions."""

from __future__ import annotations

from decimal import Decimal

import pytest
import sqlalchemy as sa
from restaurant_os import models
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)

ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
BASE_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
PACKAGE_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000303"


@pytest.mark.parametrize(
    ("path", "operation"),
    [
        ("/purchases/preview", "preview_purchase"),
        ("/purchases", "create_purchase_document"),
        ("/purchase-presentations/preview", "preview_presentation"),
        ("/recipes/product/preview", "preview_recipe"),
        ("/inventory/items/item/cost-preview", "preview_item_cost"),
        ("/products/product/modifier-configuration/copy", "copy_modifier_configuration"),
        (
            "/products/product/modifier-configuration/selection-preview",
            "preview_modifier_selection",
        ),
    ],
)
def test_workspace_storage_failure_does_not_expose_sql_or_parameters(
    monkeypatch, caplog, path, operation
):
    from restaurant_os import api
    from sqlalchemy.exc import SQLAlchemyError

    client = _client_with_seeded_database()
    marker = "SR-SENSITIVE-FOLIO-NOTES-PARAMETER"

    def fail(*args, **kwargs):
        raise SQLAlchemyError(f"INSERT SQL parameters={marker}")

    monkeypatch.setattr(api, operation, fail)
    response = client.post("/api/v1" + path, headers=_admin_headers(), json={})
    assert response.status_code == 503
    assert marker not in response.text
    assert marker not in caplog.text
    assert response.json()["detail"] == {
        "code": "database_unavailable",
        "message": "Storage is temporarily unavailable; retry the same command.",
    }


def _workspace():
    client = _client_with_seeded_database()
    headers = _admin_headers()
    suppliers = []
    for code in ("SR-SUP-1", "SR-SUP-2"):
        response = client.post(
            "/api/v1/suppliers",
            headers=headers,
            json={
                "code": code,
                "commercial_name": code,
                "branch_id": BRANCH_ID,
            },
        )
        assert response.status_code == 200, response.text
        suppliers.append(response.json()["id"])
    return client, headers, suppliers


def _presentation(supplier_id: str):
    return {
        "branch_id": BRANCH_ID,
        "supplier_id": supplier_id,
        "item_id": ITEM_ID,
        "code": "SR-PRES",
        "name": "Paquete explícito",
        "commercial_unit_id": PACKAGE_UNIT_ID,
        "base_unit_id": BASE_UNIT_ID,
        "commercial_quantity": "1",
        "usable_content": "5",
        "base_unit_yield": "5",
        "yield_percent": "1",
        "last_net_price": "0",
        "tax_rate": "0",
    }


def _effects(client):
    with _test_session_factory(client)() as session:
        return {
            table.name: list(session.execute(sa.select(table)).mappings())
            for table in (
                models.purchase_presentations,
                models.supplier_price_history,
                models.inventory_movements,
                models.inventory_cost_states,
                models.cash_movements,
                models.purchase_documents,
                models.purchase_document_lines,
                models.purchase_create_commands,
                models.recipes,
                models.recipe_cost_calculations,
                models.audit_events,
            )
        }


@pytest.mark.parametrize("supplier_id", ["", "missing-supplier"])
def test_presentation_rejects_missing_provider_without_fallback(supplier_id):
    client, headers, _ = _workspace()
    before = _effects(client)
    response = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json=_presentation(supplier_id),
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "presentation_reference_not_found"
    assert _effects(client) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("base_unit_id", "018f6f73-2d0a-74f0-8f1c-000000000302"),
        ("commercial_unit_id", "missing-unit"),
        ("usable_content", "0"),
        ("base_unit_yield", ""),
        ("usable_content", "NaN"),
        ("last_net_price", "Infinity"),
        ("base_unit_yield", "1000000000000"),
        ("tax_rate", "-1"),
    ],
)
def test_presentation_rejects_invalid_relations_or_decimals(field, value):
    client, headers, suppliers = _workspace()
    before = _effects(client)
    response = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json={**_presentation(suppliers[0]), field: value},
    )
    assert response.status_code == 409, response.text
    assert _effects(client) == before


def test_presentation_explicit_zero_and_price_update_do_not_receive_inventory():
    client, headers, suppliers = _workspace()
    before = _effects(client)
    created = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    )
    assert created.status_code == 200, created.text
    assert Decimal(str(created.json()["last_net_price"])) == 0
    assert Decimal(str(created.json()["tax_rate"])) == 0
    updated = client.put(
        f"/api/v1/purchase-presentations/{created.json()['id']}/price",
        headers=headers,
        json={"net_price": "0"},
    )
    assert updated.status_code == 200, updated.text
    assert Decimal(str(updated.json()["cost_per_base_unit"])) == 0
    after = _effects(client)
    for table in ("inventory_movements", "inventory_cost_states", "cash_movements"):
        assert after[table] == before[table]


def test_purchase_presentation_listing_names_related_product_and_supplier():
    client, headers, suppliers = _workspace()
    created = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    )
    assert created.status_code == 200, created.text
    listed = client.get(
        "/api/v1/purchase-presentations",
        headers=headers,
        params={"branch_id": BRANCH_ID},
    )
    assert listed.status_code == 200, listed.text
    selected = next(item for item in listed.json() if item["id"] == created.json()["id"])
    assert selected["item_name"]
    assert selected["item_sku"]
    assert selected["supplier_name"] == "SR-SUP-1"


@pytest.mark.parametrize("field", ["usable_content", "base_unit_yield"])
def test_presentation_update_does_not_replace_zero_with_previous_yield(field):
    client, headers, suppliers = _workspace()
    created = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    )
    assert created.status_code == 200
    before = _effects(client)
    rejected = client.put(
        f"/api/v1/purchase-presentations/{created.json()['id']}", headers=headers, json={field: "0"}
    )
    assert rejected.status_code == 409, rejected.text
    assert _effects(client) == before


def _purchase_payload(supplier_id: str, presentation_id: str):
    return {
        "branch_id": BRANCH_ID,
        "supplier_id": supplier_id,
        "document_type": "note",
        "folio": "SR-NOTE-001",
        "document_date": "2026-09-30",
        "paid_from_cash": False,
        "payment_method": "other",
        "lines": [
            {
                "presentation_id": presentation_id,
                "quantity": "2",
                "unit_price": "250",
                "discount": "1",
                "tax": "40",
            },
            {
                "presentation_id": presentation_id,
                "quantity": "1",
                "unit_price": "19.99",
                "discount": "0.29",
                "tax": "3.15",
            },
            {
                "presentation_id": presentation_id,
                "quantity": "0.5",
                "unit_price": "0.29",
                "discount": "0",
                "tax": "0.02",
            },
        ],
    }


def test_supplier_catalog_exception_is_explicit_audited_and_does_not_reprice_catalog():
    client, headers, suppliers = _workspace()
    first_payload = _presentation(suppliers[0])
    first_payload.update({"code": "SR-PRES-CATALOG", "last_net_price": "125"})
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=first_payload
    ).json()
    payload = _purchase_payload(suppliers[1], presentation["id"])
    payload["lines"] = [payload["lines"][0]]

    before = _effects(client)
    rejected = client.post("/api/v1/purchases/preview", headers=headers, json=payload)
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "purchase_presentation_not_found"
    assert _effects(client) == before

    payload["supplier_catalog_exception"] = True
    missing_reason = client.post("/api/v1/purchases/preview", headers=headers, json=payload)
    assert missing_reason.status_code == 409
    assert missing_reason.json()["detail"]["code"] == "purchase_supplier_exception_reason_required"
    assert _effects(client) == before

    payload["supplier_catalog_exception_reason"] = "Compra urgente por desabasto"
    preview = client.post("/api/v1/purchases/preview", headers=headers, json=payload)
    assert preview.status_code == 200, preview.text
    snapshot = preview.json()["lines"][0]["presentation_snapshot"]
    assert snapshot["supplier_catalog_exception"] is True
    assert snapshot["purchase_supplier_id"] == suppliers[1]
    assert snapshot["catalog_supplier_id"] == suppliers[0]
    assert snapshot["supplier_catalog_exception_reason"] == "Compra urgente por desabasto"

    created = client.post(
        "/api/v1/purchases",
        headers={
            **headers,
            "Idempotency-Key": "purchase-exception-command-1",
            "If-Purchase-Preview": preview.json()["context_fingerprint"],
        },
        json=payload,
    )
    assert created.status_code == 200, created.text
    confirmed = client.post(
        f"/api/v1/purchases/{created.json()['id']}/confirm",
        headers={**headers, "Idempotency-Key": "purchase-exception-confirm-1"},
        json={},
    )
    assert confirmed.status_code == 200, confirmed.text

    after = _effects(client)
    catalog_row = next(
        row
        for row in after["purchase_presentations"]
        if row["id"] == presentation["id"]
    )
    assert Decimal(str(catalog_row["last_net_price"])) == Decimal("125")
    assert after["supplier_price_history"] == before["supplier_price_history"]
    created_audit = next(
        row for row in after["audit_events"] if row["action"] == "purchase.created"
    )
    assert created_audit["payload"]["supplier_catalog_exception_lines"] == 1
    assert "Compra urgente" not in str(created_audit["payload"])


def test_purchase_preview_is_pure_and_matches_document_calculations():
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = _purchase_payload(suppliers[0], presentation["id"])
    before = _effects(client)
    preview = client.post("/api/v1/purchases/preview", headers=headers, json=payload)
    assert preview.status_code == 200, preview.text
    assert _effects(client) == before
    data = preview.json()
    assert data["source"] == "python"
    assert len(data["context_fingerprint"]) == 64
    assert data["total"] == "562.015000"
    assert data["cash_total_cents"] == 56202
    persisted = client.post("/api/v1/purchases", headers=headers, json=payload)
    assert persisted.status_code == 200, persisted.text
    for key in ("subtotal", "discount_total", "tax_total", "total"):
        assert Decimal(data[key]) == Decimal(persisted.json()[key])
    assert len(data["lines"]) == len(persisted.json()["lines"]) == 3


def test_presentation_preview_does_not_create_catalog():
    client, headers, suppliers = _workspace()
    before = _effects(client)
    preview = client.post(
        "/api/v1/purchase-presentations/preview",
        headers=headers,
        json={**_presentation(suppliers[0]), "last_net_price": "19.99"},
    )
    assert preview.status_code == 200, preview.text
    assert preview.json()["cost_per_base_unit"] == "3.998000"
    assert preview.json()["source"] == "python"
    assert _effects(client) == before


def test_recipe_preview_uses_canonical_waste_without_creating_version():
    client, headers, _ = _workspace()
    before = _effects(client)
    factory = _test_session_factory(client)
    with factory() as session:
        versions_before = list(session.execute(sa.select(models.recipes)).mappings())
    response = client.post(
        "/api/v1/recipes/018f6f73-2d0a-74f0-8f1c-000000000111/preview",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "yield_quantity": "2",
            "yield_unit_id": PACKAGE_UNIT_ID,
            "components": [
                {
                    "item_id": ITEM_ID,
                    "unit_id": BASE_UNIT_ID,
                    "net_quantity": "9",
                    "waste_rate": "0.1",
                }
            ],
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["breakdown"][0]["gross_quantity"] == "10.000000"
    assert response.json()["source"] == "python"
    assert _effects(client) == before
    with factory() as session:
        assert list(session.execute(sa.select(models.recipes)).mappings()) == versions_before


@pytest.mark.parametrize(
    "line_update",
    [
        {"unit_price": "NaN"},
        {"quantity": "Infinity"},
        {"quantity": "0.0000001"},
        {"quantity": "999999999999", "unit_price": "999999999999"},
        {"computed_total": "0"},
    ],
)
def test_purchase_preview_and_writer_reject_invalid_decimal_lines(line_update):
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = _purchase_payload(suppliers[0], presentation["id"])
    payload["lines"][-1].update(line_update)
    before = _effects(client)
    for endpoint in ("/api/v1/purchases/preview", "/api/v1/purchases"):
        response = client.post(endpoint, headers=headers, json=payload)
        assert response.status_code == 409, response.text
    assert _effects(client) == before


def test_preview_payload_size_limit_rejects_before_processing():
    client, headers, _ = _workspace()
    response = client.post(
        "/api/v1/purchases/preview", headers=headers, json={"notes": "x" * 300000}
    )
    assert response.status_code == 413, response.text


def test_body_limit_counts_chunks_before_dispatch_even_with_false_content_length():
    import asyncio

    from restaurant_os.workspace_body_limit import WorkspaceBodyLimitMiddleware

    dispatched = []
    responses = []
    chunks = iter(
        [
            {"type": "http.request", "body": b"x" * 131072, "more_body": True},
            {"type": "http.request", "body": b"x" * 131073, "more_body": False},
        ]
    )

    async def app(scope, receive, send):
        dispatched.append(True)

    async def receive():
        return next(chunks)

    async def send(message):
        responses.append(message)

    asyncio.run(
        WorkspaceBodyLimitMiddleware(app)(
            {
                "type": "http",
                "method": "POST",
                "path": "/api/v1/purchases",
                "headers": [(b"content-length", b"1")],
            },
            receive,
            send,
        )
    )
    assert dispatched == []
    assert responses[0]["status"] == 413


def test_new_presentation_preview_requires_explicit_commercial_unit():
    client, headers, suppliers = _workspace()
    payload = _presentation(suppliers[0])
    del payload["commercial_unit_id"]
    before = _effects(client)
    response = client.post("/api/v1/purchase-presentations/preview", headers=headers, json=payload)
    assert response.status_code == 409, response.text
    assert _effects(client) == before


def test_item_cost_preview_is_pure_and_explicit_about_missing_cost():
    client, headers, _ = _workspace()
    before = _effects(client)
    response = client.post(
        f"/api/v1/inventory/items/{ITEM_ID}/cost-preview",
        headers=headers,
        json={"branch_id": BRANCH_ID, "tax_rate": "0", "waste_rate": "0"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["source"] == "python"
    assert response.json()["cost_source"] in {"unavailable", "inventory_last_receipt"}
    assert _effects(client) == before


def test_purchase_creation_recovers_same_id_after_lost_response_and_rejects_key_reuse():
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = _purchase_payload(suppliers[0], presentation["id"])
    command_headers = {**headers, "Idempotency-Key": "sr-create-note-key-001"}
    created = client.post("/api/v1/purchases", headers=command_headers, json=payload)
    assert created.status_code == 200, created.text
    baseline = _effects(client)
    replay = client.post("/api/v1/purchases", headers=command_headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == created.json()["id"]
    assert replay.json() == created.json()
    assert _effects(client) == baseline

    conflict = client.post(
        "/api/v1/purchases", headers=command_headers, json={**payload, "folio": "SR-NOTE-OTHER"}
    )
    assert conflict.status_code == 409, conflict.text
    assert conflict.json()["detail"]["code"] == "purchase_creation_idempotency_conflict"
    assert _effects(client) == baseline


def test_keyed_creation_and_preview_require_explicit_price():
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = _purchase_payload(suppliers[0], presentation["id"])
    del payload["lines"][-1]["unit_price"]
    before = _effects(client)
    for path in ("/api/v1/purchases/preview", "/api/v1/purchases"):
        response = client.post(
            path, headers={**headers, "Idempotency-Key": "sr-price-required"}, json=payload
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "invalid_purchase_line"
    assert _effects(client) == before


def test_item_percent_preview_uses_python_conversion_and_zero_is_not_defaulted():
    client, headers, _ = _workspace()
    response = client.post(
        f"/api/v1/inventory/items/{ITEM_ID}/cost-preview",
        headers=headers,
        json={"branch_id": BRANCH_ID, "tax_percent": "0", "waste_percent": "10"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["tax_rate"] == "0.000000"
    assert response.json()["waste_rate"] == "0.100000"


@pytest.mark.parametrize("value", ["bad-date", "2026-02-30", ""])
def test_purchase_invalid_date_fails_without_partial_state(value):
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = {**_purchase_payload(suppliers[0], presentation["id"]), "document_date": value}
    before = _effects(client)
    for endpoint in ("/api/v1/purchases/preview", "/api/v1/purchases"):
        response = client.post(
            endpoint, headers={**headers, "Idempotency-Key": "invalid-date-command"}, json=payload
        )
        assert response.status_code == 409, response.text
    assert _effects(client) == before


@pytest.mark.parametrize(
    "component_patch",
    [
        {"net_quantity": "NaN"},
        {"unit_id": "missing-unit"},
        {"waste_percent": "100"},
        {"waste_rate": "-0.1"},
    ],
)
def test_versioned_recipe_writer_and_preview_reject_invalid_components(component_patch):
    client, headers, _ = _workspace()
    product = "018f6f73-2d0a-74f0-8f1c-000000000111"
    active = client.get(
        f"/api/v1/products/{product}/recipe?branch_id={BRANCH_ID}", headers=headers
    ).json()
    payload = {
        "branch_id": BRANCH_ID,
        "yield_quantity": "1",
        "yield_unit_id": PACKAGE_UNIT_ID,
        "components": [
            {
                "item_id": ITEM_ID,
                "unit_id": BASE_UNIT_ID,
                "net_quantity": "9",
                "waste_rate": "0",
                **component_patch,
            }
        ],
    }
    if "waste_percent" in component_patch:
        payload["components"][0].pop("waste_rate")
    before = _effects(client)
    preview = client.post(f"/api/v1/recipes/{product}/preview", headers=headers, json=payload)
    assert preview.status_code == 409, preview.text
    persisted = client.put(
        f"/api/v1/products/{product}/recipe",
        headers={**headers, "Idempotency-Key": "recipe-invalid-workspace"},
        json={**payload, "expected_active_recipe_id": active.get("id")},
    )
    assert persisted.status_code in {409, 422}, persisted.text
    assert _effects(client) == before


def test_presentation_reader_excludes_other_branch_items():
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    with _test_session_factory(client)() as session:
        branch = dict(
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        other_branch = "018f6f73-2d0a-74f0-8f1c-000000008803"
        session.execute(
            models.branches.insert().values(**{**branch, "id": other_branch, "code": "SR-OTHER"})
        )
        item = dict(
            session.execute(
                sa.select(models.inventory_items).where(models.inventory_items.c.id == ITEM_ID)
            )
            .mappings()
            .one()
        )
        item_id = "018f6f73-2d0a-74f0-8f1c-000000008811"
        session.execute(
            models.inventory_items.insert().values(
                **{
                    **item,
                    "id": item_id,
                    "sku": "SR-LOCAL",
                    "catalog_scope": "branch",
                    "source_branch_id": other_branch,
                }
            )
        )
        session.execute(
            models.purchase_presentations.update()
            .where(models.purchase_presentations.c.id == presentation["id"])
            .values(item_id=item_id)
        )
        session.commit()
    response = client.get("/api/v1/purchase-presentations?branch_id=" + BRANCH_ID, headers=headers)
    assert response.status_code == 200, response.text
    assert presentation["id"] not in {row["id"] for row in response.json()}


def test_purchase_creation_rolls_back_domain_when_receipt_write_fails(monkeypatch):
    from sqlalchemy.orm import Session

    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    before = _effects(client)
    original = Session.execute

    def fail_receipt(session, statement, *args, **kwargs):
        if getattr(
            getattr(statement, "table", None), "name", None
        ) == "purchase_create_commands" and getattr(statement, "is_insert", False):
            raise RuntimeError("synthetic receipt failure")
        return original(session, statement, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Session, "execute", fail_receipt)
        with pytest.raises(RuntimeError, match="synthetic receipt failure"):
            client.post(
                "/api/v1/purchases",
                headers={**headers, "Idempotency-Key": "sr-rollback-receipt"},
                json=_purchase_payload(suppliers[0], presentation["id"]),
            )
    assert _effects(client) == before


def test_missing_item_preview_rates_are_not_inferred():
    client, headers, _ = _workspace()
    before = _effects(client)
    for rates in ({}, {"tax_rate": "0"}, {"waste_rate": "0"}):
        response = client.post(
            f"/api/v1/inventory/items/{ITEM_ID}/cost-preview",
            headers=headers,
            json={"branch_id": BRANCH_ID, **rates},
        )
        assert response.status_code == 409, response.text
    assert _effects(client) == before


def test_reviewed_purchase_rejects_catalog_change_and_recovers_original_result():
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = _purchase_payload(suppliers[0], presentation["id"])
    preview = client.post("/api/v1/purchases/preview", headers=headers, json=payload).json()
    updated = client.put(
        "/api/v1/purchase-presentations/" + presentation["id"],
        headers=headers,
        json={"base_unit_yield": "10"},
    )
    assert updated.status_code == 200, updated.text
    before = _effects(client)
    command_headers = {
        **headers,
        "Idempotency-Key": "sr-reviewed-catalog-change",
        "If-Purchase-Preview": preview["context_fingerprint"],
    }
    changed = client.post("/api/v1/purchases", headers=command_headers, json=payload)
    assert changed.status_code == 409, changed.text
    assert changed.json()["detail"]["code"] == "purchase_preview_changed"
    assert _effects(client) == before
    preview = client.post("/api/v1/purchases/preview", headers=headers, json=payload).json()
    command_headers["If-Purchase-Preview"] = preview["context_fingerprint"]
    created = client.post("/api/v1/purchases", headers=command_headers, json=payload)
    assert created.status_code == 200, created.text
    assert created.json()["lines"][0]["base_quantity"] == "20.000000"
    assert (
        client.put(
            "/api/v1/purchase-presentations/" + presentation["id"],
            headers=headers,
            json={"base_unit_yield": "7"},
        ).status_code
        == 200
    )
    before_replay = _effects(client)
    replay = client.post("/api/v1/purchases", headers=command_headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json() == created.json()
    assert _effects(client) == before_replay


@pytest.mark.parametrize(
    "field,value",
    [
        ("folio", None),
        ("payment_method", None),
        ("document_type", None),
        ("paid_from_cash", "false"),
    ],
)
def test_new_purchase_capture_rejects_invalid_header_types(field, value):
    client, headers, suppliers = _workspace()
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    ).json()
    payload = {**_purchase_payload(suppliers[0], presentation["id"]), field: value}
    before = _effects(client)
    for path in ("/api/v1/purchases/preview", "/api/v1/purchases"):
        response = client.post(
            path, headers={**headers, "Idempotency-Key": "sr-invalid-header"}, json=payload
        )
        assert response.status_code == 409, response.text
    assert _effects(client) == before


def test_three_line_cash_receipt_has_exact_prior_weighted_cost_and_compensation():
    from restaurant_os.operations import _now
    from test_platform_api import _open_shift

    client, headers, suppliers = _workspace()
    factory = _test_session_factory(client)
    with factory() as session:
        movement = dict(
            session.execute(
                sa.select(models.inventory_movements).where(
                    models.inventory_movements.c.item_id == ITEM_ID
                )
            )
            .mappings()
            .first()
        )
        warehouse_id = movement["warehouse_id"]
        session.execute(
            models.inventory_movements.delete().where(
                models.inventory_movements.c.item_id == ITEM_ID
            )
        )
        session.execute(
            models.inventory_movements.insert().values(
                **{
                    **movement,
                    "quantity_delta": Decimal("10"),
                    "unit_cost": Decimal("2"),
                    "total_cost": Decimal("20"),
                }
            )
        )
        session.execute(
            models.inventory_cost_states.delete().where(
                models.inventory_cost_states.c.item_id == ITEM_ID
            )
        )
        session.execute(
            models.inventory_cost_states.insert().values(
                branch_id=BRANCH_ID,
                warehouse_id=warehouse_id,
                item_id=ITEM_ID,
                quantity_on_hand=Decimal("10"),
                average_unit_cost=Decimal("2"),
                last_unit_cost=Decimal("2"),
                updated_at=_now(),
            )
        )
        session.commit()
    assert _open_shift(client, opening_cash_cents=200000, headers=headers).status_code == 200
    presentations = []
    for index, base_yield in enumerate(("10", "5")):
        response = client.post(
            "/api/v1/purchase-presentations",
            headers=headers,
            json={
                **_presentation(suppliers[0]),
                "code": "SR-CASH-" + str(index),
                "base_unit_yield": base_yield,
                "usable_content": base_yield,
            },
        )
        assert response.status_code == 200, response.text
        presentations.append(response.json()["id"])
    payload = _purchase_payload(suppliers[0], presentations[0])
    payload["lines"][1]["presentation_id"] = presentations[1]
    payload.update(paid_from_cash=True, payment_method="cash")
    created = client.post(
        "/api/v1/purchases",
        headers={**headers, "Idempotency-Key": "sr-prior-cash-create"},
        json=payload,
    )
    assert created.status_code == 200, created.text
    confirm_headers = {**headers, "Idempotency-Key": "sr-prior-cash-confirm"}
    path = "/api/v1/purchases/" + created.json()["id"]
    confirmed = client.post(
        path + "/confirm", headers=confirm_headers, json={"register_id": "CAJA-01"}
    )
    assert confirmed.status_code == 200, confirmed.text
    assert len(confirmed.json()["inventory_movements"]) == 3
    assert confirmed.json()["cash_movements"][0]["amount_cents"] == 56202
    with factory() as session:
        state = (
            session.execute(
                sa.select(models.inventory_cost_states).where(
                    models.inventory_cost_states.c.item_id == ITEM_ID
                )
            )
            .mappings()
            .one()
        )
        assert state["quantity_on_hand"] == Decimal("40")
        assert state["average_unit_cost"] == Decimal("13.471125")
    before_replay = _effects(client)
    assert (
        client.post(
            path + "/confirm", headers=confirm_headers, json={"register_id": "CAJA-01"}
        ).status_code
        == 200
    )
    assert _effects(client) == before_replay
    cancelled = client.post(
        path + "/cancel", headers=headers, json={"reason": "Synthetic compensation"}
    )
    assert cancelled.status_code == 200, cancelled.text
    assert len(cancelled.json()["inventory_movements"]) == 6
    assert len(cancelled.json()["cash_movements"]) == 2
    with factory() as session:
        quantity = session.scalar(
            sa.select(sa.func.sum(models.inventory_movements.c.quantity_delta)).where(
                models.inventory_movements.c.item_id == ITEM_ID
            )
        )
        assert quantity == Decimal("10")
