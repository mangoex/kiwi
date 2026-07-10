from __future__ import annotations

# ruff: noqa: E501
"""minimum catalog

Revision ID: 202607072030
Revises: 202607071900
Create Date: 2026-07-07 20:30:00
"""

from collections.abc import Sequence
from datetime import datetime, timezone
UTC = timezone.utc

UTC = UTC

import sqlalchemy as sa
from alembic import op

revision: str = "202607072030"
down_revision: str | None = "202607071900"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
FOOD_CATEGORY_ID = "018f6f73-2d0a-74f0-8f1c-000000000101"
DRINK_CATEGORY_ID = "018f6f73-2d0a-74f0-8f1c-000000000102"
BURGER_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
FRIES_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000112"
SODA_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000113"
BURGER_PRICE_ID = "018f6f73-2d0a-74f0-8f1c-000000000121"
FRIES_PRICE_ID = "018f6f73-2d0a-74f0-8f1c-000000000122"
SODA_PRICE_ID = "018f6f73-2d0a-74f0-8f1c-000000000123"


def upgrade() -> None:
    op.create_table(
        "product_categories",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "name", name="uq_product_categories_org_name"),
    )
    op.create_table(
        "products",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column(
            "organization_id",
            sa.String(length=36),
            sa.ForeignKey("organizations.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "category_id",
            sa.String(length=36),
            sa.ForeignKey("product_categories.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("sku", sa.String(length=64), nullable=False),
        sa.Column("description", sa.String(length=360), nullable=True),
        sa.Column("station", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organization_id", "sku", name="uq_products_org_sku"),
    )
    op.create_table(
        "price_versions",
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
        sa.Column("price_cents", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="MXN"),
        sa.Column("valid_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("valid_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "branch_product_availability",
        sa.Column(
            "branch_id",
            sa.String(length=36),
            sa.ForeignKey("branches.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "product_id",
            sa.String(length=36),
            sa.ForeignKey("products.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    _seed_catalog()


def downgrade() -> None:
    op.drop_table("branch_product_availability")
    op.drop_table("price_versions")
    op.drop_table("products")
    op.drop_table("product_categories")


def _seed_catalog() -> None:
    now = datetime(2026, 7, 7, 20, 30, tzinfo=UTC)
    categories = sa.table(
        "product_categories",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("name"),
        sa.column("display_order"),
        sa.column("status"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    products = sa.table(
        "products",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("category_id"),
        sa.column("name"),
        sa.column("sku"),
        sa.column("description"),
        sa.column("station"),
        sa.column("status"),
        sa.column("created_at"),
        sa.column("updated_at"),
    )
    prices = sa.table(
        "price_versions",
        sa.column("id"),
        sa.column("organization_id"),
        sa.column("product_id"),
        sa.column("price_cents"),
        sa.column("currency"),
        sa.column("valid_from"),
        sa.column("valid_to"),
        sa.column("created_at"),
    )
    availability = sa.table(
        "branch_product_availability",
        sa.column("branch_id"),
        sa.column("product_id"),
        sa.column("is_available"),
        sa.column("updated_at"),
    )

    op.bulk_insert(
        categories,
        [
            {
                "id": FOOD_CATEGORY_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Comida",
                "display_order": 10,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": DRINK_CATEGORY_ID,
                "organization_id": ORGANIZATION_ID,
                "name": "Bebidas",
                "display_order": 20,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.bulk_insert(
        products,
        [
            {
                "id": BURGER_PRODUCT_ID,
                "organization_id": ORGANIZATION_ID,
                "category_id": FOOD_CATEGORY_ID,
                "name": "Hamburguesa Kiwi",
                "sku": "KIWI-BURGER",
                "description": "Producto semilla para flujo POS.",
                "station": "kitchen",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": FRIES_PRODUCT_ID,
                "organization_id": ORGANIZATION_ID,
                "category_id": FOOD_CATEGORY_ID,
                "name": "Papas",
                "sku": "KIWI-FRIES",
                "description": "Producto semilla para empaque.",
                "station": "kitchen",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": SODA_PRODUCT_ID,
                "organization_id": ORGANIZATION_ID,
                "category_id": DRINK_CATEGORY_ID,
                "name": "Refresco",
                "sku": "KIWI-SODA",
                "description": "Producto semilla para bebidas.",
                "station": "drinks",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ],
    )
    op.bulk_insert(
        prices,
        [
            {
                "id": BURGER_PRICE_ID,
                "organization_id": ORGANIZATION_ID,
                "product_id": BURGER_PRODUCT_ID,
                "price_cents": 9500,
                "currency": "MXN",
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
            {
                "id": FRIES_PRICE_ID,
                "organization_id": ORGANIZATION_ID,
                "product_id": FRIES_PRODUCT_ID,
                "price_cents": 4500,
                "currency": "MXN",
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
            {
                "id": SODA_PRICE_ID,
                "organization_id": ORGANIZATION_ID,
                "product_id": SODA_PRODUCT_ID,
                "price_cents": 3000,
                "currency": "MXN",
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
        ],
    )
    op.bulk_insert(
        availability,
        [
            {
                "branch_id": BRANCH_ID,
                "product_id": BURGER_PRODUCT_ID,
                "is_available": True,
                "updated_at": now,
            },
            {
                "branch_id": BRANCH_ID,
                "product_id": FRIES_PRODUCT_ID,
                "is_available": True,
                "updated_at": now,
            },
            {
                "branch_id": BRANCH_ID,
                "product_id": SODA_PRODUCT_ID,
                "is_available": True,
                "updated_at": now,
            },
        ],
    )
