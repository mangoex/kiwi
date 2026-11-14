from __future__ import annotations

from restaurant_os.receipt_formatting import (
    ESCPOS_CUT_PARTIAL,
    ESCPOS_INIT,
    ESCPOS_KICK_DRAWER,
    entero_a_letras,
    format_kitchen_text,
    format_ticket_text,
    generate_escpos_kitchen,
    generate_escpos_ticket,
    number_to_words_mxn,
)


def test_number_to_words_mxn() -> None:
    assert number_to_words_mxn(0) == "SON: CERO PESOS 00/100 M.N."
    assert number_to_words_mxn(100) == "SON: UN PESO 00/100 M.N."
    assert number_to_words_mxn(36000) == "SON: TRESCIENTOS SESENTA PESOS 00/100 M.N."
    assert number_to_words_mxn(31034) == "SON: TRESCIENTOS DIEZ PESOS 34/100 M.N."
    assert number_to_words_mxn(152450) == "SON: UN MIL QUINIENTOS VEINTICUATRO PESOS 50/100 M.N."
    words_million = number_to_words_mxn(100000000)
    assert words_million == "SON: UN MILLON DE PESOS 00/100 M.N." or "UN MILLON" in words_million


def test_entero_a_letras() -> None:
    assert entero_a_letras(0) == "CERO"
    assert entero_a_letras(1) == "UN"
    assert entero_a_letras(21) == "VEINTIUN"
    assert entero_a_letras(100) == "CIEN"
    assert entero_a_letras(360) == "TRESCIENTOS SESENTA"
    assert entero_a_letras(1000) == "UN MIL"
    assert entero_a_letras(2500) == "DOS MIL QUINIENTOS"


def test_format_ticket_matches_kiwi_layout() -> None:
    payload = {
        "folio": "102778",
        "order_number": 68,
        "created_at": "06/11/2026 02:06:04 PM",
        "customer_name": "VERONICA COTA",
        "customer_phone": "6673030384",
        "service_type_label": "PASA POR EL",
        "colonia": "KIWI PASAN POR EL",
        "zone": "PASA POR EL",
        "lines": [
            {"quantity": 1, "product_name": "AGUA MINERAL", "line_total_cents": 3000},
            {"quantity": 1, "product_name": "CHILE JALAPEÑO EXTR", "line_total_cents": 2800},
            {"quantity": 1, "product_name": "ENSALADA DE ARANDAN", "line_total_cents": 13000},
            {"quantity": 1, "product_name": "ENSALADA DE ARANDAN", "line_total_cents": 13000},
            {"quantity": 1, "product_name": "POLLO EXTRA", "line_total_cents": 4200},
        ],
        "subtotal_cents": 31034,
        "tax_cents": 4966,
        "total_cents": 36000,
        "cash_tender": {
            "received_cents": 36000,
            "change_cents": 0,
        },
    }

    ticket_text = format_ticket_text(payload, 42)

    assert "KIWI COMIDA NATURAL" in ticket_text
    assert "ELISA AMAYRANI INZUNZA DOMINGUEZ" in ticket_text
    assert "RFC:IUDE931111KM2" in ticket_text
    assert "FOLIO:102778" in ticket_text
    assert "ORDEN:68" in ticket_text
    assert "CLIENTE:VERONICA COTA" in ticket_text
    assert "TEL.:6673030384" in ticket_text
    assert "AGUA MINERAL" in ticket_text
    assert "$30.00" in ticket_text
    assert "ENSALADA DE ARANDAN" in ticket_text
    assert "$130.00" in ticket_text
    assert "POLLO EXTRA" in ticket_text
    assert "$42.00" in ticket_text
    assert "SUBTOTAL:" in ticket_text
    assert "$310.34" in ticket_text
    assert "IVA:" in ticket_text
    assert "$49.66" in ticket_text
    assert "TOTAL:" in ticket_text
    assert "$360.00" in ticket_text
    assert "SON: TRESCIENTOS SESENTA PESOS 00/100 M.N." in ticket_text
    assert "CANTIDAD A RECIBIR:" in ticket_text
    assert "CAMBIO REPARTIDOR:" in ticket_text
    assert "GRACIAS POR SU PREFERENCIA" in ticket_text
    assert "ESTE NO ES UN COMPROBANTE FISCAL" in ticket_text


