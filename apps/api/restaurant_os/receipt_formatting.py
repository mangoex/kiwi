"""
Generador y formateador canónico de tickets y comandas térmicas para RestaurantOS (Kiwi).
Soporta generación de texto monoespaciado (42 columnas) y comandos binarios ESC/POS
compatibles con impresoras térmicas de 80mm y 58mm (Epson, Bixolon, Xprinter).
"""

from __future__ import annotations

from typing import Any

UNIDADES: list[str] = [
    "",
    "UN",
    "DOS",
    "TRES",
    "CUATRO",
    "CINCO",
    "SEIS",
    "SIETE",
    "OCHO",
    "NUEVE",
    "DIEZ",
    "ONCE",
    "DOCE",
    "TRECE",
    "CATORCE",
    "QUINCE",
    "DIECISEIS",
    "DIECISIETE",
    "DIECIOCHO",
    "DIECINUEVE",
    "VEINTE",
    "VEINTIUN",
    "VEINTIDOS",
    "VEINTITRES",
    "VEINTICUATRO",
    "VEINTICINCO",
    "VEINTISEIS",
    "VEINTISIETE",
    "VEINTIOCHO",
    "VEINTINUEVE",
]

DECENAS: list[str] = [
    "",
    "DIEZ",
    "VEINTE",
    "TREINTA",
    "CUARENTA",
    "CINCUENTA",
    "SESENTA",
    "SETENTA",
    "OCHENTA",
    "NOVENTA",
]

CENTENAS: list[str] = [
    "",
    "CIENTO",
    "DOSCIENTOS",
    "TRESCIENTOS",
    "CUATROCIENTOS",
    "QUINIENTOS",
    "SEISCIENTOS",
    "SETECIENTOS",
    "OCHOCIENTOS",
    "NOVECIENTOS",
]


def _convertir_grupo(n: int) -> str:
    if n == 0:
        return ""
    if n == 100:
        return "CIEN"

    resultado: list[str] = []
    c = n // 100
    d = (n % 100) // 10
    u = n % 10
    du = n % 100

    if c > 0:
        resultado.append(CENTENAS[c])

    if 0 < du <= 29:
        resultado.append(UNIDADES[du])
    elif du > 29:
        if u > 0:
            resultado.append(f"{DECENAS[d]} Y {UNIDADES[u]}")
        else:
            resultado.append(DECENAS[d])

    return " ".join(resultado).strip()


def entero_a_letras(n: int) -> str:
    if n == 0:
        return "CERO"
    if n < 0:
        return "MENOS " + entero_a_letras(abs(n))

    millones = n // 1_000_000
    resto_millones = n % 1_000_000
    miles = resto_millones // 1_000
    unidades = resto_millones % 1_000

    partes: list[str] = []
    if millones > 0:
        if millones == 1:
            partes.append("UN MILLON")
        else:
            partes.append(f"{_convertir_grupo(millones)} MILLONES")

    if miles > 0:
        if miles == 1:
            partes.append("UN MIL")
        else:
            partes.append(f"{_convertir_grupo(miles)} MIL")

    if unidades > 0:
        partes.append(_convertir_grupo(unidades))

    return " ".join(partes).strip()


def number_to_words_mxn(total_cents: int) -> str:
    cents = max(0, int(total_cents))
    pesos = cents // 100
    centavos = cents % 100
    texto_pesos = entero_a_letras(pesos)
    moneda = "PESO" if pesos == 1 else "PESOS"
    return f"SON: {texto_pesos} {moneda} {centavos:02d}/100 M.N."


def format_money(cents: int) -> str:
    return f"${cents / 100:.2f}"


def wrap_text(text: str, max_width: int) -> list[str]:
    if not text:
        return []
    words = text.strip().split()
    lines: list[str] = []
    current_line = ""

    for word in words:
        if not current_line:
            current_line = word
        elif len(current_line) + 1 + len(word) <= max_width:
            current_line += " " + word
        else:
            lines.append(current_line)
            current_line = word
    if current_line:
        lines.append(current_line)
    return lines


def pad_center(text: str, width: int) -> str:
    if len(text) >= width:
        return text[:width]
    left = (width - len(text)) // 2
    right = width - len(text) - left
    return " " * left + text + " " * right


