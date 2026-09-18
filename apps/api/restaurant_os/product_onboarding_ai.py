"""Conversational Product & Recipe Onboarding AI Engine.

Provides:
- Multi-turn conversational state machine (Slot-Filling Wizard).
- Pure deterministic Python calculations for mermas, conversions, gross quantities and food cost.
- Reconciles inputs against the live inventory catalog.
- Canonical transactional persistence for products, recipes, presentations, and supplies.
"""

from __future__ import annotations

# ruff: noqa: E501, I001
import re
from dataclasses import asdict, dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    create_inventory_item,
    create_product,
    update_product_recipe_versioned,
    _id,
)
from restaurant_os.recipe_ai import (
    match_ingredient_to_catalog,
    parse_recipe_text,
)

SUBRECIPE_KEYWORDS = {
    "aderezo",
    "salsa",
    "masa",
    "vinagreta",
    "mezcla",
    "marinada",
    "relleno",
    "glaseado",
    "fondo",
    "caldo",
    "crema",
}

STATION_KEYWORDS = {
    "drinks": ["bebida", "agua", "refresco", "cerveza", "coctel", "jugo", "cafe", "te", "malteada"],
    "packing": ["empaque", "combo", "paquete", "caja"],
}


@dataclass
class OnboardingIngredient:
    raw_name: str
    normalized_name: str
    net_quantity: Decimal
    unit: str
    waste_rate: Decimal = Decimal("0.00")
    gross_quantity: Decimal = Decimal("0.000000")
    matched_item_id: str | None = None
    unit_cost: Decimal = Decimal("0.00")
    line_cost_cents: int = 0
    line_cost: Decimal = Decimal("0.00")
    is_new_supply: bool = False
    is_subrecipe: bool = False
    subrecipe_yield: Decimal | None = None
    supplier_name: str | None = None
    presentation_name: str | None = None
    package_yield: Decimal | None = None
    package_price_cents: int | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["net_quantity"] = str(self.net_quantity)
        d["waste_rate"] = str(self.waste_rate)
        d["gross_quantity"] = str(self.gross_quantity)
        d["unit_cost"] = str(self.unit_cost)
        d["line_cost"] = str(self.line_cost)
        if self.subrecipe_yield is not None:
            d["subrecipe_yield"] = str(self.subrecipe_yield)
        if self.package_yield is not None:
            d["package_yield"] = str(self.package_yield)
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OnboardingIngredient:
        return cls(
            raw_name=str(data.get("raw_name") or ""),
            normalized_name=str(data.get("normalized_name") or ""),
            net_quantity=Decimal(str(data.get("net_quantity") or "1")),
            unit=str(data.get("unit") or "pza"),
            waste_rate=Decimal(str(data.get("waste_rate") or "0")),
            gross_quantity=Decimal(str(data.get("gross_quantity") or "0")),
            matched_item_id=data.get("matched_item_id"),
            unit_cost=Decimal(str(data.get("unit_cost") or "0")),
            line_cost_cents=int(data.get("line_cost_cents") or 0),
            line_cost=Decimal(str(data.get("line_cost") or "0")),
            is_new_supply=bool(data.get("is_new_supply", False)),
            is_subrecipe=bool(data.get("is_subrecipe", False)),
            subrecipe_yield=Decimal(str(data["subrecipe_yield"])) if data.get("subrecipe_yield") is not None else None,
            supplier_name=data.get("supplier_name"),
            presentation_name=data.get("presentation_name"),
            package_yield=Decimal(str(data["package_yield"])) if data.get("package_yield") is not None else None,
            package_price_cents=int(data["package_price_cents"]) if data.get("package_price_cents") is not None else None,
        )