def test_format_kitchen_comanda() -> None:
    payload = {
        "folio": "102778",
        "order_number": 68,
        "created_at": "06/11/2026 02:06:04 PM",
        "service_type_label": "PASA POR EL",
        "customer_name": "VERONICA COTA",
        "lines": [
            {
                "quantity": 1,
                "product_name": "ENSALADA DE ARANDAN",
                "selected_modifiers": [{"text": "POLLO EXTRA"}],
                "line_notes": "Aderezo aparte",
            },
            {"quantity": 1, "product_name": "AGUA MINERAL"},
        ],
    }

    kitchen_text = format_kitchen_text(payload, 42)

    assert "*** COMANDA DE COCINA ***" in kitchen_text
    assert "FOLIO:102778" in kitchen_text
    assert "ORDEN:#68" in kitchen_text
    assert "PASA POR EL" in kitchen_text
    assert "[ 1 ] ENSALADA DE ARANDAN" in kitchen_text
    assert "POLLO EXTRA" in kitchen_text
    assert "* NOTA: ADEREZO APARTE" in kitchen_text
    assert "[ 1 ] AGUA MINERAL" in kitchen_text
    # No debe contener precios en comanda de cocina
    assert "$" not in kitchen_text


def test_generate_escpos_ticket_bytes() -> None:
    payload = {
        "folio": "102778",
        "total_cents": 36000,
        "lines": [{"quantity": 1, "product_name": "AGUA MINERAL", "line_total_cents": 3000}],
    }
    raw = generate_escpos_ticket(payload, kick_drawer=True)

    assert raw.startswith(ESCPOS_INIT)
    assert ESCPOS_KICK_DRAWER in raw
    assert ESCPOS_CUT_PARTIAL in raw
    assert b"AGUA MINERAL" in raw


def test_generate_escpos_kitchen_bytes() -> None:
    payload = {
        "folio": "102778",
        "lines": [{"quantity": 1, "product_name": "ENSALADA DE ARANDAN"}],
    }
    raw = generate_escpos_kitchen(payload)

    assert raw.startswith(ESCPOS_INIT)
    assert b"COMANDA DE COCINA" in raw
    assert b"ENSALADA DE ARANDAN" in raw


def test_default_print_areas_and_smart_product_routing() -> None:
    from restaurant_os.receipt_formatting import (
        DEFAULT_PRINT_AREAS,
        extract_short_order_number,
        resolve_product_print_area,
        split_kitchen_payload_by_area,
    )

    codes = [area["code"] for area in DEFAULT_PRINT_AREAS]
    assert "salads" in codes
    assert "baguettes" in codes
    assert "kitchen" in codes
    assert "drinks" in codes
    assert "packing" in codes

    assert extract_short_order_number("SUC04-000001") == "1"
    assert extract_short_order_number("SUC01-000025") == "25"
    assert extract_short_order_number("103326", 3) == "3"

    # Smart resolution for Kiwi catalog products
    assert (
        resolve_product_print_area(
            {
                "product_name": "ENSALADA DE ARANDANO",
                "category_name": "ENSALADAS",
                "station": "kitchen",
            }
        )
        == "salads"
    )
    assert (
        resolve_product_print_area(
            {
                "product_name": "SANDWICH INTEGRAL POLLO BBQ",
                "category_name": "BAGUETTES",
                "station": "kitchen",
            }
        )
        == "baguettes"
    )
    assert (
        resolve_product_print_area(
            {"product_name": "CUERNITO BBQ", "category_name": "BAGUETTES", "station": "kitchen"}
        )
        == "baguettes"
    )
    assert (
        resolve_product_print_area(
            {
                "product_name": "AGUA DE FRESA LIMON CHICA",
                "category_name": "AGUAS",
                "station": "drinks",
            }
        )
        == "drinks"
    )

    # Splitting a single order into multiple area-specific kitchen comandas
    order_payload = {
        "folio": "SUC04-000003",
        "created_at": "14/11/2026 08:23:24 AM",
        "service_type_label": "CONSUMIR AQUI",
        "customer_name": "MIGUEL GONZALEZ",
        "lines": [
            {
                "quantity": 1,
                "product_name": "ENSALADA DE ARANDANO",
                "category_name": "ENSALADAS",
                "station": "kitchen",
                "selected_modifiers": [{"text": "ADEREZO RANCH"}],
            },
            {
                "quantity": 1,
                "product_name": "SANDWICH INTEGRAL POLLO BBQ",
                "category_name": "BAGUETTES",
                "station": "kitchen",
                "selected_modifiers": [
                    {"text": "ADEREZO DE CHIPOTLE CHI"},
                    {"text": "MANCHEGUITO"},
                ],
            },
            {
                "quantity": 1,
                "product_name": "CUERNITO BBQ",
                "category_name": "BAGUETTES",
                "station": "kitchen",
                "selected_modifiers": [{"text": "ADEREZO DE CHIPOTLE CHI"}],
            },
            {
                "quantity": 1,
                "product_name": "AGUA DE FRESA LIMON CHICA",
                "category_name": "AGUAS",
                "station": "drinks",
            },
        ],
    }

    split_jobs = split_kitchen_payload_by_area(order_payload)
    assert [job["area_code"] for job in split_jobs] == ["salads", "baguettes", "drinks"]
    assert len(split_jobs[0]["lines"]) == 1
    assert split_jobs[0]["lines"][0]["product_name"] == "ENSALADA DE ARANDANO"
    assert len(split_jobs[1]["lines"]) == 2
    assert split_jobs[1]["area_name"] == "BAGUETTES(RAPIDO)"

    baguettes_text = format_kitchen_text(split_jobs[1], 42)
    assert "BAGUETTES(RAPIDO) ORDEN: 3" in baguettes_text
    assert "SANDWICH INTEGRAL POLLO BBQ" in baguettes_text
    assert "CUERNITO BBQ" in baguettes_text
    assert "ENSALADA DE ARANDANO" not in baguettes_text


