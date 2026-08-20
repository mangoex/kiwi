# ruff: noqa: E501
"""Versioned, deterministic manifests accepted by :mod:`internal_seed` only.

The values below are the catalog/topology portions of the former local seed
scripts.  They deliberately exclude their old random cash, order and payment
fixtures.  Identifiers are stable names derived only from the literal legacy
SKU/code, never generated at execution time.
"""

from __future__ import annotations

from typing import Any


def _id(prefix: str, value: str) -> str:
    return f"{prefix}-{value.lower()}"


_CATEGORIES = (
    ("Jugos y Extractos", 1), ("Café y Matcha", 2), ("Smoothies y Licuados", 3),
    ("Aguas y Bebidas", 4), ("Panadería", 5), ("Ensaladas", 6),
    ("Emparedados y Sandos", 7), ("Frutas", 8), ("Combos", 9),
)
_UNITS = (
    ("KG", "Kilogramo", 3), ("L", "Litro", 3), ("PZ", "Pieza", 0), ("POR", "Porción", 0),
)
_ITEMS = (
    ("Naranja", "INS-NAR", "KG"), ("Piña", "INS-PIN", "KG"), ("Pepino", "INS-PEP", "KG"),
    ("Apio", "INS-API", "KG"), ("Nopal", "INS-NOP", "KG"), ("Papaya", "INS-PAP", "KG"),
    ("Fresa", "INS-FRE", "KG"), ("Manzana", "INS-MAN", "KG"), ("Limón", "INS-LIM", "KG"),
    ("Zanahoria", "INS-ZAN", "KG"), ("Betabel", "INS-BET", "KG"), ("Espinaca", "INS-ESP", "KG"),
    ("Plátano", "INS-PLA", "KG"), ("Melón", "INS-MEL", "KG"), ("Jengibre", "INS-JEN", "KG"),
    ("Jícama", "INS-JIC", "KG"), ("Aguacate", "INS-AGU", "KG"), ("Tomates Cherry", "INS-TOMC", "KG"),
    ("Gajos de tomate", "INS-TOMG", "KG"), ("Cebolla", "INS-CEB", "KG"),
    ("Leche Entera", "INS-LEC-ENT", "L"), ("Leche Deslactosada", "INS-LEC-DES", "L"),
    ("Leche Almendra", "INS-LEC-ALM", "L"), ("Leche Coco", "INS-LEC-COC", "L"),
    ("Yogurt Natural", "INS-YOG", "L"), ("Lecherita", "INS-LECHERITA", "L"),
    ("Avena", "INS-AVE", "KG"), ("Chía", "INS-CHI", "KG"), ("Nuez", "INS-NUE", "KG"),
    ("Ajonjolí", "INS-AJO", "KG"), ("Cacahuates garapiñados", "INS-CAC", "KG"),
    ("Semillas de girasol", "INS-GIR", "KG"), ("Quinoa", "INS-QUI", "KG"),
    ("Amaranto", "INS-AMA", "KG"), ("Pasas", "INS-PAS", "KG"), ("Miel de abeja", "INS-MIE", "KG"),
    ("Dátil", "INS-DAT", "KG"), ("Cacao", "INS-CAC-POL", "KG"),
    ("Proteína en polvo", "INS-PROT", "KG"), ("Café en grano", "INS-CAF", "KG"),
    ("Matcha", "INS-MAT", "KG"), ("Pollo a la plancha", "INS-POL-PLA", "KG"),
    ("Pollo BBQ", "INS-POL-BBQ", "KG"), ("Jamón", "INS-JAM", "KG"), ("Atún", "INS-ATU", "KG"),
    ("Queso Cabra", "INS-QUE-CAB", "KG"), ("Queso Panela", "INS-QUE-PAN", "KG"),
    ("Philadelphia", "INS-PHI", "KG"), ("Mezcla Quesos", "INS-QUE-MIX", "KG"),
    ("Pan Cuernito", "INS-PAN-CUE", "PZ"), ("Pan Baguette", "INS-PAN-BAG", "PZ"),
    ("Pan Focaccia", "INS-PAN-FOC", "PZ"), ("Pan Sándwich", "INS-PAN-SAN", "PZ"),
    ("Tostaditas horneadas", "INS-TOS-HOR", "KG"), ("Tostaditas crujientes", "INS-TOS-CRU", "KG"),
    ("Pasta Fusili", "INS-FUS", "KG"), ("Aceitunas negras", "INS-ACE", "KG"),
    ("Granos de elote", "INS-ELO", "KG"), ("Aderezo balsámico", "INS-ADE-BAL", "L"),
    ("Aderezo cilantro", "INS-ADE-CIL", "L"), ("Aderezo casa", "INS-ADE-CAS", "L"),
    ("Germinado de alfalfa", "INS-GER", "KG"), ("Galleta chispas", "INS-GAL-CHI", "PZ"),
)
_MENU = (
    ("Jugo Verde", "JUG-VER", "Jugos y Extractos", 6500, "Naranja, piña, pepino, apio y nopal.", ("INS-NAR", "INS-PIN", "INS-PEP", "INS-API", "INS-NOP")),
    ("Jugo Relajante", "JUG-REL", "Jugos y Extractos", 6500, "Naranja, papaya y avena.", ("INS-NAR", "INS-PAP", "INS-AVE")),
    ("Jugo Vitamínico", "JUG-VIT", "Jugos y Extractos", 6500, "Naranja, fresa, manzana y pepino.", ("INS-NAR", "INS-FRE", "INS-MAN", "INS-PEP")),
    ("Jugo Energetizante", "JUG-ENE", "Jugos y Extractos", 6500, "Naranja, piña y limón.", ("INS-NAR", "INS-PIN", "INS-LIM")),
    ("Jugo Anti-anemia", "JUG-ANT", "Jugos y Extractos", 6500, "Naranja, zanahoria y betabel.", ("INS-NAR", "INS-ZAN", "INS-BET")),
    ("Extracto Verde", "EXT-VER", "Jugos y Extractos", 6300, "Mezcla de pepino, apio, espinaca verde, jugo de limón y acidita manzana verde.", ("INS-PEP", "INS-API", "INS-ESP", "INS-LIM", "INS-MAN")),
    ("Extracto Rojo", "EXT-ROJ", "Jugos y Extractos", 6300, "Fresco sabor del pepino con apio, betabel, jugo de limón y dulce de la manzana roja.", ("INS-PEP", "INS-API", "INS-BET", "INS-LIM", "INS-MAN")),
    ("Shot Jengibre-Piña", "SHO-JEN", "Jugos y Extractos", 4000, "Energizante mezcla de extracto de jengibre y rico jugo de piña.", ("INS-JEN", "INS-PIN")),
    ("Kiwi Latte", "CAF-LAT", "Café y Matcha", 7000, "", ("INS-CAF", "INS-LEC-ENT")),
    ("Kiwi Latte Fresh", "CAF-LAT-FRE", "Café y Matcha", 8000, "", ("INS-CAF", "INS-LEC-ENT")),
    ("Café Solo", "CAF-SOL", "Café y Matcha", 5000, "", ("INS-CAF",)),
    ("Café Solo Fresh", "CAF-SOL-FRE", "Café y Matcha", 5500, "", ("INS-CAF",)),
    ("Café Naranja", "CAF-NAR", "Café y Matcha", 7500, "", ("INS-CAF", "INS-NAR")),
    ("Maccha Shiru", "MAT-SHI", "Café y Matcha", 12000, "", ("INS-MAT",)),
    ("Maccha Pinku (con fresa)", "MAT-PIN", "Café y Matcha", 13000, "", ("INS-MAT", "INS-FRE")),
    ("Smoothie Fresh", "SMO-FRE", "Smoothies y Licuados", 9000, "Manzana, leche de almendra, miel de abeja, dátil, chía y espinaca.", ("INS-MAN", "INS-LEC-ALM", "INS-MIE", "INS-DAT", "INS-CHI", "INS-ESP")),
    ("Smoothie Rosa", "SMO-ROS", "Smoothies y Licuados", 9000, "Fresa con leche de almendra, miel de abeja, dátil, chía y espinaca.", ("INS-FRE", "INS-LEC-ALM", "INS-MIE", "INS-DAT", "INS-CHI", "INS-ESP")),
    ("Smoothie Cacao", "SMO-CAC", "Smoothies y Licuados", 9000, "Plátano, leche de almendra, miel de abeja, cacao, chía y espinaca.", ("INS-PLA", "INS-LEC-ALM", "INS-MIE", "INS-CAC-POL", "INS-CHI", "INS-ESP")),
    ("Smoothie Pro", "SMO-PRO", "Smoothies y Licuados", 12000, "Smoothie Fresh, Rosa o Cacao con scoop de proteína.", ("INS-PROT", "INS-LEC-ALM")),
    ("Bisquet", "PAN-BIS", "Panadería", 3500, "", ()),
    ("Baguette", "PAN-BAG", "Panadería", 2600, "", ("INS-PAN-BAG",)),
    ("Cuernito Jamón/Phila", "PAN-CUE", "Panadería", 3800, "Relleno de jamón y philadelphia.", ("INS-PAN-CUE", "INS-JAM", "INS-PHI")),
    ("Barra de pan sándwich", "PAN-BAR", "Panadería", 6000, "", ("INS-PAN-SAN",)),
    ("Ensalada Manzana Nuez", "ENS-MAN", "Ensaladas", 12000, "Lechuga, queso de cabra, nuez, dulces cubitos de manzana, ajonjolí y aderezo balsámico.", ("INS-LEC-ENT", "INS-QUE-CAB", "INS-NUE", "INS-MAN", "INS-AJO", "INS-ADE-BAL")),
    ("Ensalada Frutos Rojos", "ENS-FRU", "Ensaladas", 12500, "Lechuga, fresa, arándanos, queso panela, cacahuates garapiñados y aderezo balsámico.", ("INS-LEC-ENT", "INS-FRE", "INS-QUE-PAN", "INS-CAC", "INS-ADE-BAL")),
    ("Ensalada Del Chef", "ENS-CHE", "Ensaladas", 12500, "Lechuga, pollo a la plancha, pepino, jamón, panela, tostaditas, germinado, gajos de tomate, cebolla, aderezo.", ("INS-LEC-ENT", "INS-POL-PLA", "INS-PEP", "INS-JAM", "INS-QUE-PAN", "INS-TOS-HOR", "INS-GER", "INS-TOMG", "INS-CEB", "INS-ADE-CAS")),
    ("Emparedado de Pollo", "EMP-POL", "Emparedados y Sandos", 11500, "Con Cuernito, Baguette o Focaccia.", ("INS-PAN-CUE", "INS-POL-PLA")),
    ("Sando Kyoto Pollo BBQ", "SAN-KYO-BBQ", "Emparedados y Sandos", 12000, "Sandwich tipo Sando relleno.", ("INS-PAN-SAN", "INS-POL-BBQ")),
    ("Combo Ligero", "COM-LIG", "Combos", 10500, "Sándwich básico + fresco jugo de naranja del día + dulce galleta con chispas.", ("INS-PAN-SAN", "INS-JAM", "INS-QUE-PAN", "INS-NAR", "INS-GAL-CHI")),
    ("Combo Premium", "COM-PRE", "Combos", 18000, "Media ensalada premium y medio baguette de pollo, pollo bbq o atún.", ("INS-LEC-ENT", "INS-PAN-BAG", "INS-POL-PLA")),
)
_BRANCH_NAMES = (
    "Centro Histórico", "Plaza Mayor", "Zona Norte", "Aeropuerto", "Distrito Financiero",
    "Campus Sur", "Paseo de la Reforma",
)


