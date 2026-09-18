"""TDD suite for Conversational Product & Recipe Onboarding AI Engine.

Covers:
- Given-When-Then extraction and slot filling from natural language.
- Deterministic waste rate and theoretical cost calculation (strictly Decimal).
- Catalog reconciliation (existing supplies vs new supplies).
- Subrecipe detection and guided interview generation.
- Multi-turn conversation progression until review readiness.
- Transactional and idempotent persistence in canonical sequence.
"""

# ruff: noqa: E501, E402, I001, F401
from decimal import Decimal
from typing import Any
import pytest

from restaurant_os.product_onboarding_ai import (
    OnboardingIngredient,
    OnboardingSessionState,
    calculate_deterministic_component_cost,
    calculate_deterministic_onboarding_summary,
    reconcile_ingredients_with_catalog,
    detect_subrecipe_intent,
    process_onboarding_turn,
)


def test_calculate_deterministic_component_cost():
    """Given a component with net quantity and waste rate,
    When calculating gross quantity and line cost,
    Then Python computes exact Decimal values using gross = net / (1 - waste).
    """
    # 200g net of meat at $140/kg with 10% cooking shrinkage
    net_qty = Decimal("0.200")
    waste_rate = Decimal("0.10")
    unit_cost = Decimal("140.00")

    result = calculate_deterministic_component_cost(
        net_quantity=net_qty,
        waste_rate=waste_rate,
        unit_cost=unit_cost,
    )

    # 0.200 / 0.90 = 0.222222...
    expected_gross = (net_qty / (Decimal("1") - waste_rate)).quantize(Decimal("0.000001"))
    assert result["gross_quantity"] == expected_gross
    # 0.222222 * 140 = 31.11108 -> rounded to cents $31.11
    assert result["line_cost_cents"] == 3111
    assert result["line_cost"] == Decimal("31.11")

    # Edge case: 0% waste
    no_waste = calculate_deterministic_component_cost(
        net_quantity=Decimal("1.000"),
        waste_rate=Decimal("0.00"),
        unit_cost=Decimal("3.90"),
    )
    assert no_waste["gross_quantity"] == Decimal("1.000000")
    assert no_waste["line_cost_cents"] == 390


def test_calculate_deterministic_component_cost_invalid_waste():
    """Given an invalid waste rate >= 1.0 or < 0.0,
    When calculating cost,
    Then it raises a ValueError.
    """
    with pytest.raises(ValueError, match="Waste rate must be between 0 and 0.999999"):
        calculate_deterministic_component_cost(
            net_quantity=Decimal("1"),
            waste_rate=Decimal("1.0"),
            unit_cost=Decimal("100"),
        )


def test_calculate_deterministic_onboarding_summary():
    """Given a list of priced ingredients and a sale price,
    When computing the summary,
    Then theoretical cost, food cost % and gross margin % are computed deterministically.
    """
    ingredients = [
        OnboardingIngredient(
            raw_name="Carne Sirloin",
            normalized_name="CARNE MOLIDA SIRLOIN",
            net_quantity=Decimal("0.200"),
            unit="kg",
            waste_rate=Decimal("0.10"),
            unit_cost=Decimal("140.00"),
            line_cost_cents=3111,
        ),
        OnboardingIngredient(
            raw_name="Pan Brioche",
            normalized_name="PAN BRIOCHE ARTESANAL",
            net_quantity=Decimal("1.000"),
            unit="pza",
            waste_rate=Decimal("0.00"),
            unit_cost=Decimal("3.90"),
            line_cost_cents=390,
        ),
        OnboardingIngredient(
            raw_name="Queso Cheddar",
            normalized_name="QUESO CHEDDAR AMERICANO",
            net_quantity=Decimal("0.040"),
            unit="kg",
            waste_rate=Decimal("0.00"),
            unit_cost=Decimal("180.00"),
            line_cost_cents=720,
        ),
    ]

    sale_price_cents = 14900  # $149.00 MXN

    summary = calculate_deterministic_onboarding_summary(
        ingredients=ingredients,
        sale_price_cents=sale_price_cents,
    )

    # 3111 + 390 + 720 = 4221 cents ($42.21 MXN)
    assert summary["theoretical_cost_cents"] == 4221
    assert summary["theoretical_cost"] == Decimal("42.21")
    # Food cost = 42.21 / 149.00 * 100 = 28.33%
    assert summary["food_cost_percentage"] == Decimal("28.33")
    # Gross margin = 100 - 28.33 = 71.67%
    assert summary["gross_margin_percentage"] == Decimal("71.67")