def test_print_routing_api_persistence_and_preview() -> None:
    from collections.abc import Generator
    from datetime import datetime, timezone

    from fastapi.testclient import TestClient
    from restaurant_os import models, operations
    from restaurant_os.database import get_session
    from restaurant_os.main import create_app
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session, sessionmaker
    from sqlalchemy.pool import StaticPool

    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(timezone.utc)
    with factory() as session:
        session.execute(
            models.organizations.insert().values(
                id=operations.ORGANIZATION_ID,
                name="Kiwi Org",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()

    app = create_app()

    def override() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override
    client = TestClient(app)

    res_get = client.get("/api/v1/print-routing")
    assert res_get.status_code == 200
    initial = res_get.json()
    assert initial["ticket_printer"]["printer_name"] == "caja"
    assert initial["area_printers"]["salads"]["printer_name"] == "ensaladas"
    assert initial["area_printers"]["baguettes"]["printer_name"] == "barra"

    # Update custom area & printers
    updated_payload = {
        "areas": [
            *initial["areas"],
            {
                "code": "postres",
                "name": "REPOSTERIA FRIA",
                "station": "kitchen",
                "print_comanda": True,
                "sort_order": 7,
            },
        ],
        "category_areas": {"ENSALADAS": "salads", "BAGUETTES": "baguettes"},
        "ticket_printer": {"enabled": True, "printer_name": "caja", "host": "", "port": 9100},
        "area_printers": {
            "salads": {"enabled": True, "printer_name": "ensaladas", "host": "", "port": 9100},
            "baguettes": {"enabled": True, "printer_name": "barra", "host": "", "port": 9100},
            "postres": {"enabled": True, "printer_name": "reposteria", "host": "", "port": 9100},
        },
    }
    res_put = client.put("/api/v1/print-routing", json=updated_payload)
    assert res_put.status_code == 200
    saved = res_put.json()
    assert any(a["code"] == "postres" for a in saved["areas"])
    assert saved["area_printers"]["postres"]["printer_name"] == "reposteria"

    # Assign specific product to print area
    res_prod = client.put(
        "/api/v1/print-routing/products/prod-cheesecake-01",
        json={"print_area": "postres"},
    )
    assert res_prod.status_code == 200
    assert res_prod.json()["product_areas"]["prod-cheesecake-01"] == "postres"

    # Preview order split across multiple printers
    preview_res = client.post(
        "/api/v1/print-routing/preview-order",
        json={
            "folio": "SUC04-000003",
            "branch_name": "SUCURSAL CHAPULTEPEC",
            "created_at": "14/11/2026 08:23:24 AM",
            "service_type_label": "CONSUMIR AQUI",
            "customer_name": "MIGUEL GONZALEZ",
            "total_cents": 32500,
            "lines": [
                {
                    "product_id": "prod-salad-01",
                    "product_name": "ENSALADA DE ARANDANO",
                    "category_name": "ENSALADAS",
                    "quantity": 1,
                    "unit_price_cents": 13500,
                    "line_total_cents": 13500,
                },
                {
                    "product_id": "prod-baguette-01",
                    "product_name": "SANDWICH INTEGRAL POLLO BBQ",
                    "category_name": "BAGUETTES",
                    "quantity": 1,
                    "unit_price_cents": 11500,
                    "line_total_cents": 11500,
                },
                {
                    "product_id": "prod-cheesecake-01",
                    "product_name": "PAY DE QUESO",
                    "category_name": "EXTRAS",
                    "quantity": 1,
                    "unit_price_cents": 7500,
                    "line_total_cents": 7500,
                },
            ],
        },
    )
    assert preview_res.status_code == 200
    preview = preview_res.json()
    assert preview["order_number"] == "3"
    assert preview["ticket"]["printer_name"] == "caja"
    assert "ORDEN:3" in preview["ticket"]["text"]
    assert [c["area_code"] for c in preview["comandas"]] == ["salads", "baguettes", "postres"]
    assert [c["printer_name"] for c in preview["comandas"]] == ["ensaladas", "barra", "reposteria"]
