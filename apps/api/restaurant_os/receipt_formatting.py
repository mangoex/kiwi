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
    "SUCURSAL:CALLE JOSEFA ORTIZ DE DOMINGUEZ NUM 598 INT 6 COLONIA CHAPULTEPEC CULIACAN SINALOA"
)


DEFAULT_PRINT_AREAS: list[dict[str, Any]] = [
    {
        "code": "salads",
        "name": "ENSALADAS",
        "station": "kitchen",
        "print_comanda": True,
        "sort_order": 1,
        "is_system": True,
    },
    {
        "code": "baguettes",
        "name": "BAGUETTES(RAPIDO)",
        "station": "kitchen",
        "print_comanda": True,
        "sort_order": 2,
        "is_system": True,
    },
    {
        "code": "kitchen",
        "name": "BARRA / CALIENTE",
        "station": "kitchen",
        "print_comanda": True,
        "sort_order": 3,
        "is_system": True,
    },
    {
        "code": "drinks",
        "name": "BEBIDAS (BARRA / FUENTES)",
        "station": "drinks",
        "print_comanda": True,
        "sort_order": 4,
        "is_system": True,
    },
    {
        "code": "packing",
        "name": "EMPAQUE",
        "station": "packing",
        "print_comanda": False,
        "sort_order": 5,
        "is_system": True,
    },
    {
        "code": "none",
        "name": "SIN IMPRESION",
        "station": "kitchen",
        "print_comanda": False,
        "sort_order": 6,
        "is_system": True,
    },
]

_BAGUETTE_BARRA_KEYWORDS = (
    "BAGUETTE",
    "SANDWICH",
    "SÁNDWICH",
    "CUERNITO",
    "PANINI",
    "DESAYUNO",
    "OMELETTE",
    "MOLLETE",
    "TOSTADA",
    "WRAP",
    "BURRITO",
    "QUESADILLA",
    "CHAPATA",
    "CIABATTA",
    "CROISSANT",
)

_DRINK_KEYWORDS = (
    "AGUA",
    "AGUAS",
    "BEBIDA",
    "BEBIDAS",
    "JUGO",
    "JUGOS",
    "LICUADO",
    "LICUADOS",
    "SMOOTHIE",
    "EXTRACTO",
    "CAFE",
    "CAFÉ",
    "CAFES",
    "FRAPPE",
    "MATCHA",
    "REFRESCO",
    "TISANA",
)

_PACKING_KEYWORDS = (
    "DOMICILIO",
    "EMPAQUE",
    "BOLSA",
    "DESECHABLE",
    "ENVIO",
    "ENVÍO",
)


def extract_short_order_number(folio: str, order_number: Any = None) -> str:
    folio_str = str(folio or "").strip()
    if order_number is not None:
        ord_str = str(order_number).strip()
        if ord_str and ord_str != folio_str:
            return ord_str
    if "-" in folio_str:
        suffix = folio_str.rsplit("-", 1)[-1].strip()
        if suffix.isdigit():
            return str(int(suffix))
    return str(order_number if order_number is not None else folio_str).strip() or "1"


