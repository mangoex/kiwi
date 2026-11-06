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
