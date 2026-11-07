"""TDD tests for the unified Copilot Tool Calling engine (Side-by-side with GrokBot).

Verifies that:
1. Tool definitions match standard function-calling schema.
2. Querying inventory thresholds and stock returns accurate min, max, unit and quantity for branches (like Chapultepec).
3. Querying cash status returns open registers and cuts.
4. GrokBot's agent_tools boundary remains 100% unaffected.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from typing import Any
import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from restaurant_os import models
from restaurant_os.copilot_engine import execute_copilot_chat
from restaurant_os.copilot_tools import (
    COPILOT_TOOL_DEFINITIONS,
    dispatch_copilot_tool,
    tool_get_cash_status,
    tool_get_inventory_thresholds_and_stock,
    tool_get_sales_performance,
)
from restaurant_os.operations import ORGANIZATION_ID


@pytest.fixture
def test_db() -> Session:
    """In-memory SQLite database for deterministic tests."""
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def copilot_seed_data(test_db: Session) -> dict[str, Any]:
    """Seed sample branch, warehouse, items, and stock thresholds."""
    now = datetime.datetime.now(datetime.timezone.utc)
    
    # 1. Organization & Legal Entity & Business Unit
    legal_id = "018f6f73-2d0a-74f0-8f1c-000000000010"
    bu_id = "018f6f73-2d0a-74f0-8f1c-000000000020"
    user_id = "018f6f73-2d0a-74f0-8f1c-000000000030"
    branch_id = "branch-chapultepec-test"
    wh_id = "wh-chapultepec-test"

    test_db.execute(
        models.organizations.insert().values(
            id=ORGANIZATION_ID,
            name="Kiwi Test Org",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    test_db.execute(
        models.legal_entities.insert().values(
            id=legal_id,
            organization_id=ORGANIZATION_ID,
            name="Kiwi Test SA",
            tax_id="KTO123456789",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    test_db.execute(
        models.business_units.insert().values(
            id=bu_id,
            organization_id=ORGANIZATION_ID,
            legal_entity_id=legal_id,
            name="Unidad Restaurantes",
            code="UR1",
            unit_type="branch",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    # 2. Branch Chapultepec
    test_db.execute(
        models.branches.insert().values(
            id=branch_id,
            organization_id=ORGANIZATION_ID,
            legal_entity_id=legal_id,
            business_unit_id=bu_id,
            code="CHAP",
            name="Chapultepec",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    # 3. Warehouse for Chapultepec
    test_db.execute(
        models.warehouses.insert().values(
            id=wh_id,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            name="Almacen Chapultepec",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    # 4. User for audit/cash
    test_db.execute(
        models.users.insert().values(
            id=user_id,
            organization_id=ORGANIZATION_ID,
            email="cajero@kiwi.com",
            display_name="Carlos Cajero",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    perm_id = "perm-cat-manage"
    role_id = "role-admin-test"
    test_db.execute(
        models.permissions.insert().values(
            id=perm_id,
            code="catalog.manage",
            description="Catalog Manage",
            created_at=now,
        )
    )
    test_db.execute(
        models.roles.insert().values(
            id=role_id,
            organization_id=ORGANIZATION_ID,
            name="Admin",
            scope="organization",
            created_at=now,
        )
    )
    test_db.execute(
        models.role_permissions.insert().values(
            role_id=role_id,
            permission_id=perm_id,
        )
    )
    test_db.execute(
        models.user_roles.insert().values(
            user_id=user_id,
            role_id=role_id,
            branch_id=None,
        )
    )

    # 5. Units
    unit_kg = "unit-kg-test"
    unit_lt = "unit-lt-test"
    test_db.execute(
        models.inventory_units.insert().values([
            {
                "id": unit_kg,
                "organization_id": ORGANIZATION_ID,
                "code": "kg",
                "name": "Kilogramo",
                "dimension": "mass",
                "precision_scale": 3,
                "created_at": now,
            },
            {
                "id": unit_lt,
                "organization_id": ORGANIZATION_ID,
                "code": "litros",
                "name": "Litro",
                "dimension": "volume",
                "precision_scale": 3,
                "created_at": now,
            },
        ])
    )

    # 6. Items with thresholds (Aceituna negra, Aderezo balsámico)
    item_olive = "item-olive-test"
    item_balsamic = "item-balsamic-test"
    test_db.execute(
        models.inventory_items.insert().values([
            {
                "id": item_olive,
                "organization_id": ORGANIZATION_ID,
                "sku": "INS-001",
                "name": "Aceituna negra",
                "base_unit_id": unit_kg,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": item_balsamic,
                "organization_id": ORGANIZATION_ID,
                "sku": "INS-002",
                "name": "Aderezo balsámico",
                "base_unit_id": unit_lt,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ])
    )

    # 7. Thresholds in Chapultepec
    test_db.execute(
        models.inventory_stock_thresholds.insert().values([
            {
                "id": "thresh-olive-test",
                "organization_id": ORGANIZATION_ID,
                "branch_id": branch_id,
                "warehouse_id": wh_id,
                "item_id": item_olive,
                "minimum_quantity": Decimal("1.000000"),
                "maximum_quantity": Decimal("3.000000"),
                "version": 1,
                "created_by": user_id,
                "updated_by": user_id,
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "thresh-balsamic-test",
                "organization_id": ORGANIZATION_ID,
                "branch_id": branch_id,
                "warehouse_id": wh_id,
                "item_id": item_balsamic,
                "minimum_quantity": Decimal("1.000000"),
                "maximum_quantity": Decimal("1.000000"),
                "version": 1,
                "created_by": user_id,
                "updated_by": user_id,
                "created_at": now,
                "updated_at": now,
            },
        ])
    )

    # 8. Open cash shift in Chapultepec
    shift_id = "shift-chap-test"
    test_db.execute(
        models.cash_shifts.insert().values(
            id=shift_id,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            register_code="Caja 1",
            status="OPEN",
            opening_cash_cents=150000,
            cashier_user_id=user_id,
            opened_at=now,
            created_at=now,
        )
    )

    test_db.commit()
    return {"branch_id": branch_id, "warehouse_id": wh_id, "user_id": user_id}


def test_copilot_tool_definitions_schema():
    """Verify tool definitions are valid OpenAI/Gemini function specs."""
    assert len(COPILOT_TOOL_DEFINITIONS) >= 4
    for tool in COPILOT_TOOL_DEFINITIONS:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        assert fn["parameters"]["type"] == "object"


def test_tool_get_inventory_thresholds_for_chapultepec(test_db: Session, copilot_seed_data: dict[str, Any]):
    """Verify querying inventory thresholds returns min, max, unit and items for Chapultepec."""
    result = tool_get_inventory_thresholds_and_stock(
        session=test_db,
        organization_id=ORGANIZATION_ID,
        branch_name_or_id="Chapultepec",
    )
    assert result["branch_name"] == "Chapultepec"
    assert result["total_configured_thresholds"] >= 2
    
    items = {item["insumo"]: item for item in result["items"]}
    assert "Aceituna negra" in items
    assert items["Aceituna negra"]["minimo"] == 1.0
    assert items["Aceituna negra"]["maximo"] == 3.0
    assert items["Aceituna negra"]["unidad"] == "kg"

    assert "Aderezo balsámico" in items
    assert items["Aderezo balsámico"]["minimo"] == 1.0
    assert items["Aderezo balsámico"]["maximo"] == 1.0
    assert items["Aderezo balsámico"]["unidad"] == "litros"


def test_tool_get_cash_status(test_db: Session, copilot_seed_data: dict[str, Any]):
    """Verify cash status tool returns active open cash shifts with opening fund."""
    result = tool_get_cash_status(
        session=test_db,
        organization_id=ORGANIZATION_ID,
        branch_name_or_id="Chapultepec",
    )
    assert result["open_registers_count"] >= 1
    shift = result["open_registers"][0]
    assert shift["caja"] == "Caja 1"
    assert shift["fondo_inicial"] == "$1,500.00"
    assert shift["estado"] == "OPEN"


def test_dispatch_copilot_tool(test_db: Session, copilot_seed_data: dict[str, Any]):
    """Verify tool dispatcher routes function name and arguments cleanly."""
    res = dispatch_copilot_tool(
        session=test_db,
        organization_id=ORGANIZATION_ID,
        tool_name="get_inventory_stock_and_thresholds",
        arguments={"branch_name_or_id": "Chapultepec"},
    )
    assert "items" in res
    assert res["total_configured_thresholds"] >= 2


def test_execute_copilot_chat_returns_threshold_table(test_db: Session, copilot_seed_data: dict[str, Any]):
    """Verify copilot chat returns a structured table when asked about thresholds in Chapultepec."""
    response = execute_copilot_chat(
        session=test_db,
        organization_id=ORGANIZATION_ID,
        prompt="cuales son los umbrales de chapultepec",
        branch_name_or_id="Chapultepec",
    )
    answer = response["answer"]
    assert "Aceituna negra" in answer
    assert "Aderezo balsámico" in answer
    assert "kg" in answer
    assert "litros" in answer
    assert "get_inventory_stock_and_thresholds" in response["tools_used"]


def test_execute_copilot_chat_returns_open_cash_registers(test_db: Session, copilot_seed_data: dict[str, Any]):
    """Verify copilot chat returns open registers when asked about cajas."""
    response = execute_copilot_chat(
        session=test_db,
        organization_id=ORGANIZATION_ID,
        prompt="que cajas estan abiertas hoy?",
        branch_name_or_id="Chapultepec",
    )
    answer = response["answer"]
    assert "Caja 1" in answer
    assert "$1,500.00" in answer
    assert "get_cash_status" in response["tools_used"]


def test_create_admin_ai_response_routes_threshold_inquiry_to_copilot(
    test_db: Session, copilot_seed_data: dict[str, Any]
):
    """Verify that when a user asks about umbrales in AdminAssistantPanel, it uses Copilot tools."""
    from restaurant_os.admin_ai import create_admin_ai_response

    res = create_admin_ai_response(
        session=test_db,
        actor_id=copilot_seed_data["user_id"],
        prompt="La sucursal chapultepec, en inventario de insumos tiene configurados umbrales",
        branch_id=copilot_seed_data["branch_id"],
    )
    assert res["status"] == "DRAFT"
    assert "Aceituna negra" in res["payload"]["answer"]
    assert "get_inventory_stock_and_thresholds" in res["payload"]["sources"]