@dataclass
class OnboardingSessionState:
    session_id: str
    product_name: str | None = None
    category_name: str | None = None
    station: str = "kitchen"
    price_cents: int | None = None
    ingredients: list[OnboardingIngredient] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    next_question: str = ""
    is_ready_for_review: bool = False
    summary: dict[str, Any] | None = None
    conversation_history: list[dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "product_name": self.product_name,
            "category_name": self.category_name,
            "station": self.station,
            "price_cents": self.price_cents,
            "ingredients": [i.to_dict() for i in self.ingredients],
            "missing_fields": self.missing_fields,
            "next_question": self.next_question,
            "is_ready_for_review": self.is_ready_for_review,
            "summary": self.summary,
            "conversation_history": self.conversation_history,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> OnboardingSessionState:
        return cls(
            session_id=str(data.get("session_id") or uuid4()),
            product_name=data.get("product_name"),
            category_name=data.get("category_name"),
            station=str(data.get("station") or "kitchen"),
            price_cents=int(data["price_cents"]) if data.get("price_cents") is not None else None,
            ingredients=[OnboardingIngredient.from_dict(i) for i in (data.get("ingredients") or [])],
            missing_fields=list(data.get("missing_fields") or []),
            next_question=str(data.get("next_question") or ""),
            is_ready_for_review=bool(data.get("is_ready_for_review", False)),
            summary=data.get("summary"),
            conversation_history=list(data.get("conversation_history") or []),
        )


def calculate_deterministic_component_cost(
    net_quantity: Decimal,
    waste_rate: Decimal,
    unit_cost: Decimal,
) -> dict[str, Any]:
    """Calculate gross quantity and line cost using strictly Decimal arithmetic."""
    if waste_rate < Decimal("0") or waste_rate >= Decimal("1"):
        raise ValueError("Waste rate must be between 0 and 0.999999")

    # gross = net / (1 - waste_rate)
    gross = (net_quantity / (Decimal("1") - waste_rate)).quantize(
        Decimal("0.000001"), rounding=ROUND_HALF_UP
    )
    line_cost = (gross * unit_cost).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    line_cost_cents = int((line_cost * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))

    return {
        "gross_quantity": gross,
        "line_cost": line_cost,
        "line_cost_cents": line_cost_cents,
    }


def calculate_deterministic_onboarding_summary(
    ingredients: list[OnboardingIngredient],
    sale_price_cents: int | None,
) -> dict[str, Any]:
    """Calculate total theoretical cost, food cost % and gross margin %."""
    total_cents = sum(ing.line_cost_cents for ing in ingredients)
    total_cost = (Decimal(total_cents) / Decimal("100")).quantize(Decimal("0.01"))

    food_cost_pct: Decimal | None = None
    gross_margin_pct: Decimal | None = None

    if sale_price_cents and sale_price_cents > 0:
        sale_price = (Decimal(sale_price_cents) / Decimal("100")).quantize(Decimal("0.01"))
        food_cost_pct = ((total_cost / sale_price) * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        gross_margin_pct = (Decimal("100") - food_cost_pct).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

    return {
        "theoretical_cost_cents": total_cents,
        "theoretical_cost": total_cost,
        "food_cost_percentage": food_cost_pct,
        "gross_margin_percentage": gross_margin_pct,
    }


def detect_subrecipe_intent(name: str) -> bool:
    """Detect if a culinary ingredient is likely a prepared subrecipe."""
    norm = name.strip().lower()
    return any(kw in norm for kw in SUBRECIPE_KEYWORDS)


def reconcile_ingredients_with_catalog(
    raw_ingredients: list[dict[str, Any]],
    catalog_supplies: list[dict[str, Any]],
) -> list[OnboardingIngredient]:
    """Reconcile extracted ingredients against active catalog supplies."""
    result: list[OnboardingIngredient] = []

    for item in raw_ingredients:
        raw_name = str(item.get("name") or item.get("raw_name") or "")
        qty = Decimal(str(item.get("quantity") or item.get("net_quantity") or "1.0"))
        unit = str(item.get("unit") or "pza").lower()
        waste = Decimal(str(item.get("waste_rate") or "0.00"))

        match = match_ingredient_to_catalog(raw_name, catalog_supplies)
        is_sub = detect_subrecipe_intent(raw_name)

        if match:
            matched_id = match["matched_item_id"]
            matched_name = match["matched_item_name"]
            unit_cost = Decimal(str(match.get("unit_cost") or match.get("cost") or "0.00"))
            is_new = False
        else:
            matched_id = None
            matched_name = raw_name.strip().upper()
            unit_cost = Decimal("0.00")
            is_new = True

        costs = calculate_deterministic_component_cost(qty, waste, unit_cost)

        result.append(
            OnboardingIngredient(
                raw_name=raw_name,
                normalized_name=matched_name,
                net_quantity=qty,
                unit=unit,
                waste_rate=waste,
                gross_quantity=costs["gross_quantity"],
                matched_item_id=matched_id,
                unit_cost=unit_cost,
                line_cost_cents=costs["line_cost_cents"],
                line_cost=costs["line_cost"],
                is_new_supply=is_new,
                is_subrecipe=is_sub,
            )
        )

    return result


def _extract_price_cents_from_text(text: str) -> int | None:
    """Extract monetary sale price in cents from user message."""
    match = re.search(
        r"(?:\$|precio(?:\s+de)?|costar[aá]|en)\s*(\d+(?:\.\d{1,2})?)\s*(?:pesos|mxn|\$)?",
        text,
        re.IGNORECASE,
    )
    if match:
        amount = Decimal(match.group(1))
        return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))

    # Just bare number e.g. "149" or "$149.00"
    match_bare = re.search(r"\$?\s*(\d+(?:\.\d{1,2})?)\s*(?:pesos|mxn)", text, re.IGNORECASE)
    if match_bare:
        amount = Decimal(match_bare.group(1))
        return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))

    digits_only = re.match(r"^\s*\$?\s*(\d+(?:\.\d{1,2})?)\s*\$?$", text.strip())
    if digits_only:
        amount = Decimal(digits_only.group(1))
        return int((amount * Decimal("100")).to_integral_value(rounding=ROUND_HALF_UP))

    return None


