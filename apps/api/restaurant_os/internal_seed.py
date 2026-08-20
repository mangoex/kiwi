from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import _audit

OPERATION_ORDER = {
    "ensure_organization.v1": 0,
    "ensure_branch_topology.v1": 1,
    "ensure_menu_catalog.v1": 2,
}
REQUIRED_TABLES = {
    "organizations",
    "legal_entities",
    "business_units",
    "branches",
    "warehouses",
    "product_categories",
    "inventory_units",
    "inventory_items",
    "products",
    "price_versions",
    "branch_product_availability",
    "recipes",
    "recipe_components",
    "users",
    "audit_events",
}


def _invalid() -> None:
    raise ValueError("seed_manifest_invalid")


def _mapping(value: object, keys: set[str]) -> Mapping[str, Any]:
    if not isinstance(value, dict) or set(value) != keys:
        _invalid()
    return value


def _text(value: object, *, maximum: int = 360) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        _invalid()
    return value.strip()


def _identifier(value: object) -> str:
    return _text(value, maximum=36)


def _decimal(value: object, *, allow_zero: bool = False, maximum: Decimal | None = None) -> Decimal:
    if not isinstance(value, str):
        _invalid()
    try:
        parsed = Decimal(value)
    except InvalidOperation:
        _invalid()
    if not parsed.is_finite() or parsed < 0 or (not allow_zero and parsed == 0):
        _invalid()
    if maximum is not None and parsed > maximum:
        _invalid()
    return parsed


def _integer(value: object, *, minimum: int = 0, maximum: int = 999_999_999) -> int:
    if type(value) is not int or value < minimum or value > maximum:
        _invalid()
    return value


def _list(value: object, *, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list) or (nonempty and not value):
        _invalid()
    return value


def _unique(values: list[str]) -> None:
    if len(values) != len(set(values)):
        _invalid()


def _validate_organization(operation: Mapping[str, Any], organization_id: str) -> None:
    _mapping(operation, {"type", "id", "name"})
    if operation["type"] != "ensure_organization.v1":
        _invalid()
    if _identifier(operation["id"]) != organization_id:
        _invalid()
    _text(operation["name"], maximum=160)


def _validate_topology(operation: Mapping[str, Any]) -> set[str]:
    _mapping(operation, {"type", "legal_entity", "business_unit", "branches"})
    legal_entity = _mapping(operation["legal_entity"], {"id", "name"})
    legal_entity_id = _identifier(legal_entity["id"])
    _text(legal_entity["name"], maximum=180)
    business_unit = _mapping(
        operation["business_unit"],
        {"id", "legal_entity_id", "name", "code", "unit_type"},
    )
    _identifier(business_unit["id"])
    if _identifier(business_unit["legal_entity_id"]) != legal_entity_id:
        _invalid()
    _text(business_unit["name"], maximum=160)
    _text(business_unit["code"], maximum=32)
    _text(business_unit["unit_type"], maximum=32)
    branch_ids: list[str] = []
    branch_codes: list[str] = []
    warehouse_ids: list[str] = []
    for raw_branch in _list(operation["branches"], nonempty=True):
        branch = _mapping(
            raw_branch,
            {
                "id",
                "legal_entity_id",
                "business_unit_id",
                "name",
                "code",
                "timezone",
                "warehouse",
            },
        )
        branch_ids.append(_identifier(branch["id"]))
        branch_codes.append(_text(branch["code"], maximum=32))
        if _identifier(branch["legal_entity_id"]) != legal_entity_id:
            _invalid()
        if _identifier(branch["business_unit_id"]) != business_unit["id"]:
            _invalid()
        _text(branch["name"], maximum=160)
        _text(branch["timezone"], maximum=64)
        warehouse = _mapping(branch["warehouse"], {"id", "name"})
        warehouse_ids.append(_identifier(warehouse["id"]))
        _text(warehouse["name"], maximum=160)
    _unique(branch_ids)
    _unique(branch_codes)
    _unique(warehouse_ids)
    return set(branch_ids)


