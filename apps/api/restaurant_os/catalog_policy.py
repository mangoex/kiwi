from __future__ import annotations

import re

LEADING_IMPORT_QUOTES = "'´‘’"
ASCII_NUMERIC_SKU = re.compile(r"^[0-9]+$")

DRINK_CATEGORIES = frozenset(
    {
        "AGUAS",
        "BEBIDAS",
        "EXTRA JUGOS",
        "EXTRA LICUADOS",
        "JUGOS",
        "LICUADOS",
        "SMOOTHIES Y EXTRACTOS",
    }
)
PACKING_CATEGORIES = frozenset({"SERVICIOS A DOMICILIO"})
DRINK_WORDS = frozenset(
    {
        "AGUA",
        "BEBIDA",
        "BEBIDAS",
        "CAFE",
        "CAFÉ",
        "EXTRACTO",
        "EXTRACTOS",
        "JUGO",
        "JUGOS",
        "LICUADO",
        "LICUADOS",
        "MATCHA",
        "REFRESCO",
        "SMOOTHIE",
        "SMOOTHIES",
        "TE",
        "TÉ",
    }
)
PACKING_WORDS = frozenset(
    {
        "BAG",
        "BOLSA",
        "BOLSAS",
        "CONTENEDOR",
        "CONTENEDORES",
        "CUBIERTO",
        "CUBIERTOS",
        "EMPAQUE",
        "EMPAQUES",
        "SERVILLETA",
        "SERVILLETAS",
    }
)
PACKAGING_ITEM_CATEGORIES = frozenset({"PLASTICOS Y DESECHABLES", "PLÁSTICOS Y DESECHABLES"})


def normalize_product_sku(value: object) -> str:
    return str(value or "").strip().lstrip(LEADING_IMPORT_QUOTES).strip()


def normalize_inventory_sku(value: object) -> str:
    return str(value or "").strip()


def is_numeric_sku(value: object) -> bool:
    return bool(ASCII_NUMERIC_SKU.fullmatch(str(value or "")))


def is_uppercase_name(value: object) -> bool:
    normalized = str(value or "").strip()
    return bool(normalized) and normalized == normalized.upper()


def canonical_category_name(value: object) -> str:
    return str(value or "").strip().upper()


def product_station(name: object, category_name: object) -> str:
    normalized_name = str(name or "").strip().upper()
    normalized_category = canonical_category_name(category_name)
    words = frozenset(re.findall(r"[A-ZÁÉÍÓÚÜÑ]+", normalized_name))
    if normalized_category in PACKING_CATEGORIES or words & PACKING_WORDS:
        return "packing"
    if normalized_category in DRINK_CATEGORIES or words & DRINK_WORDS:
        return "drinks"
    return "kitchen"


def canonical_inventory_item_type(category_name: object, current_type: object) -> str:
    normalized_category = canonical_category_name(category_name)
    if normalized_category in PACKAGING_ITEM_CATEGORIES:
        return "packaging"
    return str(current_type or "ingredient").strip().lower() or "ingredient"