def two_columns(left: str, right: str, width: int) -> str:
    available_left = width - len(right) - 1
    truncated_left = left[:available_left] if len(left) > available_left else left
    spaces = width - len(truncated_left) - len(right)
    return truncated_left + (" " * max(1, spaces)) + right


DEFAULT_BRAND = "KIWI COMIDA NATURAL"
DEFAULT_BUSINESS = "ELISA AMAYRANI INZUNZA DOMINGUEZ"
DEFAULT_RFC = "RFC:IUDE931111KM2"
DEFAULT_ADDRESS = (
    "CALLE JOSEFA ORTIZ DE DOMINGUEZ NUM 598 INT 6 COLONIA CHAPULTEPEC "
    "CULIACAN SINALOA MEXICO CP 80040"
)
DEFAULT_BRANCH = (
    "SUCURSAL:CALLE JOSEFA ORTIZ DE DOMINGUEZ NUM 598 INT 6 COLONIA "
    "CHAPULTEPEC CULIACAN SINALOA"
)


def format_ticket_text(payload: dict[str, Any], width: int = 42) -> str:
    divider = "=" * width
    out: list[str] = []

    # Encabezado
    out.append(pad_center(DEFAULT_BRAND, width))
    out.append(pad_center(DEFAULT_BUSINESS, width))
    out.append(pad_center(DEFAULT_RFC, width))

    for line in wrap_text(DEFAULT_ADDRESS, width):
        out.append(pad_center(line, width))
    for line in wrap_text(DEFAULT_BRANCH, width):
        out.append(pad_center(line, width))

    out.append(divider)

    # Folio y entrega
    folio = str(payload.get("folio", ""))
    out.append(pad_center(f"FOLIO:{folio}", width))
    driver = str(payload.get("driver_name", "") or "")
    out.append(f"REPARTIDOR:{(' ' + driver) if driver else ''}")

    order_num = payload.get("order_number") or folio
    date_str = str(payload.get("created_at", "") or "")
    out.append(two_columns(f"ORDEN:{order_num}", date_str, width))

    client = str(payload.get("customer_name") or "PUBLICO GENERAL").upper()
    out.append(f"CLIENTE:{client}")

    phone = payload.get("customer_phone")
    if phone:
        out.append(f"TEL.:{phone}")

    zona = str(payload.get("zone") or payload.get("service_type_label") or "MOSTRADOR").upper()
    col = str(payload.get("colonia") or "").upper()
    delivery_info = f"COL. {col} ZONA:{zona}".strip() if col else f"ZONA:{zona}"
    for line in wrap_text(delivery_info, width):
        out.append(line)

    out.append(divider)

    # Detalle de productos
    col_cant = 5
    col_imp = 10
    col_desc = width - col_cant - col_imp
    out.append("CANT.DESCRIPCION" + " " * max(1, width - 16 - 7) + "IMPORTE")

    for item in payload.get("lines", []):
        cant_str = str(item.get("quantity", 1)).ljust(col_cant)
        cents = int(item.get("line_total_cents") or item.get("total_cents") or 0)
        imp_str = format_money(cents).rjust(col_imp)
        desc = str(item.get("product_name") or "PRODUCTO").upper()

        if len(desc) <= col_desc:
            out.append(cant_str + desc.ljust(col_desc) + imp_str)
        else:
            wrapped = wrap_text(desc, col_desc)
            out.append(cant_str + wrapped[0].ljust(col_desc) + imp_str)
            for w in wrapped[1:]:
                out.append(" " * col_cant + w)

        # Modificadores
        mods = item.get("selected_modifiers") or []
        for mod in mods:
            mod_text = ""
            if isinstance(mod, dict):
                mod_text = str(mod.get("kitchen_text") or mod.get("text") or mod.get("name") or "")
            elif isinstance(mod, str):
                mod_text = mod
            if mod_text:
                for line in wrap_text(f"+ {mod_text.upper()}", width - col_cant):
                    out.append(" " * col_cant + line)

        # Notas
        note = item.get("line_notes")
        if note:
            for line in wrap_text(f"* {note}", width - col_cant):
                out.append(" " * col_cant + line)

    out.append("")

    # Totales e impuestos
    total_cents = int(payload.get("total_cents", 0))
    subtotal_cents = int(payload.get("subtotal_cents") or round(total_cents / 1.16))
    tax_cents = int(payload.get("tax_cents") or (total_cents - subtotal_cents))

    out.append(two_columns("SUBTOTAL:", format_money(subtotal_cents), width))
    out.append(two_columns("IVA:", format_money(tax_cents), width))
    out.append(two_columns("TOTAL:", format_money(total_cents), width))

    for line in wrap_text(number_to_words_mxn(total_cents), width):
        out.append(line)

    out.append("")

    # Cobro y cambio
    tender = payload.get("cash_tender")
    if isinstance(tender, dict):
        recibido = int(tender.get("received_cents", 0))
        cambio = int(tender.get("change_cents", 0))
        out.append(two_columns("CANTIDAD A RECIBIR:", format_money(recibido), width))
        out.append(two_columns("CAMBIO REPARTIDOR:", format_money(cambio), width))
        out.append("")

    # Pie
    footers = [
        "GRACIAS POR SU PREFERENCIA",
        "ESTE NO ES UN COMPROBANTE FISCAL",
        "FACTURA VIGENCIA: ULTIMO DIA DEL MES",
        "*** RESTAURANTOS - KIWI ***",
    ]
    for footer in footers:
        out.append(pad_center(footer, width))

    return "\n".join(out)