def kiwi_v1_manifest() -> dict[str, Any]:
    """Return the immutable, non-production migration of the legacy seed data."""
    category_ids = {name: f"category-{position:02d}" for name, position in _CATEGORIES}
    item_units = {sku: unit for _name, sku, unit in _ITEMS}
    branches = [
        {
            "id": f"branch-{position:02d}", "legal_entity_id": "legal-kiwi-v1",
            "business_unit_id": "unit-kiwi-v1", "name": name, "code": f"BR-{position:03d}",
            "timezone": "America/Chihuahua",
            "warehouse": {"id": f"warehouse-{position:02d}", "name": f"Almacén {name}"},
        }
        for position, name in enumerate(_BRANCH_NAMES, 1)
    ]
    return {
        "organization_id": "org-kiwi-v1", "environment": "development",
        "operations": [
            {"type": "ensure_organization.v1", "id": "org-kiwi-v1", "name": "Kiwi Restaurante"},
            {
                "type": "ensure_branch_topology.v1",
                "legal_entity": {"id": "legal-kiwi-v1", "name": "Kiwi S.A. de C.V."},
                "business_unit": {"id": "unit-kiwi-v1", "legal_entity_id": "legal-kiwi-v1", "name": "Operaciones Kiwi", "code": "KIWI", "unit_type": "restaurant"},
                "branches": branches,
            },
            {
                "type": "ensure_menu_catalog.v1", "branch_id": "branch-01",
                "categories": [{"id": category_ids[name], "name": name, "display_order": position} for name, position in _CATEGORIES],
                "units": [{"id": _id("unit", code), "code": code, "name": name, "dimension": "discrete", "precision_scale": precision} for code, name, precision in _UNITS],
                "items": [{"id": _id("item", sku), "name": name, "sku": sku, "base_unit_id": _id("unit", unit), "item_type": "ingredient"} for name, sku, unit in _ITEMS],
                "products": [
                    {
                        "id": _id("product", sku), "category_id": category_ids[category], "name": name,
                        "sku": sku, "description": description,
                        "station": "cocina" if "Ensalada" in name or "Sando" in name else "barra",
                        "price": {"id": _id("price", sku), "price_cents": price_cents, "currency": "MXN"},
                        "recipe": {
                            "id": _id("recipe", sku), "version": 1, "yield_quantity": "1",
                            "yield_unit_id": "unit-por",
                            "components": [{"item_id": _id("item", item_sku), "unit_id": _id("unit", item_units[item_sku]), "quantity_base_units": "100", "net_quantity": "100", "waste_rate": "0", "gross_quantity": "100", "sort_order": 0} for item_sku in components],
                        },
                    }
                    for name, sku, category, price_cents, description, components in _MENU
                ],
            },
        ],
    }