def _validate_catalog(operation: Mapping[str, Any], branch_ids: set[str]) -> None:
    _mapping(operation, {"type", "branch_id", "categories", "units", "items", "products"})
    branch_id = _identifier(operation["branch_id"])
    if branch_id not in branch_ids:
        _invalid()

    category_ids: list[str] = []
    category_names: list[str] = []
    for raw_category in _list(operation["categories"], nonempty=True):
        category = _mapping(raw_category, {"id", "name", "display_order"})
        category_ids.append(_identifier(category["id"]))
        category_names.append(_text(category["name"], maximum=120))
        _integer(category["display_order"], maximum=10_000)
    _unique(category_ids)
    _unique(category_names)

    unit_ids: list[str] = []
    unit_codes: list[str] = []
    for raw_unit in _list(operation["units"], nonempty=True):
        unit = _mapping(raw_unit, {"id", "code", "name", "dimension", "precision_scale"})
        unit_ids.append(_identifier(unit["id"]))
        unit_codes.append(_text(unit["code"], maximum=24))
        _text(unit["name"], maximum=80)
        _text(unit["dimension"], maximum=24)
        _integer(unit["precision_scale"], maximum=6)
    _unique(unit_ids)
    _unique(unit_codes)

    item_ids: list[str] = []
    item_skus: list[str] = []
    for raw_item in _list(operation["items"]):
        item = _mapping(raw_item, {"id", "name", "sku", "base_unit_id", "item_type"})
        item_ids.append(_identifier(item["id"]))
        item_skus.append(_text(item["sku"], maximum=64))
        _text(item["name"], maximum=160)
        _text(item["item_type"], maximum=32)
        if _identifier(item["base_unit_id"]) not in unit_ids:
            _invalid()
    _unique(item_ids)
    _unique(item_skus)

    product_ids: list[str] = []
    product_skus: list[str] = []
    price_ids: list[str] = []
    recipe_ids: list[str] = []
    for raw_product in _list(operation["products"], nonempty=True):
        product = _mapping(
            raw_product,
            {
                "id",
                "category_id",
                "name",
                "sku",
                "description",
                "station",
                "price",
                "recipe",
            },
        )
        product_ids.append(_identifier(product["id"]))
        product_skus.append(_text(product["sku"], maximum=64))
        if _identifier(product["category_id"]) not in category_ids:
            _invalid()
        _text(product["name"], maximum=160)
        if not isinstance(product["description"], str) or len(product["description"]) > 360:
            _invalid()
        _text(product["station"], maximum=32)
        price = _mapping(product["price"], {"id", "price_cents", "currency"})
        price_ids.append(_identifier(price["id"]))
        _integer(price["price_cents"])
        currency = _text(price["currency"], maximum=3)
        if len(currency) != 3 or currency != currency.upper():
            _invalid()
        recipe = _mapping(
            product["recipe"],
            {"id", "version", "yield_quantity", "yield_unit_id", "components"},
        )
        recipe_ids.append(_identifier(recipe["id"]))
        _integer(recipe["version"], minimum=1, maximum=10_000)
        _decimal(recipe["yield_quantity"])
        if _identifier(recipe["yield_unit_id"]) not in unit_ids:
            _invalid()
        component_items: list[str] = []
        for raw_component in _list(recipe["components"]):
            component = _mapping(
                raw_component,
                {
                    "item_id",
                    "unit_id",
                    "quantity_base_units",
                    "net_quantity",
                    "waste_rate",
                    "gross_quantity",
                    "sort_order",
                },
            )
            component_items.append(_identifier(component["item_id"]))
            if (
                component_items[-1] not in item_ids
                or _identifier(component["unit_id"]) not in unit_ids
            ):
                _invalid()
            _decimal(component["quantity_base_units"])
            _decimal(component["net_quantity"])
            _decimal(component["waste_rate"], allow_zero=True, maximum=Decimal("1"))
            _decimal(component["gross_quantity"])
            _integer(component["sort_order"], maximum=10_000)
        _unique(component_items)
    _unique(product_ids)
    _unique(product_skus)
    _unique(price_ids)
    _unique(recipe_ids)