def format_kitchen_text(payload: dict[str, Any], width: int = 42) -> str:
    divider = "-" * width
    out: list[str] = []

    out.append(pad_center("*** COMANDA DE COCINA ***", width))
    station = payload.get("station")
    if station:
        out.append(pad_center(f"ESTACION: {str(station).upper()}", width))

    folio = str(payload.get("folio", ""))
    order_num = payload.get("order_number") or folio
    out.append(two_columns(f"ORDEN:#{order_num}", f"FOLIO:{folio}", width))

    created = str(payload.get("created_at", "") or "")
    svc = str(payload.get("service_type_label") or "MOSTRADOR").upper()
    out.append(two_columns(f"FECHA:{created}", svc, width))

    client = payload.get("customer_name")
    if client:
        out.append(f"CLIENTE: {str(client).upper()}")

    driver = payload.get("driver_name")
    if driver:
        out.append(f"REPARTIDOR: {str(driver).upper()}")

    out.append(divider)

    for item in payload.get("lines", []):
        qty = item.get("quantity", 1)
        name = str(item.get("product_name") or "PRODUCTO").upper()
        out.append(f"[ {qty} ] {name}")

        mods = item.get("selected_modifiers") or []
        for mod in mods:
            mod_text = ""
            if isinstance(mod, dict):
                mod_text = str(mod.get("kitchen_text") or mod.get("text") or mod.get("name") or "")
            elif isinstance(mod, str):
                mod_text = mod
            if mod_text:
                out.append(f"    >> {mod_text.upper()}")

        note = item.get("line_notes")
        if note:
            out.append(f"    * NOTA: {str(note).upper()}")

    order_notes = payload.get("order_notes")
    if order_notes:
        out.append(divider)
        out.append("NOTAS DEL PEDIDO:")
        for line in wrap_text(str(order_notes).upper(), width):
            out.append(line)

    out.append(divider)
    out.append(pad_center("RESTAURANTOS KITCHEN", width))

    return "\n".join(out)


# Códigos de control ESC/POS
ESCPOS_INIT = b"\x1b@"
ESCPOS_CUT_PARTIAL = b"\x1dV\x42\x03"
ESCPOS_CUT_FULL = b"\x1dV\x41\x03"
ESCPOS_KICK_DRAWER = b"\x1bp\x00\x19\xfa"


def generate_escpos_ticket(payload: dict[str, Any], kick_drawer: bool = False) -> bytes:
    text = format_ticket_text(payload, 42)
    parts = [ESCPOS_INIT]
    if kick_drawer:
        parts.append(ESCPOS_KICK_DRAWER)
    parts.append(text.encode("latin-1", errors="replace") + b"\n\n\n")
    parts.append(ESCPOS_CUT_PARTIAL)
    return b"".join(parts)


def generate_escpos_kitchen(payload: dict[str, Any]) -> bytes:
    text = format_kitchen_text(payload, 42)
    parts = [ESCPOS_INIT, text.encode("latin-1", errors="replace") + b"\n\n\n", ESCPOS_CUT_FULL]
    return b"".join(parts)