def test_reconcile_ingredients_with_catalog():
    """Given catalog supplies and extracted recipe ingredients,
    When reconciling,
    Then existing supplies match with their IDs and unit costs,
    while new supplies are marked as needing supplier/presentation details.
    """
    catalog = [
        {"id": "item-carne", "name": "CARNE MOLIDA SIRLOIN", "unit": "KILO", "cost": Decimal("140.00")},
        {"id": "item-pan", "name": "PAN BRIOCHE", "unit": "PIEZA", "cost": Decimal("3.90")},
    ]

    raw_items = [
        {"name": "carne de sirloin molida", "quantity": Decimal("0.200"), "unit": "kg", "waste_rate": Decimal("0.10")},
        {"name": "pan brioche", "quantity": Decimal("1"), "unit": "pza", "waste_rate": Decimal("0")},
        {"name": "tocino ahumado artesanal", "quantity": Decimal("0.040"), "unit": "kg", "waste_rate": Decimal("0.15")},
    ]

    reconciled = reconcile_ingredients_with_catalog(raw_items, catalog)

    assert len(reconciled) == 3
    # Carne matches
    assert reconciled[0].matched_item_id == "item-carne"
    assert reconciled[0].is_new_supply is False
    assert reconciled[0].unit_cost == Decimal("140.00")

    # Pan matches
    assert reconciled[1].matched_item_id == "item-pan"
    assert reconciled[1].is_new_supply is False

    # Tocino is new supply
    assert reconciled[2].matched_item_id is None
    assert reconciled[2].is_new_supply is True
    assert reconciled[2].unit_cost == Decimal("0.00")


def test_detect_subrecipe_intent():
    """Given culinary terms,
    When detecting subrecipe intent,
    Then words like aderezo, salsa, masa, vinagreta, mezcla return True.
    """
    assert detect_subrecipe_intent("Aderezo chipotle de la casa") is True
    assert detect_subrecipe_intent("Salsa marinara casera") is True
    assert detect_subrecipe_intent("Masa para pizza fermentada") is True
    assert detect_subrecipe_intent("Carne molida") is False
    assert detect_subrecipe_intent("Queso manchego") is False


def test_process_onboarding_turn_initial_product():
    """Given an empty onboarding state and an initial product message,
    When processing the turn,
    Then product name, category, station and initial ingredients are extracted,
    and the assistant formulates the next logical question.
    """
    state = OnboardingSessionState(session_id="test-session-1")
    catalog = [
        {"id": "item-carne", "name": "CARNE MOLIDA SIRLOIN", "unit": "KILO", "cost": Decimal("140.00")},
        {"id": "item-pan", "name": "PAN BRIOCHE", "unit": "PIEZA", "cost": Decimal("3.90")},
    ]

    user_msg = "Quiero agregar una Hamburguesa Especial con 200g de carne sirloin y 1 pan brioche"

    next_state = process_onboarding_turn(state, user_msg, catalog)

    assert next_state.product_name == "HAMBURGUESA ESPECIAL"
    assert next_state.station == "kitchen"
    assert len(next_state.ingredients) >= 2
    # Price is not provided yet, so it should be in missing fields
    assert "price" in next_state.missing_fields
    assert next_state.is_ready_for_review is False
    assert "precio" in next_state.next_question.lower()


