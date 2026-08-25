"""Recipe AI Agent Module.

Provides intelligent natural language recipe parsing, culinary unit conversions,
catalog semantic matching against Kiwi inventory supplies, and theoretical food cost calculations.
"""

from __future__ import annotations

# ruff: noqa: E501
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from enum import Enum
from typing import Any


class CulinaryUnit(str, Enum):
    MASS_GRAM = "g"
    MASS_KILO = "kg"
    MASS_OUNCE = "oz"
    MASS_POUND = "lb"
    VOL_MILLILITER = "ml"
    VOL_LITER = "l"
    VOL_CUP = "taza"
    VOL_TABLESPOON = "cucharada"
    VOL_TEASPOON = "cucharadita"
    VOL_PINCH = "pizca"
    DISCRETE_PIECE = "pieza"
    DISCRETE_PORTION = "porcion"


# Density conversion factors (approximate kilograms per liter or cup for common restaurant items)
CULINARY_DENSITY_GRAMS_PER_CUP: dict[str, Decimal] = {
    "queso": Decimal("120"),         # 1 cup shredded cheese ~ 120g
    "mozzarella": Decimal("120"),
    "cheddar": Decimal("120"),
    "harina": Decimal("125"),        # 1 cup flour ~ 125g
    "azucar": Decimal("200"),        # 1 cup sugar ~ 200g
    "avena": Decimal("90"),          # 1 cup rolled oats ~ 90g
    "arroz": Decimal("185"),
    "miel": Decimal("340"),
    "salsa": Decimal("240"),
    "aderezo": Decimal("240"),
    "default": Decimal("240"),       # 1 cup water/liquid = 240g
}

# Volume in Liters
CULINARY_VOLUME_TO_LITERS: dict[str, Decimal] = {
    "l": Decimal("1.000"),
    "lt": Decimal("1.000"),
    "lts": Decimal("1.000"),
    "litro": Decimal("1.000"),
    "litros": Decimal("1.000"),
    "ml": Decimal("0.001"),
    "mililitro": Decimal("0.001"),
    "mililitros": Decimal("0.001"),
    "cc": Decimal("0.001"),
    "taza": Decimal("0.240"),
    "tazas": Decimal("0.240"),
    "cup": Decimal("0.240"),
    "cups": Decimal("0.240"),
    "cda": Decimal("0.015"),
    "cdas": Decimal("0.015"),
    "cucharada": Decimal("0.015"),
    "cucharadas": Decimal("0.015"),
    "tbsp": Decimal("0.015"),
    "cdta": Decimal("0.005"),
    "cdtas": Decimal("0.005"),
    "cucharadita": Decimal("0.005"),
    "cucharaditas": Decimal("0.005"),
    "tsp": Decimal("0.005"),
    "chorrito": Decimal("0.010"),
    "pizca": Decimal("0.001"),
}

# Mass in Kilograms
CULINARY_MASS_TO_KILOS: dict[str, Decimal] = {
    "kg": Decimal("1.000"),
    "kilo": Decimal("1.000"),
    "kilos": Decimal("1.000"),
    "kilogramo": Decimal("1.000"),
    "kilogramos": Decimal("1.000"),
    "g": Decimal("0.001"),
    "gr": Decimal("0.001"),
    "grs": Decimal("0.001"),
    "gramo": Decimal("0.001"),
    "gramos": Decimal("0.001"),
    "oz": Decimal("0.02835"),
    "onza": Decimal("0.02835"),
    "onzas": Decimal("0.02835"),
    "lb": Decimal("0.45359"),
    "libra": Decimal("0.45359"),
    "libras": Decimal("0.45359"),
}

# Common culinary stop words to remove for semantic matching
STOP_WORDS = {
    "de", "del", "la", "el", "los", "las", "un", "una", "unos", "unas",
    "fresco", "fresca", "frescos", "frescas", "picado", "picada", "picados",
    "en", "rodajas", "tiras", "trozos", "cubos", "al", "gusto", "cocida", "cocido",
    "deshebrada", "deshebrado", "rallado", "rallada", "fundido", "fundida",
    "calentado", "calentada", "pocos", "minutos", "para", "con", "sin", "por",
    "limpio", "limpia", "dente", "extra", "opcional"
}