def _infer_station(name: str) -> str:
    """Infer preparation station: kitchen, drinks, or packing."""
    norm = name.lower()
    for station, keywords in STATION_KEYWORDS.items():
        if any(kw in norm for kw in keywords):
            return station
    return "kitchen"


def _infer_category(name: str) -> str:
    """Infer sale category name from product title."""
    norm = name.lower()
    if "hamburguesa" in norm:
        return "HAMBURGUESAS"
    if any(k in norm for k in ["pizza", "calzone"]):
        return "PIZZAS"
    if any(k in norm for k in ["taco", "gringa", "quesadilla"]):
        return "TACOS"
    if any(k in norm for k in ["baguette", "panini", "sandwich", "torta"]):
        return "BAGUETTES"
    if any(k in norm for k in ["agua", "refresco", "bebida", "jugo"]):
        return "BEBIDAS"
    if any(k in norm for k in ["cafe", "te", "capuchino"]):
        return "CAFETERIA"
    if any(k in norm for k in ["alitas", "boneless", "papas", "aros", "snack"]):
        return "SNACKS"
    if any(k in norm for k in ["postre", "pastel", "pay", "flan", "nieve"]):
        return "POSTRES"
    return "PLATILLOS"


def extract_conversational_ingredients(text: str) -> list[dict[str, Any]]:
    """Extract ingredients and amounts from conversational phrases (e.g. 'con 200g de carne sirloin y 1 pan brioche')."""
    # If the user is just stating the price, do not extract ingredients
    if re.search(r"^\s*(?:el\s+)?precio\s+(?:es|ser[aá]|de)?\s*\$?\d+", text, re.IGNORECASE):
        return []
    if re.search(r"^\s*\$?\d+(?:\.\d{1,2})?\s*(?:pesos|mxn)?\s*$", text.strip(), re.IGNORECASE):
        return []

    # 1. Try parse_recipe_text if structured with line breaks
    parsed = parse_recipe_text(text)
    if parsed.get("ingredients") and len(parsed["ingredients"]) >= 2:
        return parsed["ingredients"]

    # 2. Extract from inline phrases
    # Look for the section after 'con', 'lleva', 'ingredientes:'
    match_section = re.search(r"(?:con|lleva|ingredientes(?:\s*:)?)[\s:]+(.*)", text, re.IGNORECASE)
    phrase = match_section.group(1) if match_section else text

    # Split by conjunctions: commas, ' y ', ' e ', ' + '
    parts = re.split(r"[,;]|\s+(?:y|e|\+)\s+", phrase, flags=re.IGNORECASE)
    ingredients: list[dict[str, Any]] = []

    item_pattern = re.compile(
        r"(\d+(?:\.\d+)?)\s*(g|gr|gramos|kg|kilo|kilos|ml|l|lt|lts|litro|litros|taza|tazas|cda|cdas|cucharada|cucharadas|pza|pieza|piezas|rebanada|rebanadas|pan)?\s*(?:de\s+)?([A-Za-z0-9áéíóúÁÉÍÓÚñÑ\s]+)",
        re.IGNORECASE,
    )

    NON_INGREDIENT_WORDS = {"pesos", "peso", "mxn", "dolares", "centavos", "minutos", "horas"}

    for part in parts:
        clean_part = part.strip()
        if not clean_part:
            continue
        m = item_pattern.search(clean_part)
        if m:
            raw_qty = Decimal(m.group(1))
            raw_unit = (m.group(2) or "").lower()
            name = m.group(3).strip()

            # Clean name from words like 'precio', 'costo'
            name = re.sub(r"\s+(?:precio|en|por|para).*$", "", name, flags=re.IGNORECASE).strip()
            if not name or name.lower() in NON_INGREDIENT_WORDS or raw_unit in NON_INGREDIENT_WORDS:
                continue

            unit = raw_unit or "pza"

            # Normalize grams to kg or ml to l for standard base units
            if unit in ["g", "gr", "gramos"]:
                normalized_qty = (raw_qty / Decimal("1000")).quantize(Decimal("0.001"))
                std_unit = "kg"
            elif unit in ["ml", "mililitros"]:
                normalized_qty = (raw_qty / Decimal("1000")).quantize(Decimal("0.001"))
                std_unit = "l"
            elif unit in ["pan", "rebanada", "rebanadas", "pieza", "piezas", "pza"]:
                normalized_qty = raw_qty
                std_unit = "pza"
                if unit == "pan" and "pan" not in name.lower():
                    name = f"pan {name}"
            else:
                normalized_qty = raw_qty
                std_unit = unit

            ingredients.append({
                "raw_name": name,
                "name": name,
                "quantity": normalized_qty,
                "unit": std_unit,
                "waste_rate": Decimal("0.10") if any(w in name.lower() for w in ["carne", "sirloin", "pollo", "pescado", "res"]) else Decimal("0.00"),
            })

    return ingredients


