"""TDD-TC-474 / BDD-SC-804: Multimodal and document-assisted purchase draft extraction."""

from __future__ import annotations

import base64
import io
import json
from decimal import Decimal

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import Settings, get_settings
from restaurant_os.operations import ORGANIZATION_ID, _now
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)

SECOND_BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000099"

ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
SECOND_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000312"
BASE_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
PACKAGE_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000303"

PNG_1X1_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)


def _setup_catalog():
    client = _client_with_seeded_database()
    headers = _admin_headers()
    sup1_resp = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "code": "SUP-PAN-01",
            "commercial_name": "Panadería del Pacífico",
            "legal_name": "Panificadora del Pacífico SA de CV",
            "tax_id": "PPA200101ABC",
            "branch_id": BRANCH_ID,
        },
    )
    assert sup1_resp.status_code == 200, sup1_resp.text
    sup1_id = sup1_resp.json()["id"]

    sup2_resp = client.post(
        "/api/v1/suppliers",
        headers=headers,
        json={
            "code": "SUP-ALT-02",
            "commercial_name": "Distribuidora Alterna",
            "tax_id": "DAL210202XYZ",
            "branch_id": BRANCH_ID,
        },
    )
    assert sup2_resp.status_code == 200, sup2_resp.text
    sup2_id = sup2_resp.json()["id"]

    pres1_resp = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": sup1_id,
            "item_id": ITEM_ID,
            "code": "PAN-BRIOCHE-50",
            "name": "Caja Pan Brioche x 50",
            "commercial_unit_id": PACKAGE_UNIT_ID,
            "base_unit_id": BASE_UNIT_ID,
            "commercial_quantity": "1",
            "usable_content": "50",
            "base_unit_yield": "50",
            "yield_percent": "1",
            "last_net_price": "240.00",
            "tax_rate": "0.16",
        },
    )
    assert pres1_resp.status_code == 200, pres1_resp.text
    pres1_id = pres1_resp.json()["id"]

    pres2_resp = client.post(
        "/api/v1/purchase-presentations",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": sup2_id,
            "item_id": ITEM_ID,
            "code": "CARNE-SIRLOIN-10",
            "name": "Caja Carne Sirloin 10kg",
            "commercial_unit_id": PACKAGE_UNIT_ID,
            "base_unit_id": BASE_UNIT_ID,
            "commercial_quantity": "1",
            "usable_content": "10",
            "base_unit_yield": "10",
            "yield_percent": "1",
            "last_net_price": "1200.00",
            "tax_rate": "0",
        },
    )
    assert pres2_resp.status_code == 200, pres2_resp.text
    pres2_id = pres2_resp.json()["id"]

    return client, headers, sup1_id, sup2_id, pres1_id, pres2_id


def _db_effects(client):
    with _test_session_factory(client)() as session:
        return {
            table.name: list(session.execute(sa.select(table)).mappings())
            for table in (
                models.purchase_documents,
                models.purchase_document_lines,
                models.purchase_create_commands,
                models.inventory_movements,
                models.inventory_cost_states,
                models.cash_movements,
                models.supplier_price_history,
            )
        }