def _strip_accents(text: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", text) if unicodedata.category(c) != "Mn"
    )


def _clean_token(word: str) -> str:
    cleaned = re.sub(r"[^\w\s]", "", word).strip().lower()
    return _strip_accents(cleaned)


def parse_fraction(text: str) -> Decimal:
    """Parses text containing integer, float or fractions like '1/2', '1/4', '1 1/2'."""
    text = text.strip()
    # Replace unicode fractions
    unicode_fractions = {
        "½": "1/2", "¼": "1/4", "¾": "3/4", "⅓": "1/3", "⅔": "2/3",
        "⅛": "1/8", "⅜": "3/8", "⅝": "5/8", "⅞": "7/8"
    }
    for uf, frac in unicode_fractions.items():
        text = text.replace(uf, f" {frac}")

    parts = text.split()
    total = Decimal("0")
    for part in parts:
        if "/" in part:
            num, den = part.split("/", 1)
            try:
                total += Decimal(num.strip()) / Decimal(den.strip())
            except (InvalidOperation, ZeroDivisionError):
                pass
        else:
            try:
                total += Decimal(part.strip())
            except InvalidOperation:
                pass
    return total if total > 0 else Decimal("1")


def normalize_culinary_quantity(
    quantity: float | int | Decimal | str,
    unit: str,
    target_base_unit: str,
    density_hint: str | None = None,
) -> Decimal:
    """Converts a culinary quantity and unit into the target base unit (KILO, LITRO, PIEZA)."""
    if isinstance(quantity, str):
        qty = parse_fraction(quantity)
    else:
        qty = Decimal(str(quantity))

    unit_norm = _strip_accents(unit.strip().lower())
    target_norm = target_base_unit.strip().upper()

    # Target is KILO / KG
    if target_norm in ("KILO", "KG", "KILOGRAMO"):
        if unit_norm in CULINARY_MASS_TO_KILOS:
            return (qty * CULINARY_MASS_TO_KILOS[unit_norm]).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        elif unit_norm in CULINARY_VOLUME_TO_LITERS:
            # Check density hint
            liters = qty * CULINARY_VOLUME_TO_LITERS[unit_norm]
            density_factor = CULINARY_DENSITY_GRAMS_PER_CUP.get("default", Decimal("240"))
            if density_hint:
                hint_clean = _strip_accents(density_hint.lower())
                for k, v in CULINARY_DENSITY_GRAMS_PER_CUP.items():
                    if k in hint_clean:
                        density_factor = v
                        break
            # 1 cup = 0.240 L -> grams = (liters / 0.240) * density_factor -> kg = grams / 1000
            cups = liters / Decimal("0.240")
            kg = (cups * density_factor) / Decimal("1000")
            return kg.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        else:
            # Discrete or unspecified assumed 1 unit = approx 0.100 kg or return qty as kg
            return qty.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    # Target is LITRO / L
    elif target_norm in ("LITRO", "L", "LTS"):
        if unit_norm in CULINARY_VOLUME_TO_LITERS:
            return (qty * CULINARY_VOLUME_TO_LITERS[unit_norm]).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        elif unit_norm in CULINARY_MASS_TO_KILOS:
            # Mass to volume (assume approx 1kg = 1L for liquids/purees)
            return (qty * CULINARY_MASS_TO_KILOS[unit_norm]).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)
        else:
            return qty.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)

    # Target is PIEZA / PZ / PORCION
    else:
        return qty.quantize(Decimal("0.001"), rounding=ROUND_HALF_UP)