def process_onboarding_turn(
    state: OnboardingSessionState,
    user_message: str,
    catalog_supplies: list[dict[str, Any]],
) -> OnboardingSessionState:
    """Process a single conversational turn in the product onboarding wizard."""
    msg = user_message.strip()
    state.conversation_history.append({"role": "user", "content": msg})

    # 1. Price extraction if missing or explicitly mentioned
    extracted_price = _extract_price_cents_from_text(msg)
    if extracted_price is not None:
        state.price_cents = extracted_price

    # 2. Product Name / Initialization if not set
    if not state.product_name:
        # Match pattern "agregar una Hamburguesa Especial" or "dar de alta X"
        name_match = re.search(
            r"(?:agregar|alta|crear|nuevo producto|un[a]?)\s+(?:de\s+)?([A-Za-z0-9áéíóúÁÉÍÓÚñÑ\s]+?)(?:con|precio|por|en|$)",
            msg,
            re.IGNORECASE,
        )
        if name_match:
            candidate = name_match.group(1).strip()
            # Clean up common filler words
            candidate = re.sub(
                r"^(?:una|un|el|la)\s+", "", candidate, flags=re.IGNORECASE
            ).strip()
            if candidate:
                state.product_name = candidate.upper()
        else:
            # Fallback: first 4 words of the message
            words = msg.split()[:4]
            state.product_name = " ".join(words).upper()

        if state.product_name:
            state.category_name = _infer_category(state.product_name)
            state.station = _infer_station(state.product_name)

    # 3. Ingredients extraction if message mentions ingredients
    raw_ings = extract_conversational_ingredients(msg)
    if raw_ings:
        new_reconciled = reconcile_ingredients_with_catalog(
            raw_ings, catalog_supplies
        )
        # Merge with existing ingredients (avoid duplicates by raw_name)
        existing_names = {i.raw_name.lower() for i in state.ingredients}
        for ing in new_reconciled:
            if ing.raw_name.lower() not in existing_names:
                state.ingredients.append(ing)
                existing_names.add(ing.raw_name.lower())

    # 4. Check for answers to supplier/presentation info of new supplies
    for ing in state.ingredients:
        if ing.is_new_supply and (not ing.supplier_name or not ing.presentation_name):
            # Check if user mentioned package / price
            # e.g. "El proveedor es San Juan, caja de 5 kg en 450"
            if ing.raw_name.lower() in msg.lower() or len(state.ingredients) == 1:
                cost_cents = _extract_price_cents_from_text(msg)
                if cost_cents:
                    ing.package_price_cents = cost_cents
                    # Infer base unit cost
                    ing.unit_cost = (
                        Decimal(cost_cents) / Decimal("100")
                    )  # Default assuming 1 unit package
                    costs = calculate_deterministic_component_cost(
                        ing.net_quantity, ing.waste_rate, ing.unit_cost
                    )
                    ing.gross_quantity = costs["gross_quantity"]
                    ing.line_cost_cents = costs["line_cost_cents"]
                    ing.line_cost = costs["line_cost"]

    # 5. Evaluate missing fields
    missing: list[str] = []
    if not state.product_name:
        missing.append("product_name")
    if len(state.ingredients) == 0:
        missing.append("ingredients")
    if state.price_cents is None or state.price_cents <= 0:
        missing.append("price")

    # Check if any new supply needs price/supplier
    unresolved_new = [i for i in state.ingredients if i.is_new_supply and i.unit_cost <= Decimal("0")]
    for u in unresolved_new:
        missing.append(f"new_supply_cost:{u.raw_name}")

    state.missing_fields = missing

    # 6. Recalculate summary deterministically
    state.summary = calculate_deterministic_onboarding_summary(
        state.ingredients, state.price_cents
    )

    # 7. Formulate next question
    if not missing:
        state.is_ready_for_review = True
        cost_str = f"${state.summary['theoretical_cost']} MXN"
        price_str = f"${Decimal(state.price_cents or 0)/Decimal(100):.2f} MXN"
        fc_str = f"{state.summary['food_cost_percentage']}%"
        margin_str = f"{state.summary['gross_margin_percentage']}%"

        state.next_question = (
            f"¡Ficha técnica completa para **{state.product_name}**!\n\n"
            f"- **Costo Teórico de Producción:** {cost_str}\n"
            f"- **Precio de Venta:** {price_str}\n"
            f"- **Food Cost Estimado:** {fc_str}\n"
            f"- **Margen de Ganancia:** {margin_str}\n\n"
            f"He preparado el escandallo con {len(state.ingredients)} ingredientes. "
            f"¿Deseas confirmar el registro en el catálogo?"
        )
    elif "product_name" in missing:
        state.next_question = "¿Qué producto o platillo deseas dar de alta en tu catálogo?"
    elif "ingredients" in missing:
        state.next_question = (
            f"Excelente, vamos a configurar **{state.product_name}**. "
            f"¿Qué ingredientes o componentes principales lleva y en qué cantidades?"
        )
    elif "price" in missing:
        state.next_question = (
            f"He registrado {len(state.ingredients)} ingredientes para {state.product_name}. "
            f"¿A qué precio de venta al público ($ MXN) se va a ofrecer en caja?"
        )
    elif any(m.startswith("new_supply_cost:") for m in missing):
        target_item = unresolved_new[0].raw_name
        state.next_question = (
            f"El insumo **'{target_item}'** es nuevo y no está en tu inventario. "
            f"¿Cómo te lo vende tu proveedor (ej. costal de 25 kg, caja de 10 kg) y qué precio aproximado tiene?"
        )

    state.conversation_history.append({"role": "assistant", "content": state.next_question})
    return state


