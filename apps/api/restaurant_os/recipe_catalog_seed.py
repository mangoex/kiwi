"""Append-only publisher for the reviewed SoftRestaurant recipe manifest.

This module intentionally contains no PDF/XLS parsing and never updates or deletes
catalogue history.  It is a manually invoked data operation, never an Alembic or
application-startup migration.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session

from . import models
from .config import get_settings
from .database import get_engine

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
MANIFEST_PATH = Path(__file__).with_name("data") / "recipes_catalog_data.json"
MANIFEST_SHA256 = "34f9bf8bde3f523abeed0d5e87f38b5d9e26a6b30b92f3876c1a637df2cea492"
MANIFEST_RECIPE_COUNT = 329
MANIFEST_MODIFIER_COUNT = 14
PUBLISHABLE_RECIPE_COUNT = 315
PUBLISHABLE_COMPONENT_COUNT = 1413
PRESERVED_SKU = "06002"
PRODUCTION_SCHEMA_HEAD = "0053_cash_offline_sync"
PRODUCTION_PLAN_CONFIRMATION = "314-recipes-preserve-06002"
MISSING_PRODUCT_SKUS = frozenset(
    {"11057", "24001", "24002", "24003", "24004", "24005", "24006", "24007"}
)
MISSING_PRODUCT_PRICE_CENTS = {
    "11057": 3000,
    "24001": 5000,
    "24002": 5500,
    "24003": 7500,
    "24004": 7000,
    "24005": 7500,
    "24006": 10000,
    "24007": 11000,
}
MISSING_ITEM_SPECS = {
    "001026": ("CAFE MOLIDO", "KILO"),
    "001027": ("MACCHA", "KILO"),
    "001028": ("PROTEINA", "KILO"),
}
PRODUCT_CATEGORY_BY_SKU = {
    "11057": "INGREDIENTE EXTRA",
    "24001": "CAFE Y MACCHA",
    "24002": "CAFE Y MACCHA",
    "24003": "CAFE Y MACCHA",
    "24004": "CAFE Y MACCHA",
    "24005": "CAFE Y MACCHA",
    "24006": "CAFE Y MACCHA",
    "24007": "CAFE Y MACCHA",
}
APPROVED_CATEGORY_SPECS = {"CAFE Y MACCHA": {"display_order": 2}}
UNIT_CODES = {
    "KILO": frozenset({"KG", "KILO"}),
    "LITRO": frozenset({"L", "LT", "LITRO"}),
    "PZA": frozenset({"PZ", "PZA", "PIEZA"}),
}


class RecipeCatalogSeedError(RuntimeError):
    """Raised before any write when the immutable manifest cannot be resolved safely."""


@dataclass(frozen=True)
class SeedPlan:
    recipes: tuple[dict[str, Any], ...]
    skipped_modifiers: tuple[str, ...]
    product_ids: dict[str, str]
    item_ids: dict[str, tuple[str, str]]
    unit_ids: dict[str, str]
    create_products: tuple[dict[str, Any], ...]
    create_items: tuple[dict[str, Any], ...]
    create_categories: tuple[str, ...]
    recipes_to_seed: tuple[str, ...]
    recipes_to_replay: tuple[str, ...]
    preserved_skus: tuple[str, ...]

    def report(self, *, applied: bool) -> dict[str, Any]:
        return {
            "applied": applied,
            "manifest_recipes": MANIFEST_RECIPE_COUNT,
            "skipped_modifiers": len(self.skipped_modifiers),
            "publishable_recipes": len(self.recipes),
            "preserved_skus": list(self.preserved_skus),
            "recipes_to_seed": len(self.recipes_to_seed),
            "recipes_replayed": len(self.recipes_to_replay),
            "components_to_seed": sum(
                len(recipe["components"])
                for recipe in self.recipes
                if recipe["sku"] in self.recipes_to_seed
            ),
            "products_to_create": [product["sku"] for product in self.create_products],
            "items_to_create": [item["sku"] for item in self.create_items],
            "categories_to_create": list(self.create_categories),
            "resolved_product_skus": sorted(self.product_ids),
            "resolved_item_skus": sorted(self.item_ids),
        }


def _id(kind: str, organization_id: str, key: str) -> str:
    namespace_key = f"restaurantos:recipe-catalog-v1:{kind}:{organization_id}:{key}"
    return str(uuid5(NAMESPACE_URL, namespace_key))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _sku(value: object) -> str:
    raw = _source_sku(value)
    return str(int(raw)) if raw.isdigit() else raw


def _source_sku(value: object) -> str:
    raw = str(value).strip().upper().lstrip("'")
    for prefix in ("PROD-", "INS-"):
        if raw.startswith(prefix):
            raw = raw[len(prefix) :]
    if not raw:
        raise RecipeCatalogSeedError("empty catalog SKU")
    return raw


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise RecipeCatalogSeedError(f"invalid decimal for {label}") from exc
    exponent = result.as_tuple().exponent
    if not result.is_finite() or not isinstance(exponent, int) or exponent < -6:
        raise RecipeCatalogSeedError(f"decimal precision exceeds NUMERIC(18,6) for {label}")
    return result


def _load_manifest() -> tuple[tuple[dict[str, Any], ...], tuple[str, ...]]:
    try:
        manifest_bytes = MANIFEST_PATH.read_bytes()
        if hashlib.sha256(manifest_bytes).hexdigest() != MANIFEST_SHA256:
            raise RecipeCatalogSeedError("canonical recipe manifest hash differs")
        raw = json.loads(manifest_bytes)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise RecipeCatalogSeedError("canonical recipe manifest is unavailable or invalid") from exc
    if not isinstance(raw, list) or len(raw) != MANIFEST_RECIPE_COUNT:
        raise RecipeCatalogSeedError("unexpected canonical recipe manifest count")
    recipes: list[dict[str, Any]] = []
    modifiers: list[str] = []
    seen: set[str] = set()
    total_components = 0
    for entry in raw:
        if not isinstance(entry, dict):
            raise RecipeCatalogSeedError("recipe manifest entry must be an object")
        sku = _source_sku(entry.get("sku"))
        name = str(entry.get("name", "")).strip()
        group = str(entry.get("group", "")).strip()
        if not name or len(name) > 160 or not group or len(sku) > 64 or sku in seen:
            raise RecipeCatalogSeedError(f"invalid recipe identity for {sku}")
        seen.add(sku)
        components = entry.get("components")
        if not isinstance(components, list):
            raise RecipeCatalogSeedError(f"recipe {sku} components are invalid")
        if sku.startswith("25") and len(sku) == 5:
            modifiers.append(sku)
            continue
        normalized_components: list[dict[str, Any]] = []
        component_skus: set[str] = set()
        for component in components:
            if not isinstance(component, dict):
                raise RecipeCatalogSeedError(f"recipe {sku} component is invalid")
            item_sku = _source_sku(component.get("insumo_sku"))
            item_name = str(component.get("insumo_name", "")).strip()
            unit = str(component.get("unit", "")).strip().upper()
            quantity = _decimal(component.get("quantity"), f"{sku}/{item_sku}")
            if not item_name or len(item_name) > 160 or unit not in UNIT_CODES:
                raise RecipeCatalogSeedError(f"recipe {sku} component metadata is invalid")
            if quantity <= 0:
                continue
            if item_sku in component_skus:
                raise RecipeCatalogSeedError(f"recipe {sku} repeats component {item_sku}")
            component_skus.add(item_sku)
            normalized_components.append(
                {"sku": item_sku, "name": item_name, "unit": unit, "quantity": quantity}
            )
        if not normalized_components:
            raise RecipeCatalogSeedError(f"recipe {sku} has no positive components")
        total_components += len(normalized_components)
        recipes.append(
            {
                "sku": sku,
                "name": name,
                "group": group,
                "price": _decimal(entry.get("price"), sku),
                "components": tuple(normalized_components),
            }
        )
    if len(modifiers) != MANIFEST_MODIFIER_COUNT or len(recipes) != PUBLISHABLE_RECIPE_COUNT:
        raise RecipeCatalogSeedError("unexpected modifier or publishable recipe count")
    if total_components != PUBLISHABLE_COMPONENT_COUNT:
        raise RecipeCatalogSeedError("unexpected publishable component count")
    return tuple(recipes), tuple(modifiers)


def _unique_mapping(rows: Sequence[Any], key: str, entity: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for row in rows:
        normalized = _sku(row[key])
        if normalized in result:
            raise RecipeCatalogSeedError(f"ambiguous active {entity} SKU {normalized}")
        result[normalized] = row
    return result


def _unit_ids(session: Session, organization_id: str) -> dict[str, str]:
    rows = (
        session.execute(
            sa.select(models.inventory_units.c.id, models.inventory_units.c.code).where(
                models.inventory_units.c.organization_id == organization_id
            )
        )
        .mappings()
        .all()
    )
    result: dict[str, str] = {}
    for unit, codes in UNIT_CODES.items():
        exact = [str(row["id"]) for row in rows if str(row["code"]).upper() == unit]
        matches = exact or [str(row["id"]) for row in rows if str(row["code"]).upper() in codes]
        if len(matches) != 1:
            raise RecipeCatalogSeedError(
                f"expected one inventory unit for {unit}, got {len(matches)}"
            )
        result[unit] = matches[0]
    return result


def build_seed_plan(session: Session, organization_id: str = ORGANIZATION_ID) -> SeedPlan:
    """Validate every reference and return a write-free, deterministic seed plan."""
    recipes, modifiers = _load_manifest()
    units = _unit_ids(session, organization_id)
    unit_codes = {
        str(row["id"]): str(row["code"]).upper()
        for row in session.execute(
            sa.select(models.inventory_units.c.id, models.inventory_units.c.code).where(
                models.inventory_units.c.organization_id == organization_id
            )
        )
        .mappings()
        .all()
    }
    active_products = _unique_mapping(
        session.execute(
            sa.select(models.products.c.id, models.products.c.sku).where(
                models.products.c.organization_id == organization_id,
                models.products.c.status == "active",
            )
        )
        .mappings()
        .all(),
        "sku",
        "product",
    )
    active_items = _unique_mapping(
        session.execute(
            sa.select(
                models.inventory_items.c.id,
                models.inventory_items.c.sku,
                models.inventory_items.c.base_unit_id,
            ).where(
                models.inventory_items.c.organization_id == organization_id,
                models.inventory_items.c.status == "active",
            )
        )
        .mappings()
        .all(),
        "sku",
        "inventory item",
    )
    product_statuses = {
        _sku(row["sku"]): str(row["status"])
        for row in session.execute(
            sa.select(models.products.c.sku, models.products.c.status).where(
                models.products.c.organization_id == organization_id
            )
        )
        .mappings()
        .all()
    }
    item_statuses = {
        _sku(row["sku"]): str(row["status"])
        for row in session.execute(
            sa.select(models.inventory_items.c.sku, models.inventory_items.c.status).where(
                models.inventory_items.c.organization_id == organization_id
            )
        )
        .mappings()
        .all()
    }
    manifest_by_sku = {recipe["sku"]: recipe for recipe in recipes}
    inactive_products = sorted(
        sku
        for sku in manifest_by_sku
        if _sku(sku) not in active_products and _sku(sku) in product_statuses
    )
    if inactive_products:
        raise RecipeCatalogSeedError(f"catalog product is inactive: {inactive_products}")
    item_specs: dict[str, tuple[str, str]] = {}
    for recipe in recipes:
        for component in recipe["components"]:
            specification = (component["name"], component["unit"])
            existing_specification = item_specs.setdefault(component["sku"], specification)
            if existing_specification != specification:
                raise RecipeCatalogSeedError(
                    f"inconsistent manifest inventory item {component['sku']}"
                )
    inactive_items = sorted(
        sku for sku in item_specs if _sku(sku) not in active_items and _sku(sku) in item_statuses
    )
    if inactive_items:
        raise RecipeCatalogSeedError(f"catalog inventory item is inactive: {inactive_items}")
    missing_products = {sku for sku in manifest_by_sku if _sku(sku) not in active_products}
    missing_items = {sku for sku in item_specs if _sku(sku) not in active_items}
    if missing_products not in (set(), MISSING_PRODUCT_SKUS):
        raise RecipeCatalogSeedError(
            f"unexpected missing active products: {sorted(missing_products)}"
        )
    if missing_items not in (set(), set(MISSING_ITEM_SPECS)):
        raise RecipeCatalogSeedError(
            f"unexpected missing active inventory items: {sorted(missing_items)}"
        )
    create_products = tuple(manifest_by_sku[sku] for sku in sorted(missing_products))
    create_items = tuple(
        {"sku": sku, "name": name, "unit": unit}
        for sku, (name, unit) in sorted(MISSING_ITEM_SPECS.items())
        if sku in missing_items
    )
    product_ids = {
        sku: str(active_products[_sku(sku)]["id"])
        for sku in manifest_by_sku
        if _sku(sku) in active_products
    }
    product_ids.update(
        {
            product["sku"]: _id("product", organization_id, product["sku"])
            for product in create_products
        }
    )
    item_ids = {
        sku: (str(active_items[_sku(sku)]["id"]), str(active_items[_sku(sku)]["base_unit_id"]))
        for sku in item_specs
        if _sku(sku) in active_items
    }
    item_ids.update(
        {
            item["sku"]: (_id("item", organization_id, item["sku"]), units[item["unit"]])
            for item in create_items
        }
    )
    for recipe in recipes:
        for component in recipe["components"]:
            item_unit = unit_codes.get(item_ids[component["sku"]][1])
            if item_unit not in UNIT_CODES[component["unit"]]:
                raise RecipeCatalogSeedError(
                    f"unit mismatch for {recipe['sku']}/{component['sku']}"
                )
    recipes_to_seed: list[str] = []
    recipes_to_replay: list[str] = []
    preserved_skus: list[str] = []
    for recipe in recipes:
        recipe_id = _id("recipe", organization_id, recipe["sku"])
        if (
            session.execute(
                sa.select(models.recipes.c.id).where(models.recipes.c.id == recipe_id)
            ).scalar_one_or_none()
            is not None
        ):
            recipes_to_replay.append(recipe["sku"])
            continue
        if (
            session.execute(
                sa.select(models.recipes.c.id).where(
                    models.recipes.c.product_id == product_ids[recipe["sku"]]
                )
            )
            .scalars()
            .first()
            is not None
        ):
            preserved_skus.append(recipe["sku"])
            continue
        recipes_to_seed.append(recipe["sku"])
    create_categories = _plan_product_categories(
        session,
        organization_id,
        {PRODUCT_CATEGORY_BY_SKU[product["sku"]] for product in create_products},
    )
    plan = SeedPlan(
        recipes,
        modifiers,
        product_ids,
        item_ids,
        units,
        create_products,
        create_items,
        create_categories,
        tuple(recipes_to_seed),
        tuple(recipes_to_replay),
        tuple(preserved_skus),
    )
    recipes_by_sku = {recipe["sku"]: recipe for recipe in recipes}
    for sku in plan.recipes_to_replay:
        _assert_recipe(
            session,
            _id("recipe", organization_id, sku),
            recipes_by_sku[sku],
            plan,
            organization_id,
        )
    _assert_catalog_product_categories(session, plan, organization_id)
    return plan


def _active_category_id(session: Session, organization_id: str, name: str) -> str:
    rows = (
        session.execute(
            sa.select(
                models.product_categories.c.id,
                models.product_categories.c.display_order,
            ).where(
                models.product_categories.c.organization_id == organization_id,
                models.product_categories.c.name == name,
                models.product_categories.c.status == "active",
            )
        )
        .mappings()
        .all()
    )
    if len(rows) != 1:
        raise RecipeCatalogSeedError(f"required active product category is unavailable: {name}")
    row = rows[0]
    expected = APPROVED_CATEGORY_SPECS.get(name)
    if expected and row["display_order"] != expected["display_order"]:
        raise RecipeCatalogSeedError(
            f"required product category has unexpected display order: {name}"
        )
    return str(row["id"])


def _plan_product_categories(
    session: Session, organization_id: str, required_names: set[str]
) -> tuple[str, ...]:
    create_categories: list[str] = []
    for name in sorted(required_names):
        rows = (
            session.execute(
                sa.select(
                    models.product_categories.c.id,
                    models.product_categories.c.status,
                    models.product_categories.c.display_order,
                ).where(
                    models.product_categories.c.organization_id == organization_id,
                    models.product_categories.c.name == name,
                )
            )
            .mappings()
            .all()
        )
        active = [row for row in rows if row["status"] == "active"]
        if len(rows) == 1 and len(active) == 1:
            expected = APPROVED_CATEGORY_SPECS.get(name)
            if expected and active[0].get("display_order") != expected["display_order"]:
                raise RecipeCatalogSeedError(
                    f"required product category has unexpected display order: {name}"
                )
            continue
        if rows:
            if len(active) > 1:
                raise RecipeCatalogSeedError(f"required product category is ambiguous: {name}")
            raise RecipeCatalogSeedError(f"required product category is inactive: {name}")
        if name not in APPROVED_CATEGORY_SPECS:
            raise RecipeCatalogSeedError(f"required active product category is unavailable: {name}")
        create_categories.append(name)
    return tuple(create_categories)


def _assert_catalog_product_categories(
    session: Session, plan: SeedPlan, organization_id: str
) -> None:
    creating = {product["sku"] for product in plan.create_products}
    for sku, category_name in PRODUCT_CATEGORY_BY_SKU.items():
        if sku in creating:
            continue
        row = (
            session.execute(
                sa.select(
                    models.products.c.category_id,
                    models.product_categories.c.id,
                    models.product_categories.c.name,
                    models.product_categories.c.status,
                    models.product_categories.c.display_order,
                )
                .select_from(
                    models.products.join(
                        models.product_categories,
                        models.products.c.category_id == models.product_categories.c.id,
                    )
                )
                .where(
                    models.products.c.id == plan.product_ids[sku],
                    models.products.c.organization_id == organization_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if row is None or row["name"] != category_name or row["status"] != "active":
            raise RecipeCatalogSeedError(f"catalog product category differs: {sku}")
        expected = APPROVED_CATEGORY_SPECS.get(category_name)
        if expected and row["display_order"] != expected["display_order"]:
            raise RecipeCatalogSeedError(f"catalog product category differs: {sku}")


def _category_audit_entries(organization_id: str, names: Sequence[str]) -> list[dict[str, object]]:
    return [
        {
            "name": name,
            "id": _id("product-category", organization_id, name),
            "display_order": APPROVED_CATEGORY_SPECS[name]["display_order"],
        }
        for name in names
    ]


def _lock_organization(session: Session, organization_id: str) -> None:
    locked_organization = session.execute(
        sa.select(models.organizations.c.id)
        .where(models.organizations.c.id == organization_id)
        .with_for_update()
    ).scalar_one_or_none()
    if locked_organization is None:
        raise RecipeCatalogSeedError("recipe catalog organization does not exist")


def _require_publication_actor(session: Session, actor_user_id: str, organization_id: str) -> None:
    actor = session.execute(
        sa.select(models.users.c.id).where(
            models.users.c.id == actor_user_id,
            models.users.c.organization_id == organization_id,
            models.users.c.status == "active",
        )
    ).scalar_one_or_none()
    authority = session.execute(
        sa.select(models.user_roles.c.user_id)
        .select_from(
            models.user_roles.join(
                models.roles, models.user_roles.c.role_id == models.roles.c.id
            ).join(
                models.role_authority_grants,
                models.role_authority_grants.c.role_id == models.roles.c.id,
            )
        )
        .where(
            models.user_roles.c.user_id == actor_user_id,
            models.roles.c.organization_id == organization_id,
            models.roles.c.scope == "organization",
            models.role_authority_grants.c.authority_kind == "organization_all_permissions",
        )
        .limit(1)
    ).scalar_one_or_none()
    recipes_permission = session.execute(
        sa.select(models.permissions.c.id)
        .where(models.permissions.c.code == "recipes.manage")
        .limit(1)
    ).scalar_one_or_none()
    if actor is None or authority is None or recipes_permission is None:
        raise RecipeCatalogSeedError(
            "recipe catalog actor lacks active organization recipes authority"
        )


def _assert_recipe(
    session: Session,
    recipe_id: str,
    recipe: dict[str, Any],
    plan: SeedPlan,
    organization_id: str = ORGANIZATION_ID,
) -> None:
    existing = (
        session.execute(sa.select(models.recipes).where(models.recipes.c.id == recipe_id))
        .mappings()
        .one()
    )
    expected_recipe_values = {
        "organization_id": organization_id,
        "product_id": plan.product_ids[recipe["sku"]],
        "output_item_id": None,
        "branch_id": None,
        "recipe_type": "sale",
        "version": 1,
        "status": "active",
        "yield_quantity": Decimal("1"),
        "yield_unit_id": plan.unit_ids["PZA"],
        "valid_to": None,
    }
    if any(existing[key] != value for key, value in expected_recipe_values.items()):
        raise RecipeCatalogSeedError(f"seed recipe {recipe['sku']} has unexpected state")
    actual = (
        session.execute(
            sa.select(models.recipe_components).where(
                models.recipe_components.c.recipe_id == recipe_id
            )
        )
        .mappings()
        .all()
    )
    expected = {
        plan.item_ids[c["sku"]][0]: (index, c)
        for index, c in enumerate(recipe["components"], start=1)
    }
    if len(actual) != len(expected):
        raise RecipeCatalogSeedError(f"seed recipe {recipe['sku']} component count differs")
    for component in actual:
        expected_entry = expected.get(str(component["item_id"]))
        if (
            not expected_entry
            or Decimal(component["quantity_base_units"]) != expected_entry[1]["quantity"]
            or str(component["unit_id"]) != plan.item_ids[expected_entry[1]["sku"]][1]
            or Decimal(component["net_quantity"]) != expected_entry[1]["quantity"]
            or Decimal(component["waste_rate"]) != Decimal("0")
            or Decimal(component["gross_quantity"]) != expected_entry[1]["quantity"]
            or component["sort_order"] != expected_entry[0]
            or component["notes"] is not None
        ):
            raise RecipeCatalogSeedError(f"seed recipe {recipe['sku']} component differs")


def apply_seed_plan(
    session: Session, plan: SeedPlan, organization_id: str = ORGANIZATION_ID
) -> dict[str, Any]:
    """Apply a validated plan without changing any existing recipe or component."""
    now = _now()
    required_categories = {
        PRODUCT_CATEGORY_BY_SKU[product["sku"]] for product in plan.create_products
    }
    if (
        _plan_product_categories(session, organization_id, required_categories)
        != plan.create_categories
    ):
        raise RecipeCatalogSeedError("product category state changed after dry-run")
    for category_name in plan.create_categories:
        session.execute(
            models.product_categories.insert().values(
                id=_id("product-category", organization_id, category_name),
                organization_id=organization_id,
                name=category_name,
                display_order=APPROVED_CATEGORY_SPECS[category_name]["display_order"],
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
    categories: dict[str, str] = {}
    for product in plan.create_products:
        category_name = PRODUCT_CATEGORY_BY_SKU[product["sku"]]
        categories.setdefault(
            category_name, _active_category_id(session, organization_id, category_name)
        )
        product_id = plan.product_ids[product["sku"]]
        existing = session.execute(
            sa.select(models.products.c.id).where(models.products.c.id == product_id)
        ).scalar_one_or_none()
        if existing is None:
            price_cents = MISSING_PRODUCT_PRICE_CENTS[product["sku"]]
            session.execute(
                models.products.insert().values(
                    id=product_id,
                    organization_id=organization_id,
                    category_id=categories[category_name],
                    name=product["name"],
                    sku=product["sku"],
                    description=None,
                    station="barra",
                    status="active",
                    catalog_scope="organization",
                    source_branch_id=None,
                    created_at=now,
                    updated_at=now,
                )
            )
            session.execute(
                models.price_versions.insert().values(
                    id=_id("price", organization_id, product["sku"]),
                    organization_id=organization_id,
                    product_id=product_id,
                    price_cents=price_cents,
                    currency="MXN",
                    valid_from=now,
                    valid_to=None,
                    created_at=now,
                )
            )
    _assert_catalog_product_categories(session, plan, organization_id)
    for item in plan.create_items:
        item_id, unit_id = plan.item_ids[item["sku"]]
        if (
            session.execute(
                sa.select(models.inventory_items.c.id).where(models.inventory_items.c.id == item_id)
            ).scalar_one_or_none()
            is None
        ):
            session.execute(
                models.inventory_items.insert().values(
                    id=item_id,
                    organization_id=organization_id,
                    name=item["name"],
                    sku=item["sku"],
                    base_unit_id=unit_id,
                    item_type="ingredient",
                    category_name="ABARROTE",
                    catalog_scope="organization",
                    source_branch_id=None,
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
    for recipe in plan.recipes:
        if recipe["sku"] in plan.preserved_skus:
            continue
        recipe_id = _id("recipe", organization_id, recipe["sku"])
        if recipe["sku"] in plan.recipes_to_replay:
            _assert_recipe(session, recipe_id, recipe, plan, organization_id)
            continue
        product_id = plan.product_ids[recipe["sku"]]
        any_recipe = (
            session.execute(
                sa.select(models.recipes.c.id).where(models.recipes.c.product_id == product_id)
            )
            .scalars()
            .first()
        )
        if any_recipe is not None:
            raise RecipeCatalogSeedError(
                f"recipe history changed after dry-run for {recipe['sku']}"
            )
        session.execute(
            models.recipes.insert().values(
                id=recipe_id,
                organization_id=organization_id,
                product_id=product_id,
                output_item_id=None,
                branch_id=None,
                recipe_type="sale",
                version=1,
                status="active",
                yield_quantity=Decimal("1"),
                yield_unit_id=plan.unit_ids["PZA"],
                valid_from=now,
                valid_to=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.recipe_components.insert(),
            [
                {
                    "recipe_id": recipe_id,
                    "item_id": plan.item_ids[c["sku"]][0],
                    "quantity_base_units": c["quantity"],
                    "unit_id": plan.item_ids[c["sku"]][1],
                    "net_quantity": c["quantity"],
                    "waste_rate": Decimal("0"),
                    "gross_quantity": c["quantity"],
                    "sort_order": index,
                    "notes": None,
                }
                for index, c in enumerate(recipe["components"], start=1)
            ],
        )
    session.flush()
    return plan.report(applied=True)


def _validate_production_plan(plan: SeedPlan) -> None:
    """Accept only the reviewed initial state or its complete deterministic replay."""
    if plan.preserved_skus != (PRESERVED_SKU,):
        raise RecipeCatalogSeedError(
            f"unexpected preserved recipe histories: {list(plan.preserved_skus)}"
        )
    initial = (
        set(product["sku"] for product in plan.create_products) == MISSING_PRODUCT_SKUS
        and set(item["sku"] for item in plan.create_items) == set(MISSING_ITEM_SPECS)
        and len(plan.recipes_to_seed) == 314
        and not plan.recipes_to_replay
        and plan.create_categories == ("CAFE Y MACCHA",)
    )
    replay = (
        not plan.create_products
        and not plan.create_items
        and not plan.recipes_to_seed
        and len(plan.recipes_to_replay) == 314
        and not plan.create_categories
    )
    if not (initial or replay):
        raise RecipeCatalogSeedError("recipe catalog state is neither reviewed initial nor replay")


def publish_recipe_catalog(
    session: Session,
    *,
    apply: bool,
    actor_user_id: str,
    configured_environment: str,
    confirmed_environment: str,
    organization_id: str = ORGANIZATION_ID,
) -> dict[str, Any]:
    """Dry-run or publish atomically; the caller owns the transaction and commit."""
    if not confirmed_environment or confirmed_environment != configured_environment:
        raise RecipeCatalogSeedError("recipe catalog environment confirmation differs")
    _require_publication_actor(session, actor_user_id, organization_id)

    plan = build_seed_plan(session, organization_id)
    _validate_production_plan(plan)
    if not apply:
        return {
            **plan.report(applied=False),
            "dry_run": True,
            "replayed": bool(plan.recipes_to_replay),
            "manifest_sha256": MANIFEST_SHA256,
        }

    # The organization row is the serialization boundary for this one-off R3
    # publication.  Rebuild after locking so the applied plan is the reviewed plan.
    _lock_organization(session, organization_id)
    plan = build_seed_plan(session, organization_id)
    _validate_production_plan(plan)

    audit_entity_id = _id("publication", organization_id, MANIFEST_SHA256)
    existing_audit = (
        session.execute(
            sa.select(models.audit_events.c.id, models.audit_events.c.payload).where(
                models.audit_events.c.organization_id == organization_id,
                models.audit_events.c.action == "recipe_catalog.applied",
                models.audit_events.c.entity_id == audit_entity_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if plan.recipes_to_replay:
        if existing_audit is None:
            raise RecipeCatalogSeedError("complete recipe replay has no publication audit")
        expected_categories = _category_audit_entries(
            organization_id,
            [
                name
                for name in APPROVED_CATEGORY_SPECS
                if _active_category_id(session, organization_id, name)
                == _id("product-category", organization_id, name)
            ],
        )
        if existing_audit["payload"].get("categories_created") != expected_categories:
            raise RecipeCatalogSeedError("recipe replay category audit differs")
        return {
            **plan.report(applied=False),
            "dry_run": False,
            "replayed": True,
            "manifest_sha256": MANIFEST_SHA256,
        }
    if existing_audit is not None:
        raise RecipeCatalogSeedError("publication audit exists before recipe data")

    result = apply_seed_plan(session, plan, organization_id)
    session.execute(
        models.audit_events.insert().values(
            id=_id("audit", organization_id, MANIFEST_SHA256),
            organization_id=organization_id,
            branch_id=None,
            actor_user_id=actor_user_id,
            action="recipe_catalog.applied",
            entity_type="recipe_catalog_manifest",
            entity_id=audit_entity_id,
            payload={
                "manifest_sha256": MANIFEST_SHA256,
                "publishable_recipes": PUBLISHABLE_RECIPE_COUNT,
                "seeded_recipes": len(plan.recipes_to_seed),
                "preserved_skus": list(plan.preserved_skus),
                "products_created": [row["sku"] for row in plan.create_products],
                "items_created": [row["sku"] for row in plan.create_items],
                "categories_created": _category_audit_entries(
                    organization_id, plan.create_categories
                ),
                "operator_id": actor_user_id,
                "environment": configured_environment,
            },
            correlation_id=None,
            created_at=_now(),
        )
    )
    session.flush()
    return {
        **result,
        "dry_run": False,
        "replayed": False,
        "manifest_sha256": MANIFEST_SHA256,
    }


def _require_reviewed_schema_head(session: Session) -> None:
    try:
        heads = set(session.execute(sa.text("SELECT version_num FROM alembic_version")).scalars())
    except sa.exc.SQLAlchemyError as exc:
        raise RecipeCatalogSeedError("recipe catalog schema version is unavailable") from exc
    if heads != {PRODUCTION_SCHEMA_HEAD}:
        raise RecipeCatalogSeedError(
            f"recipe catalog requires schema head {PRODUCTION_SCHEMA_HEAD}, got {sorted(heads)}"
        )


def main(argv: list[str] | None = None) -> int:
    """Run the governed publisher against only the configured application database."""
    parser = argparse.ArgumentParser(description="Governed append-only recipe catalog publisher")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--confirm-environment", required=True)
    parser.add_argument("--confirm-manifest-sha256", required=True)
    parser.add_argument("--confirm-plan")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    if not settings.database_url:
        raise SystemExit("recipe_catalog_database_not_configured")
    if args.confirm_manifest_sha256 != MANIFEST_SHA256:
        raise SystemExit("recipe_catalog_manifest_confirmation_required")
    if args.apply and args.confirm_plan != PRODUCTION_PLAN_CONFIRMATION:
        raise SystemExit("recipe_catalog_plan_confirmation_required")

    with Session(get_engine()) as session:
        if args.apply:
            with session.begin():
                _require_reviewed_schema_head(session)
                result = publish_recipe_catalog(
                    session,
                    apply=True,
                    actor_user_id=args.actor,
                    configured_environment=settings.environment,
                    confirmed_environment=args.confirm_environment,
                )
        else:
            _require_reviewed_schema_head(session)
            result = publish_recipe_catalog(
                session,
                apply=False,
                actor_user_id=args.actor,
                configured_environment=settings.environment,
                confirmed_environment=args.confirm_environment,
            )
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