def _validate_manifest(
    session: Session, manifest: dict[str, Any], actor_id: str
) -> list[Mapping[str, Any]]:
    _mapping(manifest, {"organization_id", "environment", "operations"})
    organization_id = _identifier(manifest["organization_id"])
    if manifest["environment"] not in {"development", "test", "staging"}:
        _invalid()
    _text(actor_id, maximum=180)
    operations = _list(manifest["operations"], nonempty=True)
    if any(not isinstance(operation, dict) for operation in operations):
        _invalid()
    operation_types = [operation.get("type") for operation in operations]
    if any(operation_type not in OPERATION_ORDER for operation_type in operation_types):
        _invalid()
    if len(operation_types) != len(set(operation_types)):
        _invalid()
    if operation_types != sorted(operation_types, key=OPERATION_ORDER.__getitem__):
        _invalid()
    if operation_types[0] != "ensure_organization.v1":
        _invalid()

    typed_operations = list(operations)
    _validate_organization(typed_operations[0], organization_id)
    branch_ids: set[str] = set()
    for operation in typed_operations[1:]:
        if operation["type"] == "ensure_branch_topology.v1":
            branch_ids = _validate_topology(operation)
        elif operation["type"] == "ensure_menu_catalog.v1":
            if not branch_ids:
                branch_id = _identifier(operation.get("branch_id"))
                persisted = session.execute(
                    sa.select(models.branches.c.id).where(
                        models.branches.c.id == branch_id,
                        models.branches.c.organization_id == organization_id,
                    )
                ).scalar_one_or_none()
                if persisted is None:
                    _invalid()
                branch_ids = {branch_id}
            _validate_catalog(operation, branch_ids)
    return typed_operations


def _equal(actual: object, expected: object) -> bool:
    if isinstance(expected, Decimal):
        return actual is not None and Decimal(str(actual)) == expected
    return actual == expected


def _ensure_row(
    session: Session,
    table: sa.Table,
    identity: Mapping[str, object],
    values: Mapping[str, object],
    *,
    natural_identity: Mapping[str, object] | None = None,
    write: bool,
) -> None:
    identity_filter = [table.c[key] == value for key, value in identity.items()]
    existing = session.execute(sa.select(table).where(*identity_filter)).mappings().first()
    expected = {**identity, **values}
    if existing is not None:
        compared = {
            key: value
            for key, value in expected.items()
            if key not in {"created_at", "updated_at", "valid_from"}
        }
        if any(not _equal(existing[key], value) for key, value in compared.items()):
            raise ValueError("seed_manifest_conflict")
        return
    if natural_identity:
        collision = session.execute(
            sa.select(table).where(
                *(table.c[key] == value for key, value in natural_identity.items())
            )
        ).first()
        if collision is not None:
            raise ValueError("seed_manifest_conflict")
    if write:
        session.execute(table.insert().values(**expected))