def test_purchase_ai_extract_enforces_branch_scope_and_permissions():
    client, headers, *_ = _setup_catalog()

    # Unauthenticated -> 401/403
    unauth = client.post(
        "/api/v1/purchases/ai-extract",
        json={"branch_id": BRANCH_ID, "raw_text": "Caja Pan Brioche x 50 | 2 | 250.00"},
    )
    assert unauth.status_code in (401, 403)

    # Missing branch_id -> 422
    no_branch = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={"raw_text": "Caja Pan Brioche x 50 | 2 | 250.00"},
    )
    assert no_branch.status_code == 422

    # Actor without purchases.manage permission cannot extract for BRANCH_ID
    now = _now()
    with _test_session_factory(client)() as session:
        session.execute(
            models.users.insert().values(
                id="018f6f73-2d0a-74f0-8f1c-000000009981",
                organization_id=ORGANIZATION_ID,
                email="cashier-other-branch@example.com",
                display_name="Cajero Sin Permiso",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
    token = create_session_token(
        {
            "sub": "018f6f73-2d0a-74f0-8f1c-000000009981",
            "organization_id": ORGANIZATION_ID,
            "branch_id": SECOND_BRANCH_ID,
        },
        get_settings().secret_key,
    )
    denied = client.post(
        "/api/v1/purchases/ai-extract",
        headers={"Authorization": f"Bearer {token}"},
        json={"branch_id": BRANCH_ID, "raw_text": "Caja Pan Brioche x 50 | 2 | 250.00"},
    )
    assert denied.status_code == 403


def test_purchase_ai_extract_parses_cfdi_xml_and_matches_branch_catalog():
    client, headers, sup1_id, _sup2_id, pres1_id, pres2_id = _setup_catalog()
    before = _db_effects(client)

    cfdi_xml = """<?xml version="1.0" encoding="UTF-8"?>
<cfdi:Comprobante xmlns:cfdi="http://www.sat.gob.mx/cfd/4"
    Serie="FAC" Folio="8842" Fecha="2026-10-25T14:22:10"
    SubTotal="1750.00" Descuento="10.00" Total="1820.00" FormaPago="03">
  <cfdi:Emisor Rfc="PPA200101ABC" Nombre="Panificadora del Pacífico SA de CV"/>
  <cfdi:Conceptos>
    <cfdi:Concepto NoIdentificacion="PAN-BRIOCHE-50" Cantidad="2.000000"
        Descripcion="Caja Pan Brioche x 50" ValorUnitario="250.00"
        Importe="500.00" Descuento="10.00">
      <cfdi:Impuestos>
        <cfdi:Traslados>
          <cfdi:Traslado Base="490.00" Impuesto="002" TipoFactor="Tasa"
              TasaOCuota="0.160000" Importe="78.40"/>
        </cfdi:Traslados>
      </cfdi:Impuestos>
    </cfdi:Concepto>
    <cfdi:Concepto NoIdentificacion="CARNE-SIRLOIN-10" Cantidad="1"
        Descripcion="Caja Carne Sirloin 10kg" ValorUnitario="1250.00" Importe="1250.00"/>
    <cfdi:Concepto NoIdentificacion="SERV-HIELO-99" Cantidad="3"
        Descripcion="Bolsa Hielo Gourmet 5kg" ValorUnitario="45.50" Importe="136.50"/>
  </cfdi:Conceptos>
</cfdi:Comprobante>"""

    response = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "filename": "factura-8842.xml",
            "mime_type": "application/xml",
            "file_base64": base64.b64encode(cfdi_xml.encode("utf-8")).decode("ascii"),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_kind"] == "xml_cfdi"
    assert body["status"] == "needs_review"
    assert body["supplier_id"] == sup1_id
    assert body["folio"] == "FAC-8842"
    assert body["document_date"] == "2026-10-25"
    assert body["payment_method"] == "transfer"
    assert len(body["lines"]) == 3

    line_matched, line_cross, line_unmatched = body["lines"]
    assert line_matched["presentation_id"] == pres1_id
    assert line_matched["match_status"] == "matched"
    assert line_matched["quantity"] == "2.00"
    assert line_matched["unit_price"] == "250.00"
    assert line_matched["discount"] == "10.00"
    assert line_matched["tax"] == "78.40"

    assert line_cross["presentation_id"] == pres2_id
    assert line_cross["match_status"] == "cross_supplier"
    assert line_cross["quantity"] == "1.00"
    assert line_cross["unit_price"] == "1250.00"

    assert line_unmatched["presentation_id"] == ""
    assert line_unmatched["match_status"] == "unmatched"
    assert line_unmatched["raw_description"] == "Bolsa Hielo Gourmet 5kg"
    assert line_unmatched["quantity"] == "3.00"
    assert line_unmatched["unit_price"] == "45.50"

    assert _db_effects(client) == before, "Extraction must never write to DB tables"

    # Disable sup1 for BRANCH_ID and verify it is excluded from branch supplier matching
    disable_resp = client.put(
        f"/api/v1/suppliers/{sup1_id}/branches/{BRANCH_ID}",
        headers=headers,
        json={"is_enabled": False},
    )
    assert disable_resp.status_code == 200, disable_resp.text
    after_disable = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "raw_text": "Proveedor: Panadería del Pacífico\nBolsa Hielo Gourmet 5kg | 3 | $45.50",
        },
    )
    assert after_disable.status_code == 200, after_disable.text
    assert after_disable.json()["supplier_id"] == ""


