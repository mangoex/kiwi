#!/home/antigravity/.kiwi-venv/bin/python
"""Canonical CLI & Domain/API Bridge for Kiwi Multi-Agent Operations.

Coordinates the 4 governed Kiwi agent profiles:
- administrator (kiwi-administrador)
- inventory     (kiwi-inventarios)
- kitchen       (kiwi-cocinero)
- purchasing    (kiwi-compras)

Supports two execution modes:
1. Local/Direct Domain Mode (default): Executes against RESTAURANTOS_DATABASE_URL
   (default: sqlite:////home/antigravity/kiwi-agents/kiwi_operational.db) using the
   canonical restaurant_os.agent_tools, restaurant_os.admin_ai, and restaurant_os.operations
   domain boundary with full RBAC, capability checks, Idempotency-Key deduplication,
   and audit_events logging.
2. Remote REST API Mode: When KIWI_API_URL and KIWI_CLIENT_ID_<PROFILE> /
   KIWI_CLIENT_SECRET_<PROFILE> are set, exchanges OAuth2 client_credentials at
   POST /api/v1/agent-auth/token and calls /api/v1/agent-tools/*.
"""

from __future__ import annotations

import os
import sys

# Auto-reexec into /home/antigravity/.kiwi-venv/bin/python if invoked with system python3
VENV_DIR = "/home/antigravity/.kiwi-venv"
VENV_PYTHON = f"{VENV_DIR}/bin/python"
if os.path.exists(VENV_PYTHON) and os.path.abspath(sys.prefix) != os.path.abspath(VENV_DIR):
    os.execv(VENV_PYTHON, [VENV_PYTHON] + sys.argv)

from pathlib import Path

# Asegurar que apps/api esté disponible para importar restaurant_os
for _candidate in [
    Path("/home/antigravity/mangoex/kiwi/apps/api"),
    Path(__file__).resolve().parents[4] / "apps" / "api",
]:
    if _candidate.exists() and str(_candidate) not in sys.path:
        sys.path.insert(0, str(_candidate))

# Sanitize no_proxy/NO_PROXY for httpx (removes IPv6 ::1 bracket issue)
for _k in ["no_proxy", "NO_PROXY"]:
    if _k in os.environ:
        os.environ[_k] = ",".join([_x for _x in os.environ[_k].split(",") if "::" not in _x])

import argparse
import base64
import hashlib
import json
import math
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from restaurant_os import admin_ai, agent_tools, models
from restaurant_os.auth import create_session_token, generate_password_salt, hash_password
from restaurant_os.config import get_settings
from restaurant_os.operations import ADMIN_USER_ID, ORGANIZATION_ID

UTC = timezone.utc
DEFAULT_DB_PATH = Path("/home/antigravity/kiwi-agents/kiwi_operational.db")
DEFAULT_DB_URL = f"sqlite:///{DEFAULT_DB_PATH}"

# Canonical UUID constants for Kiwi Operational Seed
LEGAL_ENTITY_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"
BUSINESS_UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000015"
ADMIN_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000000005"

BRANCHES_SEED = [
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000003",
        "code": "BR-001",
        "name": "Centro Histórico",
        "warehouse_id": "018f6f73-2d0a-74f0-8f1c-000000000004",
        "warehouse_name": "Almacén Centro Histórico",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000013",
        "code": "BR-002",
        "name": "Plaza Mayor",
        "warehouse_id": "018f6f73-2d0a-74f0-8f1c-000000000014",
        "warehouse_name": "Almacén Plaza Mayor",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000023",
        "code": "BR-003",
        "name": "Zona Norte",
        "warehouse_id": "018f6f73-2d0a-74f0-8f1c-000000000024",
        "warehouse_name": "Almacén Zona Norte",
    },
]

PRIMARY_BRANCH_ID = BRANCHES_SEED[0]["id"]
PRIMARY_WAREHOUSE_ID = BRANCHES_SEED[0]["warehouse_id"]

UNITS_SEED = [
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000301", "code": "KG", "name": "Kilogramo", "scale": 3},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000302", "code": "L", "name": "Litro", "scale": 3},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000303", "code": "PZ", "name": "Pieza", "scale": 0},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000304", "code": "POR", "name": "Porción", "scale": 0},
]

CATEGORIES_SEED = [
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000101", "name": "JUGOS Y EXTRACTOS", "order": 1},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000102", "name": "CAFE Y MATCHA", "order": 2},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000103", "name": "SMOOTHIES Y LICUADOS", "order": 3},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000104", "name": "ENSALADAS", "order": 4},
    {"id": "018f6f73-2d0a-74f0-8f1c-000000000105", "name": "EMPAREDADOS Y SANDOS", "order": 5},
]