def _run_organization(
    session: Session,
    organization_id: str,
    operation: Mapping[str, Any],
    now: datetime,
    *,
    write: bool,
) -> None:
    _ensure_row(
        session,
        models.organizations,
        {"id": organization_id},
        {
            "name": operation["name"].strip(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        write=write,
    )


def _run_topology(
    session: Session,
    organization_id: str,
    operation: Mapping[str, Any],
    now: datetime,
    *,
    write: bool,
) -> None:
    legal_entity = operation["legal_entity"]
    _ensure_row(
        session,
        models.legal_entities,
        {"id": legal_entity["id"]},
        {
            "organization_id": organization_id,
            "name": legal_entity["name"].strip(),
            "tax_id": None,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        write=write,
    )
    business_unit = operation["business_unit"]
    _ensure_row(
        session,
        models.business_units,
        {"id": business_unit["id"]},
        {
            "organization_id": organization_id,
            "legal_entity_id": business_unit["legal_entity_id"],
            "name": business_unit["name"].strip(),
            "code": business_unit["code"].strip(),
            "unit_type": business_unit["unit_type"].strip(),
            "status": "active",
            "created_at": now,
            "updated_at": now,
        },
        natural_identity={
            "organization_id": organization_id,
            "code": business_unit["code"].strip(),
        },
        write=write,
    )
    for branch in operation["branches"]:
        _ensure_row(
            session,
            models.branches,
            {"id": branch["id"]},
            {
                "organization_id": organization_id,
                "legal_entity_id": branch["legal_entity_id"],
                "business_unit_id": branch["business_unit_id"],
                "name": branch["name"].strip(),
                "code": branch["code"].strip(),
                "timezone": branch["timezone"].strip(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            natural_identity={"organization_id": organization_id, "code": branch["code"].strip()},
            write=write,
        )
        warehouse = branch["warehouse"]
        _ensure_row(
            session,
            models.warehouses,
            {"id": warehouse["id"]},
            {
                "organization_id": organization_id,
                "branch_id": branch["id"],
                "name": warehouse["name"].strip(),
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            natural_identity={"branch_id": branch["id"]},
            write=write,
        )


def _run_catalog(
    session: Session,
    organization_id: str,
    operation: Mapping[str, Any],
    now: datetime,
    *,
    write: bool,
) -> None:
    branch_id = operation["branch_id"]
    for category in operation["categories"]:
        _ensure_row(
            session,
            models.product_categories,
            {"id": category["id"]},
            {
                "organization_id": organization_id,
                "name": category["name"].strip(),
                "display_order": category["display_order"],
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            natural_identity={"organization_id": organization_id, "name": category["name"].strip()},
            write=write,
        )
    for unit in operation["units"]:
        _ensure_row(
            session,
            models.inventory_units,
            {"id": unit["id"]},
            {
                "organization_id": organization_id,
                "code": unit["code"].strip(),
                "name": unit["name"].strip(),
                "dimension": unit["dimension"].strip(),
                "precision_scale": unit["precision_scale"],
                "created_at": now,
            },
            natural_identity={"organization_id": organization_id, "code": unit["code"].strip()},
            write=write,
        )
    for item in operation["items"]:
        _ensure_row(
            session,
            models.inventory_items,
            {"id": item["id"]},
            {
                "organization_id": organization_id,
                "name": item["name"].strip(),
                "sku": item["sku"].strip(),
                "base_unit_id": item["base_unit_id"],
                "item_type": item["item_type"].strip(),
                "category_name": None,
                "catalog_scope": "organization",
                "source_branch_id": None,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            natural_identity={"organization_id": organization_id, "sku": item["sku"].strip()},
            write=write,
        )
    for product in operation["products"]:
        _ensure_row(
            session,
            models.products,
            {"id": product["id"]},
            {
                "organization_id": organization_id,
                "category_id": product["category_id"],
                "name": product["name"].strip(),
                "sku": product["sku"].strip(),
                "description": product["description"],
                "station": product["station"].strip(),
                "status": "active",
                "image_url": None,
                "catalog_scope": "organization",
                "source_branch_id": None,
                "created_at": now,
                "updated_at": now,
            },
            natural_identity={"organization_id": organization_id, "sku": product["sku"].strip()},
            write=write,
        )
        _ensure_row(
            session,
            models.branch_product_availability,
            {"branch_id": branch_id, "product_id": product["id"]},
            {"is_available": True, "updated_at": now},
            write=write,
        )
        price = product["price"]
        _ensure_row(
            session,
            models.price_versions,
            {"id": price["id"]},
            {
                "organization_id": organization_id,
                "product_id": product["id"],
                "price_cents": price["price_cents"],
                "currency": price["currency"].strip(),
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
            },
            write=write,
        )
        recipe = product["recipe"]
        _ensure_row(
            session,
            models.recipes,
            {"id": recipe["id"]},
            {
                "organization_id": organization_id,
                "product_id": product["id"],
                "output_item_id": None,
                "branch_id": None,
                "recipe_type": "sale",
                "version": recipe["version"],
                "status": "active",
                "yield_quantity": _decimal(recipe["yield_quantity"]),
                "yield_unit_id": recipe["yield_unit_id"],
                "valid_from": now,
                "valid_to": None,
                "created_at": now,
                "updated_at": now,
            },
            natural_identity={"product_id": product["id"], "version": recipe["version"]},
            write=write,
        )
        for component in recipe["components"]:
            _ensure_row(
                session,
                models.recipe_components,
                {"recipe_id": recipe["id"], "item_id": component["item_id"]},
                {
                    "quantity_base_units": _decimal(component["quantity_base_units"]),
                    "unit_id": component["unit_id"],
                    "net_quantity": _decimal(component["net_quantity"]),
                    "waste_rate": _decimal(
                        component["waste_rate"], allow_zero=True, maximum=Decimal("1")
                    ),
                    "gross_quantity": _decimal(component["gross_quantity"]),
                    "sort_order": component["sort_order"],
                    "notes": None,
                },
                write=write,
            )


def _run_operations(
    session: Session,
    organization_id: str,
    operations: list[Mapping[str, Any]],
    now: datetime,
    *,
    write: bool,
) -> None:
    handlers = {
        "ensure_organization.v1": _run_organization,
        "ensure_branch_topology.v1": _run_topology,
        "ensure_menu_catalog.v1": _run_catalog,
    }
    for operation in operations:
        handlers[operation["type"]](session, organization_id, operation, now, write=write)


def apply_manifest(
    session: Session,
    manifest: dict[str, Any],
    *,
    apply: bool,
    actor_id: str,
    _failure_hook: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Validate and execute the versioned internal seed allowlist without an HTTP surface."""
    _require_migrated_schema(session)
    operations = _validate_manifest(session, manifest, actor_id)
    # audit_events.entity_id is bounded to 36 characters. A 144-bit canonical
    # BLAKE2 digest fits without truncating the idempotency key.
    manifest_id = hashlib.blake2b(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8"),
        digest_size=18,
    ).hexdigest()
    result = {
        "dry_run": not apply,
        "operations": len(operations),
        "operation_types": [operation["type"] for operation in operations],
        "replayed": False,
    }
    if apply:
        existing = session.execute(
            sa.select(models.audit_events.c.id).where(
                models.audit_events.c.action == "internal_seed.applied",
                models.audit_events.c.entity_id == manifest_id,
            )
        ).first()
        if existing:
            return {**result, "replayed": True}

    now = datetime.now(timezone.utc)
    _run_operations(session, str(manifest["organization_id"]), operations, now, write=False)
    if not apply:
        return result
    try:
        _run_operations(session, str(manifest["organization_id"]), operations, now, write=True)
        if _failure_hook:
            _failure_hook()
        persisted_actor = session.execute(
            sa.select(models.users.c.id).where(
                models.users.c.id == actor_id,
                models.users.c.organization_id == manifest["organization_id"],
                models.users.c.status == "active",
            )
        ).scalar_one_or_none()
        _audit(
            session,
            action="internal_seed.applied",
            entity_type="seed_manifest",
            entity_id=manifest_id,
            payload={
                "operation_count": len(operations),
                "operation_types": [operation["type"] for operation in operations],
                "operator_id": actor_id,
            },
            branch_id=None,
            organization_id=str(manifest["organization_id"]),
            actor_user_id=persisted_actor,
        )
        session.commit()
    except Exception:
        session.rollback()
        raise
    return result


def _require_migrated_schema(session: Session) -> None:
    table_names = set(sa.inspect(session.get_bind()).get_table_names())
    if not REQUIRED_TABLES <= table_names:
        raise ValueError("seed_database_not_migrated")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--confirm-environment", required=True)
    parser.add_argument("--sqlite-url", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    if not isinstance(manifest, dict) or manifest.get("environment") != args.confirm_environment:
        raise SystemExit("seed_environment_confirmation_required")
    if manifest["environment"] == "production" or not args.sqlite_url.startswith("sqlite"):
        raise SystemExit("seed_environment_denied")
    engine = create_engine(args.sqlite_url)
    with Session(engine) as session:
        result = apply_manifest(session, manifest, apply=args.apply, actor_id=args.actor)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