def test_purchase_ai_extract_rejects_xxe_xml_and_mismatched_magic_bytes():
    client, headers, *_ = _setup_catalog()

    xxe_xml = b"""<?xml version="1.0"?><!DOCTYPE foo [<!ENTITY xxe SYSTEM "file:///etc/passwd">]><Comprobante>&xxe;</Comprobante>"""
    xxe_resp = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "filename": "xxe.xml",
            "mime_type": "application/xml",
            "file_base64": base64.b64encode(xxe_xml).decode("ascii"),
        },
    )
    assert xxe_resp.status_code == 422
    assert xxe_resp.json()["detail"]["code"] == "purchase_extract_invalid_file"

    fake_pdf = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "filename": "nota.pdf",
            "mime_type": "application/pdf",
            "file_base64": base64.b64encode(b"NOT_A_REAL_PDF_FILE").decode("ascii"),
        },
    )
    assert fake_pdf.status_code == 422
    assert fake_pdf.json()["detail"]["code"] == "purchase_extract_invalid_file"


def test_purchase_ai_extract_parses_handwritten_or_typed_shopping_list_and_feeds_preview():
    client, headers, sup1_id, _sup2_id, pres1_id, _pres2_id = _setup_catalog()
    before = _db_effects(client)

    shopping_list = """
    Proveedor: Panadería del Pacífico
    Folio: NOTA-PAPEL-77
    Fecha: 2026-10-24
    Entregó: Juan Pérez
    Pago: efectivo
    - 2 Caja Pan Brioche x 50 $500.00
    - Concepto inválido | -1 | $50.00
    """
    response = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "raw_text": shopping_list,
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_kind"] == "text_list"
    assert body["supplier_id"] == sup1_id
    assert body["folio"] == "NOTA-PAPEL-77"
    assert body["document_date"] == "2026-10-24"
    assert body["delivered_by_name"] == "Juan Pérez"
    assert body["payment_method"] == "cash"
    assert len(body["lines"]) == 1
    line = body["lines"][0]
    assert line["presentation_id"] == pres1_id
    assert line["match_status"] == "matched"
    assert line["quantity"] == "2.00"
    assert line["unit_price"] == "250.00"
    assert any("negative" in w["code"] or "invalid" in w["code"] for w in body["warnings"])
    assert _db_effects(client) == before

    # Feed extracted draft directly into canonical /api/v1/purchases/preview
    preview_resp = client.post(
        "/api/v1/purchases/preview",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": body["supplier_id"],
            "document_type": "note",
            "folio": body["folio"],
            "document_date": body["document_date"],
            "delivered_by_name": body["delivered_by_name"],
            "payment_method": body["payment_method"],
            "paid_from_cash": body["payment_method"] == "cash",
            "supplier_catalog_exception": False,
            "supplier_catalog_exception_reason": "",
            "notes": body["notes"],
            "evidence_url": "",
            "lines": [
                {
                    "presentation_id": item["presentation_id"],
                    "quantity": item["quantity"],
                    "unit_price": item["unit_price"],
                    "discount": item["discount"],
                    "tax": item["tax"],
                }
                for item in body["lines"]
            ],
        },
    )
    assert preview_resp.status_code == 200, preview_resp.text
    assert Decimal(preview_resp.json()["subtotal"]) == Decimal("500.00")