ITEMS_SEED = [
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000311",
        "sku": "2001",
        "name": "Naranja Valencia",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("12.000000"),
        "min_qty": Decimal("25.000000"),
        "max_qty": Decimal("80.000000"),
        "unit_cost": Decimal("18.500000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000312",
        "sku": "2002",
        "name": "Piña Miel",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("8.000000"),
        "min_qty": Decimal("15.000000"),
        "max_qty": Decimal("45.000000"),
        "unit_cost": Decimal("24.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000313",
        "sku": "2003",
        "name": "Espinaca Baby Lavada",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("9.500000"),
        "min_qty": Decimal("5.000000"),
        "max_qty": Decimal("15.000000"),
        "unit_cost": Decimal("65.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000314",
        "sku": "2004",
        "name": "Café en Grano Especialidad",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("2.500000"),
        "min_qty": Decimal("5.000000"),
        "max_qty": Decimal("15.000000"),
        "unit_cost": Decimal("320.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000315",
        "sku": "2005",
        "name": "Leche de Almendra Sin Azúcar",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000302",  # L
        "on_hand": Decimal("6.000000"),
        "min_qty": Decimal("12.000000"),
        "max_qty": Decimal("36.000000"),
        "unit_cost": Decimal("48.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000316",
        "sku": "2006",
        "name": "Matcha Ceremonial Japonés",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("3.200000"),
        "min_qty": Decimal("1.500000"),
        "max_qty": Decimal("5.000000"),
        "unit_cost": Decimal("1200.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000317",
        "sku": "2007",
        "name": "Pechuga de Pollo a la Plancha",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("14.000000"),
        "min_qty": Decimal("8.000000"),
        "max_qty": Decimal("25.000000"),
        "unit_cost": Decimal("145.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000318",
        "sku": "2008",
        "name": "Pan Baguette Artesanal",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000303",  # PZ
        "on_hand": Decimal("35.000000"),
        "min_qty": Decimal("20.000000"),
        "max_qty": Decimal("60.000000"),
        "unit_cost": Decimal("12.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000319",
        "sku": "2009",
        "name": "Miel de Abeja Orgánica",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("5.000000"),
        "min_qty": Decimal("2.000000"),
        "max_qty": Decimal("8.000000"),
        "unit_cost": Decimal("160.000000"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000320",
        "sku": "2010",
        "name": "Fresa Seleccionada",
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",  # KG
        "on_hand": Decimal("11.000000"),
        "min_qty": Decimal("6.000000"),
        "max_qty": Decimal("20.000000"),
        "unit_cost": Decimal("75.000000"),
    },
]

SUPPLIERS_SEED = [
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000701",
        "code": "PROV-FRUTAS-01",
        "name": "Frutas y Verduras Selectas del Norte S.A.",
        "type": "insumos",
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000702",
        "code": "PROV-BARRA-02",
        "name": "Tostadores y Lácteos Especiales Kiwi S.A.",
        "type": "insumos",
    },
]

PRESENTATIONS_SEED = [
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000711",
        "supplier_id": "018f6f73-2d0a-74f0-8f1c-000000000701",
        "item_id": "018f6f73-2d0a-74f0-8f1c-000000000311",  # Naranja Valencia
        "code": "PRES-NAR-20KG",
        "name": "Arpilla Naranja Valencia 20 KG",
        "package_type": "sack",
        "commercial_quantity": Decimal("1"),
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",
        "base_unit_yield": Decimal("20"),
        "usable_content": Decimal("20"),
        "last_net_price": Decimal("370.00"),
        "cost_per_base_unit": Decimal("18.50"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000712",
        "supplier_id": "018f6f73-2d0a-74f0-8f1c-000000000701",
        "item_id": "018f6f73-2d0a-74f0-8f1c-000000000312",  # Piña Miel
        "code": "PRES-PIN-10KG",
        "name": "Caja Piña Miel 10 KG",
        "package_type": "box",
        "commercial_quantity": Decimal("1"),
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",
        "base_unit_yield": Decimal("10"),
        "usable_content": Decimal("10"),
        "last_net_price": Decimal("240.00"),
        "cost_per_base_unit": Decimal("24.00"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000713",
        "supplier_id": "018f6f73-2d0a-74f0-8f1c-000000000702",
        "item_id": "018f6f73-2d0a-74f0-8f1c-000000000314",  # Café en Grano
        "code": "PRES-CAF-5KG",
        "name": "Saco Café Especialidad 5 KG",
        "package_type": "bag",
        "commercial_quantity": Decimal("1"),
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000301",
        "base_unit_yield": Decimal("5"),
        "usable_content": Decimal("5"),
        "last_net_price": Decimal("1600.00"),
        "cost_per_base_unit": Decimal("320.00"),
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000714",
        "supplier_id": "018f6f73-2d0a-74f0-8f1c-000000000702",
        "item_id": "018f6f73-2d0a-74f0-8f1c-000000000315",  # Leche de Almendra
        "code": "PRES-ALM-12L",
        "name": "Caja Leche de Almendra 12 Litros",
        "package_type": "box",
        "commercial_quantity": Decimal("1"),
        "unit_id": "018f6f73-2d0a-74f0-8f1c-000000000302",
        "base_unit_yield": Decimal("12"),
        "usable_content": Decimal("12"),
        "last_net_price": Decimal("576.00"),
        "cost_per_base_unit": Decimal("48.00"),
    },
]

PRODUCTS_SEED = [
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000111",
        "category_id": "018f6f73-2d0a-74f0-8f1c-000000000101",
        "sku": "1001",
        "name": "JUGO VERDE KIWI",
        "description": "Naranja, piña y espinaca fresca.",
        "station": "drinks",
        "price_id": "018f6f73-2d0a-74f0-8f1c-000000000121",
        "price_cents": 6500,
        "recipe_id": "018f6f73-2d0a-74f0-8f1c-000000000321",
        "yield_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000304",
        "components": [
            ("018f6f73-2d0a-74f0-8f1c-000000000311", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.250000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000312", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.120000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000313", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.050000"),
        ],
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000112",
        "category_id": "018f6f73-2d0a-74f0-8f1c-000000000102",
        "sku": "1002",
        "name": "KIWI LATTE ESPECIAL",
        "description": "Espresso doble con leche de almendra.",
        "station": "drinks",
        "price_id": "018f6f73-2d0a-74f0-8f1c-000000000122",
        "price_cents": 7500,
        "recipe_id": "018f6f73-2d0a-74f0-8f1c-000000000322",
        "yield_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000304",
        "components": [
            ("018f6f73-2d0a-74f0-8f1c-000000000314", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.018000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000315", "018f6f73-2d0a-74f0-8f1c-000000000302", "0.250000"),
        ],
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000113",
        "category_id": "018f6f73-2d0a-74f0-8f1c-000000000103",
        "sku": "1003",
        "name": "SMOOTHIE ROSA ANTIOXIDANTE",
        "description": "Fresa, leche de almendra, miel y espinaca.",
        "station": "drinks",
        "price_id": "018f6f73-2d0a-74f0-8f1c-000000000123",
        "price_cents": 9000,
        "recipe_id": "018f6f73-2d0a-74f0-8f1c-000000000323",
        "yield_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000304",
        "components": [
            ("018f6f73-2d0a-74f0-8f1c-000000000320", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.150000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000315", "018f6f73-2d0a-74f0-8f1c-000000000302", "0.250000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000319", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.025000"),
        ],
    },
    {
        "id": "018f6f73-2d0a-74f0-8f1c-000000000114",
        "category_id": "018f6f73-2d0a-74f0-8f1c-000000000105",
        "sku": "1004",
        "name": "BAGUETTE POLLO ARTESANAL",
        "description": "Baguette artesanal con pechuga a la plancha y espinaca.",
        "station": "kitchen",
        "price_id": "018f6f73-2d0a-74f0-8f1c-000000000124",
        "price_cents": 11500,
        "recipe_id": "018f6f73-2d0a-74f0-8f1c-000000000324",
        "yield_unit_id": "018f6f73-2d0a-74f0-8f1c-000000000304",
        "components": [
            ("018f6f73-2d0a-74f0-8f1c-000000000318", "018f6f73-2d0a-74f0-8f1c-000000000303", "1.000000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000317", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.160000"),
            ("018f6f73-2d0a-74f0-8f1c-000000000313", "018f6f73-2d0a-74f0-8f1c-000000000301", "0.030000"),
        ],
    },
]

INTEGRATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000600"
AGENT_IDENTITIES_SEED = {
    "administrator": "018f6f73-2d0a-74f0-8f1c-000000000601",
    "kitchen": "018f6f73-2d0a-74f0-8f1c-000000000602",
    "inventory": "018f6f73-2d0a-74f0-8f1c-000000000603",
    "purchasing": "018f6f73-2d0a-74f0-8f1c-000000000604",
}


def get_database_url() -> str:
    return os.environ.get("RESTAURANTOS_DATABASE_URL", DEFAULT_DB_URL)


def ensure_operational_database(db_url: str | None = None) -> sessionmaker[Session]:
    url = db_url or get_database_url()
    if url.startswith("sqlite:///"):
        db_file = Path(url.removeprefix("sqlite:///"))
        db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        existing_org = session.scalar(
            sa.select(models.organizations.c.id).where(
                models.organizations.c.id == ORGANIZATION_ID
            )
        )
        if not existing_org:
            _seed_operational_data(session)
    return factory


def _seed_operational_data(session: Session) -> None:
    now = datetime.now(UTC)
    yesterday = now - timedelta(hours=18)
    two_hours_ago = now - timedelta(hours=2)
    one_hour_ago = now - timedelta(hours=1)

    session.execute(
        models.organizations.insert().values(
            id=ORGANIZATION_ID,
            name="Kiwi Restaurante",
            status="active",
            created_at=yesterday,
            updated_at=now,
        )
    )
    if sa.inspect(session.connection()).has_table("offline_authorization_rollouts"):
        session.execute(
            models.offline_authorization_rollouts.insert().values(
                organization_id=ORGANIZATION_ID,
                state="clean_install",
                registration_started_at=yesterday,
                legacy_drain_until=yesterday,
                created_at=yesterday,
            )
        )
    session.execute(
        models.legal_entities.insert().values(
            id=LEGAL_ENTITY_ID,
            organization_id=ORGANIZATION_ID,
            name="Kiwi S.A. de C.V.",
            tax_id="KIW240101AAA",
            status="active",
            created_at=yesterday,
            updated_at=now,
        )
    )
    session.execute(
        models.business_units.insert().values(
            id=BUSINESS_UNIT_ID,
            organization_id=ORGANIZATION_ID,
            legal_entity_id=LEGAL_ENTITY_ID,
            name="Operaciones Kiwi",
            code="KIWI",
            unit_type="restaurant",
            status="active",
            created_at=yesterday,
            updated_at=now,
        )
    )
    for br in BRANCHES_SEED:
        session.execute(
            models.branches.insert().values(
                id=br["id"],
                organization_id=ORGANIZATION_ID,
                legal_entity_id=LEGAL_ENTITY_ID,
                business_unit_id=BUSINESS_UNIT_ID,
                name=br["name"],
                code=br["code"],
                timezone="America/Chihuahua",
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )
        session.execute(
            models.warehouses.insert().values(
                id=br["warehouse_id"],
                organization_id=ORGANIZATION_ID,
                branch_id=br["id"],
                name=br["warehouse_name"],
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )

    # Admin role, permissions & user
    session.execute(
        models.roles.insert().values(
            id=ADMIN_ROLE_ID,
            organization_id=ORGANIZATION_ID,
            name="Administrador corporativo",
            scope="organization",
            created_at=yesterday,
        )
    )
    perm_codes = [
        ("018f6f73-2d0a-74f0-8f1c-000000000901", "admin.manage"),
        ("018f6f73-2d0a-74f0-8f1c-000000000902", "catalog.manage"),
        ("018f6f73-2d0a-74f0-8f1c-000000000903", "inventory.adjust"),
        ("018f6f73-2d0a-74f0-8f1c-000000000905", "cash.shift.read"),
        ("018f6f73-2d0a-74f0-8f1c-000000000908", "orders.read"),
        ("018f6f73-2d0a-74f0-8f1c-000000000910", "payments.read"),
        ("018f6f73-2d0a-74f0-8f1c-000000000912", "dashboard.read"),
        ("018f6f73-2d0a-74f0-8f1c-000000000920", "inventory.read"),
        ("018f6f73-2d0a-74f0-8f1c-000000000921", "purchases.read"),
        ("018f6f73-2d0a-74f0-8f1c-000000000922", "purchases.manage"),
        ("018f6f73-2d0a-74f0-8f1c-000000000927", "recipes.manage"),
    ]
    for pid, code in perm_codes:
        session.execute(
            models.permissions.insert().values(
                id=pid,
                code=code,
                description=code,
                created_at=yesterday,
            )
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=ADMIN_ROLE_ID,
                permission_id=pid,
            )
        )
    session.execute(
        models.users.insert().values(
            id=ADMIN_USER_ID,
            organization_id=ORGANIZATION_ID,
            email="mangoex@gmail.com",
            display_name="Administrador General Kiwi",
            status="active",
            created_at=yesterday,
            updated_at=now,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=ADMIN_USER_ID,
            role_id=ADMIN_ROLE_ID,
            branch_id=None,
        )
    )

    # Units & Categories
    for u in UNITS_SEED:
        session.execute(
            models.inventory_units.insert().values(
                id=u["id"],
                organization_id=ORGANIZATION_ID,
                code=u["code"],
                name=u["name"],
                dimension="discrete",
                precision_scale=u["scale"],
                created_at=yesterday,
            )
        )
    for cat in CATEGORIES_SEED:
        session.execute(
            models.product_categories.insert().values(
                id=cat["id"],
                organization_id=ORGANIZATION_ID,
                name=cat["name"],
                display_order=cat["order"],
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )

    # Suppliers
    for sup in SUPPLIERS_SEED:
        session.execute(
            models.suppliers.insert().values(
                id=sup["id"],
                organization_id=ORGANIZATION_ID,
                code=sup["code"],
                commercial_name=sup["name"],
                supplier_type=sup["type"],
                credit_days=15,
                currency="MXN",
                delivery_days=["monday", "wednesday", "friday"],
                payment_methods=["transfer", "cash"],
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )

    # Inventory items, cost states, movements, and thresholds
    for idx, item in enumerate(ITEMS_SEED, start=1):
        session.execute(
            models.inventory_items.insert().values(
                id=item["id"],
                organization_id=ORGANIZATION_ID,
                name=item["name"],
                sku=item["sku"],
                base_unit_id=item["unit_id"],
                item_type="ingredient",
                catalog_scope="organization",
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )
        session.execute(
            models.inventory_cost_states.insert().values(
                branch_id=PRIMARY_BRANCH_ID,
                warehouse_id=PRIMARY_WAREHOUSE_ID,
                item_id=item["id"],
                quantity_on_hand=item["on_hand"],
                average_unit_cost=item["unit_cost"],
                last_unit_cost=item["unit_cost"],
                last_supplier_id=SUPPLIERS_SEED[0]["id"],
                last_cost_at=yesterday,
                updated_at=now,
            )
        )
        session.execute(
            models.inventory_stock_thresholds.insert().values(
                id=f"018f6f73-2d0a-74f0-8f1c-00000000035{idx:01x}",
                organization_id=ORGANIZATION_ID,
                branch_id=PRIMARY_BRANCH_ID,
                warehouse_id=PRIMARY_WAREHOUSE_ID,
                item_id=item["id"],
                minimum_quantity=item["min_qty"],
                maximum_quantity=item["max_qty"],
                version=1,
                created_by=ADMIN_USER_ID,
                updated_by=ADMIN_USER_ID,
                created_at=yesterday,
                updated_at=now,
            )
        )
        session.execute(
            models.inventory_movements.insert().values(
                id=f"018f6f73-2d0a-74f0-8f1c-00000000037{idx:01x}",
                organization_id=ORGANIZATION_ID,
                branch_id=PRIMARY_BRANCH_ID,
                warehouse_id=PRIMARY_WAREHOUSE_ID,
                item_id=item["id"],
                movement_type="OPENING_BALANCE",
                quantity_delta=item["on_hand"],
                unit_id=item["unit_id"],
                reason="Inventario inicial operativo Kiwi",
                source_type="seed",
                source_id=None,
                status="APPLIED",
                effective_at=two_hours_ago,
                created_at=two_hours_ago,
            )
        )

    # Purchase presentations
    for pres in PRESENTATIONS_SEED:
        session.execute(
            models.purchase_presentations.insert().values(
                id=pres["id"],
                organization_id=ORGANIZATION_ID,
                supplier_id=pres["supplier_id"],
                item_id=pres["item_id"],
                code=pres["code"],
                name=pres["name"],
                package_type=pres["package_type"],
                commercial_quantity=pres["commercial_quantity"],
                commercial_unit_id=pres["unit_id"],
                base_unit_id=pres["unit_id"],
                base_unit_yield=pres["base_unit_yield"],
                usable_content=pres["usable_content"],
                yield_percent=Decimal("1"),
                tax_rate=Decimal("0"),
                last_net_price=pres["last_net_price"],
                cost_per_base_unit=pres["cost_per_base_unit"],
                is_preferred=True,
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )

    # Products, prices, availability, and recipes
    for prod in PRODUCTS_SEED:
        session.execute(
            models.products.insert().values(
                id=prod["id"],
                organization_id=ORGANIZATION_ID,
                category_id=prod["category_id"],
                name=prod["name"],
                sku=prod["sku"],
                description=prod["description"],
                station=prod["station"],
                catalog_scope="organization",
                status="active",
                created_at=yesterday,
                updated_at=now,
            )
        )
        session.execute(
            models.price_versions.insert().values(
                id=prod["price_id"],
                organization_id=ORGANIZATION_ID,
                product_id=prod["id"],
                price_cents=prod["price_cents"],
                currency="MXN",
                valid_from=yesterday,
                valid_to=None,
                created_at=yesterday,
            )
        )
        for br in BRANCHES_SEED:
            session.execute(
                models.branch_product_availability.insert().values(
                    branch_id=br["id"],
                    product_id=prod["id"],
                    is_available=True,
                    updated_at=now,
                )
            )
        session.execute(
            models.recipes.insert().values(
                id=prod["recipe_id"],
                organization_id=ORGANIZATION_ID,
                product_id=prod["id"],
                output_item_id=None,
                branch_id=None,
                recipe_type="sale",
                version=1,
                status="active",
                yield_quantity=Decimal("1.000000"),
                yield_unit_id=prod["yield_unit_id"],
                valid_from=yesterday,
                valid_to=None,
                created_at=yesterday,
                updated_at=now,
            )
        )
        for sort_idx, (item_id, unit_id, qty) in enumerate(prod["components"]):
            dec_qty = Decimal(qty)
            session.execute(
                models.recipe_components.insert().values(
                    recipe_id=prod["recipe_id"],
                    item_id=item_id,
                    quantity_base_units=dec_qty,
                    unit_id=unit_id,
                    net_quantity=dec_qty,
                    waste_rate=Decimal("0"),
                    gross_quantity=dec_qty,
                    sort_order=sort_idx,
                    notes=None,
                )
            )

    # Cash shifts (1 CLOSED shift with FINALIZED cut + 2 OPEN live registers!)
    closed_shift_id = "018f6f73-2d0a-74f0-8f1c-000000000990"
    open_shift_1_id = "018f6f73-2d0a-74f0-8f1c-000000000991"
    open_shift_2_id = "018f6f73-2d0a-74f0-8f1c-000000000992"

    session.execute(
        models.cash_shifts.insert(),
        [
            {
                "id": closed_shift_id,
                "organization_id": ORGANIZATION_ID,
                "branch_id": PRIMARY_BRANCH_ID,
                "register_code": "CAJA-01",
                "status": "CLOSED",
                "opening_cash_cents": 150000,
                "cashier_user_id": ADMIN_USER_ID,
                "opened_at": yesterday,
                "closed_at": two_hours_ago,
                "created_at": yesterday,
            },
            {
                "id": open_shift_1_id,
                "organization_id": ORGANIZATION_ID,
                "branch_id": PRIMARY_BRANCH_ID,
                "register_code": "CAJA-01",
                "status": "OPEN",
                "opening_cash_cents": 200000,
                "cashier_user_id": ADMIN_USER_ID,
                "opened_at": two_hours_ago,
                "closed_at": None,
                "created_at": two_hours_ago,
            },
            {
                "id": open_shift_2_id,
                "organization_id": ORGANIZATION_ID,
                "branch_id": PRIMARY_BRANCH_ID,
                "register_code": "CAJA-BARRA-02",
                "status": "OPEN",
                "opening_cash_cents": 100000,
                "cashier_user_id": ADMIN_USER_ID,
                "opened_at": one_hour_ago,
                "closed_at": None,
                "created_at": one_hour_ago,
            },
        ],
    )

    session.execute(
        models.user_cash_cuts.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000000981",
            organization_id=ORGANIZATION_ID,
            branch_id=PRIMARY_BRANCH_ID,
            cash_shift_id=closed_shift_id,
            register_code_snapshot="CAJA-01",
            cashier_user_id=ADMIN_USER_ID,
            timezone="America/Chihuahua",
            period_start=yesterday,
            period_end=two_hours_ago,
            status="FINALIZED",
            opening_cash_cents=150000,
            cash_payment_cents=485000,
            deposit_cents=0,
            withdrawal_cents=50000,
            expected_cash_cents=585000,
            counted_cash_cents=585000,
            difference_cents=0,
            tolerance_cents=0,
            created_by_user_id=ADMIN_USER_ID,
            finalized_by_user_id=ADMIN_USER_ID,
            version=1,
            created_at=two_hours_ago,
            counted_at=two_hours_ago,
            finalized_at=two_hours_ago,
        )
    )

    # Confirmed Orders, Payments, and Sales Operation Snapshots
    sales_specs = [
        (
            "018f6f73-2d0a-74f0-8f1c-000000000904",
            "018f6f73-2d0a-74f0-8f1c-000000000903",
            "018f6f73-2d0a-74f0-8f1c-000000000901",
            "018f6f73-2d0a-74f0-8f1c-000000000906",
            "018f6f73-2d0a-74f0-8f1c-000000000902",
            open_shift_1_id,
            "CAJA-01",
            "KIWI-ORD-101",
            "takeout",
            "POS",
            "cash",
            PRODUCTS_SEED[0],
            4,
            one_hour_ago,
        ),
        (
            "018f6f73-2d0a-74f0-8f1c-000000000914",
            "018f6f73-2d0a-74f0-8f1c-000000000913",
            "018f6f73-2d0a-74f0-8f1c-000000000911",
            "018f6f73-2d0a-74f0-8f1c-000000000916",
            "018f6f73-2d0a-74f0-8f1c-000000000912",
            open_shift_1_id,
            "CAJA-01",
            "KIWI-ORD-102",
            "takeout",
            "POS",
            "card",
            PRODUCTS_SEED[3],
            3,
            one_hour_ago + timedelta(minutes=15),
        ),
        (
            "018f6f73-2d0a-74f0-8f1c-000000000924",
            "018f6f73-2d0a-74f0-8f1c-000000000923",
            "018f6f73-2d0a-74f0-8f1c-000000000921",
            "018f6f73-2d0a-74f0-8f1c-000000000926",
            "018f6f73-2d0a-74f0-8f1c-000000000922",
            open_shift_2_id,
            "CAJA-BARRA-02",
            "KIWI-ORD-103",
            "delivery",
            "UBER_EATS",
            "transfer",
            PRODUCTS_SEED[2],
            5,
            one_hour_ago + timedelta(minutes=30),
        ),
    ]
    for (
        order_id,
        payment_id,
        snap_id,
        line_id,
        snap_line_id,
        shift_id,
        reg_code,
        folio,
        service_type,
        channel,
        pay_method,
        prod,
        qty,
        confirmed_time,
    ) in sales_specs:
        gross_cents = prod["price_cents"] * qty
        tax_cents = int(round(gross_cents * 16 / 116))
        net_cents = gross_cents - tax_cents
        session.execute(
            models.orders.insert().values(
                id=order_id,
                organization_id=ORGANIZATION_ID,
                branch_id=PRIMARY_BRANCH_ID,
                cash_shift_id=shift_id,
                folio=folio,
                channel=channel,
                status="COMPLETED",
                total_cents=gross_cents,
                currency="MXN",
                owner_name="Cliente Kiwi",
                order_type=service_type,
                payment_method_intent=pay_method,
                version=1,
                created_at=confirmed_time,
                accepted_at=confirmed_time,
            )
        )
        session.execute(
            models.order_lines.insert().values(
                id=line_id,
                order_id=order_id,
                product_id=prod["id"],
                product_name=prod["name"],
                quantity=qty,
                unit_price_cents=prod["price_cents"],
                line_total_cents=gross_cents,
                station=prod["station"],
                selected_modifiers=[],
                modifier_total_cents=0,
                line_notes=None,
                status="DELIVERED",
                revision=1,
                supersedes_line_id=None,
                updated_at=confirmed_time,
                removed_at=None,
                family_id_snapshot=prod["category_id"],
                family_name_snapshot="CATALOGO KIWI",
                family_snapshot_source="captured",
                created_at=confirmed_time,
            )
        )
        session.execute(
            models.payments.insert().values(
                id=payment_id,
                organization_id=ORGANIZATION_ID,
                branch_id=PRIMARY_BRANCH_ID,
                order_id=order_id,
                cash_shift_id=shift_id,
                method=pay_method,
                status="CONFIRMED",
                amount_cents=gross_cents,
                currency="MXN",
                confirmed_at=confirmed_time,
                created_at=confirmed_time,
            )
        )
        session.execute(
            models.sales_operation_snapshots.insert().values(
                id=snap_id,
                organization_id=ORGANIZATION_ID,
                branch_id=PRIMARY_BRANCH_ID,
                payment_id=payment_id,
                order_id=order_id,
                cash_shift_id=shift_id,
                register_code_snapshot=reg_code,
                folio_snapshot=folio,
                service_type_snapshot=service_type,
                currency="MXN",
                gross_cents=gross_cents,
                net_cents=gross_cents,
                discount_cents=0,
                courtesy_cents=0,
                tax_cents=tax_cents,
                quality_status="captured",
                confirmed_at=confirmed_time,
                created_at=confirmed_time,
            )
        )
        session.execute(
            models.sales_operation_line_snapshots.insert().values(
                id=snap_line_id,
                sales_operation_snapshot_id=snap_id,
                payment_id=payment_id,
                order_line_id=line_id,
                product_id=prod["id"],
                product_name_snapshot=prod["name"],
                family_id_snapshot=prod["category_id"],
                family_name_snapshot="CATALOGO KIWI",
                family_snapshot_source="captured",
                quantity=qty,
                gross_cents=gross_cents,
                net_cents=gross_cents,
                discount_cents=0,
                courtesy_cents=0,
                tax_cents=tax_cents,
            )
        )

    # Expense concept & confirmed operating expense
    expense_concept_id = "018f6f73-2d0a-74f0-8f1c-000000000951"
    session.execute(
        models.expense_concepts.insert().values(
            id=expense_concept_id,
            organization_id=ORGANIZATION_ID,
            code="HIELO_Y_AGUA",
            name="Hielo y Agua Purificada",
            description="Compra de hielo y garrafones de agua purificada para barra",
            status="active",
            version=1,
            created_by=ADMIN_USER_ID,
            created_at=yesterday,
            updated_at=now,
        )
    )
    session.execute(
        models.expense_documents.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000000952",
            organization_id=ORGANIZATION_ID,
            branch_id=PRIMARY_BRANCH_ID,
            concept_id=expense_concept_id,
            concept_snapshot={"code": "HIELO_Y_AGUA", "name": "Hielo y Agua Purificada"},
            folio="GASTO-HIELO-001",
            document_date=now.date(),
            total_cents=35000,
            tax_cents=0,
            currency="MXN",
            payment_method="cash",
            reference="TICKET-HIELO-001",
            notes="Compra de bolsas de hielo para barra de smoothies",
            evidence_refs=[],
            status="confirmed",
            version=1,
            cash_movement_id=None,
            compensation_movement_id=None,
            created_by=ADMIN_USER_ID,
            confirmed_by=ADMIN_USER_ID,
            cancelled_by=None,
            created_at=one_hour_ago,
            updated_at=one_hour_ago,
            confirmed_at=one_hour_ago,
            cancelled_at=None,
            cancellation_reason=None,
        )
    )

    # Configure GrokBot / External Agent Integration and all 4 Agent Profiles
    session.execute(
        models.external_agent_integrations.insert().values(
            id=INTEGRATION_ID,
            organization_id=ORGANIZATION_ID,
            provider="GROKBOT",
            display_name="Equipo Multi-Agente Kiwi (Antigravity)",
            base_url="https://agents.kiwi.example.com",
            callback_url=None,
            callback_secret_ref=None,
            callback_key_id="kiwi-antigravity-01",
            is_enabled=True,
            state="CONNECTED",
            created_by_user_id=ADMIN_USER_ID,
            created_at=yesterday,
            updated_at=now,
        )
    )

    for profile, identity_id in AGENT_IDENTITIES_SEED.items():
        capabilities = sorted(agent_tools.BASELINE_CAPABILITIES[profile])
        client_id = f"gkb_{profile}_kiwi_local"
        secret = f"secret_{profile}_kiwi_local_v1"
        salt = generate_password_salt()
        session.execute(
            models.external_agent_identities.insert().values(
                id=identity_id,
                organization_id=ORGANIZATION_ID,
                integration_id=INTEGRATION_ID,
                profile=profile,
                client_id=client_id,
                is_enabled=True,
                corporate_scope=True,
                authorization_version=1,
                capabilities=capabilities,
                created_at=yesterday,
                updated_at=now,
                last_rotated_at=now,
            )
        )
        session.execute(
            models.external_agent_credentials.insert().values(
                id=f"018f6f73-2d0a-74f0-8f1c-00000000061{list(AGENT_IDENTITIES_SEED).index(profile) + 1}",
                identity_id=identity_id,
                version=1,
                secret_salt=salt,
                secret_hash=hash_password(secret, salt),
                created_at=yesterday,
                revoked_at=None,
            )
        )
        for br in BRANCHES_SEED:
            session.execute(
                models.external_agent_identity_branches.insert().values(
                    identity_id=identity_id,
                    branch_id=br["id"],
                    organization_id=ORGANIZATION_ID,
                    created_at=yesterday,
                )
            )

    session.commit()


def _resolve_branch_id(session: Session, branch_arg: str | None) -> str:
    if not branch_arg:
        return PRIMARY_BRANCH_ID
    try:
        UUID(branch_arg)
        return branch_arg
    except ValueError:
        pass
    row = (
        session.execute(
            sa.select(models.branches.c.id).where(
                models.branches.c.organization_id == ORGANIZATION_ID,
                sa.or_(
                    sa.func.lower(models.branches.c.code) == branch_arg.lower(),
                    sa.func.lower(models.branches.c.name).contains(branch_arg.lower()),
                ),
            )
        )
        .scalars()
        .first()
    )
    return str(row) if row else PRIMARY_BRANCH_ID


def _mint_local_agent_bearer(session: Session, profile: str) -> str:
    identity = (
        session.execute(
            sa.select(models.external_agent_identities).where(
                models.external_agent_identities.c.organization_id == ORGANIZATION_ID,
                models.external_agent_identities.c.profile == profile,
            )
        )
        .mappings()
        .first()
    )
    if not identity:
        raise RuntimeError(f"Agent identity for profile '{profile}' is not configured")
    token = create_session_token(
        {
            "typ": "agent",
            "aud": "kiwi-agent-tools-v1",
            "sub": str(identity["id"]),
            "org": str(identity["organization_id"]),
            "integration": str(identity["integration_id"]),
            "profile": str(identity["profile"]),
            "authorization_version": int(identity["authorization_version"]),
            "jti": f"cli-{profile}-{int(datetime.now(UTC).timestamp())}",
        },
        get_settings().secret_key,
        ttl_seconds=300,
    )
    return f"Bearer {token}"


def _window_bounds(from_arg: str | None, to_arg: str | None, days: int = 7) -> tuple[datetime, datetime]:
    now = datetime.now(UTC)
    end = (
        datetime.fromisoformat(to_arg.replace("Z", "+00:00")).astimezone(UTC)
        if to_arg
        else now + timedelta(minutes=5)
    )
    start = (
        datetime.fromisoformat(from_arg.replace("Z", "+00:00")).astimezone(UTC)
        if from_arg
        else end - timedelta(days=days)
    )
    return start, end


class KiwiAgentBridge:
    """Executes governed Agent Tools operations either locally in-domain or via remote HTTP."""

    def __init__(self, profile: str, branch_arg: str | None = None) -> None:
        self.profile = profile
        self.remote_url = os.environ.get("KIWI_API_URL", "").strip().rstrip("/")
        if not self.remote_url and os.path.exists(os.path.expanduser("~/.kiwi_session.json")):
            self.remote_url = "https://kiwipos.mimenu.onl"
        self.factory = ensure_operational_database()
        with self.factory() as session:
            self.branch_id = _resolve_branch_id(session, branch_arg)

        if self.remote_url and branch_arg:
            try:
                resp = httpx.get(f"{self.remote_url}/api/v1/public/branches", timeout=10.0)
                if resp.status_code == 200:
                    for b in resp.json():
                        if branch_arg.strip().lower() in (b["name"].lower(), b["code"].lower(), b["id"].lower()):
                            self.branch_id = b["id"]
                            break
            except Exception:
                pass

    def _remote_token(self) -> str:
        session_file = os.path.expanduser("~/.kiwi_session.json")
        if os.path.exists(session_file):
            try:
                with open(session_file) as f:
                    data = json.load(f)
                    if data.get("token"):
                        return f"Bearer {data['token']}"
            except Exception:
                pass
        bearer = os.environ.get("KIWI_BEARER_TOKEN")
        if bearer:
            return f"Bearer {bearer.removeprefix('Bearer ')}"
        env_key = self.profile.upper()
        client_id = os.environ.get(f"KIWI_CLIENT_ID_{env_key}") or os.environ.get("KIWI_CLIENT_ID")
        client_secret = os.environ.get(f"KIWI_CLIENT_SECRET_{env_key}") or os.environ.get(
            "KIWI_CLIENT_SECRET"
        )
        if not client_id or not client_secret:
            raise RuntimeError(
                f"Remote mode requires active session in ~/.kiwi_session.json or KIWI_CLIENT_ID_{env_key}"
            )
        basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
        resp = httpx.post(
            f"{self.remote_url}/api/v1/agent-auth/token",
            headers={"Authorization": f"Basic {basic}"},
            data={"grant_type": "client_credentials"},
            timeout=15.0,
        )
        resp.raise_for_status()
        return f"Bearer {resp.json()['access_token']}"

    def context(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/context",
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.agent_context(session=session, authorization=auth)

    def open_registers(self) -> dict[str, Any]:
        if self.remote_url:
            open_shifts = []
            for reg in ["REG-01", "CAJA-01", "default", "1", "01"]:
                try:
                    r = httpx.get(
                        f"{self.remote_url}/api/v1/cash/shifts/current",
                        params={"branch_id": self.branch_id, "register_id": reg},
                        headers={"Authorization": self._remote_token()},
                        timeout=5.0,
                    )
                    if r.status_code == 200:
                        shift = r.json().get("cash_shift")
                        if shift and shift.get("status") in ("OPEN", "CLOSING"):
                            open_shifts.append(shift)
                except Exception:
                    pass
            return {
                "branch_id": self.branch_id,
                "open_register_count": len(open_shifts),
                "open_registers": open_shifts,
            }
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            principal = agent_tools._agent(session, auth, None)
            agent_tools._capability(principal, "agent.sales.read")
            branch_id = agent_tools._branch(session, principal, self.branch_id)
            shifts = (
                session.execute(
                    sa.select(
                        models.cash_shifts.c.id,
                        models.cash_shifts.c.branch_id,
                        models.branches.c.name.label("branch_name"),
                        models.cash_shifts.c.register_code,
                        models.cash_shifts.c.status,
                        models.cash_shifts.c.opening_cash_cents,
                        models.cash_shifts.c.opened_at,
                        models.users.c.display_name.label("cashier_name"),
                    )
                    .join(models.branches, models.branches.c.id == models.cash_shifts.c.branch_id)
                    .outerjoin(models.users, models.users.c.id == models.cash_shifts.c.cashier_user_id)
                    .where(
                        models.cash_shifts.c.organization_id == principal.organization_id,
                        models.cash_shifts.c.branch_id == branch_id,
                        models.cash_shifts.c.status.in_(("OPEN", "CLOSING")),
                    )
                    .order_by(models.cash_shifts.c.opened_at.desc())
                )
                .mappings()
                .all()
            )
            items = []
            for s in shifts:
                shift_sales_cents = int(
                    session.scalar(
                        sa.select(
                            sa.func.coalesce(
                                sa.func.sum(models.sales_operation_snapshots.c.gross_cents), 0
                            )
                        ).where(
                            models.sales_operation_snapshots.c.cash_shift_id == s["id"],
                            models.sales_operation_snapshots.c.organization_id
                            == principal.organization_id,
                        )
                    )
                    or 0
                )
                shift_orders = int(
                    session.scalar(
                        sa.select(
                            sa.func.count(sa.distinct(models.sales_operation_snapshots.c.order_id))
                        ).where(
                            models.sales_operation_snapshots.c.cash_shift_id == s["id"],
                            models.sales_operation_snapshots.c.organization_id
                            == principal.organization_id,
                        )
                    )
                    or 0
                )
                items.append(
                    {
                        "cash_shift_id": s["id"],
                        "branch_id": s["branch_id"],
                        "branch_name": s["branch_name"],
                        "register_code": s["register_code"],
                        "status": s["status"],
                        "cashier_name": s["cashier_name"],
                        "opening_cash_cents": int(s["opening_cash_cents"]),
                        "opening_cash_mxn": f"{Decimal(s['opening_cash_cents']) / 100:.2f}",
                        "accumulated_sales_cents": shift_sales_cents,
                        "accumulated_sales_mxn": f"{Decimal(shift_sales_cents) / 100:.2f}",
                        "order_count": shift_orders,
                        "opened_at": s["opened_at"].isoformat()
                        if isinstance(s["opened_at"], datetime)
                        else str(s["opened_at"]),
                    }
                )
            return {
                "branch_id": branch_id,
                "open_register_count": len(items),
                "open_registers": items,
            }

    def sales_summary(self, from_utc: str | None = None, to_utc: str | None = None) -> dict[str, Any]:
        start, end = _window_bounds(from_utc, to_utc)
        if self.remote_url:
            try:
                resp = httpx.get(
                    f"{self.remote_url}/api/v1/agent-tools/sales/summary",
                    params={
                        "branch_id": self.branch_id,
                        "from_utc": start.isoformat(),
                        "to_utc": end.isoformat(),
                    },
                    headers={"Authorization": self._remote_token()},
                    timeout=15.0,
                )
                if resp.status_code == 200:
                    return resp.json()
            except Exception:
                pass
            # Fallback to orders endpoint
            resp_orders = httpx.get(
                f"{self.remote_url}/api/v1/orders",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            if resp_orders.status_code == 200:
                orders = resp_orders.json()
                total_cents = sum(o.get("total_cents", 0) for o in orders if o.get("status") in ("ACCEPTED", "FULFILLED", "COMPLETED"))
                last_order = orders[0] if orders else None
                return {
                    "branch_id": self.branch_id,
                    "order_count": len(orders),
                    "total_sales_cents": total_cents,
                    "total_sales_formatted": f"${total_cents / 100:,.2f} MXN",
                    "latest_order": last_order,
                }
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.get_agent_sales_summary(
                branch_id=self.branch_id,
                from_utc=start,
                to_utc=end,
                session=session,
                authorization=auth,
            )

    def payments_by_method(
        self, from_utc: str | None = None, to_utc: str | None = None
    ) -> dict[str, Any]:
        start, end = _window_bounds(from_utc, to_utc)
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/payments/by-method",
                params={
                    "branch_id": self.branch_id,
                    "from_utc": start.isoformat(),
                    "to_utc": end.isoformat(),
                },
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.get_agent_payments_by_method(
                branch_id=self.branch_id,
                from_utc=start,
                to_utc=end,
                session=session,
                authorization=auth,
            )

    def expenses_summary(
        self, from_utc: str | None = None, to_utc: str | None = None
    ) -> dict[str, Any]:
        start, end = _window_bounds(from_utc, to_utc)
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/expenses/summary",
                params={
                    "branch_id": self.branch_id,
                    "from_utc": start.isoformat(),
                    "to_utc": end.isoformat(),
                },
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.get_agent_expense_summary(
                branch_id=self.branch_id,
                from_utc=start,
                to_utc=end,
                session=session,
                authorization=auth,
            )

    def cash_cuts(self, from_utc: str | None = None, to_utc: str | None = None) -> dict[str, Any]:
        start, end = _window_bounds(from_utc, to_utc)
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/cash/cuts",
                params={
                    "branch_id": self.branch_id,
                    "from_utc": start.isoformat(),
                    "to_utc": end.isoformat(),
                },
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_cash_cuts(
                branch_id=self.branch_id,
                from_utc=start,
                to_utc=end,
                session=session,
                authorization=auth,
            )

    def daily_reconciliation(
        self, from_date: str | None = None, to_date: str | None = None
    ) -> dict[str, Any]:
        today_str = datetime.now(UTC).date().isoformat()
        f_date = from_date or today_str
        t_date = to_date or f_date
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/cash/daily-reconciliation",
                params={
                    "branch_id": self.branch_id,
                    "from_date": f_date,
                    "to_date": t_date,
                },
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.get_agent_cash_daily_reconciliation(
                branch_id=self.branch_id,
                from_date=f_date,
                to_date=t_date,
                session=session,
                authorization=auth,
            )

    def catalog_items(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/catalog/items",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_catalog(
                session=session,
                branch_id=self.branch_id,
                authorization=auth,
            )

    def inventory_items(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/inventory/items",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            data = agent_tools.list_agent_inventory_items(
                session=session,
                branch_id=self.branch_id,
                authorization=auth,
            )
            units = {
                str(r["id"]): r["code"]
                for r in session.execute(
                    sa.select(models.inventory_units.c.id, models.inventory_units.c.code).where(
                        models.inventory_units.c.organization_id == ORGANIZATION_ID
                    )
                ).mappings()
            }
            for item in data["items"]:
                item["unit_code"] = units.get(str(item["unit_id"]), "")
            return data

    def inventory_stock(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/inventory/stock",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            stock_page = agent_tools.list_agent_stock(
                branch_id=self.branch_id,
                session=session,
                authorization=auth,
            )
            item_lookup = {
                str(r["id"]): {"name": r["name"], "sku": r["sku"]}
                for r in session.execute(
                    sa.select(
                        models.inventory_items.c.id,
                        models.inventory_items.c.name,
                        models.inventory_items.c.sku,
                    ).where(models.inventory_items.c.organization_id == ORGANIZATION_ID)
                ).mappings()
            }
            unit_lookup = {
                str(r["id"]): r["code"]
                for r in session.execute(
                    sa.select(models.inventory_units.c.id, models.inventory_units.c.code).where(
                        models.inventory_units.c.organization_id == ORGANIZATION_ID
                    )
                ).mappings()
            }
            for row in stock_page["items"]:
                meta = item_lookup.get(str(row["item_id"]), {})
                row["item_name"] = meta.get("name", "")
                row["sku"] = meta.get("sku", "")
                row["unit_code"] = unit_lookup.get(str(row["unit_id"]), "")
                avail = Decimal(str(row["available_quantity"]))
                min_q = (
                    Decimal(str(row["min_quantity"]))
                    if row.get("min_quantity") is not None
                    else None
                )
                max_q = (
                    Decimal(str(row["max_quantity"]))
                    if row.get("max_quantity") is not None
                    else None
                )
                row["below_threshold"] = bool(min_q is not None and avail <= min_q)
                row["deficit_to_max"] = (
                    str(max(max_q - avail, Decimal("0")))
                    if (max_q is not None and min_q is not None and avail <= min_q)
                    else "0"
                )
            return stock_page

    def check_thresholds(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/admin-catalog/stock-thresholds",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            if resp.status_code == 200:
                raw_items = resp.json()
                configured = [x for x in raw_items if x.get("status") != "no_thresholds"]
                below_min = [x for x in configured if x.get("status") == "below_minimum"]
                return {
                    "branch_id": self.branch_id,
                    "total_items_checked": len(raw_items),
                    "items_with_thresholds_count": len(configured),
                    "items_below_threshold_count": len(below_min),
                    "items_below_threshold": below_min,
                    "all_configured_thresholds": configured,
                }
        stock_data = self.inventory_stock()
        alerts = [item for item in stock_data["items"] if item.get("below_threshold")]
        return {
            "branch_id": self.branch_id,
            "total_items_checked": len(stock_data["items"]),
            "items_below_threshold_count": len(alerts),
            "items_below_threshold": alerts,
        }

    def inventory_movements(
        self, from_utc: str | None = None, to_utc: str | None = None
    ) -> dict[str, Any]:
        start, end = _window_bounds(from_utc, to_utc)
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/inventory/movements",
                params={
                    "branch_id": self.branch_id,
                    "from_utc": start.isoformat(),
                    "to_utc": end.isoformat(),
                },
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_inventory_movements(
                branch_id=self.branch_id,
                from_utc=start,
                to_utc=end,
                session=session,
                authorization=auth,
            )

    def recipes(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/recipes",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            page = agent_tools.list_agent_recipes(
                session=session,
                branch_id=self.branch_id,
                authorization=auth,
            )
            prod_names = {
                str(r["id"]): {"name": r["name"], "sku": r["sku"]}
                for r in session.execute(
                    sa.select(
                        models.products.c.id, models.products.c.name, models.products.c.sku
                    ).where(models.products.c.organization_id == ORGANIZATION_ID)
                ).mappings()
            }
            item_names = {
                str(r["id"]): {"name": r["name"], "sku": r["sku"]}
                for r in session.execute(
                    sa.select(
                        models.inventory_items.c.id,
                        models.inventory_items.c.name,
                        models.inventory_items.c.sku,
                    ).where(models.inventory_items.c.organization_id == ORGANIZATION_ID)
                ).mappings()
            }
            for rec in page["items"]:
                pmeta = prod_names.get(str(rec["target_id"]), {})
                rec["product_name"] = pmeta.get("name", "")
                rec["product_sku"] = pmeta.get("sku", "")
                for comp in rec["components"]:
                    imeta = item_names.get(str(comp["item_id"]), {})
                    comp["item_name"] = imeta.get("name", "")
                    comp["item_sku"] = imeta.get("sku", "")
            return page

    def suppliers(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/suppliers",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_suppliers(
                branch_id=self.branch_id,
                session=session,
                authorization=auth,
            )

    def purchase_presentations(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/purchase-presentations",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_purchase_presentations(
                branch_id=self.branch_id,
                session=session,
                authorization=auth,
            )

    def purchase_history(
        self, from_utc: str | None = None, to_utc: str | None = None
    ) -> dict[str, Any]:
        start, end = _window_bounds(from_utc, to_utc)
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/purchases/history",
                params={
                    "branch_id": self.branch_id,
                    "from_utc": start.isoformat(),
                    "to_utc": end.isoformat(),
                },
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_purchase_history(
                branch_id=self.branch_id,
                from_utc=start,
                to_utc=end,
                session=session,
                authorization=auth,
            )

    def purchase_needs(self) -> dict[str, Any]:
        if self.remote_url:
            resp = httpx.get(
                f"{self.remote_url}/api/v1/agent-tools/purchase-needs",
                params={"branch_id": self.branch_id},
                headers={"Authorization": self._remote_token()},
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            return agent_tools.list_agent_purchase_needs(
                branch_id=self.branch_id,
                session=session,
                authorization=auth,
            )

    def propose_recipe(
        self,
        *,
        product_id: str,
        yield_quantity: str,
        yield_unit_id: str,
        components: list[dict[str, Any]],
        expected_active_recipe_id: str | None = None,
        scope_kind: str = "corporate",
        idempotency_key: str | None = None,
        apply_immediately: bool = False,
    ) -> dict[str, Any]:
        with self.factory() as session:
            if expected_active_recipe_id is None:
                expected_active_recipe_id = session.scalar(
                    sa.select(models.recipes.c.id)
                    .where(
                        models.recipes.c.product_id == product_id,
                        models.recipes.c.recipe_type == "sale",
                        models.recipes.c.branch_id.is_(None)
                        if scope_kind == "corporate"
                        else models.recipes.c.branch_id == self.branch_id,
                        models.recipes.c.status == "active",
                        models.recipes.c.valid_to.is_(None),
                    )
                    .order_by(models.recipes.c.version.desc())
                )
            scope_payload: dict[str, Any] = (
                {"kind": "corporate"}
                if scope_kind == "corporate"
                else {"kind": "branch", "branch_id": self.branch_id}
            )
            payload: dict[str, Any] = {
                "scope": scope_payload,
                "target_id": product_id,
                "expected_active_recipe_id": expected_active_recipe_id,
                "yield_quantity": str(yield_quantity),
                "yield_unit_id": yield_unit_id,
                "components": [
                    {
                        "item_id": str(c["item_id"]),
                        "unit_id": str(c["unit_id"]),
                        "net_quantity": str(c["net_quantity"]),
                        "waste_rate": str(c.get("waste_rate", "0")),
                    }
                    for c in components
                ],
            }
            idem_key = idempotency_key or (
                "kiwi-recipe-"
                + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
            )
            auth = _mint_local_agent_bearer(session, self.profile)
            operation = agent_tools.create_recipe_proposal(
                payload=payload,
                session=session,
                authorization=auth,
                idempotency_key=idem_key,
            )
            if apply_immediately and operation.get("resource_id"):
                applied = admin_ai.review_proposal(
                    session=session,
                    proposal_id=str(operation["resource_id"]),
                    actor_id=ADMIN_USER_ID,
                    accept=True,
                    idempotency_key=f"apply-{idem_key}",
                )
                return {
                    "operation": operation,
                    "applied_proposal": {
                        "proposal_id": applied["id"],
                        "status": applied["status"],
                        "applied_at": applied["applied_at"],
                        "new_recipe": applied["result"],
                    },
                }
            return {"operation": operation}

    def propose_catalog(
        self,
        *,
        action: str,
        fields: dict[str, Any],
        target_id: str | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
        apply_immediately: bool = False,
    ) -> dict[str, Any]:
        with self.factory() as session:
            payload: dict[str, Any] = {
                "scope": {"kind": "corporate"},
                "action": action,
                "target_id": target_id,
                "expected_version": expected_version,
                "fields": fields,
            }
            idem_key = idempotency_key or (
                "kiwi-cat-"
                + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
            )
            auth = _mint_local_agent_bearer(session, self.profile)
            operation = agent_tools.create_catalog_proposal(
                payload=payload,
                session=session,
                authorization=auth,
                idempotency_key=idem_key,
            )
            if apply_immediately and operation.get("resource_id"):
                applied = admin_ai.review_proposal(
                    session=session,
                    proposal_id=str(operation["resource_id"]),
                    actor_id=ADMIN_USER_ID,
                    accept=True,
                    idempotency_key=f"apply-{idem_key}",
                )
                return {
                    "operation": operation,
                    "applied_proposal": {
                        "proposal_id": applied["id"],
                        "status": applied["status"],
                        "result": applied["result"],
                    },
                }
            return {"operation": operation}

    def propose_inventory_item(
        self,
        *,
        sku: str,
        name: str,
        base_unit_id: str,
        idempotency_key: str | None = None,
        apply_immediately: bool = False,
    ) -> dict[str, Any]:
        with self.factory() as session:
            payload = {
                "scope": {"kind": "corporate"},
                "sku": sku,
                "name": name,
                "base_unit_id": base_unit_id,
                "item_type": "ingredient",
            }
            idem_key = idempotency_key or (
                "kiwi-inv-"
                + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
            )
            auth = _mint_local_agent_bearer(session, self.profile)
            operation = agent_tools.create_inventory_item_proposal(
                payload=payload,
                session=session,
                authorization=auth,
                idempotency_key=idem_key,
            )
            if apply_immediately and operation.get("resource_id"):
                applied = admin_ai.review_proposal(
                    session=session,
                    proposal_id=str(operation["resource_id"]),
                    actor_id=ADMIN_USER_ID,
                    accept=True,
                    idempotency_key=f"apply-{idem_key}",
                )
                return {
                    "operation": operation,
                    "applied_proposal": {
                        "proposal_id": applied["id"],
                        "status": applied["status"],
                        "result": applied["result"],
                    },
                }
            return {"operation": operation}

    def create_purchase_draft(
        self,
        *,
        supplier_id: str,
        folio: str,
        lines: list[dict[str, Any]],
        document_type: str = "invoice",
        document_date: str | None = None,
        payment_method: str = "transfer",
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        doc_date = document_date or datetime.now(UTC).date().isoformat()
        payload = {
            "branch_id": self.branch_id,
            "supplier_id": supplier_id,
            "document_type": document_type,
            "folio": folio,
            "document_date": doc_date,
            "payment_method": payment_method,
            "paid_from_cash": payment_method == "cash",
            "freight_total": "0",
            "lines": [
                {
                    "presentation_id": str(line["presentation_id"]),
                    "quantity": str(line["quantity"]),
                    "unit_price": str(line["unit_price"]),
                    "discount": str(line.get("discount", "0")),
                    "tax": str(line.get("tax", "0")),
                }
                for line in lines
            ],
        }
        idem_key = idempotency_key or (
            "kiwi-po-"
            + hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]
        )
        if self.remote_url:
            resp = httpx.post(
                f"{self.remote_url}/api/v1/agent-tools/purchase-drafts",
                headers={
                    "Authorization": self._remote_token(),
                    "Idempotency-Key": idem_key,
                },
                json=payload,
                timeout=15.0,
            )
            resp.raise_for_status()
            return resp.json()
        with self.factory() as session:
            auth = _mint_local_agent_bearer(session, self.profile)
            operation = agent_tools.create_purchase_draft(
                payload=payload,
                session=session,
                authorization=auth,
                idempotency_key=idem_key,
            )
            doc_row = (
                session.execute(
                    sa.select(
                        models.purchase_documents.c.id,
                        models.purchase_documents.c.folio,
                        models.purchase_documents.c.status,
                        models.purchase_documents.c.subtotal,
                        models.purchase_documents.c.total,
                        models.suppliers.c.commercial_name.label("supplier_name"),
                    )
                    .join(
                        models.suppliers,
                        models.suppliers.c.id == models.purchase_documents.c.supplier_id,
                    )
                    .where(models.purchase_documents.c.id == operation["resource_id"])
                )
                .mappings()
                .first()
            )
            return {
                "operation": operation,
                "purchase_draft": {
                    "id": str(doc_row["id"]),
                    "folio": doc_row["folio"],
                    "status": doc_row["status"],
                    "supplier_name": doc_row["supplier_name"],
                    "subtotal": str(doc_row["subtotal"]),
                    "total": str(doc_row["total"]),
                }
                if doc_row
                else None,
            }

    def auto_replenish_thresholds(self, dry_run: bool = False) -> dict[str, Any]:
        """Automated routine: inspect stock thresholds -> compute packages to reach max -> schedule purchase drafts."""
        inv_bridge = KiwiAgentBridge("inventory", self.branch_id)
        pur_bridge = KiwiAgentBridge("purchasing", self.branch_id)

        threshold_report = inv_bridge.check_thresholds()
        shortages = threshold_report["items_below_threshold"]
        if not shortages:
            return {
                "branch_id": self.branch_id,
                "status": "NO_SHORTAGES",
                "shortages_detected": 0,
                "scheduled_purchase_drafts": [],
            }

        presentations_page = pur_bridge.purchase_presentations()
        presentations_by_item: dict[str, list[dict[str, Any]]] = {}
        for pres in presentations_page["items"]:
            presentations_by_item.setdefault(str(pres["item_id"]), []).append(pres)

        grouped_by_supplier: dict[str, list[dict[str, Any]]] = {}
        replenishment_plan: list[dict[str, Any]] = []
        unmatched_items: list[dict[str, Any]] = []

        for item in shortages:
            item_id = str(item["item_id"])
            candidates = presentations_by_item.get(item_id, [])
            if not candidates:
                unmatched_items.append(item)
                continue
            candidates.sort(
                key=lambda c: (not bool(c.get("preferred")), Decimal(str(c["cost_per_base_unit"])))
            )
            chosen = candidates[0]
            deficit_base = Decimal(str(item["deficit_to_max"]))
            usable = Decimal(str(chosen["usable_content"]))
            packages_needed = max(1, int(math.ceil(deficit_base / usable)))
            unit_price = Decimal(str(chosen["last_net_price"]))

            line_spec = {
                "presentation_id": str(chosen["id"]),
                "presentation_name": chosen["name"],
                "item_id": item_id,
                "item_name": item["item_name"],
                "sku": item["sku"],
                "available_quantity": str(item["available_quantity"]),
                "min_quantity": str(item["min_quantity"]),
                "max_quantity": str(item["max_quantity"]),
                "deficit_base_units": str(deficit_base),
                "usable_content_per_package": str(usable),
                "quantity": str(packages_needed),
                "unit_price": str(unit_price),
                "estimated_line_total": str(unit_price * packages_needed),
                "discount": "0",
                "tax": "0",
            }
            replenishment_plan.append(line_spec)
            grouped_by_supplier.setdefault(str(chosen["supplier_id"]), []).append(line_spec)

        scheduled_drafts: list[dict[str, Any]] = []
        today_str = datetime.now(UTC).date().isoformat()
        if not dry_run:
            for supplier_id, supplier_lines in grouped_by_supplier.items():
                short_sup = supplier_id[-4:].upper()
                folio = f"AUTO-UMB-{today_str.replace('-', '')}-{short_sup}"
                idem_key = f"auto-replenish-{self.branch_id}-{supplier_id}-{today_str}"
                draft_res = pur_bridge.create_purchase_draft(
                    supplier_id=supplier_id,
                    folio=folio,
                    lines=supplier_lines,
                    document_type="invoice",
                    document_date=today_str,
                    payment_method="transfer",
                    idempotency_key=idem_key,
                )
                scheduled_drafts.append(draft_res)

        return {
            "branch_id": self.branch_id,
            "dry_run": dry_run,
            "status": "REPLENISHMENT_SCHEDULED" if not dry_run else "DRY_RUN_READY",
            "shortages_detected": len(shortages),
            "replenishment_lines": replenishment_plan,
            "unmatched_items": unmatched_items,
            "scheduled_purchase_drafts": scheduled_drafts,
        }

    def purchase_drafts(self) -> dict[str, Any]:
        with self.factory() as session:
            docs = (
                session.execute(
                    sa.select(
                        models.purchase_documents.c.id,
                        models.purchase_documents.c.branch_id,
                        models.purchase_documents.c.supplier_id,
                        models.suppliers.c.commercial_name.label("supplier_name"),
                        models.purchase_documents.c.folio,
                        models.purchase_documents.c.document_type,
                        models.purchase_documents.c.document_date,
                        models.purchase_documents.c.status,
                        models.purchase_documents.c.subtotal,
                        models.purchase_documents.c.total,
                        models.purchase_documents.c.created_at,
                    )
                    .join(
                        models.suppliers,
                        models.suppliers.c.id == models.purchase_documents.c.supplier_id,
                    )
                    .where(
                        models.purchase_documents.c.organization_id == ORGANIZATION_ID,
                        models.purchase_documents.c.branch_id == self.branch_id,
                    )
                    .order_by(models.purchase_documents.c.created_at.desc())
                )
                .mappings()
                .all()
            )
            items = []
            for d in docs:
                lines = [
                    {
                        "item_id": str(ln["item_id"]),
                        "presentation_id": str(ln["presentation_id"]),
                        "presentation_quantity": str(ln["presentation_quantity"]),
                        "base_quantity": str(ln["base_quantity"]),
                        "unit_price": str(ln["unit_price"]),
                        "line_total": str(ln["line_total"]),
                    }
                    for ln in session.execute(
                        sa.select(models.purchase_document_lines).where(
                            models.purchase_document_lines.c.purchase_document_id == d["id"]
                        )
                    ).mappings()
                ]
                items.append(
                    {
                        "id": str(d["id"]),
                        "branch_id": str(d["branch_id"]),
                        "supplier_id": str(d["supplier_id"]),
                        "supplier_name": d["supplier_name"],
                        "folio": d["folio"],
                        "document_type": d["document_type"],
                        "document_date": str(d["document_date"]),
                        "status": d["status"],
                        "subtotal": str(d["subtotal"]),
                        "total": str(d["total"]),
                        "lines": lines,
                    }
                )
            return {
                "branch_id": self.branch_id,
                "count": len(items),
                "purchase_documents": items,
            }

    def audit_log(self, limit: int = 20) -> dict[str, Any]:
        with self.factory() as session:
            events = [
                {
                    "id": str(e["id"]),
                    "action": e["action"],
                    "entity_type": e["entity_type"],
                    "entity_id": str(e["entity_id"]),
                    "actor_user_id": e["actor_user_id"],
                    "actor_agent_identity_id": e["actor_agent_identity_id"],
                    "payload": e["payload"],
                    "created_at": str(e["created_at"]),
                }
                for e in session.execute(
                    sa.select(models.audit_events)
                    .where(models.audit_events.c.organization_id == ORGANIZATION_ID)
                    .order_by(models.audit_events.c.created_at.desc())
                    .limit(limit)
                ).mappings()
            ]
            commands = [
                {
                    "operation_id": str(c["id"]),
                    "identity_id": str(c["identity_id"]),
                    "operation_type": c["operation_type"],
                    "idempotency_key": c["idempotency_key"],
                    "status": c["status"],
                    "resource_id": str(c["resource_id"]),
                    "created_at": str(c["created_at"]),
                }
                for c in session.execute(
                    sa.select(models.external_agent_commands)
                    .where(models.external_agent_commands.c.organization_id == ORGANIZATION_ID)
                    .order_by(models.external_agent_commands.c.created_at.desc())
                    .limit(limit)
                ).mappings()
            ]
            return {
                "recent_agent_commands": commands,
                "recent_audit_events": events,
            }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Canonical Kiwi Multi-Agent Operations CLI Bridge"
    )
    parser.add_argument(
        "--profile",
        choices=("administrator", "kitchen", "inventory", "purchasing"),
        default="administrator",
        help="Governed Kiwi agent identity profile",
    )
    parser.add_argument(
        "--branch-id",
        default=None,
        help="Branch UUID, code (e.g. BR-001), or name (default: Centro Histórico)",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("context", help="Read effective agent identity, capabilities, and branches")
    sub.add_parser("open-registers", help="List currently open cash registers and active shift totals")

    for cmd_name in (
        "sales-summary",
        "payments-by-method",
        "expenses-summary",
        "cash-cuts",
        "inventory-movements",
        "purchase-history",
    ):
        p = sub.add_parser(cmd_name)
        p.add_argument("--from-utc", default=None)
        p.add_argument("--to-utc", default=None)

    p_rec = sub.add_parser("daily-reconciliation")
    p_rec.add_argument("--from-date", default=None)
    p_rec.add_argument("--to-date", default=None)

    sub.add_parser("catalog-items")
    sub.add_parser("inventory-items")
    sub.add_parser("inventory-stock")
    sub.add_parser("check-thresholds")
    sub.add_parser("recipes")
    sub.add_parser("suppliers")
    sub.add_parser("purchase-presentations")
    sub.add_parser("purchase-needs")
    sub.add_parser("purchase-drafts")
    sub.add_parser("audit-log")

    p_prop_rec = sub.add_parser("propose-recipe", help="Create or apply a versioned recipe proposal")
    p_prop_rec.add_argument("--product-id", required=True)
    p_prop_rec.add_argument("--yield-quantity", default="1")
    p_prop_rec.add_argument(
        "--yield-unit-id", default="018f6f73-2d0a-74f0-8f1c-000000000304"
    )
    p_prop_rec.add_argument(
        "--components-json",
        required=True,
        help='JSON array of [{"item_id": "...", "unit_id": "...", "net_quantity": "...", "waste_rate": "0"}]',
    )
    p_prop_rec.add_argument("--expected-active-recipe-id", default=None)
    p_prop_rec.add_argument("--idempotency-key", default=None)
    p_prop_rec.add_argument(
        "--apply",
        action="store_true",
        help="Immediately review and apply the recipe version in domain",
    )

    p_apply_rec = sub.add_parser(
        "apply-recipe", help="Create and immediately activate a versioned recipe in Kiwi"
    )
    p_apply_rec.add_argument("--product-id", required=True)
    p_apply_rec.add_argument("--yield-quantity", default="1")
    p_apply_rec.add_argument(
        "--yield-unit-id", default="018f6f73-2d0a-74f0-8f1c-000000000304"
    )
    p_apply_rec.add_argument("--components-json", required=True)
    p_apply_rec.add_argument("--idempotency-key", default=None)

    p_prop_cat = sub.add_parser("propose-catalog")
    p_prop_cat.add_argument("--action", choices=("product.create", "product.update"), required=True)
    p_prop_cat.add_argument("--fields-json", required=True)
    p_prop_cat.add_argument("--target-id", default=None)
    p_prop_cat.add_argument("--expected-version", type=int, default=None)
    p_prop_cat.add_argument("--idempotency-key", default=None)
    p_prop_cat.add_argument("--apply", action="store_true")

    p_prop_inv = sub.add_parser("propose-inventory-item")
    p_prop_inv.add_argument("--sku", required=True)
    p_prop_inv.add_argument("--name", required=True)
    p_prop_inv.add_argument(
        "--base-unit-id", default="018f6f73-2d0a-74f0-8f1c-000000000301"
    )
    p_prop_inv.add_argument("--idempotency-key", default=None)
    p_prop_inv.add_argument("--apply", action="store_true")

    p_po = sub.add_parser("create-purchase-draft", help="Schedule a DRAFT purchase order")
    p_po.add_argument("--supplier-id", required=True)
    p_po.add_argument("--folio", required=True)
    p_po.add_argument("--lines-json", required=True)
    p_po.add_argument("--document-type", default="invoice")
    p_po.add_argument("--document-date", default=None)
    p_po.add_argument("--payment-method", default="transfer")
    p_po.add_argument("--idempotency-key", default=None)

    p_auto = sub.add_parser(
        "auto-replenish-thresholds",
        help="Check stock thresholds and automatically schedule purchase drafts for items at or below min_quantity",
    )
    p_auto.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    bridge = KiwiAgentBridge(profile=args.profile, branch_arg=args.branch_id)

    try:
        if args.command == "context":
            out = bridge.context()
        elif args.command == "open-registers":
            out = bridge.open_registers()
        elif args.command == "sales-summary":
            out = bridge.sales_summary(args.from_utc, args.to_utc)
        elif args.command == "payments-by-method":
            out = bridge.payments_by_method(args.from_utc, args.to_utc)
        elif args.command == "expenses-summary":
            out = bridge.expenses_summary(args.from_utc, args.to_utc)
        elif args.command == "cash-cuts":
            out = bridge.cash_cuts(args.from_utc, args.to_utc)
        elif args.command == "daily-reconciliation":
            out = bridge.daily_reconciliation(args.from_date, args.to_date)
        elif args.command == "catalog-items":
            out = bridge.catalog_items()
        elif args.command == "inventory-items":
            out = bridge.inventory_items()
        elif args.command == "inventory-stock":
            out = bridge.inventory_stock()
        elif args.command == "check-thresholds":
            out = bridge.check_thresholds()
        elif args.command == "inventory-movements":
            out = bridge.inventory_movements(args.from_utc, args.to_utc)
        elif args.command == "recipes":
            out = bridge.recipes()
        elif args.command == "suppliers":
            out = bridge.suppliers()
        elif args.command == "purchase-presentations":
            out = bridge.purchase_presentations()
        elif args.command == "purchase-needs":
            out = bridge.purchase_needs()
        elif args.command == "purchase-drafts":
            out = bridge.purchase_drafts()
        elif args.command == "audit-log":
            out = bridge.audit_log()
        elif args.command in ("propose-recipe", "apply-recipe"):
            out = bridge.propose_recipe(
                product_id=args.product_id,
                yield_quantity=args.yield_quantity,
                yield_unit_id=args.yield_unit_id,
                components=json.loads(args.components_json),
                expected_active_recipe_id=getattr(args, "expected_active_recipe_id", None),
                idempotency_key=args.idempotency_key,
                apply_immediately=(args.command == "apply-recipe" or bool(getattr(args, "apply", False))),
            )
        elif args.command == "propose-catalog":
            out = bridge.propose_catalog(
                action=args.action,
                fields=json.loads(args.fields_json),
                target_id=args.target_id,
                expected_version=args.expected_version,
                idempotency_key=args.idempotency_key,
                apply_immediately=args.apply,
            )
        elif args.command == "propose-inventory-item":
            out = bridge.propose_inventory_item(
                sku=args.sku,
                name=args.name,
                base_unit_id=args.base_unit_id,
                idempotency_key=args.idempotency_key,
                apply_immediately=args.apply,
            )
        elif args.command == "create-purchase-draft":
            out = bridge.create_purchase_draft(
                supplier_id=args.supplier_id,
                folio=args.folio,
                lines=json.loads(args.lines_json),
                document_type=args.document_type,
                document_date=args.document_date,
                payment_method=args.payment_method,
                idempotency_key=args.idempotency_key,
            )
        elif args.command == "auto-replenish-thresholds":
            out = bridge.auto_replenish_thresholds(dry_run=args.dry_run)
        else:
            parser.error(f"Unknown command: {args.command}")
            return 2
    except HTTPException as exc:
        print(
            json.dumps(
                {"error": True, "status_code": exc.status_code, "detail": exc.detail},
                indent=2,
                ensure_ascii=False,
                default=str,
            )
        )
        return 1

    print(json.dumps(out, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