def match_ingredient_to_catalog(
    ingredient_text: str,
    catalog_items: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Matches an ingredient name against catalog supplies using token similarity and semantic synonyms."""
    if not ingredient_text or not catalog_items:
        return None

    raw_clean = _strip_accents(ingredient_text.lower())
    tokens = {
        _clean_token(t)
        for t in re.split(r"[\s\(\)\,\.\/]+", raw_clean)
        if _clean_token(t) and _clean_token(t) not in STOP_WORDS
    }

    best_match = None
    highest_score = 0.0

    # Synonym mappings for Mexican restaurant kitchens
    synonyms = {
        "pollo": ["pollo", "pechuga", "pechuga de pollo"],
        "bbq": ["bbq", "aderezo bbq", "salsa bbq"],
        "baguette": ["baguette", "pan baguette", "pan"],
        "cuernito": ["cuernito", "croissant"],
        "focaccia": ["focaccia"],
        "queso": ["queso", "mozzarella", "cheddar", "manchego", "panela", "cabra", "philadelphia"],
        "cebolla": ["cebolla", "cebolla morada", "cebolla blanca"],
        "aceite": ["aceite", "aceite de oliva", "mantequilla"],
        "cilantro": ["cilantro", "verdura", "aderezo cilantro"],
        "atun": ["atun", "lata de atun"],
        "fresa": ["fresa", "fresas"],
        "naranja": ["naranja", "jugo naranja"],
        "avena": ["avena", "cereal"],
        "miel": ["miel", "miel de abeja"],
        "datil": ["datil", "datiles"],
        "cacao": ["cacao", "chocomilk", "hershey"],
    }

    for item in catalog_items:
        item_id = str(item.get("id") or item.get("sku") or "")
        item_name = str(item.get("name", ""))
        item_clean = _strip_accents(item_name.lower())
        item_tokens = {
            _clean_token(t)
            for t in re.split(r"[\s\(\)\,\.\/]+", item_clean)
            if _clean_token(t) and _clean_token(t) not in STOP_WORDS
        }

        # 1. Exact token set match (e.g. 'aderezo de arandano' vs 'ADEREZO ARANDANO')
        if tokens and item_tokens and tokens == item_tokens:
            score = 3.0
        elif item_tokens and item_tokens.issubset(tokens) and len(item_tokens) >= 2:
            score = 2.5
        elif item_clean in raw_clean or raw_clean in item_clean:
            score = 2.0 + (len(item_clean) / 100.0)
        else:
            # 2. Token overlap (Jaccard)
            intersection = tokens.intersection(item_tokens)
            score = len(intersection) / max(len(tokens), len(item_tokens), 1)

            # 3. Synonym check
            for syn_group in synonyms.values():
                has_ingredient = any(s in raw_clean for s in syn_group)
                has_catalog = any(s in item_clean for s in syn_group)
                if has_ingredient and has_catalog:
                    score += 0.75
                    break

        if score > highest_score and score >= 0.3:
            highest_score = score
            best_match = {
                "matched_item_id": item_id,
                "matched_item_name": item_name,
                "base_unit": str(item.get("unit") or item.get("base_unit") or "KILO").upper(),
                "unit_cost": Decimal(str(item.get("cost") or item.get("avg_cost") or item.get("last_cost") or 0)),
                "confidence_score": round(score, 2),
            }

    return best_match


def parse_recipe_text(raw_text: str) -> dict[str, Any]:
    """Parses unstructured text into a structured recipe with title, ingredients and preparation steps."""
    lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]
    if not lines:
        return {"title": "Nueva Receta", "ingredients": [], "steps": [], "servings": 1}

    # Extract title from first line or introductory sentence
    first_line = lines[0]
    title = first_line
    title_match = re.search(r"prepara un[a]?\s+delicioso[a]?\s+([^,\.]+)", first_line, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip().title()
    elif len(first_line) > 60:
        title = first_line[:60].strip()

    ingredients: list[dict[str, Any]] = []
    steps: list[str] = []
    current_section = "intro"

    # Regex for matching quantity and units at the beginning of an ingredient line
    qty_unit_regex = re.compile(
        r"^(?:[-*•]\s*)?((?:\d+(?:\s+\d+/\d+|\.\d+|/\d+)?)|(?:1/2|1/4|3/4|1/3|2/3|1/8|½|¼|¾|⅓|⅔))\s*(?:de\s+)?(g|gr|gramos|kg|kilo|kilos|ml|l|lt|lts|litro|litros|taza|tazas|cup|cups|cda|cdas|cucharada|cucharadas|tbsp|cdta|cdtas|cucharadita|cucharaditas|tsp|pza|pieza|piezas|pan|rebanada|rebanadas|diente|dientes|pizca|gotas)?\s*(?:de\s+)?(.*)$",
        re.IGNORECASE,
    )

    for line in lines:
        lower_line = line.lower()
        if "ingrediente" in lower_line:
            current_section = "ingredients"
            continue
        elif "preparaci" in lower_line or "instrucci" in lower_line or "pasos" in lower_line:
            current_section = "steps"
            continue

        if current_section == "ingredients" or (current_section == "intro" and qty_unit_regex.match(line)):
            m = qty_unit_regex.match(line)
            if m:
                raw_qty = m.group(1).strip()
                raw_unit = (m.group(2) or "pieza").strip().lower()
                name = m.group(3).strip()
                # Clean trailing periods or notes
                name = re.sub(r"[\.]$", "", name).strip()
                qty_dec = parse_fraction(raw_qty)
                ingredients.append({
                    "raw_name": name,
                    "quantity": qty_dec,
                    "unit": raw_unit,
                    "original_line": line,
                })
            elif len(line) < 100 and not line.endswith(":"):
                # Possible unquantified ingredient (e.g. "Cilantro fresco picado al gusto")
                ingredients.append({
                    "raw_name": line.strip(" -*•."),
                    "quantity": Decimal("1"),
                    "unit": "al gusto",
                    "original_line": line,
                })

        elif current_section == "steps":
            steps.append(line)

    return {
        "title": title,
        "ingredients": ingredients,
        "steps": steps,
        "servings": 1,
    }


def calculate_theoretical_recipe_cost(
    ingredients: list[dict[str, Any]],
    yield_portions: Decimal = Decimal("1"),
    sale_price: Decimal = Decimal("0"),
) -> dict[str, Any]:
    """Calculates total theoretical cost, unit cost per portion and Food Cost percentage."""
    if yield_portions <= 0:
        yield_portions = Decimal("1")

    total_cost = Decimal("0.00")
    analyzed_ingredients = []

    for ing in ingredients:
        qty_base = Decimal(str(ing.get("normalized_quantity") or ing.get("quantity") or 0))
        unit_cost = Decimal(str(ing.get("unit_cost") or 0))
        item_cost = (qty_base * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_cost += item_cost

        analyzed_ingredients.append({
            **ing,
            "item_cost": item_cost,
            "line_cost": item_cost,
        })

    cost_per_portion = (total_cost / yield_portions).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    food_cost_pct = Decimal("0.00")
    if sale_price > 0:
        food_cost_pct = ((cost_per_portion / sale_price) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    # Food Cost Status Guidelines:
    # < 35%: Optimal (Green)
    # 35% - 50%: Warning (Yellow)
    # > 50%: Alert / Compressed margin (Red)
    if food_cost_pct == 0:
        status = "unpriced"
    elif food_cost_pct <= 35:
        status = "optimal"
    elif food_cost_pct <= 50:
        status = "warning"
    else:
        status = "alert"

    # Suggested retail price for target 32% food cost
    suggested_price = (cost_per_portion / Decimal("0.32")).quantize(Decimal("1.00"), rounding=ROUND_HALF_UP)

    return {
        "total_cost": total_cost,
        "cost_per_portion": cost_per_portion,
        "yield_portions": yield_portions,
        "sale_price": sale_price,
        "food_cost_percentage": food_cost_pct,
        "food_cost_status": status,
        "suggested_price_32pct": suggested_price,
        "ingredients": analyzed_ingredients,
    }