def test_process_onboarding_turn_fills_missing_and_ready():
    """Given a state missing only price,
    When user responds with the price,
    Then the state becomes ready for review with complete summary.
    """
    state = OnboardingSessionState(
        session_id="test-session-2",
        product_name="HAMBURGUESA ESPECIAL",
        category_name="HAMBURGUESAS",
        station="kitchen",
        ingredients=[
            OnboardingIngredient(
                raw_name="Carne Sirloin",
                normalized_name="CARNE MOLIDA SIRLOIN",
                net_quantity=Decimal("0.200"),
                unit="kg",
                waste_rate=Decimal("0.10"),
                matched_item_id="item-carne",
                unit_cost=Decimal("140.00"),
                line_cost_cents=3111,
            ),
            OnboardingIngredient(
                raw_name="Pan Brioche",
                normalized_name="PAN BRIOCHE ARTESANAL",
                net_quantity=Decimal("1.000"),
                unit="pza",
                waste_rate=Decimal("0.00"),
                matched_item_id="item-pan",
                unit_cost=Decimal("3.90"),
                line_cost_cents=390,
            ),
        ],
        missing_fields=["price"],
        next_question="¿Cuál es el precio de venta al público?",
    )

    catalog = []
    user_msg = "El precio será de 149 pesos"

    next_state = process_onboarding_turn(state, user_msg, catalog)

    assert next_state.price_cents == 14900
    assert "price" not in next_state.missing_fields
    assert next_state.is_ready_for_review is True
    assert next_state.summary is not None
    assert next_state.summary["theoretical_cost_cents"] == 3501


import uuid
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import ORGANIZATION_ID
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