def execute_canonical_product_onboarding(
    session: Session,
    state: OnboardingSessionState,
    actor_user_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    """Persist the approved onboarding session into the database in strict canonical sequence."""
    if not state.product_name:
        raise ValueError("Product name is required")
    if not state.price_cents or state.price_cents <= 0:
        raise ValueError("Valid sale price is required")
    if not state.ingredients:
        raise ValueError("At least one ingredient is required")

    # 1. Fetch available units
    unit_rows = session.execute(
        sa.select(models.inventory_units.c.id, models.inventory_units.c.code).where(
            models.inventory_units.c.organization_id == ORGANIZATION_ID
        )
    ).all()
    unit_map = {row.code.lower(): row.id for row in unit_rows}
    default_unit_id = unit_rows[0].id if unit_rows else _id()

    # 2. Create any missing inventory items
    for ing in state.ingredients:
        if ing.is_new_supply or not ing.matched_item_id:
            # Map unit
            matched_unit_id = (
                unit_map.get(ing.unit.lower())
                or unit_map.get("kilo" if ing.unit in ["kg", "g"] else "pieza")
                or default_unit_id
            )
            item_sku = f"{len(state.ingredients) + 9000:05d}"
            new_item = create_inventory_item(
                session=session,
                name=ing.normalized_name.upper(),
                sku=item_sku,
                base_unit_id=matched_unit_id,
                item_type="prepared" if ing.is_subrecipe else "ingredient",
                actor_user_id=actor_user_id,
            )
            ing.matched_item_id = new_item["id"]

    # 3. Create Product
    prod_sku = f"{len(state.product_name) * 100 + 1001:05d}"
    cat_name = state.category_name or "PLATILLOS"
    created_product = create_product(
        session=session,
        name=state.product_name.strip().upper(),
        sku=prod_sku,
        category_name=cat_name.strip().upper(),
        station=state.station,
        price_cents=state.price_cents,
        actor_user_id=actor_user_id,
    )

    # 4. Create Sale Recipe
    components = []
    for ing in state.ingredients:
        components.append(
            {
                "item_id": ing.matched_item_id,
                "unit_id": unit_map.get(ing.unit.lower(), default_unit_id),
                "net_quantity": str(ing.net_quantity),
                "waste_rate": str(ing.waste_rate),
            }
        )

    recipe_payload = {
        "yield_quantity": "1.000000",
        "yield_unit_id": default_unit_id,
        "components": components,
    }

    recipe_key = idempotency_key or f"recipe-onboard-{created_product['id']}-{uuid4()}"
    saved_recipe = update_product_recipe_versioned(
        session,
        created_product["id"],
        recipe_payload,
        None,
        None,
        recipe_key,
        actor_user_id,
    )

    return {
        "product": created_product,
        "recipe": saved_recipe,
        "summary": state.summary,
        "status": "created",
    }
