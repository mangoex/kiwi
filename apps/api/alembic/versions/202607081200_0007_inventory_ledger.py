# ruff: noqa: E501
"""inventory ledger

Revision ID: 202607081200
Revises: 202607080010
Create Date: 2026-07-08 12:00:00
"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "202607081200"
down_revision: str | None = "202607080010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
WAREHOUSE_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"
BURGER_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
FRIES_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000112"
SODA_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000113"
UNIT_GRAM_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
UNIT_ML_ID = "018f6f73-2d0a-74f0-8f1c-000000000302"
UNIT_PIECE_ID = "018f6f73-2d0a-74f0-8f1c-000000000303"
BEEF_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
BUN_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000312"
POTATO_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000313"
SYRUP_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000314"
BURGER_RECIPE_ID = "018f6f73-2d0a-74f0-8f1c-000000000321"
FRIES_RECIPE_ID = "018f6f73-2d0a-74f0-8f1c-000000000322"
SODA_RECIPE_ID = "018f6f73-2d0a-74f0-8f1c-000000000323"


def upgrade() -> None:
    op.create_table(
        "inventory_units",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=24), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("precision_scale", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "code", name="uq_inventory_units_org_code"),
    )
    op.create_table(
        "inventory_items",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column(
            "base_unit_id",
            sa.String(length=36),
            sa.ForeignKey("inventory_units.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(length=32), nullable=False, server_default="ingredient"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "sku", name="uq_inventory_items_org_sku"),
    )
    op.create_table(
        "recipes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("yield_quantity", sa.Integer(), nullable=False),
        sa.Column(
            "yield_unit_id",
            sa.String(length=36),
            sa.ForeignKey("inventory_units.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("product_id", "version", name="uq_recipes_product_version"),
    )
    op.create_table(
        "recipe_components",
        sa.Column(
            "recipe_id",
            sa.String(length=36),
            sa.ForeignKey("recipes.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "item_id",
            sa.String(length=36),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("quantity_base_units", sa.Integer(), nullable=False),
    )
    op.create_table(
        "inventory_movements",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.String(length=36),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.String(length=36),
            sa.ForeignKey("inventory_items.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("movement_type", sa.String(length=48), nullable=False),
        sa.Column("quantity_delta", sa.Integer(), nullable=False),
        sa.Column(
            "unit_id",
            sa.String(length=36),
            sa.ForeignKey("inventory_units.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(length=240), nullable=False),
        sa.Column("source_type", sa.String(length=80), nullable=True),
        sa.Column("source_id", sa.String(length=36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_inventory_movements_item_created", "inventory_movements", ["item_id", "created_at"]
    )
    _seed_inventory()


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_item_created", table_name="inventory_movements")
    op.drop_table("inventory_movements")
    op.drop_table("recipe_components")
    op.drop_table("recipes")
    op.drop_table("inventory_items")
    op.drop_table("inventory_units")


def _seed_inventory() -> None:
    now = datetime(2026, 7, 8, 12, 0, tzinfo=UTC)
    units = sa.table(
        "inventory_units",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("code"),
        sa.column("name"),
        sa.column("precision_scale"),
        sa.column("created_at"),
    )
    items = sa.table(
        "inventory_items",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("name"),
        sa.column("sku"),
        sa.column("base_unit_id"),
        sa.column("item_type"),
        sa.column("status"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    recipes = sa.table(
        "recipes",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("product_id"),
        sa.column("version"),
        sa.column("status"),
        sa.column("yield_quantity"),
        sa.column("yield_unit_id"),
        sa.column("created_at"),
    )
    components = sa.table(
        "recipe_components",
        sa.column("recipe_id"),
        sa.column("item_id"),
        sa.column("quantity_base_units"),
    )
    movements = sa.table(
        "inventory_movements",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("branch_id"),
        sa.column("warehouse_id"),
        sa.column("item_id"),
        sa.column("movement_type"),
        sa.column("quantity_delta"),
        sa.column("unit_id"),
        sa.column("reason"),
        sa.column("source_type"),
        sa.column("source_id"),
        sa.column("created_at"),
    )
    op.bulk_insert(
        units,
        [
            {
                "id": UNIT_GRAM_ID,
                "organization_id": ORGANIZATION_ID,
                "code": "g",
                "name": "Gramo",
                "precision_scale": 0,
                "created_at": now,
            },
            {
                "id": UNIT_ML_ID,
                "organization_id": ORGANIZATION_ID,
                "code": "ml",
                "name": "Mililitro",
                "precision_scale": 0,
                "created_at": now,
            },
            {
                "id": UNIT_PIECE_ID,
                "organization_id": ORGANIZATION_ID,
                "code": "pz",
                "name": "Pieza",
                "precision_scale": 0,
                "created_at": now,
            },
        ],
    )
    op.bulk_insert(
        items,
        [
            {
                "id": BEEF_ITEM_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Carne molida",
                "sku": "INV-BEEF",
                "base_unit_id": UNIT_GRAM_ID,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": BUN_ITEM_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Pan brioche",
                "sku": "INV-BUN",
                "base_unit_id": UNIT_PIECE_ID,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": POTATO_ITEM_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Papa blanca",
                "sku": "INV-POTATO",
                "base_unit_id": UNIT_GRAM_ID,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": SYRUP_ITEM_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Jarabe refresco",
                "sku": "INV-SYRUP",
                "base_unit_id": UNIT_ML_ID,
                "item_type": "ingredient",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.bulk_insert(
        recipes,
        [
            {
                "id": BURGER_RECIPE_ID,
                "organization_id": ORGANIZATION_ID,
                "product_id": BURGER_PRODUCT_ID,
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": UNIT_PIECE_ID,
                "created_at": now,
            },
            {
                "id": FRIES_RECIPE_ID,
                "organization_id": ORGANIZATION_ID,
                "product_id": FRIES_PRODUCT_ID,
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": UNIT_PIECE_ID,
                "created_at": now,
            },
            {
                "id": SODA_RECIPE_ID,
                "organization_id": ORGANIZATION_ID,
                "product_id": SODA_PRODUCT_ID,
                "version": 1,
                "status": "active",
                "yield_quantity": 1,
                "yield_unit_id": UNIT_PIECE_ID,
                "created_at": now,
            },
        ],
    )
    op.bulk_insert(
        components,
        [
            {"recipe_id": BURGER_RECIPE_ID, "item_id": BEEF_ITEM_ID, "quantity_base_units": 120},
            {"recipe_id": BURGER_RECIPE_ID, "item_id": BUN_ITEM_ID, "quantity_base_units": 1},
            {"recipe_id": FRIES_RECIPE_ID, "item_id": POTATO_ITEM_ID, "quantity_base_units": 180},
            {"recipe_id": SODA_RECIPE_ID, "item_id": SYRUP_ITEM_ID, "quantity_base_units": 80},
        ],
    )
    op.bulk_insert(
        movements,
        [
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000331",
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "warehouse_id": WAREHOUSE_ID,
                "item_id": BEEF_ITEM_ID,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 25000,
                "unit_id": UNIT_GRAM_ID,
                "reason": "Saldo inicial semilla",
                "source_type": "migration",
                "source_id": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000332",
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "warehouse_id": WAREHOUSE_ID,
                "item_id": BUN_ITEM_ID,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 120,
                "unit_id": UNIT_PIECE_ID,
                "reason": "Saldo inicial semilla",
                "source_type": "migration",
                "source_id": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000333",
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "warehouse_id": WAREHOUSE_ID,
                "item_id": POTATO_ITEM_ID,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 35000,
                "unit_id": UNIT_GRAM_ID,
                "reason": "Saldo inicial semilla",
                "source_type": "migration",
                "source_id": None,
                "created_at": now,
            },
            {
                "id": "018f6f73-2d0a-74f0-8f1c-000000000334",
                "organization_id": ORGANIZATION_ID,
                "branch_id": BRANCH_ID,
                "warehouse_id": WAREHOUSE_ID,
                "item_id": SYRUP_ITEM_ID,
                "movement_type": "OPENING_BALANCE",
                "quantity_delta": 10000,
                "unit_id": UNIT_ML_ID,
                "reason": "Saldo inicial semilla",
                "source_type": "migration",
                "source_id": None,
                "created_at": now,
            },
        ],
    )