app = create_app()
USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()

    now = datetime.now(timezone.utc)
    session.execute(
        models.organizations.insert().values(
            id=ORGANIZATION_ID,
            name="Kiwi Corporativo",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    legal_id = str(uuid.uuid4())
    session.execute(
        models.legal_entities.insert().values(
            id=legal_id,
            organization_id=ORGANIZATION_ID,
            name="Kiwi SA de CV",
            created_at=now,
            updated_at=now,
        )
    )
    bu_id = str(uuid.uuid4())
    session.execute(
        models.business_units.insert().values(
            id=bu_id,
            organization_id=ORGANIZATION_ID,
            legal_entity_id=legal_id,
            name="Kiwi Natural",
            code="KN",
            unit_type="restaurant",
            created_at=now,
            updated_at=now,
        )
    )
    branch_id = str(uuid.uuid4())
    session.execute(
        models.branches.insert().values(
            id=branch_id,
            organization_id=ORGANIZATION_ID,
            legal_entity_id=legal_id,
            business_unit_id=bu_id,
            name="Sucursal Centro",
            code="CENTRO",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    unit_kg = str(uuid.uuid4())
    session.execute(
        models.inventory_units.insert().values(
            id=unit_kg,
            organization_id=ORGANIZATION_ID,
            code="KILO",
            name="Kilogramo",
            created_at=now,
        )
    )
    unit_pza = str(uuid.uuid4())
    session.execute(
        models.inventory_units.insert().values(
            id=unit_pza,
            organization_id=ORGANIZATION_ID,
            code="PIEZA",
            name="Pieza",
            created_at=now,
        )
    )
    item_carne_id = str(uuid.uuid4())
    session.execute(
        models.inventory_items.insert().values(
            id=item_carne_id,
            organization_id=ORGANIZATION_ID,
            sku="01010",
            name="CARNE DE RES",
            base_unit_id=unit_kg,
            item_type="ingredient",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    item_pan_id = str(uuid.uuid4())
    session.execute(
        models.inventory_items.insert().values(
            id=item_pan_id,
            organization_id=ORGANIZATION_ID,
            sku="01011",
            name="PAN BRIOCHE",
            base_unit_id=unit_pza,
            item_type="ingredient",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    supplier_id = str(uuid.uuid4())
    session.execute(
        models.suppliers.insert().values(
            id=supplier_id,
            organization_id=ORGANIZATION_ID,
            code="SUP-01",
            commercial_name="Carnes del Norte",
            tax_id="CDN900101AA1",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.purchase_presentations.insert().values(
            id=str(uuid.uuid4()),
            organization_id=ORGANIZATION_ID,
            item_id=item_carne_id,
            supplier_id=supplier_id,
            code="PRES-CARNE-10KG",
            name="Caja 10 kg",
            package_type="caja",
            commercial_quantity=Decimal("1.0"),
            base_unit_id=unit_kg,
            base_unit_yield=Decimal("10.0"),
            usable_content=Decimal("10.0"),
            yield_percent=Decimal("1.0"),
            commercial_unit_id=unit_kg,
            cost_per_base_unit=Decimal("130.00"),
            last_net_price=Decimal("1300.00"),
            tax_rate=Decimal("0.00"),
            is_preferred=True,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.purchase_presentations.insert().values(
            id=str(uuid.uuid4()),
            organization_id=ORGANIZATION_ID,
            item_id=item_pan_id,
            supplier_id=supplier_id,
            code="PRES-PAN-30PZ",
            name="Charola 30 pzas",
            package_type="charola",
            commercial_quantity=Decimal("1.0"),
            base_unit_id=unit_pza,
            base_unit_yield=Decimal("30.0"),
            usable_content=Decimal("30.0"),
            yield_percent=Decimal("1.0"),
            commercial_unit_id=unit_pza,
            cost_per_base_unit=Decimal("4.00"),
            last_net_price=Decimal("120.00"),
            tax_rate=Decimal("0.00"),
            is_preferred=True,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.users.insert().values(
            id=USER_ID,
            organization_id=ORGANIZATION_ID,
            email="admin@kiwi.com",
            display_name="Admin User",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.roles.insert().values(
            id=ROLE_ID,
            organization_id=ORGANIZATION_ID,
            name="Administrador",
            scope="organization",
            created_at=now,
        )
    )
    session.execute(models.user_roles.insert().values(user_id=USER_ID, role_id=ROLE_ID))
    for perm in ["catalog.manage", "recipes.manage", "inventory.manage", "purchases.manage"]:
        perm_id = str(uuid.uuid4())
        session.execute(
            models.permissions.insert().values(
                id=perm_id, code=perm, description=perm, created_at=now
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=ROLE_ID, permission_id=perm_id)
        )

    session.commit()
    yield session
    session.close()


@pytest.fixture
def client(test_db):
    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers():
    token = create_session_token(
        {"sub": USER_ID, "org_id": ORGANIZATION_ID, "role": "admin"},
        get_settings().secret_key,
    )
    return {"Authorization": f"Bearer {token}"}


def test_api_onboarding_ai_message_and_confirm(client, auth_headers):
    """Given an authenticated user,
    When calling /catalog/onboarding-ai/message and /catalog/onboarding-ai/confirm,
    Then the product and its recipe are created canonically in the database.
    """
    # Turn 1: Initial message
    resp1 = client.post(
        "/api/v1/catalog/onboarding-ai/message",
        json={"message": "Quiero dar de alta una Hamburguesa Clasica con 150g de carne de res y 1 pan brioche"},
        headers=auth_headers,
    )
    assert resp1.status_code == 200
    state1 = resp1.json()
    assert state1["product_name"] == "HAMBURGUESA CLASICA"
    assert state1["station"] == "kitchen"
    assert len(state1["ingredients"]) >= 2
    assert "price" in state1["missing_fields"]

    # Turn 2: Give price
    resp2 = client.post(
        "/api/v1/catalog/onboarding-ai/message",
        json={"message": "El precio de venta será de 125 pesos", "state": state1},
        headers=auth_headers,
    )
    assert resp2.status_code == 200
    state2 = resp2.json()
    assert state2["price_cents"] == 12500
    assert state2["is_ready_for_review"] is True
    assert state2["summary"] is not None

    # Turn 3: Confirm creation with Idempotency-Key
    idempotency_key = f"idemp-onboard-{uuid.uuid4()}"
    resp3 = client.post(
        "/api/v1/catalog/onboarding-ai/confirm",
        json={"session_id": state2["session_id"], "state": state2},
        headers={**auth_headers, "Idempotency-Key": idempotency_key},
    )
    assert resp3.status_code == 200
    res = resp3.json()
    assert res["status"] == "created"
    assert res["product"]["name"] == "HAMBURGUESA CLASICA"
    assert res["product"]["price_cents"] == 12500
    assert res["recipe"]["product_id"] == res["product"]["id"]
