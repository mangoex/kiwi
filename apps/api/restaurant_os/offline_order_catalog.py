"""Frozen, scoped catalog snapshots for ORD-OFF001 gateway execution.

The central bundle signer owns the manifest and signature.  This module only
serializes the catalog/operational rows that the canonical Python order domain
can read, and hydrates them into a dedicated SQLite catalog database.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from weakref import WeakSet

import sqlalchemy as sa
from sqlalchemy import event
from sqlalchemy.dialects import sqlite
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from restaurant_os import models
from restaurant_os.operations import BusinessError

CATALOG_SCHEMA = "ord-off-catalog/v2"
CLASSIFICATION_CATALOG_SCHEMA = "ord-off-catalog/v3"
_CLASSIFICATION_TABLES = (
    "category_option_groups",
    "category_option_values",
    "product_option_value_assignments",
)
_LEGACY_CATALOG_SCHEMA = "ord-off-catalog/v1"
OPERATIONAL_SEED_SCHEMA = "ord-off-operational-seed/v1"

# These are deliberately concrete table names, rather than a metadata walk.
# Adding a domain read requires an explicit review of its scope and data class.
_CATALOG_TABLES = (
    "organizations",
    "legal_entities",
    "business_units",
    "branches",
    "warehouses",
    "product_categories",
    "inventory_units",
    "inventory_items",
    "products",
    *_CLASSIFICATION_TABLES,
    "price_versions",
    "branch_product_availability",
    "modifier_groups",
    "modifier_options",
    "branch_modifier_options",
    "order_comment_presets",
    "order_comment_products",
    "ingredient_variations",
    "ingredient_variation_products",
    "recipes",
    "recipe_components",
    "product_compositions",
    "product_composition_components",
    "inventory_cost_states",
)
_SEED_TABLES = (
    "permissions",
    "roles",
    "employee_code_registry",
    "users",
    "role_permissions",
    "role_authority_grants",
    "user_roles",
    "cash_shifts",
)
# SQLite requires even nullable foreign-key targets to have a table.  These
# tables carry no bundle rows and are never read by order execution.
_SCHEMA_ONLY_TABLES = ("suppliers",)

_installation_metadata = sa.MetaData()
_catalog_installations = sa.Table(
    "offline_order_catalog_installations",
    _installation_metadata,
    sa.Column("branch_id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), nullable=False),
    sa.Column("bundle_hash", sa.String(64), nullable=False),
    sa.Column("installed_at", sa.DateTime(timezone=True), nullable=False),
)
_catalog_generations = sa.Table(
    "offline_order_catalog_generations",
    _installation_metadata,
    sa.Column("branch_id", sa.String(36), primary_key=True),
    sa.Column("organization_id", sa.String(36), nullable=False),
    sa.Column("catalog_generation", sa.Integer(), nullable=False),
    sa.Column("catalog_classification_mode", sa.String(16), nullable=False),
    sa.Column("bundle_hash", sa.String(64), nullable=False),
)
_READ_ONLY_ENGINES: WeakSet[Engine] = WeakSet()


def hydrate_bundle(
    engine: Engine, bundle: Mapping[str, Any], include_operational_seed: bool = False
) -> dict[str, str]:
    """Install verified bundle rows into either gateway database.

    ``include_operational_seed`` selects the writable operational database.
    The separate catalog database is installed read-only, but still receives
    the minimal seed because composition history has actor foreign keys.
    Signature verification deliberately remains at the transport boundary.
    """
    if not isinstance(bundle, Mapping):
        raise BusinessError("offline_bundle_invalid", "Bundle is invalid")
    required = {"manifest", "catalog", "operational_seed"}
    if not required.issubset(bundle):
        raise BusinessError("offline_bundle_invalid", "Bundle is invalid")
    manifest = bundle["manifest"]
    if not isinstance(manifest, Mapping):
        raise BusinessError("offline_bundle_invalid", "Bundle is invalid")
    snapshot = hydrate_catalog_snapshot(
        engine,
        manifest=manifest,
        catalog=bundle["catalog"],
        operational_seed=bundle["operational_seed"],
        read_only=not include_operational_seed,
        full_operational_schema=include_operational_seed,
    )
    try:
        return {
            "branch_id": str(manifest["branch_id"]),
            "bundle_hash": str(manifest["bundle_hash"]),
        }
    finally:
        snapshot.close()


def build_catalog_snapshot(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    catalog_schema: str = CATALOG_SCHEMA,
) -> dict[str, Any]:
    """Capture the branch-effective, order-readable catalog as JSON-safe data."""
    _require_scope(organization_id, branch_id)
    branch = _one(
        session,
        models.branches,
        models.branches.c.id == branch_id,
        models.branches.c.organization_id == organization_id,
    )
    organization = _one(session, models.organizations, models.organizations.c.id == organization_id)
    legal_entity = _one(
        session,
        models.legal_entities,
        models.legal_entities.c.id == branch["legal_entity_id"],
        models.legal_entities.c.organization_id == organization_id,
    )
    business_unit = _one(
        session,
        models.business_units,
        models.business_units.c.id == branch["business_unit_id"],
        models.business_units.c.organization_id == organization_id,
    )
    warehouses = _rows(
        session,
        models.warehouses,
        models.warehouses.c.organization_id == organization_id,
        models.warehouses.c.branch_id == branch_id,
    )
    if len(warehouses) != 1:
        raise BusinessError("offline_bundle_catalog_invalid", "Branch warehouse is invalid")

    products = _rows(
        session,
        models.products,
        models.products.c.organization_id == organization_id,
        sa.or_(
            models.products.c.catalog_scope == "organization",
            sa.and_(
                models.products.c.catalog_scope == "branch",
                models.products.c.source_branch_id == branch_id,
            ),
        ),
    )
    product_ids = {str(row["id"]) for row in products}
    categories = _rows(
        session,
        models.product_categories,
        models.product_categories.c.organization_id == organization_id,
        models.product_categories.c.id.in_({row["category_id"] for row in products}),
    )
    units = _rows(
        session,
        models.inventory_units,
        models.inventory_units.c.organization_id == organization_id,
    )
    items = _rows(
        session,
        models.inventory_items,
        models.inventory_items.c.organization_id == organization_id,
        sa.or_(
            models.inventory_items.c.catalog_scope == "organization",
            sa.and_(
                models.inventory_items.c.catalog_scope == "branch",
                models.inventory_items.c.source_branch_id == branch_id,
            ),
        ),
    )
    item_ids = {str(row["id"]) for row in items}
    prices = _rows(
        session,
        models.price_versions,
        models.price_versions.c.organization_id == organization_id,
        models.price_versions.c.product_id.in_(product_ids),
        models.price_versions.c.valid_to.is_(None),
    )
    availability = _rows(
        session,
        models.branch_product_availability,
        models.branch_product_availability.c.branch_id == branch_id,
        models.branch_product_availability.c.product_id.in_(product_ids),
    )
    groups = _rows(
        session,
        models.modifier_groups,
        models.modifier_groups.c.organization_id == organization_id,
        models.modifier_groups.c.product_id.in_(product_ids),
    )
    group_ids = {str(row["id"]) for row in groups}
    options = _rows(
        session,
        models.modifier_options,
        models.modifier_options.c.group_id.in_(group_ids),
    )
    option_ids = {str(row["id"]) for row in options}
    branch_options = _rows(
        session,
        models.branch_modifier_options,
        models.branch_modifier_options.c.branch_id == branch_id,
        models.branch_modifier_options.c.option_id.in_(option_ids),
    )
    comments = _rows(
        session,
        models.order_comment_presets,
        models.order_comment_presets.c.organization_id == organization_id,
    )
    comment_ids = {str(row["id"]) for row in comments}
    comment_products = _rows(
        session,
        models.order_comment_products,
        models.order_comment_products.c.comment_preset_id.in_(comment_ids),
        models.order_comment_products.c.product_id.in_(product_ids),
    )
    variations = _rows(
        session,
        models.ingredient_variations,
        models.ingredient_variations.c.organization_id == organization_id,
        models.ingredient_variations.c.inventory_item_id.in_(item_ids),
    )
    variation_ids = {str(row["id"]) for row in variations}
    variation_products = _rows(
        session,
        models.ingredient_variation_products,
        models.ingredient_variation_products.c.variation_id.in_(variation_ids),
        models.ingredient_variation_products.c.product_id.in_(product_ids),
    )
    recipes = _rows(
        session,
        models.recipes,
        models.recipes.c.organization_id == organization_id,
        models.recipes.c.product_id.in_(product_ids),
        sa.or_(models.recipes.c.branch_id.is_(None), models.recipes.c.branch_id == branch_id),
    )
    recipe_ids = {str(row["id"]) for row in recipes}
    recipe_components = _rows(
        session,
        models.recipe_components,
        models.recipe_components.c.recipe_id.in_(recipe_ids),
        models.recipe_components.c.item_id.in_(item_ids),
    )
    compositions = _rows(
        session,
        models.product_compositions,
        models.product_compositions.c.organization_id == organization_id,
        models.product_compositions.c.combo_product_id.in_(product_ids),
        sa.or_(
            models.product_compositions.c.branch_id.is_(None),
            models.product_compositions.c.branch_id == branch_id,
        ),
    )
    composition_ids = {str(row["id"]) for row in compositions}
    composition_components = _rows(
        session,
        models.product_composition_components,
        models.product_composition_components.c.composition_id.in_(composition_ids),
        models.product_composition_components.c.product_id.in_(product_ids),
    )
    costs = _rows(
        session,
        models.inventory_cost_states,
        models.inventory_cost_states.c.branch_id == branch_id,
        models.inventory_cost_states.c.warehouse_id == warehouses[0]["id"],
        models.inventory_cost_states.c.item_id.in_(item_ids),
    )
    # Supplier history is not a catalog input to order pricing.  Its foreign key
    # would otherwise carry supplier data outside the defined bundle allowlist.
    for cost in costs:
        cost["last_supplier_id"] = None

    tables = {
        "organizations": [organization],
        "legal_entities": [legal_entity],
        "business_units": [business_unit],
        "branches": [branch],
        "warehouses": warehouses,
        "product_categories": categories,
        "inventory_units": units,
        "inventory_items": items,
        "products": products,
        "price_versions": prices,
        "branch_product_availability": availability,
        "modifier_groups": groups,
        "modifier_options": options,
        "branch_modifier_options": branch_options,
        "order_comment_presets": _clear_foreign_auditors(comments),
        "order_comment_products": _clear_foreign_auditors(comment_products),
        "ingredient_variations": variations,
        "ingredient_variation_products": variation_products,
        "recipes": recipes,
        "recipe_components": recipe_components,
        "product_compositions": compositions,
        "product_composition_components": composition_components,
        "inventory_cost_states": costs,
    }
    if catalog_schema == CLASSIFICATION_CATALOG_SCHEMA:
        option_groups = _rows(
            session,
            models.category_option_groups,
            models.category_option_groups.c.organization_id == organization_id,
            models.category_option_groups.c.category_id.in_({row["id"] for row in categories}),
        )
        subgroup_ids = {row["id"] for row in option_groups}
        tables["category_option_groups"] = option_groups
        tables["category_option_values"] = _rows(
            session,
            models.category_option_values,
            models.category_option_values.c.group_id.in_(subgroup_ids),
        )
        tables["product_option_value_assignments"] = _rows(
            session,
            models.product_option_value_assignments,
            models.product_option_value_assignments.c.group_id.in_(subgroup_ids),
            models.product_option_value_assignments.c.product_id.in_(product_ids),
        )
    elif catalog_schema == CATALOG_SCHEMA:
        for row in categories:
            row.pop("classification_code", None)
            row.pop("configuration_version", None)
    else:
        raise BusinessError("offline_bundle_catalog_invalid", "Unsupported catalog schema")
    return {"schema_version": catalog_schema, "tables": _wire(tables)}


def build_operational_seed(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    actor_ids: Iterable[str],
) -> dict[str, Any]:
    """Capture only users, grants and open shifts required by named actors.

    Authentication material, device credentials and grants are intentionally
    absent.  A signed order grant is supplied through its separate protocol.
    """
    _require_scope(organization_id, branch_id)
    ids = {str(actor_id) for actor_id in actor_ids if str(actor_id)}
    if not ids:
        raise BusinessError("offline_bundle_seed_invalid", "At least one actor is required")
    shifts = _rows(
        session,
        models.cash_shifts,
        models.cash_shifts.c.organization_id == organization_id,
        models.cash_shifts.c.branch_id == branch_id,
        sa.func.upper(models.cash_shifts.c.status).in_(("OPEN", "CLOSING")),
    )
    composition_authors = {
        str(author_id)
        for author_id in session.scalars(
            sa.select(models.product_compositions.c.created_by)
            .select_from(
                models.product_compositions.join(
                    models.products,
                    models.products.c.id == models.product_compositions.c.combo_product_id,
                )
            )
            .where(
                models.product_compositions.c.organization_id == organization_id,
                sa.or_(
                    models.product_compositions.c.branch_id.is_(None),
                    models.product_compositions.c.branch_id == branch_id,
                ),
                sa.or_(
                    models.products.c.catalog_scope == "organization",
                    sa.and_(
                        models.products.c.catalog_scope == "branch",
                        models.products.c.source_branch_id == branch_id,
                    ),
                ),
            )
        )
    }
    identity_ids = (
        ids
        | {str(row["cashier_user_id"]) for row in shifts if row["cashier_user_id"] is not None}
        | composition_authors
    )
    users = _rows(
        session,
        models.users,
        models.users.c.organization_id == organization_id,
        models.users.c.id.in_(identity_ids),
    )
    if not ids <= {str(row["id"]) for row in users}:
        raise BusinessError("offline_bundle_seed_invalid", "Actor is outside organization")
    employee_codes = {str(row["employee_code"]) for row in users if row["employee_code"]}
    registry = _rows(
        session,
        models.employee_code_registry,
        models.employee_code_registry.c.organization_id == organization_id,
        models.employee_code_registry.c.subject_type == "user",
        models.employee_code_registry.c.subject_id.in_(identity_ids),
    )
    if employee_codes and {str(row["employee_code"]) for row in registry} != employee_codes:
        raise BusinessError("offline_bundle_seed_invalid", "Actor employee identity is invalid")
    user_roles = _rows(
        session,
        models.user_roles,
        models.user_roles.c.user_id.in_(ids),
        sa.or_(models.user_roles.c.branch_id.is_(None), models.user_roles.c.branch_id == branch_id),
    )
    role_ids = {str(row["role_id"]) for row in user_roles}
    roles = _rows(
        session,
        models.roles,
        models.roles.c.organization_id == organization_id,
        models.roles.c.id.in_(role_ids),
    )
    permissions_by_role = _rows(
        session,
        models.role_permissions,
        models.role_permissions.c.role_id.in_(role_ids),
    )
    permission_ids = {str(row["permission_id"]) for row in permissions_by_role}
    permissions = _rows(session, models.permissions, models.permissions.c.id.in_(permission_ids))
    authority = _rows(
        session,
        models.role_authority_grants,
        models.role_authority_grants.c.role_id.in_(role_ids),
    )
    tables = {
        "permissions": permissions,
        "roles": roles,
        "employee_code_registry": registry,
        "users": users,
        "role_permissions": permissions_by_role,
        "role_authority_grants": authority,
        "user_roles": user_roles,
        "cash_shifts": shifts,
    }
    return {"schema_version": OPERATIONAL_SEED_SCHEMA, "tables": _wire(tables)}


def hydrate_catalog_snapshot(
    engine: Engine,
    *,
    manifest: Mapping[str, Any],
    catalog: Mapping[str, Any],
    operational_seed: Mapping[str, Any] | None = None,
    read_only: bool = True,
    full_operational_schema: bool = False,
) -> Session:
    """Hydrate an already verified bundle into a new dedicated SQLite session."""
    if engine.dialect.name != "sqlite":
        raise BusinessError("offline_bundle_target_invalid", "Catalog target must be SQLite")
    organization_id = _manifest_scope(manifest, "organization_id")
    branch_id = _manifest_scope(manifest, "branch_id")
    bundle_hash = _manifest_scope(manifest, "bundle_hash")
    catalog_rows = _decode_catalog(manifest, catalog)
    seed_rows = (
        _decode_payload(operational_seed, OPERATIONAL_SEED_SCHEMA, _SEED_TABLES, "seed")
        if operational_seed is not None
        else {name: [] for name in _SEED_TABLES}
    )
    _validate_scope(catalog_rows, seed_rows, organization_id, branch_id)
    _validate_foreign_keys(catalog_rows, seed_rows)
    _create_snapshot_tables(engine, full_operational_schema=full_operational_schema)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    target = factory()
    try:
        existing = (
            target.execute(
                sa.select(_catalog_installations).where(
                    _catalog_installations.c.branch_id == branch_id
                )
            )
            .mappings()
            .one_or_none()
        )
        _validate_generation(target, manifest)
        if existing is not None:
            if (
                existing["organization_id"] != organization_id
                or existing["bundle_hash"] != bundle_hash
            ):
                raise BusinessError(
                    "offline_bundle_target_conflict",
                    "Catalog target has a different bundle",
                )
            target.rollback()
            if read_only:
                _enforce_read_only(engine)
                _set_read_only(target)
            return target
        if _target_has_catalog_data(target):
            raise BusinessError(
                "offline_bundle_target_not_empty", "Catalog target already has bundle data"
            )
        # The marker/emptiness reads start an implicit SQLAlchemy transaction.
        # End it before the single installation transaction begins.
        target.rollback()
        with target.begin():
            _insert_hydrated_rows(target, catalog_rows, seed_rows)
            _store_generation(target, manifest)
            target.execute(
                _catalog_installations.insert().values(
                    branch_id=branch_id,
                    organization_id=organization_id,
                    bundle_hash=bundle_hash,
                    installed_at=datetime.now(UTC),
                )
            )
        if read_only:
            _enforce_read_only(engine)
            _set_read_only(target)
        return target
    except Exception:
        target.rollback()
        target.close()
        raise


def refresh_catalog_snapshot(
    engine: Engine,
    *,
    manifest: Mapping[str, Any],
    catalog: Mapping[str, Any],
    operational_seed: Mapping[str, Any],
) -> None:
    """Upsert a verified catalog/seed into the operational SQLite database.

    The routine intentionally touches only allowlisted catalog and seed tables.
    Orders, payments, movements, snapshots, audit and gateway outbox rows are
    never deleted or rewritten by a catalog renewal.
    """
    if engine.dialect.name != "sqlite":
        raise BusinessError("offline_bundle_target_invalid", "Catalog target must be SQLite")
    organization_id = _manifest_scope(manifest, "organization_id")
    branch_id = _manifest_scope(manifest, "branch_id")
    bundle_hash = _manifest_scope(manifest, "bundle_hash")
    catalog_rows = _decode_catalog(manifest, catalog)
    seed_rows = _decode_payload(operational_seed, OPERATIONAL_SEED_SCHEMA, _SEED_TABLES, "seed")
    _validate_scope(catalog_rows, seed_rows, organization_id, branch_id)
    _validate_foreign_keys(catalog_rows, seed_rows)
    _create_snapshot_tables(engine, full_operational_schema=True)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    target = factory()
    try:
        target.rollback()
        with target.begin():
            target.execute(sa.text("BEGIN IMMEDIATE"))
            _validate_generation(target, manifest)
            _upsert_hydrated_rows(target, catalog_rows, seed_rows)
            _store_generation(target, manifest)
            marker = (
                target.execute(
                    sa.select(_catalog_installations).where(
                        _catalog_installations.c.branch_id == branch_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            values = {
                "organization_id": organization_id,
                "bundle_hash": bundle_hash,
                "installed_at": datetime.now(UTC),
            }
            if marker is None:
                target.execute(
                    _catalog_installations.insert().values(branch_id=branch_id, **values)
                )
            elif marker["organization_id"] != organization_id:
                raise BusinessError(
                    "offline_bundle_target_conflict", "Catalog target has another scope"
                )
            else:
                target.execute(
                    _catalog_installations.update()
                    .where(_catalog_installations.c.branch_id == branch_id)
                    .values(**values)
                )
    except Exception:
        target.rollback()
        raise
    finally:
        target.close()


def _decode_catalog(
    manifest: Mapping[str, Any],
    catalog: Mapping[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    if not isinstance(catalog, Mapping):
        raise BusinessError("offline_bundle_catalog_invalid", "Bundle catalog is invalid")
    is_v3 = catalog.get("schema_version") == CLASSIFICATION_CATALOG_SCHEMA
    generation, mode = _generation(manifest)
    if is_v3 != (generation is not None):
        raise BusinessError("offline_bundle_catalog_invalid", "Catalog generation/schema mismatch")
    names = (
        _CATALOG_TABLES
        if is_v3
        else tuple(name for name in _CATALOG_TABLES if name not in _CLASSIFICATION_TABLES)
    )
    rows = _decode_payload(
        catalog,
        CLASSIFICATION_CATALOG_SCHEMA,
        names,
        "catalog",
        compatible_schemas=(CATALOG_SCHEMA, _LEGACY_CATALOG_SCHEMA),
    )
    for category in rows["product_categories"]:
        version = category.get("configuration_version")
        if (
            type(version) is not int
            or version < 1
            or category.get("classification_code") not in {None, "food", "drinks", "other"}
        ):
            raise BusinessError(
                "offline_bundle_catalog_invalid", "Category configuration is invalid"
            )
    if mode == "explicit" and any(
        row["status"] == "active"
        and row.get("classification_code") not in {"food", "drinks", "other"}
        for row in rows["product_categories"]
    ):
        raise BusinessError("offline_bundle_catalog_invalid", "Active category is unclassified")
    if is_v3:
        groups = {row["id"]: row for row in rows["category_option_groups"]}
        values = {row["id"]: row for row in rows["category_option_values"]}
        products = {row["id"]: row for row in rows["products"]}
        for assignment in rows["product_option_value_assignments"]:
            group = groups.get(assignment["group_id"])
            value = values.get(assignment["option_value_id"])
            product = products.get(assignment["product_id"])
            if (
                group is None
                or value is None
                or product is None
                or value["group_id"] != group["id"]
                or product["category_id"] != group["category_id"]
            ):
                raise BusinessError(
                    "offline_bundle_scope_invalid", "Subgroup assignment is invalid"
                )
    return rows


def _generation(manifest: Mapping[str, Any]) -> tuple[int | None, str]:
    generation = manifest.get("catalog_generation")
    mode = manifest.get("catalog_classification_mode", "legacy")
    if generation is None:
        if "catalog_generation" in manifest or mode != "legacy":
            raise BusinessError("offline_bundle_catalog_invalid", "Catalog generation is invalid")
        return None, "legacy"
    if (
        type(generation) is not int
        or generation < 1
        or mode not in ("legacy", "explicit")
        or "catalog_classification_mode" not in manifest
    ):
        raise BusinessError("offline_bundle_catalog_invalid", "Catalog generation is invalid")
    return generation, str(mode)


def _validate_generation(session: Session, manifest: Mapping[str, Any]) -> None:
    generation, mode = _generation(manifest)
    installed = (
        session.execute(
            sa.select(_catalog_generations).where(
                _catalog_generations.c.branch_id == manifest["branch_id"]
            )
        )
        .mappings()
        .one_or_none()
    )
    if installed is None:
        return
    if (
        installed["organization_id"] != manifest["organization_id"]
        or generation is None
        or generation < installed["catalog_generation"]
        or (
            generation == installed["catalog_generation"]
            and (
                mode != installed["catalog_classification_mode"]
                or manifest["bundle_hash"] != installed["bundle_hash"]
            )
        )
    ):
        raise BusinessError("offline_catalog_generation_conflict", "Catalog generation rejected")


def validate_catalog_refresh(engine: Engine, bundle: Mapping[str, Any]) -> None:
    """Read-only preflight before freezing command admission; repeat under install lock."""
    manifest = bundle["manifest"]
    rows = _decode_catalog(manifest, bundle["catalog"])
    seed = _decode_payload(
        bundle["operational_seed"], OPERATIONAL_SEED_SCHEMA, _SEED_TABLES, "seed"
    )
    _validate_scope(rows, seed, manifest["organization_id"], manifest["branch_id"])
    _validate_foreign_keys(rows, seed)
    if sa.inspect(engine).has_table(_catalog_generations.name):
        with Session(engine) as session:
            _validate_generation(session, manifest)


def get_installed_classification_metadata(
    session: Session,
    branch_id: str,
) -> dict[str, Any] | None:
    """Return a verified installation; absent markers identify a central database."""
    inspector = sa.inspect(session.connection())
    if not inspector.has_table(_catalog_installations.name):
        return None
    installation = (
        session.execute(
            sa.select(_catalog_installations).where(
                _catalog_installations.c.branch_id == branch_id,
            )
        )
        .mappings()
        .one_or_none()
    )
    if installation is None:
        return None
    if inspector.has_table(_catalog_generations.name):
        marker = (
            session.execute(
                sa.select(_catalog_generations).where(
                    _catalog_generations.c.branch_id == branch_id,
                )
            )
            .mappings()
            .one_or_none()
        )
        if marker is not None:
            return {
                "catalog_generation": marker["catalog_generation"],
                "catalog_classification_mode": marker["catalog_classification_mode"],
                "catalog_hash": marker["bundle_hash"],
            }
    return {
        "catalog_generation": 0,
        "catalog_classification_mode": "legacy",
        "catalog_hash": installation["bundle_hash"],
    }


def get_installed_classification_mode(session: Session, branch_id: str) -> str | None:
    metadata = get_installed_classification_metadata(session, branch_id)
    return str(metadata["catalog_classification_mode"]) if metadata is not None else None


def _store_generation(session: Session, manifest: Mapping[str, Any]) -> None:
    generation, mode = _generation(manifest)
    if generation is None:
        return
    statement = sqlite.insert(_catalog_generations).values(
        branch_id=manifest["branch_id"],
        organization_id=manifest["organization_id"],
        bundle_hash=manifest["bundle_hash"],
        catalog_generation=generation,
        catalog_classification_mode=mode,
    )
    session.execute(
        statement.on_conflict_do_update(
            index_elements=["branch_id"],
            set_={
                column.name: statement.excluded[column.name]
                for column in _catalog_generations.columns
                if column.name != "branch_id"
            },
        )
    )


def _require_scope(organization_id: str, branch_id: str) -> None:
    if (
        not isinstance(organization_id, str)
        or not organization_id
        or not isinstance(branch_id, str)
        or not branch_id
    ):
        raise BusinessError("offline_bundle_scope_invalid", "Bundle scope is invalid")


def _manifest_scope(manifest: Mapping[str, Any], field: str) -> str:
    value = manifest.get(field)
    if not isinstance(value, str) or not value:
        raise BusinessError("offline_bundle_catalog_invalid", "Bundle manifest scope is invalid")
    return value


def _one(session: Session, table: sa.Table, *criteria: Any) -> dict[str, Any]:
    row = session.execute(sa.select(table).where(*criteria)).mappings().one_or_none()
    if row is None:
        raise BusinessError(
            "offline_bundle_catalog_invalid", f"Catalog {table.name} scope is invalid"
        )
    return dict(row)


def _rows(session: Session, table: sa.Table, *criteria: Any) -> list[dict[str, Any]]:
    if any(not values for values in (criteria,)):
        return []
    return [dict(row) for row in session.execute(sa.select(table).where(*criteria)).mappings()]


def _clear_foreign_auditors(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    for row in rows:
        for field in ("created_by", "updated_by", "actor_user_id"):
            if field in row:
                row[field] = None
    return rows


def _wire(value: Any) -> Any:
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # SQLite intentionally returns the canonical UTC fields without a
            # tzinfo.  The database contract already defines them as UTC; do
            # not turn a valid gateway snapshot into a local-time conversion.
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).isoformat().replace("+00:00", "Z")
    if isinstance(value, Mapping):
        return {str(key): _wire(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_wire(item) for item in value]
    return value


def _decode_payload(
    payload: Mapping[str, Any] | None,
    schema: str,
    names: tuple[str, ...],
    label: str,
    *,
    compatible_schemas: tuple[str, ...] = (),
) -> dict[str, list[dict[str, Any]]]:
    actual_schema = payload.get("schema_version") if isinstance(payload, Mapping) else None
    if (
        not isinstance(payload, Mapping)
        or set(payload) != {"schema_version", "tables"}
        or actual_schema not in {schema, *compatible_schemas}
    ):
        raise BusinessError("offline_bundle_catalog_invalid", f"Bundle {label} is invalid")
    raw_tables = payload.get("tables")
    if not isinstance(raw_tables, Mapping) or set(raw_tables) != set(names):
        raise BusinessError(
            "offline_bundle_catalog_invalid", f"Bundle {label} table set is invalid"
        )
    decoded: dict[str, list[dict[str, Any]]] = {}
    for name in names:
        table = _table(name)
        raw_rows = raw_tables[name]
        if not isinstance(raw_rows, list):
            raise BusinessError(
                "offline_bundle_catalog_invalid", f"Bundle {label} rows are invalid"
            )
        expected = {column.name for column in table.columns}
        legacy_defaults: dict[str, Any] = {}
        if actual_schema == _LEGACY_CATALOG_SCHEMA and label == "catalog":
            if name == "modifier_groups":
                legacy_defaults = {"included_selections": 0}
            elif name == "modifier_options":
                legacy_defaults = {
                    "component_product_id": None,
                    "component_quantity": None,
                }
        if name == "product_categories" and actual_schema != CLASSIFICATION_CATALOG_SCHEMA:
            legacy_defaults.update(classification_code=None, configuration_version=1)
        accepted = expected - set(legacy_defaults)
        values: list[dict[str, Any]] = []
        for raw in raw_rows:
            raw_columns = frozenset(raw) if isinstance(raw, Mapping) else frozenset()
            if not isinstance(raw, Mapping) or raw_columns not in {
                frozenset(expected),
                frozenset(accepted),
            }:
                raise BusinessError(
                    "offline_bundle_catalog_invalid", f"Bundle {label} row is invalid"
                )
            normalized = {**legacy_defaults, **raw}
            values.append(
                {
                    column.name: _decode_column(column, normalized[column.name])
                    for column in table.columns
                }
            )
        decoded[name] = values
    return decoded


def _decode_column(column: sa.Column[Any], value: Any) -> Any:
    if value is None:
        return None
    if isinstance(column.type, sa.DateTime):
        if not isinstance(value, str):
            raise BusinessError("offline_bundle_catalog_invalid", "Bundle timestamp is invalid")
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise BusinessError(
                "offline_bundle_catalog_invalid", "Bundle timestamp is invalid"
            ) from exc
        if parsed.tzinfo is None:
            raise BusinessError("offline_bundle_catalog_invalid", "Bundle timestamp is invalid")
        return parsed.astimezone(UTC)
    if isinstance(column.type, sa.Numeric):
        if not isinstance(value, str):
            raise BusinessError("offline_bundle_catalog_invalid", "Bundle decimal is invalid")
        try:
            return Decimal(value)
        except Exception as exc:
            raise BusinessError(
                "offline_bundle_catalog_invalid", "Bundle decimal is invalid"
            ) from exc
    return value


def _validate_scope(
    catalog: Mapping[str, list[dict[str, Any]]],
    seed: Mapping[str, list[dict[str, Any]]],
    organization_id: str,
    branch_id: str,
) -> None:
    organization_tables = {
        "legal_entities",
        "business_units",
        "warehouses",
        "product_categories",
        "category_option_groups",
        "inventory_units",
        "inventory_items",
        "products",
        "price_versions",
        "modifier_groups",
        "order_comment_presets",
        "ingredient_variations",
        "recipes",
        "product_compositions",
        "roles",
        "users",
        "cash_shifts",
    }
    if {row["id"] for row in catalog["organizations"]} != {organization_id}:
        raise BusinessError("offline_bundle_scope_invalid", "Bundle organization scope is invalid")
    for name in organization_tables:
        rows = catalog.get(name, []) + seed.get(name, [])
        if any(row.get("organization_id") != organization_id for row in rows):
            raise BusinessError(
                "offline_bundle_scope_invalid", "Bundle organization scope is invalid"
            )
    exact_branch_tables = {
        "warehouses",
        "branch_product_availability",
        "branch_modifier_options",
        "inventory_cost_states",
        "cash_shifts",
    }
    if {row["id"] for row in catalog["branches"]} != {branch_id}:
        raise BusinessError("offline_bundle_scope_invalid", "Bundle branch scope is invalid")
    for name in exact_branch_tables:
        rows = catalog.get(name, []) + seed.get(name, [])
        if any(row.get("branch_id") != branch_id for row in rows):
            raise BusinessError("offline_bundle_scope_invalid", "Bundle branch scope is invalid")
    for name in ("products", "inventory_items"):
        for row in catalog[name]:
            if row["catalog_scope"] == "organization" and row["source_branch_id"] is None:
                continue
            if row["catalog_scope"] == "branch" and row["source_branch_id"] == branch_id:
                continue
            raise BusinessError("offline_bundle_scope_invalid", "Catalog item scope is invalid")
    for name in ("recipes", "product_compositions"):
        if any(row["branch_id"] not in (None, branch_id) for row in catalog[name]):
            raise BusinessError("offline_bundle_scope_invalid", "Catalog version scope is invalid")
    if any(row["branch_id"] not in (None, branch_id) for row in seed["user_roles"]):
        raise BusinessError("offline_bundle_scope_invalid", "Actor role scope is invalid")


def _validate_foreign_keys(
    catalog: Mapping[str, list[dict[str, Any]]], seed: Mapping[str, list[dict[str, Any]]]
) -> None:
    rows = {**catalog, **seed}
    for name, table_rows in rows.items():
        table = _table(name)
        for constraint in table.foreign_key_constraints:
            parents = tuple(element.parent.name for element in constraint.elements)
            ref_table = constraint.elements[0].column.table.name
            references = tuple(element.column.name for element in constraint.elements)
            if ref_table not in rows:
                for row in table_rows:
                    if any(row[field] is not None for field in parents):
                        raise BusinessError(
                            "offline_bundle_catalog_invalid", "Bundle reference is not allowed"
                        )
                continue
            allowed = {
                tuple(reference_row[field] for field in references)
                for reference_row in rows[ref_table]
            }
            for row in table_rows:
                source = tuple(row[field] for field in parents)
                if any(value is None for value in source):
                    continue
                if source not in allowed:
                    raise BusinessError(
                        "offline_bundle_catalog_invalid", "Bundle foreign key is invalid"
                    )


def _create_snapshot_tables(engine: Engine, *, full_operational_schema: bool) -> None:
    _catalog_generations.create(engine, checkfirst=True)
    if sa.inspect(engine).has_table("product_categories"):
        columns = {
            column["name"] for column in sa.inspect(engine).get_columns("product_categories")
        }
        with engine.begin() as connection:
            if "classification_code" not in columns:
                connection.execute(
                    sa.text(
                        "ALTER TABLE product_categories ADD COLUMN classification_code VARCHAR(16)"
                    )
                )
            if "configuration_version" not in columns:
                connection.execute(
                    sa.text(
                        "ALTER TABLE product_categories ADD COLUMN "
                        "configuration_version INTEGER NOT NULL DEFAULT 1"
                    )
                )
    if full_operational_schema:
        models.metadata.create_all(engine)
        _catalog_installations.create(engine, checkfirst=True)
        return
    for name in (*_SEED_TABLES, *_CATALOG_TABLES):
        _table(name).create(engine, checkfirst=True)
    for name in _SCHEMA_ONLY_TABLES:
        _table(name).create(engine, checkfirst=True)
    _catalog_installations.create(engine, checkfirst=True)


def _set_read_only(session: Session) -> None:
    # The catalog connection is never the operational connection.  SQLite's
    # query_only guard makes accidental writes by a future catalog reader fail
    # closed after the atomic installation transaction has committed.
    session.execute(sa.text("PRAGMA query_only = ON"))


def _enforce_read_only(engine: Engine) -> None:
    if engine in _READ_ONLY_ENGINES:
        return

    def set_query_only(dbapi_connection: Any, _connection_record: Any) -> None:
        dbapi_connection.execute("PRAGMA query_only = ON")

    event.listen(engine, "connect", set_query_only)
    _READ_ONLY_ENGINES.add(engine)


def _target_has_catalog_data(session: Session) -> bool:
    return any(
        session.scalar(sa.select(sa.func.count()).select_from(_table(name)))
        for name in (*_SEED_TABLES, *_CATALOG_TABLES)
    )


def _insert_hydrated_rows(
    session: Session,
    catalog_rows: Mapping[str, list[dict[str, Any]]],
    seed_rows: Mapping[str, list[dict[str, Any]]],
) -> None:
    # The branch topology is required by user roles and cash shifts.  The user
    # seed in turn is required by versioned compositions.  This one ordering is
    # intentionally shared by both SQLite databases and works with FK checks on.
    topology = ("organizations", "legal_entities", "business_units", "branches", "warehouses")
    catalog_rest = tuple(name for name in _CATALOG_TABLES if name not in topology)
    for name in (*topology, *_SEED_TABLES, *catalog_rest):
        values = (catalog_rows if name in catalog_rows else seed_rows).get(name, [])
        if values:
            session.execute(_table(name).insert(), values)


def _upsert_hydrated_rows(
    session: Session,
    catalog_rows: Mapping[str, list[dict[str, Any]]],
    seed_rows: Mapping[str, list[dict[str, Any]]],
) -> None:
    # RBAC links are a scoped replacement, rather than an upsert.  SQLite
    # treats NULL values in a composite unique key as distinct, so upserting
    # ``user_roles`` would retain a revoked corporate role and can duplicate a
    # branch-less link on every renewal.  Replacing only the bundle's users and
    # branch leaves historical identities and all operational facts intact.
    if "product_option_value_assignments" in catalog_rows:
        product_ids = {row["id"] for row in catalog_rows["products"]}
        session.execute(
            models.product_option_value_assignments.delete().where(
                models.product_option_value_assignments.c.product_id.in_(product_ids)
            )
        )
    binding_tables = {"role_permissions", "role_authority_grants", "user_roles"}
    topology = ("organizations", "legal_entities", "business_units", "branches", "warehouses")
    catalog_rest = tuple(name for name in _CATALOG_TABLES if name not in topology)
    for name in (*topology, *_SEED_TABLES, *catalog_rest):
        if name in binding_tables:
            continue
        values = (catalog_rows if name in catalog_rows else seed_rows).get(name, [])
        if not values:
            continue
        table = _table(name)
        primary = [column.name for column in table.primary_key.columns]
        if not primary:
            raise RuntimeError(f"Offline catalog table {name} has no primary key")
        insert = sqlite.insert(table).values(values)
        updates = {
            column.name: insert.excluded[column.name]
            for column in table.columns
            if column.name not in primary
        }
        statement = (
            insert.on_conflict_do_update(index_elements=primary, set_=updates)
            if updates
            else insert.on_conflict_do_nothing(index_elements=primary)
        )
        session.execute(statement)
    _replace_seed_role_bindings(session, catalog_rows, seed_rows)


def _replace_seed_role_bindings(
    session: Session,
    catalog_rows: Mapping[str, list[dict[str, Any]]],
    seed_rows: Mapping[str, list[dict[str, Any]]],
) -> None:
    """Replace only authorization links represented by the refreshed seed."""
    branch_rows = catalog_rows["branches"]
    if len(branch_rows) != 1:
        raise BusinessError("offline_bundle_scope_invalid", "Bundle branch scope is invalid")
    branch_id = str(branch_rows[0]["id"])
    organization_id = str(branch_rows[0]["organization_id"])
    # A gateway contains authority for one organization/branch only.  Clear
    # that entire local authority projection before restoring the signed seed:
    # an actor removed from the next seed must not retain a prior user_roles
    # row.  User identities themselves remain for historical orders, payments
    # and audit foreign keys.
    role_ids = set(
        session.scalars(
            sa.select(models.roles.c.id).where(models.roles.c.organization_id == organization_id)
        )
    )
    user_ids = set(
        session.scalars(
            sa.select(models.users.c.id).where(models.users.c.organization_id == organization_id)
        )
    )
    if role_ids:
        session.execute(
            models.role_permissions.delete().where(models.role_permissions.c.role_id.in_(role_ids))
        )
        session.execute(
            models.role_authority_grants.delete().where(
                models.role_authority_grants.c.role_id.in_(role_ids)
            )
        )
    if user_ids:
        session.execute(
            models.user_roles.delete().where(
                models.user_roles.c.user_id.in_(user_ids),
                sa.or_(
                    models.user_roles.c.branch_id.is_(None),
                    models.user_roles.c.branch_id == branch_id,
                ),
            )
        )
    for name in ("role_permissions", "role_authority_grants", "user_roles"):
        values = seed_rows[name]
        if values:
            session.execute(_table(name).insert(), values)


def _table(name: str) -> sa.Table:
    table = getattr(models, name, None)
    if not isinstance(table, sa.Table):
        raise RuntimeError(f"Unknown offline catalog table: {name}")
    return table
