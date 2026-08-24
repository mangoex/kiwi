"""TDD suite for AI-assisted recipe parsing and theoretical costing."""

# ruff: noqa: E501

from decimal import Decimal

from restaurant_os.recipe_ai import (
    calculate_theoretical_recipe_cost,
    match_ingredient_to_catalog,
    normalize_culinary_quantity,
    parse_recipe_text,
)


def test_normalize_culinary_quantity():
    # Mass
    assert normalize_culinary_quantity(250, "g", "KILO") == Decimal("0.250")
    assert normalize_culinary_quantity(500, "gramos", "KILO") == Decimal("0.500")
    assert normalize_culinary_quantity(1.5, "kg", "KILO") == Decimal("1.500")
    
    # Volume
    assert normalize_culinary_quantity(1, "taza", "LITRO") == Decimal("0.240")
    assert normalize_culinary_quantity(0.25, "taza", "LITRO") == Decimal("0.060")
    assert normalize_culinary_quantity(1, "cucharada", "LITRO") == Decimal("0.015")
    assert normalize_culinary_quantity(1, "cda", "LITRO") == Decimal("0.015")
    assert normalize_culinary_quantity(2, "cucharaditas", "LITRO") == Decimal("0.010")
    
    # Density-based volume to mass (e.g. 1/2 cup grated cheese ~ 60g = 0.060 kg)
    assert normalize_culinary_quantity(0.5, "taza", "KILO", density_hint="queso") == Decimal("0.060")
    
    # Discrete pieces
    assert normalize_culinary_quantity(1, "pieza", "PIEZA") == Decimal("1.000")
    assert normalize_culinary_quantity(1, "pan", "PIEZA") == Decimal("1.000")


def test_match_ingredient_to_catalog():
    catalog_items = [
        {"id": "item-1001", "name": "ACEITUNA NEGRA", "unit": "KILO", "cost": Decimal("202.33")},
        {"id": "item-1002", "name": "ATUN", "unit": "KILO", "cost": Decimal("217.33")},
        {"id": "item-6007", "name": "POLLO", "unit": "KILO", "cost": Decimal("200.00")},
        {"id": "item-pan-bag", "name": "PAN BAGUETTE", "unit": "PIEZA", "cost": Decimal("15.00")},
        {"id": "item-que-moz", "name": "QUESO MANCHEGO / MOZZARELLA", "unit": "KILO", "cost": Decimal("180.00")},
        {"id": "item-ceb-mor", "name": "CEBOLLA MORADA", "unit": "KILO", "cost": Decimal("35.00")},
        {"id": "item-ade-bbq", "name": "ADEREZO BBQ", "unit": "LITRO", "cost": Decimal("95.00")},
        {"id": "item-ace-oli", "name": "ACEITE", "unit": "LITRO", "cost": Decimal("90.00")},
    ]

    # Matching tests
    match_pollo = match_ingredient_to_catalog("pechuga de pollo (cocida y deshebrada)", catalog_items)
    assert match_pollo is not None
    assert match_pollo["matched_item_id"] == "item-6007"

    match_baguette = match_ingredient_to_catalog("1 pan baguette fresco", catalog_items)
    assert match_baguette is not None
    assert match_baguette["matched_item_id"] == "item-pan-bag"

    match_bbq = match_ingredient_to_catalog("salsa BBQ", catalog_items)
    assert match_bbq is not None
    assert match_bbq["matched_item_id"] == "item-ade-bbq"


def test_parse_recipe_text_full_recipe():
    raw_text = """
    Prepara un delicioso baguette de pollo BBQ calentado con queso fundido y cebolla morada en pocos minutos.
    Ingredientes
    1 pan baguette fresco.
    250 g de pechuga de pollo (cocida y deshebrada o en tiras).
    1/4 de taza de salsa BBQ.
    1/2 taza de queso mozzarella o cheddar rallado.
    1/4 de cebolla morada en rodajas finas.
    Cilantro fresco picado al gusto.
    1 cucharada de aceite de oliva o mantequilla.
    Preparación
    Calienta el pollo: Saltea el pollo en un sartén con un poco de aceite de oliva. Añade la salsa BBQ y mezcla bien hasta que el pollo esté cubierto y caliente.
    Prepara el pan: Corta el baguette por la mitad a lo largo.
    Arma el baguette: Coloca el pollo bañado en salsa BBQ sobre la base del pan.
    Agrega los extras: Distribuye el queso rallado encima del pollo y acomoda las rodajas de cebolla morada.
    Hornea o gratina: Hornea a 200 °C durante 5 a 8 minutos.
    """

    parsed = parse_recipe_text(raw_text)
    assert "baguette de pollo bbq" in parsed["title"].lower() or "baguette" in parsed["title"].lower()
    assert len(parsed["ingredients"]) >= 6

    # Verify extracted quantities
    pollo = next((i for i in parsed["ingredients"] if "pollo" in i["raw_name"].lower()), None)
    assert pollo is not None
    assert pollo["quantity"] == Decimal("250")
    assert pollo["unit"] in ["g", "gramos"]

    pan = next((i for i in parsed["ingredients"] if "baguette" in i["raw_name"].lower()), None)
    assert pan is not None
    assert pan["quantity"] == Decimal("1")


def test_calculate_theoretical_recipe_cost():
    ingredients_with_matches = [
        {
            "raw_name": "pan baguette fresco",
            "quantity": Decimal("1"),
            "unit": "pieza",
            "matched_item_id": "item-pan-bag",
            "matched_item_name": "PAN BAGUETTE",
            "base_unit": "PIEZA",
            "normalized_quantity": Decimal("1.000"),
            "unit_cost": Decimal("15.00"),
        },
        {
            "raw_name": "pechuga de pollo",
            "quantity": Decimal("250"),
            "unit": "g",
            "matched_item_id": "item-6007",
            "matched_item_name": "POLLO",
            "base_unit": "KILO",
            "normalized_quantity": Decimal("0.250"),
            "unit_cost": Decimal("200.00"),
        },
        {
            "raw_name": "salsa BBQ",
            "quantity": Decimal("0.25"),
            "unit": "taza",
            "matched_item_id": "item-ade-bbq",
            "matched_item_name": "ADEREZO BBQ",
            "base_unit": "LITRO",
            "normalized_quantity": Decimal("0.060"),
            "unit_cost": Decimal("95.00"),
        },
        {
            "raw_name": "queso mozzarella",
            "quantity": Decimal("0.5"),
            "unit": "taza",
            "matched_item_id": "item-que-moz",
            "matched_item_name": "QUESO MANCHEGO / MOZZARELLA",
            "base_unit": "KILO",
            "normalized_quantity": Decimal("0.060"),
            "unit_cost": Decimal("180.00"),
        },
    ]

    costing = calculate_theoretical_recipe_cost(
        ingredients=ingredients_with_matches,
        yield_portions=Decimal("1"),
        sale_price=Decimal("130.00"),
    )

    # 15.00 + (0.250*200 = 50.00) + (0.060*95 = 5.70) + (0.060*180 = 10.80) = 81.50
    assert costing["total_cost"] == Decimal("81.50")
    assert costing["cost_per_portion"] == Decimal("81.50")
    assert costing["food_cost_percentage"] == Decimal("62.69")  # 81.50 / 130 * 100
    assert costing["food_cost_status"] in ["warning", "alert", "optimal"]