def test_purchase_ai_extract_parses_text_pdf_stream():
    client, headers, sup1_id, _sup2_id, pres1_id, _pres2_id = _setup_catalog()

    pdf_bytes = (
        b"%PDF-1.4\n1 0 obj\n<< /Length 120 >>\nstream\n"
        b"BT (Proveedor: Panaderia del Pacifico) Tj "
        b"(Folio: PDF-901) Tj "
        b"(Fecha: 2026-10-23) Tj "
        b"(Caja Pan Brioche x 50 | 3 | $240.00) Tj ET\n"
        b"endstream\nendobj\n%%EOF"
    )
    response = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "filename": "nota-901.pdf",
            "mime_type": "application/pdf",
            "file_base64": base64.b64encode(pdf_bytes).decode("ascii"),
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_kind"] == "pdf_text"
    assert body["supplier_id"] == sup1_id
    assert body["folio"] == "PDF-901"
    assert body["document_date"] == "2026-10-23"
    assert len(body["lines"]) == 1
    assert body["lines"][0]["presentation_id"] == pres1_id
    assert body["lines"][0]["quantity"] == "3.00"
    assert body["lines"][0]["unit_price"] == "240.00"


def test_purchase_ai_extract_multimodal_image_uses_openrouter_and_fails_closed_without_key(
    monkeypatch,
):
    from restaurant_os import purchase_ai_capture

    client, headers, sup1_id, _sup2_id, pres1_id, _pres2_id = _setup_catalog()

    # Without OPENROUTER_API_KEY configured, image extraction fails closed with 503
    monkeypatch.setattr(
        purchase_ai_capture,
        "get_settings",
        lambda: Settings(openrouter_api_key=None, secret_key=get_settings().secret_key),
    )
    no_key_resp = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "filename": "foto-nota.png",
            "mime_type": "image/png",
            "file_base64": base64.b64encode(PNG_1X1_BYTES).decode("ascii"),
        },
    )
    assert no_key_resp.status_code == 503
    assert no_key_resp.json()["detail"]["code"] == "purchase_ai_provider_unavailable"

    # With OPENROUTER_API_KEY configured, verify deterministic multimodal call and schema parsing
    monkeypatch.setattr(
        purchase_ai_capture,
        "get_settings",
        lambda: Settings(
            openrouter_api_key="sk-or-test-key-1234567890",
            openrouter_model="google/gemini-2.5-flash",
            secret_key=get_settings().secret_key,
        ),
    )
    captured_request: dict[str, object] = {}

    class _FakeResponse(io.StringIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def _fake_opener(req, timeout=0):
        body = json.loads(req.data.decode("utf-8"))
        captured_request["body"] = body
        captured_request["timeout"] = timeout
        llm_payload = {
            "supplier_name": "Panadería del Pacífico",
            "supplier_tax_id": "PPA200101ABC",
            "folio": "FOTO-55",
            "document_date": "2026-10-26",
            "delivered_by_name": "Carlos Ruiz",
            "payment_method": "cash",
            "notes": "Nota escrita a mano en recepción",
            "lines": [
                {
                    "description": "Caja Pan Brioche x 50",
                    "sku": "PAN-BRIOCHE-50",
                    "quantity": "4",
                    "unit_price": "245.5",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        }
        return _FakeResponse(
            json.dumps({"choices": [{"message": {"content": json.dumps(llm_payload)}}]})
        )

    monkeypatch.setattr(purchase_ai_capture.urllib.request, "urlopen", _fake_opener)

    vision_resp = client.post(
        "/api/v1/purchases/ai-extract",
        headers=headers,
        json={
            "branch_id": BRANCH_ID,
            "filename": "foto-nota.png",
            "mime_type": "image/png",
            "file_base64": base64.b64encode(PNG_1X1_BYTES).decode("ascii"),
        },
    )
    assert vision_resp.status_code == 200, vision_resp.text
    payload = vision_resp.json()
    assert payload["source_kind"] == "ai_vision"
    assert payload[" status" if " status" in payload else "status"] == "ready"
    assert payload["supplier_id"] == sup1_id
    assert payload["folio"] == "FOTO-55"
    assert payload["document_date"] == "2026-10-26"
    assert payload["delivered_by_name"] == "Carlos Ruiz"
    assert payload["payment_method"] == "cash"
    assert len(payload["lines"]) == 1
    assert payload["lines"][0]["presentation_id"] == pres1_id
    assert payload["lines"][0]["quantity"] == "4.00"
    assert payload["lines"][0]["unit_price"] == "245.50"

    sent = captured_request["body"]
    assert isinstance(sent, dict)
    assert sent["temperature"] == 0
    assert sent["response_format"]["type"] == "json_schema"