def normalize_print_areas(raw_areas: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    by_code: dict[str, dict[str, Any]] = {area["code"]: dict(area) for area in DEFAULT_PRINT_AREAS}
    if isinstance(raw_areas, list):
        for idx, item in enumerate(raw_areas):
            if not isinstance(item, dict):
                continue
            code = str(item.get("code") or "").strip().lower()
            name = str(item.get("name") or "").strip().upper()
            if not code or not name:
                continue
            station = str(item.get("station") or "kitchen").strip().lower()
            if station not in {"kitchen", "drinks", "packing"}:
                station = "kitchen"
            existing = by_code.get(code, {})
            by_code[code] = {
                "code": code,
                "name": name,
                "station": station,
                "print_comanda": bool(
                    item.get(
                        "print_comanda",
                        existing.get("print_comanda", code not in {"packing", "none"}),
                    )
                ),
                "sort_order": int(
                    item.get("sort_order") or existing.get("sort_order") or (idx + 1)
                ),
                "is_system": bool(existing.get("is_system", False)),
            }
    return sorted(
        by_code.values(), key=lambda a: (int(a.get("sort_order", 99)), str(a.get("code", "")))
    )


def resolve_product_print_area(
    item: dict[str, Any],
    routing_config: dict[str, Any] | None = None,
) -> str:
    cfg = routing_config or {}
    areas = normalize_print_areas(cfg.get("areas"))
    valid_codes = {a["code"] for a in areas}

    explicit_line = str(item.get("print_area") or item.get("print_area_code") or "").strip().lower()
    if explicit_line in valid_codes:
        return explicit_line

    product_areas: dict[str, str] = cfg.get("product_areas") or {}
    for key_field in ("product_id", "id", "sku", "product_name", "name"):
        val = str(item.get(key_field) or "").strip()
        if val and val in product_areas:
            mapped = str(product_areas[val]).strip().lower()
            if mapped in valid_codes:
                return mapped

    category_areas: dict[str, str] = cfg.get("category_areas") or {}
    for cat_field in ("category_id", "category_name"):
        cat_val = str(item.get(cat_field) or "").strip()
        if cat_val:
            for candidate in (cat_val, cat_val.upper()):
                if candidate in category_areas:
                    mapped = str(category_areas[candidate]).strip().lower()
                    if mapped in valid_codes:
                        return mapped

    station_raw = str(item.get("station") or "").strip().lower()
    if station_raw in valid_codes and station_raw not in {"kitchen", "drinks", "packing"}:
        return station_raw

    name_upper = str(item.get("product_name") or item.get("name") or "").strip().upper()
    cat_upper = str(item.get("category_name") or "").strip().upper()
    combined = f"{cat_upper} {name_upper}"

    if "ENSALADA" in combined and "salads" in valid_codes:
        return "salads"
    if any(kw in combined for kw in _BAGUETTE_BARRA_KEYWORDS) and "baguettes" in valid_codes:
        return "baguettes"
    if (
        station_raw == "drinks" or any(kw in combined for kw in _DRINK_KEYWORDS)
    ) and "drinks" in valid_codes:
        return "drinks"
    if (
        station_raw == "packing" or any(kw in combined for kw in _PACKING_KEYWORDS)
    ) and "packing" in valid_codes:
        return "packing"
    if station_raw in valid_codes:
        return station_raw
    return "kitchen"


def split_kitchen_payload_by_area(
    payload: dict[str, Any],
    routing_config: dict[str, Any] | None = None,
    *,
    include_non_printing: bool = False,
) -> list[dict[str, Any]]:
    cfg = routing_config or {}
    areas = normalize_print_areas(cfg.get("areas"))
    area_map = {a["code"]: a for a in areas}

    grouped: dict[str, list[dict[str, Any]]] = {}
    for line in payload.get("lines", []):
        area_code = resolve_product_print_area(line, cfg)
        area_info = area_map.get(
            area_code,
            {
                "code": area_code,
                "name": area_code.upper(),
                "station": "kitchen",
                "print_comanda": True,
                "sort_order": 99,
            },
        )
        if not include_non_printing and not area_info.get("print_comanda", True):
            continue
        grouped.setdefault(area_code, []).append(
            {
                **line,
                "print_area": area_code,
                "print_area_name": area_info["name"],
            }
        )

    ordered_codes = sorted(
        grouped.keys(),
        key=lambda c: (int(area_map.get(c, {}).get("sort_order", 99)), c),
    )

    jobs: list[dict[str, Any]] = []
    for code in ordered_codes:
        area_info = area_map.get(code, {"code": code, "name": code.upper()})
        jobs.append(
            {
                **payload,
                "area_code": code,
                "area_name": area_info["name"],
                "station": area_info["name"],
                "lines": grouped[code],
            }
        )
    return jobs


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

    order_num = extract_short_order_number(folio, payload.get("order_number"))
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
    divider = "=" * width
    out: list[str] = []

    folio = str(payload.get("folio", ""))
    order_num = extract_short_order_number(folio, payload.get("order_number"))
    station = payload.get("area_name") or payload.get("station")

    out.append(pad_center("*** COMANDA DE COCINA ***", width))
    if station:
        station_upper = str(station).upper()
        out.append(f"{station_upper} ORDEN: {order_num}")
        out.append(pad_center(f"ESTACION: {station_upper}", width))

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

        mods = item.get("selected_modifiers") or item.get("modifiers") or []
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
ESCPOS_CUT_PARTIAL = b"\x1dV\x42\x02"
ESCPOS_CUT_FULL = b"\x1dV\x41\x02"
ESCPOS_KICK_DRAWER = b"\x1bp\x00\x19\xfa"


def generate_escpos_ticket(payload: dict[str, Any], kick_drawer: bool = False) -> bytes:
    text = format_ticket_text(payload, 42)
    parts = [ESCPOS_INIT]
    if kick_drawer:
        parts.append(ESCPOS_KICK_DRAWER)
    parts.append(text.encode("latin-1", errors="replace") + b"\n\n")
    parts.append(ESCPOS_CUT_PARTIAL)
    return b"".join(parts)


def generate_escpos_kitchen(payload: dict[str, Any]) -> bytes:
    text = format_kitchen_text(payload, 42)
    parts = [ESCPOS_INIT, text.encode("latin-1", errors="replace") + b"\n\n", ESCPOS_CUT_FULL]
    return b"".join(parts)


PRINT_ROUTING_ENTITY_TYPE = "print_routing_config"
PRINT_ROUTING_ENTITY_ID = "default_print_routing"
PRINT_ROUTING_ACTION = "print_routing.updated"

DEFAULT_AREA_PRINTERS: dict[str, dict[str, Any]] = {
    "salads": {"enabled": True, "printer_name": "ensaladas", "host": "", "port": 9100},
    "baguettes": {"enabled": True, "printer_name": "barra", "host": "", "port": 9100},
    "kitchen": {"enabled": True, "printer_name": "barra", "host": "", "port": 9100},
    "drinks": {"enabled": True, "printer_name": "bebidas", "host": "", "port": 9100},
    "packing": {"enabled": False, "printer_name": "", "host": "", "port": 9100},
    "none": {"enabled": False, "printer_name": "", "host": "", "port": 9100},
}


def normalize_print_routing_config(raw: dict[str, Any] | None = None) -> dict[str, Any]:
    data = raw or {}
    areas = normalize_print_areas(data.get("areas"))
    valid_codes = {a["code"] for a in areas}

    raw_product_areas = data.get("product_areas") or {}
    product_areas: dict[str, str] = {}
    if isinstance(raw_product_areas, dict):
        for k, v in raw_product_areas.items():
            key_str = str(k).strip()
            val_str = str(v).strip().lower()
            if key_str and val_str in valid_codes:
                product_areas[key_str] = val_str

    raw_category_areas = data.get("category_areas") or {}
    category_areas: dict[str, str] = {}
    if isinstance(raw_category_areas, dict):
        for k, v in raw_category_areas.items():
            key_str = str(k).strip()
            val_str = str(v).strip().lower()
            if key_str and val_str in valid_codes:
                category_areas[key_str] = val_str

    raw_ticket_printer = (
        data.get("ticket_printer") if isinstance(data.get("ticket_printer"), dict) else {}
    )
    ticket_printer = {
        "enabled": bool(raw_ticket_printer.get("enabled", True)),
        "printer_name": str(raw_ticket_printer.get("printer_name") or "caja").strip(),
        "host": str(raw_ticket_printer.get("host") or "").strip(),
        "port": int(raw_ticket_printer.get("port") or 9100),
    }

    raw_area_printers = (
        data.get("area_printers") if isinstance(data.get("area_printers"), dict) else {}
    )
    area_printers: dict[str, dict[str, Any]] = {}
    for area in areas:
        code = area["code"]
        default_printer = DEFAULT_AREA_PRINTERS.get(
            code,
            {
                "enabled": bool(area.get("print_comanda", True)),
                "printer_name": code if area.get("print_comanda", True) else "",
                "host": "",
                "port": 9100,
            },
        )
        entry = raw_area_printers.get(code) if isinstance(raw_area_printers.get(code), dict) else {}
        area_printers[code] = {
            "enabled": bool(entry.get("enabled", default_printer["enabled"])),
            "printer_name": str(
                entry.get("printer_name")
                if "printer_name" in entry
                else default_printer["printer_name"]
            ).strip(),
            "host": str(entry.get("host") or default_printer["host"]).strip(),
            "port": int(entry.get("port") or default_printer["port"] or 9100),
        }

    return {
        "areas": areas,
        "product_areas": product_areas,
        "category_areas": category_areas,
        "ticket_printer": ticket_printer,
        "area_printers": area_printers,
        "updated_at": data.get("updated_at"),
    }


def get_print_routing_config(
    session: Any,
    organization_id: str | None = None,
) -> dict[str, Any]:
    import sqlalchemy as sa

    from restaurant_os import models, operations

    org_id = organization_id or operations.ORGANIZATION_ID
    stmt = (
        sa.select(models.audit_events.c.payload, models.audit_events.c.created_at)
        .where(
            models.audit_events.c.entity_type == PRINT_ROUTING_ENTITY_TYPE,
            models.audit_events.c.entity_id == PRINT_ROUTING_ENTITY_ID,
            models.audit_events.c.action == PRINT_ROUTING_ACTION,
        )
        .order_by(models.audit_events.c.created_at.desc())
        .limit(1)
    )
    if organization_id:
        stmt = stmt.where(models.audit_events.c.organization_id == org_id)
    row = session.execute(stmt).first()
    if not row:
        return normalize_print_routing_config({})
    payload = dict(row[0] or {})
    if row[1] and not payload.get("updated_at"):
        payload["updated_at"] = row[1].isoformat() if hasattr(row[1], "isoformat") else str(row[1])
    return normalize_print_routing_config(payload)


def save_print_routing_config(
    session: Any,
    payload: dict[str, Any],
    *,
    actor_user_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    from datetime import datetime, timezone
    from uuid import uuid4

    import sqlalchemy as sa

    from restaurant_os import models, operations

    org_id = organization_id or operations.ORGANIZATION_ID
    current = get_print_routing_config(session, organization_id=organization_id)
    merged = {
        "areas": payload.get("areas", current["areas"]),
        "product_areas": (
            payload["product_areas"] if "product_areas" in payload else current["product_areas"]
        ),
        "category_areas": (
            payload["category_areas"] if "category_areas" in payload else current["category_areas"]
        ),
        "ticket_printer": (
            payload["ticket_printer"] if "ticket_printer" in payload else current["ticket_printer"]
        ),
        "area_printers": (
            payload["area_printers"] if "area_printers" in payload else current["area_printers"]
        ),
    }
    now = datetime.now(timezone.utc)
    normalized = normalize_print_routing_config(merged)
    normalized["updated_at"] = now.isoformat()

    existing_org_id = session.scalar(
        sa.select(models.organizations.c.id).where(models.organizations.c.id == org_id)
    )
    if not existing_org_id:
        existing_org_id = session.scalar(sa.select(models.organizations.c.id).limit(1))
    if not existing_org_id:
        session.execute(
            models.organizations.insert().values(
                id=org_id,
                name="Kiwi Comida Natural",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        existing_org_id = org_id

    valid_actor_id: str | None = None
    if actor_user_id:
        valid_actor_id = session.scalar(
            sa.select(models.users.c.id).where(models.users.c.id == actor_user_id)
        )

    session.execute(
        models.audit_events.insert().values(
            id=str(uuid4()),
            organization_id=existing_org_id,
            branch_id=None,
            actor_user_id=valid_actor_id,
            action=PRINT_ROUTING_ACTION,
            entity_type=PRINT_ROUTING_ENTITY_TYPE,
            entity_id=PRINT_ROUTING_ENTITY_ID,
            payload=normalized,
            correlation_id=str(uuid4()),
            created_at=now,
        )
    )
    session.commit()
    return normalized


def set_product_print_area(
    session: Any,
    product_id: str,
    area_code: str,
    *,
    actor_user_id: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    current = get_print_routing_config(session, organization_id=organization_id)
    product_areas = dict(current.get("product_areas") or {})
    cleaned_product_id = str(product_id).strip()
    cleaned_area = str(area_code or "").strip().lower()
    valid_codes = {a["code"] for a in current.get("areas", [])}
    if not cleaned_area:
        product_areas.pop(cleaned_product_id, None)
    elif cleaned_area in valid_codes:
        product_areas[cleaned_product_id] = cleaned_area
    else:
        raise ValueError(f"Invalid print_area code: {area_code}")

    return save_print_routing_config(
        session,
        {**current, "product_areas": product_areas},
        actor_user_id=actor_user_id,
        organization_id=organization_id,
    )


def preview_order_print_routing(
    payload: dict[str, Any],
    routing_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = normalize_print_routing_config(routing_config)
    ticket_text = format_ticket_text(payload, 42)
    kitchen_jobs = split_kitchen_payload_by_area(payload, cfg)
    area_printers = cfg.get("area_printers") or {}
    comandas = []
    for job in kitchen_jobs:
        area_code = job["area_code"]
        printer_cfg = area_printers.get(area_code, {})
        comandas.append(
            {
                "area_code": area_code,
                "area_name": job["area_name"],
                "station": job["station"],
                "printer_name": printer_cfg.get("printer_name", ""),
                "host": printer_cfg.get("host", ""),
                "port": printer_cfg.get("port", 9100),
                "line_count": len(job.get("lines", [])),
                "text": format_kitchen_text(job, 42),
            }
        )
    return {
        "order_number": extract_short_order_number(
            payload.get("folio"), payload.get("order_number")
        ),
        "ticket": {
            "printer_name": cfg["ticket_printer"].get("printer_name", "caja"),
            "host": cfg["ticket_printer"].get("host", ""),
            "port": cfg["ticket_printer"].get("port", 9100),
            "text": ticket_text,
        },
        "comandas": comandas,
    }
