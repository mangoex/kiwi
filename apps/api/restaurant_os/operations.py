from __future__ import annotations

import hashlib
import json
import logging

# ruff: noqa: E501, E402
from datetime import datetime, timezone

UTC = timezone.utc

UTC = UTC
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.auth import (
    PASSWORD_ALGORITHM,
    generate_password_salt,
    hash_password,
    verify_password,
)
from restaurant_os.catalog_policy import (
    canonical_category_name,
    is_numeric_sku,
    is_uppercase_name,
    normalize_inventory_sku,
    normalize_product_sku,
)

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
DEFAULT_REGISTER = "CAJA-01"
logger = logging.getLogger(__name__)


class BusinessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class AuthorizationError(BusinessError):
    pass


class NotFoundError(BusinessError):
    pass


ADMIN_PERMISSIONS = {
    "admin.manage",
    "catalog.manage",
    "inventory.adjust",
    "orders.cancel",
    "cash.shift.read",
    "cash.shift.open",
    "cash.shift.close",
    "orders.read",
    "orders.create",
    "payments.read",
    "payments.confirm",
    "dashboard.read",
    "pos.operate",
}


def get_open_cash_shift(
    session: Session,
    register_code: str = DEFAULT_REGISTER,
    branch_id: str | None = None,
) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.select(models.cash_shifts)
            .where(
                models.cash_shifts.c.branch_id == (branch_id or BRANCH_ID),
                models.cash_shifts.c.register_code == register_code,
                sa.func.upper(models.cash_shifts.c.status) == "OPEN",
            )
            .order_by(models.cash_shifts.c.opened_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def create_role(
    session: Session,
    name: str,
    scope: str = "branch",
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    normalized_name = name.strip()
    normalized_scope = scope.strip().lower()
    if not normalized_name:
        raise BusinessError("invalid_role_name", "Role name is required")
    if normalized_scope not in {"organization", "branch"}:
        raise BusinessError("invalid_role_scope", "Role scope must be organization or branch")

    existing = (
        session.execute(
            sa.select(models.roles).where(
                models.roles.c.organization_id == ORGANIZATION_ID,
                sa.func.lower(models.roles.c.name) == normalized_name.lower(),
            )
        )
        .mappings()
        .first()
    )
    if existing:
        raise BusinessError("role_already_exists", "Role already exists")

    now = _now()
    role = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "name": normalized_name,
        "scope": normalized_scope,
        "created_at": now,
    }
    session.execute(models.roles.insert().values(**role))
    permission_codes = _assign_default_role_permissions(session, role["id"], normalized_name)
    _audit(
        session,
        action="role.created",
        entity_type="role",
        entity_id=role["id"],
        payload={
            "name": normalized_name,
            "scope": normalized_scope,
            "permissions": permission_codes,
        },
        actor_user_id=actor_id,
    )
    session.commit()
    return {**role, "permissions": permission_codes}


def create_user(
    session: Session,
    email: str,
    display_name: str,
    actor_user_id: str | None = None,
    password: str | None = None,
    role_id: str | None = None,
    branch_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    normalized_email = email.strip().lower()
    normalized_name = display_name.strip()
    if "@" not in normalized_email or "." not in normalized_email.split("@")[-1]:
        raise BusinessError("invalid_user_email", "User email is invalid")
    if not normalized_name:
        raise BusinessError("invalid_display_name", "Display name is required")

    existing = (
        session.execute(sa.select(models.users).where(models.users.c.email == normalized_email))
        .mappings()
        .first()
    )
    if existing:
        raise BusinessError("user_already_exists", "User already exists")

    now = _now()
    has_password = bool((password or "").strip())
    user = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "email": normalized_email,
        "display_name": normalized_name,
        "status": "active" if has_password else "invited",
        "created_at": now,
        "updated_at": now,
    }
    session.execute(models.users.insert().values(**user))
    if has_password:
        _set_user_password(session, user["id"], password or "", now)

    if role_id:
        assign_user_role(session, user["id"], role_id, branch_id, actor_id)

    _audit(
        session,
        action="user.created",
        entity_type="user",
        entity_id=user["id"],
        payload={
            "email": normalized_email,
            "display_name": normalized_name,
            "credential": "configured" if has_password else "pending",
        },
        actor_user_id=actor_id,
    )
    session.commit()
    return user


def authenticate_user(session: Session, email: str, password: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    user = (
        session.execute(sa.select(models.users).where(models.users.c.email == normalized_email))
        .mappings()
        .first()
    )
    if not user:
        raise AuthorizationError("invalid_credentials", "Email or password is invalid")
    credential = (
        session.execute(
            sa.select(models.user_credentials).where(
                models.user_credentials.c.user_id == user["id"],
                models.user_credentials.c.password_algorithm == PASSWORD_ALGORITHM,
            )
        )
        .mappings()
        .first()
    )
    if not credential or not verify_password(
        password,
        credential["password_salt"],
        credential["password_hash"],
    ):
        _record_authorization_denied(
            session,
            actor_user_id=user["id"],
            permission_code="auth.login",
            branch_id=BRANCH_ID,
            reason="invalid_credentials",
        )
        raise AuthorizationError("invalid_credentials", "Email or password is invalid")
    if user["status"] != "active":
        _record_authorization_denied(
            session,
            actor_user_id=user["id"],
            permission_code="auth.login",
            branch_id=BRANCH_ID,
            reason="inactive_user",
        )
        raise AuthorizationError("inactive_user", "User is not active")
    _audit(
        session,
        action="auth.login",
        entity_type="user",
        entity_id=user["id"],
        payload={"email": normalized_email},
        actor_user_id=user["id"],
    )
    session.commit()
    profile = dict(user)
    access_rows = session.execute(
        sa.select(
            models.roles.c.name.label("role_name"),
            models.roles.c.scope,
            models.user_roles.c.branch_id.label("role_branch_id"),
            models.permissions.c.code.label("permission_code"),
        )
        .select_from(
            models.user_roles.join(
                models.roles,
                models.user_roles.c.role_id == models.roles.c.id,
            )
            .outerjoin(
                models.role_permissions,
                models.roles.c.id == models.role_permissions.c.role_id,
            )
            .outerjoin(
                models.permissions,
                models.role_permissions.c.permission_id == models.permissions.c.id,
            )
        )
        .where(models.user_roles.c.user_id == user["id"])
    ).mappings()
    roles = []
    permissions = set()
    # Collect the first branch_id scoped to a branch role (for Caja users)
    assigned_branch_id: str | None = None
    for row in access_rows:
        role_name = row["role_name"]
        if role_name and role_name not in roles:
            roles.append(role_name)
        if row["permission_code"]:
            permissions.add(row["permission_code"])
        # Branch-scoped roles carry the specific branch_id the user is assigned to
        if row["role_branch_id"] and not assigned_branch_id:
            assigned_branch_id = row["role_branch_id"]
    profile["roles"] = roles
    profile["permissions"] = sorted(permissions)
    profile["is_superadmin"] = normalized_email == "mangoex@gmail.com"
    # Expose the branch the user is assigned to (critical for POS auto-configuration)
    profile["assigned_branch_id"] = assigned_branch_id
    return profile


def create_branch(
    session: Session,
    name: str,
    code: str,
    actor_user_id: str | None = None,
    business_unit_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    normalized_name = name.strip()
    normalized_code = code.strip().upper()
    if not normalized_name:
        raise BusinessError("invalid_branch_name", "Branch name is required")
    if not normalized_code:
        raise BusinessError("invalid_branch_code", "Branch code is required")

    existing = (
        session.execute(
            sa.select(models.branches).where(
                models.branches.c.organization_id == ORGANIZATION_ID,
                models.branches.c.code == normalized_code,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        raise BusinessError("branch_already_exists", "Branch code already exists")

    business_unit_query = sa.select(models.business_units).where(
        models.business_units.c.organization_id == ORGANIZATION_ID,
        models.business_units.c.status == "active",
    )
    if business_unit_id:
        business_unit_query = business_unit_query.where(models.business_units.c.id == business_unit_id)
    business_unit = session.execute(business_unit_query.order_by(models.business_units.c.created_at).limit(1)).mappings().first()
    if not business_unit:
        raise BusinessError("business_unit_not_found", "An active business unit is required")
    legal_entity_id = str(business_unit["legal_entity_id"])
    now = _now()
    branch = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "legal_entity_id": legal_entity_id,
        "business_unit_id": business_unit["id"],
        "name": normalized_name,
        "code": normalized_code,
        "timezone": "America/Chihuahua",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    warehouse = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": branch["id"],
        "name": f"Almacen {normalized_name}",
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    session.execute(models.branches.insert().values(**branch))
    session.execute(models.warehouses.insert().values(**warehouse))
    _audit(
        session,
        action="branch.created",
        entity_type="branch",
        entity_id=branch["id"],
        payload={
            "name": normalized_name,
            "code": normalized_code,
            "business_unit_id": business_unit["id"],
            "warehouse_id": warehouse["id"],
        },
        branch_id=branch["id"],
        actor_user_id=actor_id,
    )
    session.commit()
    return {**branch, "warehouse": warehouse}


def create_business_unit(
    session: Session,
    name: str,
    code: str,
    unit_type: str,
    legal_entity_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    normalized_name = name.strip()
    normalized_code = code.strip().upper()
    normalized_type = unit_type.strip().lower()
    if not normalized_name or not normalized_code:
        raise BusinessError("invalid_business_unit", "Business unit name and code are required")
    if normalized_type not in {"restaurant", "bakery", "production", "other"}:
        raise BusinessError(
            "invalid_business_unit_type",
            "Business unit type must be restaurant, bakery, production or other",
        )
    legal_entity = session.execute(
        sa.select(models.legal_entities.c.id).where(
            models.legal_entities.c.id == legal_entity_id,
            models.legal_entities.c.organization_id == ORGANIZATION_ID,
            models.legal_entities.c.status == "active",
        )
    ).scalar_one_or_none()
    if not legal_entity:
        raise BusinessError("legal_entity_not_found", "An active legal entity is required")
    duplicate = session.execute(
        sa.select(models.business_units.c.id).where(
            models.business_units.c.organization_id == ORGANIZATION_ID,
            models.business_units.c.code == normalized_code,
        )
    ).scalar_one_or_none()
    if duplicate:
        raise BusinessError("business_unit_already_exists", "Business unit code already exists")
    now = _now()
    business_unit = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "legal_entity_id": legal_entity_id,
        "name": normalized_name,
        "code": normalized_code,
        "unit_type": normalized_type,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    session.execute(models.business_units.insert().values(**business_unit))
    _audit(
        session,
        action="business_unit.created",
        entity_type="business_unit",
        entity_id=business_unit["id"],
        payload={"name": normalized_name, "code": normalized_code, "unit_type": normalized_type},
        branch_id=None,
        actor_user_id=actor_id,
    )
    session.commit()
    return business_unit


def create_product(
    session: Session,
    name: str,
    sku: str,
    category_name: str,
    station: str,
    price_cents: int,
    image_url: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    normalized_name = name.strip()
    normalized_sku = normalize_product_sku(sku)
    normalized_category = category_name.strip()
    normalized_station = station.strip().lower()
    if not is_uppercase_name(normalized_name):
        raise BusinessError("invalid_product_name", "Product name must be uppercase")
    if not is_numeric_sku(normalized_sku):
        raise BusinessError("invalid_product_sku", "Product SKU must contain only digits")
    if not normalized_category or normalized_category != canonical_category_name(normalized_category):
        raise BusinessError("invalid_category_name", "Category name must be uppercase")
    if normalized_station not in {"kitchen", "drinks", "packing"}:
        raise BusinessError("invalid_station", "Station must be kitchen, drinks or packing")
    if price_cents <= 0:
        raise BusinessError("invalid_price", "Price must be positive")

    existing = (
        session.execute(
            sa.select(models.products).where(
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.sku == normalized_sku,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        raise BusinessError("product_already_exists", "Product SKU already exists")

    now = _now()
    category = _get_or_create_category(session, normalized_category, now)
    product = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "category_id": category["id"],
        "name": normalized_name,
        "sku": normalized_sku,
        "description": "Producto creado desde Admin.",
        "station": normalized_station,
        "status": "active",
        "image_url": image_url.strip() if (image_url and image_url.strip()) else None,
        "created_at": now,
        "updated_at": now,
    }
    price = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "product_id": product["id"],
        "price_cents": price_cents,
        "currency": "MXN",
        "valid_from": now,
        "valid_to": None,
        "created_at": now,
    }
    availability = {
        "branch_id": BRANCH_ID,
        "product_id": product["id"],
        "is_available": True,
        "updated_at": now,
    }
    session.execute(models.products.insert().values(**product))
    session.execute(models.price_versions.insert().values(**price))
    session.execute(models.branch_product_availability.insert().values(**availability))
    _audit(
        session,
        action="product.created",
        entity_type="product",
        entity_id=product["id"],
        payload={"sku": normalized_sku, "price_cents": price_cents, "station": normalized_station},
        actor_user_id=actor_id,
    )
    session.commit()
    return {
        **product,
        "category_name": category["name"],
        "price_cents": price_cents,
        "currency": "MXN",
        "is_available": True,
    }


def record_inventory_opening_balance(
    session: Session,
    item_id: str,
    quantity_base_units: int,
    reason: str = "Saldo inicial",
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "inventory.adjust")
    normalized_item_id = item_id.strip()
    normalized_reason = reason.strip() or "Saldo inicial"
    if quantity_base_units <= 0:
        raise BusinessError("invalid_inventory_quantity", "Inventory quantity must be positive")

    item = (
        session.execute(
            sa.select(
                models.inventory_items.c.id,
                models.inventory_items.c.name,
                models.inventory_items.c.base_unit_id,
                models.inventory_units.c.code.label("unit_code"),
            )
            .select_from(
                models.inventory_items.join(
                    models.inventory_units,
                    models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
                )
            )
            .where(
                models.inventory_items.c.id == normalized_item_id,
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if not item:
        raise BusinessError("inventory_item_not_found", "Inventory item was not found")

    warehouse_id = _branch_warehouse_id(session)
    now = _now()
    movement = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": BRANCH_ID,
        "warehouse_id": warehouse_id,
        "item_id": item["id"],
        "movement_type": "OPENING_BALANCE",
        "quantity_delta": quantity_base_units,
        "unit_id": item["base_unit_id"],
        "reason": normalized_reason,
        "source_type": "admin",
        "source_id": None,
        "created_at": now,
    }
    session.execute(models.inventory_movements.insert().values(**movement))
    _audit(
        session,
        action="inventory.opening_balance_recorded",
        entity_type="inventory_movement",
        entity_id=movement["id"],
        payload={
            "item_id": item["id"],
            "item_name": item["name"],
            "quantity_delta": quantity_base_units,
            "unit_code": item["unit_code"],
        },
        branch_id=BRANCH_ID,
        actor_user_id=actor_id,
    )
    session.commit()
    return {**movement, "item_name": item["name"], "unit_code": item["unit_code"]}


def assign_user_role(
    session: Session,
    user_id: str,
    role_id: str,
    branch_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    user = (
        session.execute(sa.select(models.users).where(models.users.c.id == user_id))
        .mappings()
        .first()
    )
    if not user:
        raise BusinessError("user_not_found", "User was not found")
    role = (
        session.execute(sa.select(models.roles).where(models.roles.c.id == role_id))
        .mappings()
        .first()
    )
    if not role:
        raise BusinessError("role_not_found", "Role was not found")

    normalized_branch_id = branch_id or None
    if role["scope"] == "branch" and not normalized_branch_id:
        normalized_branch_id = BRANCH_ID
    if role["scope"] == "organization":
        normalized_branch_id = None
    if normalized_branch_id:
        branch = session.execute(
            sa.select(models.branches.c.id).where(models.branches.c.id == normalized_branch_id)
        ).first()
        if not branch:
            raise BusinessError("branch_not_found", "Branch was not found")

    existing = (
        session.execute(
            sa.select(models.user_roles).where(
                models.user_roles.c.user_id == user_id,
                models.user_roles.c.role_id == role_id,
                models.user_roles.c.branch_id.is_(normalized_branch_id)
                if normalized_branch_id is None
                else models.user_roles.c.branch_id == normalized_branch_id,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        return dict(existing)

    assignment = {
        "user_id": user_id,
        "role_id": role_id,
        "branch_id": normalized_branch_id,
    }
    session.execute(models.user_roles.insert().values(**assignment))
    _audit(
        session,
        action="user_role.assigned",
        entity_type="user",
        entity_id=user_id,
        payload={"role_id": role_id, "branch_id": normalized_branch_id},
        branch_id=normalized_branch_id or BRANCH_ID,
        actor_user_id=actor_id,
    )
    session.commit()
    return assignment


def open_cash_shift(
    session: Session,
    opening_cash_cents: int,
    register_code: str = DEFAULT_REGISTER,
    branch_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actual_branch_id = branch_id or BRANCH_ID
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "cash.shift.open", actual_branch_id)
    if get_open_cash_shift(session, register_code, branch_id=actual_branch_id):
        raise BusinessError("cash_shift_already_open", "Register already has an open shift")
    if opening_cash_cents < 0:
        raise BusinessError("invalid_opening_cash", "Opening cash cannot be negative")

    now = _now()
    shift = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": actual_branch_id,
        "register_code": register_code,
        "status": "OPEN",
        "opening_cash_cents": opening_cash_cents,
        "opened_at": now,
        "closed_at": None,
        "created_at": now,
    }
    session.execute(models.cash_shifts.insert().values(**shift))
    _audit(
        session,
        action="cash_shift.opened",
        entity_type="cash_shift",
        entity_id=shift["id"],
        payload={"register_code": register_code, "opening_cash_cents": opening_cash_cents},
        branch_id=shift["branch_id"],
        actor_user_id=actor_id,
    )
    session.commit()
    return shift


def close_cash_shift(session: Session, register_code: str = DEFAULT_REGISTER, branch_id: str | None = None, actor_user_id: str | None = None) -> dict[str, Any]:
    shift = get_open_cash_shift(session, register_code, branch_id=branch_id)
    if not shift:
        raise BusinessError("cash_shift_not_open", "Register does not have an open shift")

    return close_cash_shift_with_cut(
        session,
        counted_cash_cents=_cash_summary_for_shift(session, shift)["expected_cash_cents"],
        register_code=register_code,
        branch_id=branch_id,
        actor_user_id=actor_user_id,
    )


def close_cash_shift_with_cut(
    session: Session,
    counted_cash_cents: int,
    register_code: str = DEFAULT_REGISTER,
    branch_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actual_branch_id = branch_id or BRANCH_ID
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "cash.shift.close", actual_branch_id)
    shift = get_open_cash_shift(session, register_code, branch_id=actual_branch_id)
    if not shift:
        raise BusinessError("cash_shift_not_open", "Register does not have an open shift")
    if counted_cash_cents < 0:
        raise BusinessError("invalid_counted_cash", "Counted cash cannot be negative")

    now = _now()
    summary = _cash_summary_for_shift(session, shift)
    cut = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": shift["branch_id"],
        "cash_shift_id": shift["id"],
        "sales_total_cents": summary["sales_total_cents"],
        "payment_total_cents": summary["payment_total_cents"],
        "cash_payment_total_cents": summary["cash_payment_total_cents"],
        "opening_cash_cents": shift["opening_cash_cents"],
        "expected_cash_cents": summary["expected_cash_cents"],
        "counted_cash_cents": counted_cash_cents,
        "difference_cents": counted_cash_cents - summary["expected_cash_cents"],
        "status": "FINAL",
        "created_at": now,
    }
    session.execute(
        models.cash_shifts.update()
        .where(models.cash_shifts.c.id == shift["id"])
        .values(status="CLOSED", closed_at=now)
    )
    session.execute(models.cash_shift_cuts.insert().values(**cut))
    _audit(
        session,
        action="cash_shift.closed",
        entity_type="cash_shift",
        entity_id=shift["id"],
        payload={
            "register_code": register_code,
            "cut_id": cut["id"],
            "expected_cash_cents": cut["expected_cash_cents"],
            "counted_cash_cents": counted_cash_cents,
            "difference_cents": cut["difference_cents"],
        },
        branch_id=shift["branch_id"],
        actor_user_id=actor_id,
    )
    session.commit()
    shift["status"] = "CLOSED"
    shift["closed_at"] = now
    return {**shift, "cut": cut}


def create_local_order(
    session: Session,
    lines: list[dict[str, Any]],
    owner_name: str | None = None,
    order_type: str = "dine-in",
    branch_id: str | None = None,
    register_id: str | None = None,
    actor_user_id: str | None = None,
    customer_id: str | None = None,
    delivery_address_id: str | None = None,
) -> dict[str, Any]:
    if not lines:
        raise BusinessError("invalid_quantity", "Order must have at least one line")

    register_code = register_id or DEFAULT_REGISTER
    actual_branch_id = branch_id or BRANCH_ID
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "orders.create", actual_branch_id)
    shift = get_open_cash_shift(session, register_code=register_code, branch_id=actual_branch_id)
    if not shift:
        raise BusinessError("cash_shift_required", "Open cash shift is required")

    now = _now()
    order_id = _id()
    folio = _next_unique_folio(session, actual_branch_id)
    customer_snapshot, address_snapshot = _resolve_order_customer_snapshots(
        session,
        customer_id=customer_id,
        delivery_address_id=delivery_address_id,
        order_type=order_type,
    )
    if customer_snapshot:
        owner_name = str(customer_snapshot["name"])

    total_cents = 0
    order_lines_data = []
    tasks_data = []
    consumption_snapshots_data = []

    for item in lines:
        product_id = item.get("product_id")
        quantity = int(item.get("quantity", 1))

        if quantity <= 0:
            raise BusinessError("invalid_quantity", "Quantity must be positive")

        product = _get_available_product(session, product_id, actual_branch_id)
        if not product:
            raise BusinessError("product_unavailable", f"Product {product_id} is unavailable")

        order_line_id = _id()
        consumption_snapshot = _build_order_consumption_snapshot(
            session,
            order_id=order_id,
            order_line_id=order_line_id,
            product_id=product["id"],
            ordered_quantity=quantity,
            branch_id=actual_branch_id,
            created_at=now,
            selected_modifiers=list(item.get("modifiers", [])),
        )
        modifier_total_cents = int(consumption_snapshot["modifier_total_cents"])
        line_total = int(product["price_cents"]) * quantity + modifier_total_cents
        total_cents += line_total

        order_lines_data.append({
            "id": order_line_id,
            "order_id": order_id,
            "product_id": product["id"],
            "product_name": product["name"],
            "quantity": quantity,
            "unit_price_cents": product["price_cents"],
            "line_total_cents": line_total,
            "station": product["station"],
            "selected_modifiers": consumption_snapshot["modifiers"],
            "modifier_total_cents": modifier_total_cents,
            "line_notes": item.get("notes"),
            "created_at": now,
        })

        tasks_data.append({
            "id": _id(),
            "organization_id": ORGANIZATION_ID,
            "branch_id": actual_branch_id,
            "order_id": order_id,
            "order_line_id": order_line_id,
            "station": product["station"],
            "status": "PENDING",
            "product_name": product["name"],
            "quantity": quantity,
            "created_at": now,
            "started_at": None,
            "completed_at": None,
        })

        _record_calculated_consumption_movements(
            session,
            components=consumption_snapshot["components"],
            product_name=product["name"],
            movement_type="SALE_RESERVATION",
            sign=-1,
            reason=f"Reserva por pedido {folio}",
            source_type="order",
            source_id=order_id,
            created_at=now,
            branch_id=actual_branch_id,
        )
        consumption_snapshot.pop("modifier_total_cents")
        consumption_snapshots_data.append(consumption_snapshot)

    order = {
        "id": order_id,
        "organization_id": ORGANIZATION_ID,
        "branch_id": actual_branch_id,
        "cash_shift_id": shift["id"],
        "customer_id": customer_id,
        "customer_snapshot": customer_snapshot,
        "delivery_address_snapshot": address_snapshot,
        "folio": folio,
        "channel": "POS",
        "status": "ACCEPTED",
        "total_cents": total_cents,
        "currency": "MXN",
        "owner_name": owner_name,
        "order_type": order_type,
        "created_at": now,
        "accepted_at": now,
    }

    session.execute(models.orders.insert().values(**order))
    for line in order_lines_data:
        session.execute(models.order_lines.insert().values(**line))
    for snapshot in consumption_snapshots_data:
        session.execute(models.order_line_consumption_snapshots.insert().values(**snapshot))
    for task in tasks_data:
        session.execute(models.production_tasks.insert().values(**task))

    session.execute(
        models.order_events.insert().values(
            id=_id(),
            order_id=order_id,
            event_type="ORDER_ACCEPTED",
            payload={"folio": folio, "total_cents": total_cents, "lines_count": len(order_lines_data)},
            created_at=now,
        )
    )

    _audit(
        session,
        action="order.accepted",
        entity_type="order",
        entity_id=order_id,
        payload={
            "folio": folio,
            "lines": len(order_lines_data),
            "total_cents": total_cents,
            "customer_id": customer_id,
            "delivery_address_id": delivery_address_id,
        },
        branch_id=actual_branch_id,
        actor_user_id=actor_id,
    )
    session.commit()
    return {
        **order,
        "lines": order_lines_data,
        "production_tasks": tasks_data,
        "consumption_snapshots": consumption_snapshots_data,
    }


def list_recent_orders(session: Session, branch_id: str | None = None) -> list[dict[str, Any]]:
    actual_branch_id = branch_id or BRANCH_ID
    rows = session.execute(
        sa.select(models.orders)
        .where(models.orders.c.branch_id == actual_branch_id)
        .order_by(models.orders.c.created_at.desc())
        .limit(20)
    ).mappings()
    return [dict(row) for row in rows]


def cancel_order(
    session: Session,
    order_id: str,
    reason: str = "Cancelacion solicitada en POS",
    classification: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    normalized_reason = reason.strip() or "Cancelacion solicitada en POS"
    normalized_classification = (classification or "").strip().lower()
    order = (
        session.execute(sa.select(models.orders).where(models.orders.c.id == order_id))
        .mappings()
        .first()
    )
    if not order:
        raise BusinessError("order_not_found", "Order was not found")
    require_permission(session, actor_id, "orders.cancel", order["branch_id"])
    if order["status"] == "CLOSED":
        raise BusinessError("order_already_closed", "Order is already closed")
    if order["status"] == "CANCELLED":
        raise BusinessError("order_already_cancelled", "Order is already cancelled")
    if order["status"] != "ACCEPTED":
        raise BusinessError("order_not_cancellable", "Order cannot be cancelled from this state")

    paid = session.execute(
        sa.select(models.payments.c.id).where(
            models.payments.c.order_id == order_id,
            models.payments.c.status == "CONFIRMED",
        )
    ).first()
    if paid:
        raise BusinessError("order_has_payment", "Paid order cannot be cancelled here")

    tasks = [
        dict(row)
        for row in session.execute(
            sa.select(models.production_tasks).where(models.production_tasks.c.order_id == order_id)
        ).mappings()
    ]
    pending_tasks = [task for task in tasks if task["status"] == "PENDING"]
    completed_tasks = [task for task in tasks if task["status"] == "COMPLETED"]
    if any(task["status"] == "IN_PROGRESS" for task in tasks):
        raise BusinessError(
            "production_in_progress",
            "Order cannot be cancelled while production is in progress",
        )
    if len(pending_tasks) != len(tasks) and len(completed_tasks) != len(tasks):
        raise BusinessError(
            "production_not_cancellable",
            "Order can only be cancelled before production or after completed production",
        )

    now = _now()
    release_movements: list[dict[str, Any]] = []
    compensation_movements: list[dict[str, Any]] = []
    lines = session.execute(
        sa.select(models.order_lines).where(models.order_lines.c.order_id == order_id)
    ).mappings()
    if len(pending_tasks) == len(tasks):
        cancellation_kind = "reservation_release"
        for line in lines:
            release_movements.extend(
                _record_snapshot_inventory_movements(
                    session,
                    order_line_id=line["id"],
                    product_name=line["product_name"],
                    movement_type="RESERVATION_RELEASE",
                    sign=1,
                    reason=f"Libera reserva por cancelacion {order['folio']}",
                    source_type="order_cancellation",
                    source_id=order_id,
                    created_at=now,
                )
            )
    else:
        if normalized_classification not in {"waste", "recovery"}:
            raise BusinessError(
                "cancellation_classification_required",
                "Post-production cancellation requires waste or recovery classification",
            )
        cancellation_kind = normalized_classification
        movement_type = "WASTE" if normalized_classification == "waste" else "RECOVERY"
        sign = 0 if normalized_classification == "waste" else 1
        for line in lines:
            compensation_movements.extend(
                _record_snapshot_inventory_movements(
                    session,
                    order_line_id=line["id"],
                    product_name=line["product_name"],
                    movement_type=movement_type,
                    sign=sign,
                    reason=(
                        f"Cancelacion producida {order['folio']} clasificada como {movement_type}"
                    ),
                    source_type="post_production_cancellation",
                    source_id=order_id,
                    created_at=now,
                )
            )

    session.execute(
        models.orders.update().where(models.orders.c.id == order_id).values(status="CANCELLED")
    )
    if pending_tasks:
        session.execute(
            models.production_tasks.update()
            .where(models.production_tasks.c.order_id == order_id)
            .values(status="CANCELLED", completed_at=now)
        )
    session.execute(
        models.order_events.insert().values(
            id=_id(),
            order_id=order_id,
            event_type="ORDER_CANCELLED",
            payload={
                "reason": normalized_reason,
                "kind": cancellation_kind,
                "classification": normalized_classification or None,
                "inventory_releases": len(release_movements),
                "inventory_compensations": len(compensation_movements),
            },
            created_at=now,
        )
    )
    _audit(
        session,
        action="order.cancelled",
        entity_type="order",
        entity_id=order_id,
        payload={
            "folio": order["folio"],
            "reason": normalized_reason,
            "kind": cancellation_kind,
            "classification": normalized_classification or None,
            "inventory_releases": len(release_movements),
            "inventory_compensations": len(compensation_movements),
        },
        branch_id=order["branch_id"],
        actor_user_id=actor_id,
    )
    session.commit()
    returned_tasks = [
        {**task, "status": "CANCELLED", "completed_at": now}
        if task["status"] == "PENDING"
        else task
        for task in tasks
    ]
    return {
        **dict(order),
        "status": "CANCELLED",
        "cancellation_kind": cancellation_kind,
        "classification": normalized_classification or None,
        "production_tasks": returned_tasks,
    }


def pay_order(
    session: Session,
    order_id: str,
    amount_cents: int,
    method: str = "cash",
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    method_normalized = method.lower()
    if method_normalized not in {"cash", "card", "debit_card", "credit_card", "transfer"}:
        raise BusinessError("invalid_payment_method", "Payment method is not supported")
    if amount_cents <= 0:
        raise BusinessError("invalid_payment_amount", "Payment amount must be positive")

    order = (
        session.execute(sa.select(models.orders).where(models.orders.c.id == order_id))
        .mappings()
        .first()
    )
    if not order:
        raise BusinessError("order_not_found", "Order was not found")
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "payments.confirm", order["branch_id"])
    if order["status"] == "CLOSED":
        raise BusinessError("order_already_closed", "Order is already closed")
    if order["status"] == "CANCELLED":
        raise BusinessError("order_cancelled", "Cancelled order cannot be paid")

    existing_payment = session.execute(
        sa.select(models.payments.c.id).where(
            models.payments.c.order_id == order_id,
            models.payments.c.status == "CONFIRMED",
        )
    ).first()
    if existing_payment:
        raise BusinessError("payment_already_confirmed", "Order already has a confirmed payment")
    if amount_cents != int(order["total_cents"]):
        raise BusinessError("payment_total_mismatch", "Payment amount must match order total")

    now = _now()
    payment = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": order["branch_id"],
        "order_id": order_id,
        "cash_shift_id": order["cash_shift_id"],
        "method": method_normalized,
        "status": "CONFIRMED",
        "amount_cents": amount_cents,
        "currency": order["currency"],
        "confirmed_at": now,
        "created_at": now,
    }
    session.execute(models.payments.insert().values(**payment))
    session.execute(
        models.orders.update().where(models.orders.c.id == order_id).values(status="CLOSED")
    )
    session.execute(
        models.order_events.insert().values(
            id=_id(),
            order_id=order_id,
            event_type="PAYMENT_CONFIRMED",
            payload={
                "payment_id": payment["id"],
                "method": method_normalized,
                "amount_cents": amount_cents,
            },
            created_at=now,
        )
    )
    session.execute(
        models.order_events.insert().values(
            id=_id(),
            order_id=order_id,
            event_type="ORDER_CLOSED",
            payload={"payment_id": payment["id"]},
            created_at=now,
        )
    )
    print_jobs = _create_print_jobs(session, dict(order), payment, now)
    _audit(
        session,
        action="payment.confirmed",
        entity_type="payment",
        entity_id=payment["id"],
        payload={"order_id": order_id, "method": method_normalized, "amount_cents": amount_cents},
        branch_id=order["branch_id"],
        actor_user_id=actor_id,
    )
    session.commit()
    return {**payment, "order_status": "CLOSED", "print_jobs": print_jobs}


def list_payments(session: Session, branch_id: str | None = None) -> list[dict[str, Any]]:
    query = (
        sa.select(
            models.payments.c.id,
            models.payments.c.order_id,
            models.payments.c.method,
            models.payments.c.status,
            models.payments.c.amount_cents,
            models.payments.c.currency,
            models.payments.c.confirmed_at,
            models.orders.c.folio,
        )
        .select_from(
            models.payments.join(models.orders, models.payments.c.order_id == models.orders.c.id)
        )
        .order_by(models.payments.c.created_at.desc())
        .limit(50)
    )
    if branch_id:
        query = query.where(models.payments.c.branch_id == branch_id)
    rows = session.execute(
        query
    ).mappings()
    return [dict(row) for row in rows]


def get_cash_shift_summary(
    session: Session,
    register_code: str = DEFAULT_REGISTER,
    branch_id: str | None = None,
) -> dict[str, Any]:
    shift = get_open_cash_shift(session, register_code, branch_id=branch_id)
    if shift:
        return {
            "cash_shift": shift,
            "cut": None,
            "summary": _cash_summary_for_shift(session, shift),
        }

    row = (
        session.execute(
            sa.select(models.cash_shifts)
            .where(
                models.cash_shifts.c.branch_id == (branch_id or BRANCH_ID),
                models.cash_shifts.c.register_code == register_code,
            )
            .order_by(models.cash_shifts.c.opened_at.desc())
            .limit(1)
        )
        .mappings()
        .first()
    )
    if not row:
        return {"cash_shift": None, "cut": None, "summary": None}

    shift = dict(row)
    cut = (
        session.execute(
            sa.select(models.cash_shift_cuts).where(
                models.cash_shift_cuts.c.cash_shift_id == shift["id"]
            )
        )
        .mappings()
        .first()
    )
    return {
        "cash_shift": shift,
        "cut": dict(cut) if cut else None,
        "summary": _cash_summary_for_shift(session, shift),
    }


def list_print_jobs(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.print_jobs.c.id,
            models.print_jobs.c.order_id,
            models.print_jobs.c.job_type,
            models.print_jobs.c.target,
            models.print_jobs.c.status,
            models.print_jobs.c.attempts,
            models.print_jobs.c.last_error,
            models.print_jobs.c.payload,
            models.print_jobs.c.created_at,
            models.print_jobs.c.printed_at,
            models.orders.c.folio,
        )
        .select_from(
            models.print_jobs.join(
                models.orders,
                models.print_jobs.c.order_id == models.orders.c.id,
            )
        )
        .where(models.print_jobs.c.branch_id == BRANCH_ID)
        .order_by(models.print_jobs.c.created_at.desc())
        .limit(50)
    ).mappings()
    return [dict(row) for row in rows]


def retry_print_job(session: Session, job_id: str) -> dict[str, Any]:
    job = (
        session.execute(sa.select(models.print_jobs).where(models.print_jobs.c.id == job_id))
        .mappings()
        .first()
    )
    if not job:
        raise BusinessError("print_job_not_found", "Print job was not found")
    if job["status"] == "PRINTED":
        raise BusinessError("print_job_already_printed", "Print job is already printed")

    now = _now()
    attempts = int(job["attempts"]) + 1
    session.execute(
        models.print_jobs.update()
        .where(models.print_jobs.c.id == job_id)
        .values(status="PRINTED", attempts=attempts, printed_at=now, last_error=None)
    )
    _audit(
        session,
        action="print_job.retried",
        entity_type="print_job",
        entity_id=job_id,
        payload={"from": job["status"], "to": "PRINTED", "attempts": attempts},
    )
    session.commit()
    updated = (
        session.execute(sa.select(models.print_jobs).where(models.print_jobs.c.id == job_id))
        .mappings()
        .one()
    )
    return dict(updated)


def receive_sync_command(session: Session, envelope: dict[str, Any]) -> dict[str, Any]:
    _validate_sync_envelope(envelope)
    idempotency_key = str(envelope["idempotency_key"])

    existing = (
        session.execute(
            sa.select(models.sync_commands).where(
                models.sync_commands.c.idempotency_key == idempotency_key
            )
        )
        .mappings()
        .first()
    )
    if existing:
        event = _get_sync_event_for_command(session, existing["id"])
        return _sync_confirmation(dict(existing), event, replayed=True)

    branch_id = str(envelope["branch_id"])
    organization_id = str(envelope["organization_id"])
    now = _now()
    checkpoint = _next_sync_checkpoint(session, branch_id)
    command = {
        "id": _id(),
        "organization_id": organization_id,
        "branch_id": branch_id,
        "source_device_id": str(envelope["source_device_id"]),
        "command_id": str(envelope["command_id"]),
        "idempotency_key": idempotency_key,
        "command_type": str(envelope["command_type"]),
        "payload": dict(envelope["payload"]),
        "status": "CONFIRMED",
        "checkpoint": checkpoint,
        "occurred_at": _parse_datetime(str(envelope["occurred_at"])),
        "received_at": now,
        "confirmed_at": now,
    }
    event = {
        "id": _id(),
        "organization_id": organization_id,
        "branch_id": branch_id,
        "sync_command_id": command["id"],
        "event_type": f"{command['command_type']}.confirmed",
        "checkpoint": checkpoint,
        "payload": {
            "command_id": command["command_id"],
            "idempotency_key": idempotency_key,
            "command_type": command["command_type"],
        },
        "occurred_at": now,
    }
    session.execute(models.sync_commands.insert().values(**command))
    session.execute(models.sync_events.insert().values(**event))
    _audit(
        session,
        action="sync_command.confirmed",
        entity_type="sync_command",
        entity_id=command["id"],
        payload={
            "command_id": command["command_id"],
            "idempotency_key": idempotency_key,
            "checkpoint": checkpoint,
        },
        branch_id=branch_id,
        organization_id=organization_id,
    )
    session.commit()
    return _sync_confirmation(command, event, replayed=False)


def list_sync_events(session: Session, after_checkpoint: int = 0) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(models.sync_events)
        .where(
            models.sync_events.c.branch_id == BRANCH_ID,
            models.sync_events.c.checkpoint > after_checkpoint,
        )
        .order_by(models.sync_events.c.checkpoint.asc())
        .limit(100)
    ).mappings()
    return [dict(row) for row in rows]


def get_sync_status(session: Session) -> dict[str, Any]:
    command_count = int(
        session.execute(
            sa.select(sa.func.count())
            .select_from(models.sync_commands)
            .where(models.sync_commands.c.branch_id == BRANCH_ID)
        ).scalar_one()
    )
    event_count = int(
        session.execute(
            sa.select(sa.func.count())
            .select_from(models.sync_events)
            .where(models.sync_events.c.branch_id == BRANCH_ID)
        ).scalar_one()
    )
    last_checkpoint = int(
        session.execute(
            sa.select(sa.func.coalesce(sa.func.max(models.sync_events.c.checkpoint), 0)).where(
                models.sync_events.c.branch_id == BRANCH_ID
            )
        ).scalar_one()
    )
    last_confirmed_at = session.execute(
        sa.select(sa.func.max(models.sync_commands.c.confirmed_at)).where(
            models.sync_commands.c.branch_id == BRANCH_ID
        )
    ).scalar_one()
    return {
        "branch_id": BRANCH_ID,
        "last_checkpoint": last_checkpoint,
        "command_count": command_count,
        "event_count": event_count,
        "last_confirmed_at": last_confirmed_at,
    }


def list_kds_tasks(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(
            models.production_tasks.c.id,
            models.production_tasks.c.station,
            models.production_tasks.c.status,
            models.production_tasks.c.product_name,
            models.production_tasks.c.quantity,
            models.production_tasks.c.created_at,
            models.production_tasks.c.started_at,
            models.production_tasks.c.completed_at,
            models.orders.c.folio,
            models.order_lines.c.selected_modifiers,
            models.order_lines.c.line_notes,
        )
        .select_from(
            models.production_tasks.join(
                models.orders,
                models.production_tasks.c.order_id == models.orders.c.id,
            ).join(
                models.order_lines,
                models.production_tasks.c.order_line_id == models.order_lines.c.id,
            )
        )
        .where(models.production_tasks.c.branch_id == BRANCH_ID)
        .order_by(models.production_tasks.c.created_at.desc())
        .limit(50)
    ).mappings()
    return [dict(row) for row in rows]


def advance_kds_task(session: Session, task_id: str, status: str) -> dict[str, Any]:
    target = status.upper()
    task = (
        session.execute(
            sa.select(models.production_tasks).where(models.production_tasks.c.id == task_id)
        )
        .mappings()
        .first()
    )
    if not task:
        raise BusinessError("task_not_found", "Production task was not found")

    current = task["status"]
    allowed = {("PENDING", "IN_PROGRESS"), ("IN_PROGRESS", "COMPLETED")}
    if (current, target) not in allowed:
        raise BusinessError("invalid_task_transition", f"Cannot move {current} to {target}")

    now = _now()
    values: dict[str, Any] = {"status": target}
    if target == "IN_PROGRESS":
        values["started_at"] = now
    if target == "COMPLETED":
        values["completed_at"] = now
        order_line = (
            session.execute(
                sa.select(models.order_lines).where(
                    models.order_lines.c.id == task["order_line_id"]
                )
            )
            .mappings()
            .one()
        )
        _record_snapshot_inventory_movements(
            session,
            order_line_id=order_line["id"],
            product_name=order_line["product_name"],
            movement_type="RESERVATION_RELEASE",
            sign=1,
            reason=f"Libera reserva por tarea {task_id}",
            source_type="production_task",
            source_id=task_id,
            created_at=now,
        )
        consumption_movements = _record_snapshot_inventory_movements(
            session,
            order_line_id=order_line["id"],
            product_name=order_line["product_name"],
            movement_type="SALE_CONSUMPTION",
            sign=-1,
            reason=f"Consumo por tarea {task_id}",
            source_type="production_task",
            source_id=task_id,
            created_at=now,
        )
    else:
        consumption_movements = []
    session.execute(
        models.production_tasks.update()
        .where(models.production_tasks.c.id == task_id)
        .values(**values)
    )
    _audit(
        session,
        action="production_task.transitioned",
        entity_type="production_task",
        entity_id=task_id,
        payload={
            "from": current,
            "to": target,
            "inventory_consumptions": len(consumption_movements),
        },
    )
    session.commit()
    updated = (
        session.execute(
            sa.select(models.production_tasks).where(models.production_tasks.c.id == task_id)
        )
        .mappings()
        .one()
    )
    return dict(updated)


def _cash_summary_for_shift(session: Session, shift: dict[str, Any]) -> dict[str, int]:
    sales_total = int(
        session.execute(
            sa.select(sa.func.coalesce(sa.func.sum(models.orders.c.total_cents), 0)).where(
                models.orders.c.cash_shift_id == shift["id"],
                models.orders.c.status == "CLOSED",
            )
        ).scalar_one()
    )
    payment_total = int(
        session.execute(
            sa.select(sa.func.coalesce(sa.func.sum(models.payments.c.amount_cents), 0)).where(
                models.payments.c.cash_shift_id == shift["id"],
                models.payments.c.status == "CONFIRMED",
            )
        ).scalar_one()
    )
    cash_payment_total = int(
        session.execute(
            sa.select(sa.func.coalesce(sa.func.sum(models.payments.c.amount_cents), 0)).where(
                models.payments.c.cash_shift_id == shift["id"],
                models.payments.c.status == "CONFIRMED",
                models.payments.c.method == "cash",
            )
        ).scalar_one()
    )
    withdrawal_total = int(session.execute(
        sa.select(sa.func.coalesce(sa.func.sum(models.cash_movements.c.amount_cents), 0)).where(
            models.cash_movements.c.cash_shift_id == shift["id"],
            models.cash_movements.c.status == "confirmed",
            models.cash_movements.c.movement_type == "withdrawal",
        )
    ).scalar_one())
    cash_reversal_total = int(session.execute(
        sa.select(sa.func.coalesce(sa.func.sum(models.cash_movements.c.amount_cents), 0)).where(
            models.cash_movements.c.cash_shift_id == shift["id"],
            models.cash_movements.c.status == "confirmed",
            models.cash_movements.c.movement_type == "cash_reversal",
        )
    ).scalar_one())
    expected_cash = int(shift["opening_cash_cents"]) + cash_payment_total - withdrawal_total + cash_reversal_total
    return {
        "sales_total_cents": sales_total,
        "payment_total_cents": payment_total,
        "cash_payment_total_cents": cash_payment_total,
        "cash_withdrawal_total_cents": withdrawal_total,
        "cash_reversal_total_cents": cash_reversal_total,
        "opening_cash_cents": int(shift["opening_cash_cents"]),
        "expected_cash_cents": expected_cash,
    }


def _create_print_jobs(
    session: Session,
    order: dict[str, Any],
    payment: dict[str, Any],
    created_at: datetime,
) -> list[dict[str, Any]]:
    lines = [
        dict(row)
        for row in session.execute(
            sa.select(models.order_lines).where(models.order_lines.c.order_id == order["id"])
        ).mappings()
    ]
    common_payload = {
        "folio": order["folio"],
        "total_cents": order["total_cents"],
        "payment_id": payment["id"],
        "lines": [
            {
                "product_name": line["product_name"],
                "quantity": line["quantity"],
                "line_total_cents": line["line_total_cents"],
                "station": line["station"],
                "selected_modifiers": line["selected_modifiers"],
            }
            for line in lines
        ],
    }
    jobs = [
        {
            "id": _id(),
            "organization_id": ORGANIZATION_ID,
            "branch_id": BRANCH_ID,
            "order_id": order["id"],
            "job_type": "ticket",
            "target": "POS-CAJA-01",
            "status": "PENDING",
            "payload": {**common_payload, "copy": "customer"},
            "attempts": 0,
            "last_error": None,
            "created_at": created_at,
            "printed_at": None,
        },
        {
            "id": _id(),
            "organization_id": ORGANIZATION_ID,
            "branch_id": BRANCH_ID,
            "order_id": order["id"],
            "job_type": "kitchen",
            "target": "KDS-COCINA",
            "status": "PENDING",
            "payload": {**common_payload, "copy": "kitchen"},
            "attempts": 0,
            "last_error": None,
            "created_at": created_at,
            "printed_at": None,
        },
    ]
    session.execute(models.print_jobs.insert(), jobs)
    for job in jobs:
        _audit(
            session,
            action="print_job.created",
            entity_type="print_job",
            entity_id=job["id"],
            payload={"order_id": order["id"], "job_type": job["job_type"], "target": job["target"]},
        )
    return jobs


def _validate_sync_envelope(envelope: dict[str, Any]) -> None:
    required = [
        "schema_version",
        "command_id",
        "idempotency_key",
        "organization_id",
        "branch_id",
        "source_device_id",
        "command_type",
        "occurred_at",
        "payload",
    ]
    missing = [field for field in required if not envelope.get(field)]
    if missing:
        raise BusinessError("invalid_sync_command", f"Missing fields: {', '.join(missing)}")
    if envelope["schema_version"] != "1.0":
        raise BusinessError("invalid_sync_schema", "Unsupported sync schema version")
    if not isinstance(envelope["payload"], dict):
        raise BusinessError("invalid_sync_payload", "Sync command payload must be an object")
    if len(str(envelope["idempotency_key"])) < 12:
        raise BusinessError("invalid_idempotency_key", "Idempotency key is too short")


def _next_sync_checkpoint(session: Session, branch_id: str) -> int:
    current = session.execute(
        sa.select(sa.func.coalesce(sa.func.max(models.sync_commands.c.checkpoint), 0)).where(
            models.sync_commands.c.branch_id == branch_id
        )
    ).scalar_one()
    return int(current) + 1


def _get_sync_event_for_command(session: Session, command_id: str) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(models.sync_events).where(models.sync_events.c.sync_command_id == command_id)
        )
        .mappings()
        .one()
    )
    return dict(row)


def _sync_confirmation(
    command: dict[str, Any],
    event: dict[str, Any],
    replayed: bool,
) -> dict[str, Any]:
    return {
        "status": command["status"],
        "checkpoint": command["checkpoint"],
        "command": command,
        "event": event,
        "replayed": replayed,
    }


def _parse_datetime(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise BusinessError("invalid_occurred_at", "occurred_at must be a date-time") from exc


def _get_available_product(session: Session, product_id: str, branch_id: str = BRANCH_ID) -> dict[str, Any] | None:
    price = (
        sa.select(
            models.price_versions.c.product_id,
            models.price_versions.c.price_cents,
            models.price_versions.c.currency,
        )
        .where(models.price_versions.c.valid_to.is_(None))
        .subquery()
    )
    row = (
        session.execute(
            sa.select(
                models.products.c.id,
                models.products.c.name,
                models.products.c.station,
                price.c.price_cents,
                price.c.currency,
            )
            .select_from(
                models.products.join(price, models.products.c.id == price.c.product_id).outerjoin(
                    models.branch_product_availability,
                    sa.and_(
                        models.products.c.id == models.branch_product_availability.c.product_id,
                        models.branch_product_availability.c.branch_id == branch_id
                    )
                )
            )
            .where(
                models.products.c.id == product_id,
                models.products.c.status == "active",
                sa.func.coalesce(models.branch_product_availability.c.is_available, True).is_(True)
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _get_or_create_category(
    session: Session,
    category_name: str,
    created_at: datetime,
) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(models.product_categories).where(
                models.product_categories.c.organization_id == ORGANIZATION_ID,
                models.product_categories.c.name == category_name,
                models.product_categories.c.status != "archived",
            )
        )
        .mappings()
        .first()
    )
    if row:
        return dict(row)

    category = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "name": category_name,
        "display_order": 100,
        "status": "active",
        "created_at": created_at,
        "updated_at": created_at,
    }
    session.execute(models.product_categories.insert().values(**category))
    return category


def _record_recipe_inventory_movements(
    session: Session,
    product_id: str,
    product_name: str,
    quantity: int,
    movement_type: str,
    sign: int,
    reason: str,
    source_type: str,
    source_id: str,
    created_at: datetime,
    branch_id: str = BRANCH_ID,
) -> list[dict[str, Any]]:
    warehouse_id = _branch_warehouse_id(session, branch_id)
    components = _active_recipe_components(session, product_id, branch_id)
    movements: list[dict[str, Any]] = []
    for component in components:
        component_quantity = _quantity(
            Decimal(str(component["gross_quantity"]))
            / Decimal(str(component["yield_quantity"]))
            * quantity
        )
        movement = {
            "id": _id(),
            "organization_id": ORGANIZATION_ID,
            "branch_id": branch_id,
            "warehouse_id": warehouse_id,
            "item_id": component["item_id"],
            "movement_type": movement_type,
            "quantity_delta": sign * component_quantity,
            "unit_id": component["unit_id"],
            "unit_cost": 0,
            "total_cost": 0,
            "effective_at": created_at,
            "actor_user_id": None,
            "document_type": None,
            "document_id": None,
            "reference": None,
            "reason": reason,
            "notes": None,
            "idempotency_key": None,
            "status": "confirmed",
            "reversal_of_id": None,
            "source_type": source_type,
            "source_id": source_id,
            "created_at": created_at,
        }
        session.execute(models.inventory_movements.insert().values(**movement))
        movements.append(
            {
                **movement,
                "item_name": component["item_name"],
                "unit_code": component["unit_code"],
                "product_name": product_name,
            }
        )
    return movements


def _record_snapshot_inventory_movements(
    session: Session,
    order_line_id: str,
    product_name: str,
    movement_type: str,
    sign: int,
    reason: str,
    source_type: str,
    source_id: str,
    created_at: datetime,
) -> list[dict[str, Any]]:
    snapshot = session.execute(sa.select(models.order_line_consumption_snapshots).where(
        models.order_line_consumption_snapshots.c.order_line_id == order_line_id
    )).mappings().first()
    if not snapshot:
        raise BusinessError("consumption_snapshot_not_found", "Order line consumption snapshot was not found")
    warehouse_id = _branch_warehouse_id(session, snapshot["branch_id"])
    movements = []
    for component in snapshot["components"]:
        quantity = _quantity(component["gross_quantity"])
        unit_cost = _cost(component.get("unit_cost", 0))
        movement = {
            "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": snapshot["branch_id"],
            "warehouse_id": warehouse_id, "item_id": component["item_id"],
            "movement_type": movement_type, "quantity_delta": sign * quantity,
            "unit_id": component["unit_id"], "unit_cost": unit_cost,
            "total_cost": sign * _cost(component.get("total_cost", 0)), "effective_at": created_at,
            "actor_user_id": None, "document_type": "order", "document_id": snapshot["order_id"],
            "reference": order_line_id, "reason": reason, "notes": None,
            "idempotency_key": None, "status": "confirmed", "reversal_of_id": None,
            "source_type": source_type, "source_id": source_id, "created_at": created_at,
        }
        session.execute(models.inventory_movements.insert().values(**movement))
        movements.append({
            **movement, "item_name": component["item_name"],
            "unit_code": component["unit_code"], "product_name": product_name,
        })
    return movements


def _record_calculated_consumption_movements(
    session: Session,
    components: list[dict[str, Any]],
    product_name: str,
    movement_type: str,
    sign: int,
    reason: str,
    source_type: str,
    source_id: str,
    created_at: datetime,
    branch_id: str,
) -> list[dict[str, Any]]:
    warehouse_id = _branch_warehouse_id(session, branch_id)
    movements = []
    for component in components:
        quantity = _quantity(component["gross_quantity"])
        unit_cost = _cost(component.get("unit_cost", 0))
        movement = {
            "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": branch_id,
            "warehouse_id": warehouse_id, "item_id": component["item_id"],
            "movement_type": movement_type, "quantity_delta": sign * quantity,
            "unit_id": component["unit_id"], "unit_cost": unit_cost,
            "total_cost": sign * _cost(component.get("total_cost", 0)), "effective_at": created_at,
            "actor_user_id": None, "document_type": "order", "document_id": source_id,
            "reference": None, "reason": reason, "notes": None, "idempotency_key": None,
            "status": "confirmed", "reversal_of_id": None,
            "source_type": source_type, "source_id": source_id, "created_at": created_at,
        }
        session.execute(models.inventory_movements.insert().values(**movement))
        movements.append({**movement, "item_name": component["item_name"], "unit_code": component["unit_code"], "product_name": product_name})
    return movements


def _active_recipe_components(
    session: Session,
    product_id: str,
    branch_id: str = BRANCH_ID,
) -> list[dict[str, Any]]:
    active_recipe_id = (
        sa.select(models.recipes.c.id)
        .where(
            models.recipes.c.product_id == product_id,
            models.recipes.c.status == "active",
            sa.or_(models.recipes.c.branch_id == branch_id, models.recipes.c.branch_id.is_(None)),
        )
        .order_by(models.recipes.c.branch_id.is_not(None).desc(), models.recipes.c.version.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = session.execute(
        sa.select(
            models.recipe_components.c.item_id,
            models.recipe_components.c.net_quantity,
            models.recipe_components.c.gross_quantity,
            models.recipe_components.c.waste_rate,
            models.recipe_components.c.unit_id,
            models.recipes.c.id.label("recipe_id"),
            models.recipes.c.version.label("recipe_version"),
            models.recipes.c.yield_quantity,
            models.inventory_items.c.name.label("item_name"),
            models.inventory_units.c.code.label("unit_code"),
        )
        .select_from(
            models.recipe_components.join(
                models.recipes,
                models.recipe_components.c.recipe_id == models.recipes.c.id,
            ).join(
                models.inventory_items,
                models.recipe_components.c.item_id == models.inventory_items.c.id,
            ).join(
                models.inventory_units,
                models.recipe_components.c.unit_id == models.inventory_units.c.id,
            )
        )
        .where(models.recipe_components.c.recipe_id == active_recipe_id)
        .order_by(models.inventory_items.c.name)
    ).mappings()
    return [dict(row) for row in rows]


def _build_order_consumption_snapshot(
    session: Session,
    order_id: str,
    order_line_id: str,
    product_id: str,
    ordered_quantity: int,
    branch_id: str,
    created_at: datetime,
    selected_modifiers: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    components = _active_recipe_components(session, product_id, branch_id)
    if not components:
        raise BusinessError("active_recipe_required", "Product requires an active recipe")
    warehouse_id = _branch_warehouse_id(session, branch_id)
    breakdown = []
    total = Decimal("0")
    for component in components:
        gross_quantity = _quantity(
            Decimal(str(component["gross_quantity"]))
            / Decimal(str(component["yield_quantity"]))
            * ordered_quantity
        )
        state = session.execute(sa.select(models.inventory_cost_states.c.average_unit_cost).where(
            models.inventory_cost_states.c.branch_id == branch_id,
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == component["item_id"],
        )).scalar_one_or_none()
        unit_cost = _cost(state or 0)
        component_cost = _cost(gross_quantity * unit_cost)
        total += component_cost
        breakdown.append(_sanitize_for_json({
            "item_id": component["item_id"], "item_name": component["item_name"],
            "unit_id": component["unit_id"], "unit_code": component["unit_code"],
            "net_quantity": _quantity(Decimal(str(component["net_quantity"])) / Decimal(str(component["yield_quantity"])) * ordered_quantity),
            "gross_quantity": gross_quantity, "waste_rate": component["waste_rate"],
            "unit_cost": unit_cost, "total_cost": component_cost,
        }))
    final_components, modifier_snapshots, modifier_total_cents = _apply_order_modifiers(
        session,
        product_id,
        branch_id,
        ordered_quantity,
        breakdown,
        selected_modifiers or [],
    )
    total = sum((_cost(component["total_cost"]) for component in final_components), Decimal("0"))
    return {
        "order_line_id": order_line_id, "order_id": order_id,
        "recipe_id": components[0]["recipe_id"], "recipe_version": components[0]["recipe_version"],
        "branch_id": branch_id, "components": final_components, "modifiers": modifier_snapshots,
        "total_theoretical_cost": _cost(total), "created_at": created_at,
        "modifier_total_cents": modifier_total_cents,
    }


def _apply_order_modifiers(
    session: Session,
    product_id: str,
    branch_id: str,
    ordered_quantity: int,
    base_components: list[dict[str, Any]],
    selected_modifiers: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], int]:
    selected_option_ids = [str(selection.get("option_id", "")) for selection in selected_modifiers]
    legacy_remove = None
    if selected_option_ids:
        legacy_remove = session.execute(
            sa.select(models.ingredient_variation_products.c.id)
            .where(
                models.ingredient_variation_products.c.remove_option_id.in_(selected_option_ids)
            )
            .limit(1)
        ).first()
    if legacy_remove is not None:
        raise BusinessError(
            "ingredient_extra_add_only",
            "Historical ingredient removals cannot be selected in new sales",
        )
    groups = list_product_modifiers(session, product_id, branch_id)
    groups_by_id = {group["id"]: group for group in groups}
    options_by_id = {
        option["id"]: (group, option) for group in groups for option in group["options"]
    }
    ingredient_rows = session.execute(
        sa.select(
            models.ingredient_variation_products.c.add_option_id,
            models.ingredient_variation_products.c.remove_option_id,
        ).where(
            sa.or_(
                models.ingredient_variation_products.c.add_option_id.in_(
                    selected_option_ids or ["__none__"]
                ),
                models.ingredient_variation_products.c.remove_option_id.in_(
                    selected_option_ids or ["__none__"]
                ),
            )
        )
    ).mappings()
    for row in ingredient_rows:
        if (
            row["add_option_id"] in selected_option_ids
            and row["remove_option_id"] in selected_option_ids
        ):
            raise BusinessError(
                "variation_actions_conflict",
                "Add and remove cannot be selected for the same ingredient variation",
            )
    selections_by_group: dict[str, list[dict[str, Any]]] = {
        group_id: [] for group_id in groups_by_id
    }
    resolved = []
    seen_options = set()
    for selection in selected_modifiers:
        option_id = str(selection.get("option_id", ""))
        if option_id in seen_options:
            raise BusinessError(
                "duplicate_modifier_option", "Modifier option cannot be selected twice"
            )
        seen_options.add(option_id)
        match = options_by_id.get(option_id)
        if not match:
            raise BusinessError(
                "modifier_option_unavailable",
                "Modifier option is not available for this product and branch",
            )
        group, option = match
        selections_by_group[group["id"]].append(selection)
        resolved.append((group, option, selection))
    for group_id, group in groups_by_id.items():
        count = len(selections_by_group[group_id])
        minimum = int(group["minimum_selections"])
        maximum = int(group["maximum_selections"])
        if count < minimum:
            raise BusinessError(
                "modifier_group_minimum_not_met",
                f"Modifier group {group['name']} requires at least {minimum} selections",
            )
        if count > maximum:
            raise BusinessError(
                "modifier_group_maximum_exceeded",
                f"Modifier group {group['name']} allows at most {maximum} selections",
            )

    components = {component["item_id"]: dict(component) for component in base_components}
    warehouse_id = _branch_warehouse_id(session, branch_id)
    snapshots = []
    price_per_unit = 0
    for group, option, selection in resolved:
        effect = option["effect_type"]
        free_text = str(selection.get("text", "")).strip() or None
        if effect == "instruction" and free_text and len(free_text) > 240:
            raise BusinessError(
                "modifier_instruction_too_long", "Modifier instruction exceeds 240 characters"
            )
        if effect == "preset_instruction":
            # Preset notes are catalog-controlled instructions. The client may select
            # one, but can never replace the text or turn it into a priced/inventory
            # modifier at order time.
            free_text = None
        if option["inventory_effect"] and effect not in {"instruction", "preset_instruction"}:
            affected_id = option["affected_item_id"]
            replacement_id = option["replacement_item_id"]
            remove_quantity = _quantity(option["remove_quantity"]) * ordered_quantity
            add_quantity = _quantity(option["add_quantity"]) * ordered_quantity
            if effect == "remove" and remove_quantity == 0 and affected_id in components:
                remove_quantity = _quantity(components[affected_id]["gross_quantity"])
            if (
                effect in {"substitute", "variant"}
                and remove_quantity == 0
                and affected_id in components
            ):
                remove_quantity = _quantity(components[affected_id]["gross_quantity"])
            if affected_id and remove_quantity:
                current = components.get(affected_id)
                if not current or _quantity(current["gross_quantity"]) < remove_quantity:
                    raise BusinessError(
                        "modifier_quantity_exceeds_component",
                        "Modifier removes more inventory than the recipe contains",
                    )
                remaining = _quantity(current["gross_quantity"]) - remove_quantity
                if remaining == 0:
                    components.pop(affected_id)
                else:
                    current["gross_quantity"] = _sanitize_for_json(remaining)
                    current["net_quantity"] = _sanitize_for_json(
                        min(_quantity(current["net_quantity"]), remaining)
                    )
                    current["total_cost"] = _sanitize_for_json(
                        _cost(remaining * _cost(current["unit_cost"]))
                    )
            added_item_id = (
                replacement_id
                if effect in {"substitute", "variant"}
                else (replacement_id or affected_id)
            )
            if added_item_id and add_quantity:
                _add_modifier_component(
                    session, components, added_item_id, add_quantity, branch_id, warehouse_id
                )
        price_per_unit += 0 if effect == "preset_instruction" else int(option["price_delta_cents"])
        snapshots.append(
            _sanitize_for_json(
                {
                    "group_id": group["id"],
                    "group_name": group["name"],
                    "option_id": option["id"],
                    "option_name": option["name"],
                    "effect_type": effect,
                    "price_delta_cents": 0
                    if effect == "preset_instruction"
                    else option["price_delta_cents"],
                    "kitchen_text": free_text or option["kitchen_text"],
                    "station": option["station"],
                    "affected_item_id": option["affected_item_id"],
                    "replacement_item_id": option["replacement_item_id"],
                    "remove_quantity": _quantity(option["remove_quantity"]) * ordered_quantity,
                    "add_quantity": _quantity(option["add_quantity"]) * ordered_quantity,
                    "inventory_effect": option["inventory_effect"],
                }
            )
        )
    return list(components.values()), snapshots, price_per_unit * ordered_quantity


def _add_modifier_component(
    session: Session,
    components: dict[str, dict[str, Any]],
    item_id: str,
    quantity: Decimal,
    branch_id: str,
    warehouse_id: str,
) -> None:
    if item_id in components:
        component = components[item_id]
        gross = _quantity(component["gross_quantity"]) + quantity
        component["gross_quantity"] = _sanitize_for_json(gross)
        component["net_quantity"] = _sanitize_for_json(_quantity(component["net_quantity"]) + quantity)
        component["total_cost"] = _sanitize_for_json(_cost(gross * _cost(component["unit_cost"])))
        return
    item = session.execute(sa.select(
        models.inventory_items.c.id,
        models.inventory_items.c.name,
        models.inventory_items.c.base_unit_id,
        models.inventory_units.c.code.label("unit_code"),
    ).select_from(models.inventory_items.join(
        models.inventory_units,
        models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
    )).where(models.inventory_items.c.id == item_id)).mappings().first()
    if not item:
        raise BusinessError("modifier_item_not_found", "Modifier inventory item was not found")
    average = session.execute(sa.select(models.inventory_cost_states.c.average_unit_cost).where(
        models.inventory_cost_states.c.branch_id == branch_id,
        models.inventory_cost_states.c.warehouse_id == warehouse_id,
        models.inventory_cost_states.c.item_id == item_id,
    )).scalar_one_or_none()
    unit_cost = _cost(average or 0)
    components[item_id] = _sanitize_for_json({
        "item_id": item_id, "item_name": item["name"], "unit_id": item["base_unit_id"],
        "unit_code": item["unit_code"], "net_quantity": quantity, "gross_quantity": quantity,
        "waste_rate": 0, "unit_cost": unit_cost, "total_cost": _cost(quantity * unit_cost),
    })


def _branch_warehouse_id(session: Session, branch_id: str = BRANCH_ID) -> str:
    return str(
        session.execute(
            sa.select(models.warehouses.c.id)
            .where(
                models.warehouses.c.branch_id == branch_id,
                models.warehouses.c.status == "active",
            )
            .limit(1)
        ).scalar_one()
    )


def _actor_user_id(actor_user_id: str | None) -> str:
    return (actor_user_id or "").strip()


def require_permission(
    session: Session,
    actor_user_id: str,
    permission_code: str,
    branch_id: str = BRANCH_ID,
) -> None:
    if not actor_user_id:
        _record_authorization_denied(
            session,
            actor_user_id=None,
            permission_code=permission_code,
            branch_id=branch_id,
            reason="missing_actor",
        )
        raise AuthorizationError("actor_required", "Actor authentication is required")

    actor = (
        session.execute(
            sa.select(models.users).where(
                models.users.c.id == actor_user_id,
                models.users.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not actor:
        _record_authorization_denied(
            session,
            actor_user_id=None,
            permission_code=permission_code,
            branch_id=branch_id,
            reason="actor_not_found",
        )
        raise AuthorizationError("actor_not_authorized", "Actor is not authorized")
    if actor["status"] != "active":
        _record_authorization_denied(
            session,
            actor_user_id=actor_user_id,
            permission_code=permission_code,
            branch_id=branch_id,
            reason="inactive_actor",
        )
        raise AuthorizationError("actor_not_authorized", "Actor is not authorized")

    role_rows = session.execute(
        sa.select(
            models.roles.c.id.label("role_id"),
            models.roles.c.scope,
            models.user_roles.c.branch_id,
        )
        .select_from(
            models.user_roles.join(models.roles, models.user_roles.c.role_id == models.roles.c.id)
        )
        .where(
            models.user_roles.c.user_id == actor_user_id,
            models.roles.c.organization_id == ORGANIZATION_ID,
        )
    ).mappings()
    roles = [dict(row) for row in role_rows]
    scoped_role_ids = [
        role["role_id"]
        for role in roles
        if role["scope"] == "organization" or role["branch_id"] in {None, branch_id}
    ]
    if not scoped_role_ids:
        _record_authorization_denied(
            session,
            actor_user_id=actor_user_id,
            permission_code=permission_code,
            branch_id=branch_id,
            reason="no_scoped_role",
        )
        raise AuthorizationError("permission_denied", "Actor does not have the required permission")

    allowed = session.execute(
        sa.select(models.permissions.c.code)
        .select_from(
            models.role_permissions.join(
                models.permissions,
                models.role_permissions.c.permission_id == models.permissions.c.id,
            )
        )
        .where(
            models.role_permissions.c.role_id.in_(scoped_role_ids),
            models.permissions.c.code == permission_code,
        )
        .limit(1)
    ).scalar_one_or_none()
    if allowed:
        return

    _record_authorization_denied(
        session,
        actor_user_id=actor_user_id,
        permission_code=permission_code,
        branch_id=branch_id,
        reason="missing_permission",
    )
    raise AuthorizationError("permission_denied", "Actor does not have the required permission")


def authorize_branch_scope(
    session: Session,
    actor_user_id: str,
    permission_code: str,
    branch_id: str | None = None,
) -> str | None:
    actor_id = _actor_user_id(actor_user_id)
    if branch_id:
        active_branch = session.execute(
            sa.select(models.branches.c.id).where(
                models.branches.c.id == branch_id,
                models.branches.c.organization_id == ORGANIZATION_ID,
                models.branches.c.status == "active",
            )
        ).scalar_one_or_none()
        if not active_branch:
            _record_authorization_denied(
                session,
                actor_user_id=actor_id or None,
                permission_code=permission_code,
                branch_id=branch_id,
                reason="invalid_branch_scope",
            )
            raise AuthorizationError(
                "permission_denied", "Actor does not have access to the requested branch"
            )
        require_permission(session, actor_id, permission_code, branch_id)
        return branch_id
    if _actor_has_organization_scope(session, actor_id):
        require_permission(session, actor_id, permission_code, BRANCH_ID)
        return None
    scoped_branch_id = _actor_default_branch_id(session, actor_id)
    if not scoped_branch_id:
        require_permission(session, actor_id, permission_code, BRANCH_ID)
        return BRANCH_ID
    require_permission(session, actor_id, permission_code, scoped_branch_id)
    return scoped_branch_id


def _actor_has_organization_scope(session: Session, actor_user_id: str) -> bool:
    rows = session.execute(
        sa.select(models.roles.c.name, models.roles.c.scope)
        .select_from(models.user_roles.join(models.roles, models.user_roles.c.role_id == models.roles.c.id))
        .where(
            models.user_roles.c.user_id == actor_user_id,
            models.roles.c.organization_id == ORGANIZATION_ID,
        )
    ).mappings()
    return any(row["scope"] == "organization" for row in rows)


def _actor_default_branch_id(session: Session, actor_user_id: str) -> str | None:
    return session.execute(
        sa.select(models.user_roles.c.branch_id)
        .select_from(
            models.user_roles.join(
                models.branches,
                models.user_roles.c.branch_id == models.branches.c.id,
            )
        )
        .where(
            models.user_roles.c.user_id == actor_user_id,
            models.user_roles.c.branch_id.is_not(None),
            models.branches.c.organization_id == ORGANIZATION_ID,
            models.branches.c.status == "active",
        )
        .order_by(models.branches.c.code)
        .limit(1)
    ).scalar_one_or_none()


def _assign_default_role_permissions(
    session: Session,
    role_id: str,
    role_name: str,
) -> list[str]:
    normalized = role_name.strip().lower()
    profile = {
        "administrador corporativo": [
            "admin.manage",
            "catalog.manage",
            "inventory.adjust",
            "inventory.waste",
            "inventory.transfer.send",
            "inventory.transfer.receive",
            "inventory.count",
            "orders.cancel",
            "cash.shift.read",
            "cash.shift.open",
            "cash.shift.close",
            "orders.read",
            "orders.create",
            "payments.read",
            "payments.confirm",
            "dashboard.read",
            "pos.operate",
            "cash.withdraw",
            "inventory.read",
            "purchases.read",
            "purchases.manage",
            "production.manage",
            "audit.read",
            "branch.admin.access",
            "branch.staff.read",
            "catalog.branch.manage",
        ],
        "supervisor de sucursal": [
            "pos.operate", "cash.shift.read", "cash.shift.open", "cash.shift.close", "cash.withdraw",
            "orders.read", "orders.create", "orders.cancel", "payments.read", "payments.confirm",
            "dashboard.read", "inventory.read", "inventory.waste", "inventory.transfer.send",
            "inventory.count", "purchases.read", "purchases.manage", "production.manage",
            "branch.admin.access", "branch.staff.read", "catalog.branch.manage",
        ],
        "receptor de traspaso": ["inventory.read", "inventory.transfer.receive"],
        "gerente de sucursal": [
            "catalog.manage",
            "inventory.adjust",
            "orders.cancel",
            "cash.shift.read",
            "orders.read",
            "payments.read",
            "dashboard.read",
            "pos.operate",
        ],
        "cajero": [
            "cash.shift.read",
            "cash.shift.open",
            "cash.shift.close",
            "orders.read",
            "orders.create",
            "payments.confirm",
            "pos.operate",
        ],
        "caja": [
            "cash.shift.read",
            "cash.shift.open",
            "cash.shift.close",
            "orders.read",
            "orders.create",
            "payments.confirm",
            "pos.operate",
        ],
        "encargado de inventarios": ["inventory.adjust"],
    }.get(normalized, [])
    if not profile:
        return []

    rows = session.execute(
        sa.select(models.permissions.c.id, models.permissions.c.code).where(
            models.permissions.c.code.in_(profile)
        )
    ).mappings()
    permissions_by_code = {row["code"]: row["id"] for row in rows}
    assignments = [
        {"role_id": role_id, "permission_id": permissions_by_code[code]}
        for code in profile
        if code in permissions_by_code
    ]
    if assignments:
        session.execute(models.role_permissions.insert(), assignments)
    return [code for code in profile if code in permissions_by_code]


def _set_user_password(
    session: Session,
    user_id: str,
    password: str,
    updated_at: datetime,
) -> None:
    salt = generate_password_salt()
    credential = {
        "user_id": user_id,
        "password_hash": hash_password(password, salt),
        "password_salt": salt,
        "password_algorithm": PASSWORD_ALGORITHM,
        "updated_at": updated_at,
    }
    existing = (
        session.execute(
            sa.select(models.user_credentials.c.user_id).where(
                models.user_credentials.c.user_id == user_id,
                models.user_credentials.c.password_algorithm == PASSWORD_ALGORITHM,
            )
        )
        .mappings()
        .first()
    )
    if existing:
        session.execute(
            models.user_credentials.update()
            .where(
                models.user_credentials.c.user_id == user_id,
                models.user_credentials.c.password_algorithm == PASSWORD_ALGORITHM,
            )
            .values(**credential)
        )
        return
    session.execute(models.user_credentials.insert().values(**credential))


def _record_authorization_denied(
    session: Session,
    actor_user_id: str | None,
    permission_code: str,
    branch_id: str,
    reason: str,
) -> None:
    _audit(
        session,
        action="authorization.denied",
        entity_type="permission",
        entity_id=permission_code,
        payload={"permission": permission_code, "reason": reason},
        branch_id=branch_id,
        actor_user_id=actor_user_id,
    )
    session.commit()


def _next_folio(session: Session, branch_id: str = BRANCH_ID) -> str:
    branch_code = session.execute(
        sa.select(models.branches.c.code).where(models.branches.c.id == branch_id)
    ).scalar_one_or_none()
    prefix = str(branch_code or "PILOTO").strip().upper()
    folios = session.execute(
        sa.select(models.orders.c.folio).where(
            models.orders.c.branch_id == branch_id,
            models.orders.c.folio.like(f"{prefix}-%"),
        )
    ).scalars()
    max_suffix = 0
    for folio in folios:
        suffix = str(folio).rsplit("-", 1)[-1]
        if suffix.isdigit():
            max_suffix = max(max_suffix, int(suffix))
    return f"{prefix}-{max_suffix + 1:06d}"


def _next_unique_folio(session: Session, branch_id: str = BRANCH_ID) -> str:
    folio = _next_folio(session, branch_id)
    existing = session.execute(
        sa.select(models.orders.c.id).where(
            models.orders.c.branch_id == branch_id,
            models.orders.c.folio == folio,
        )
    ).first()
    if not existing:
        return folio
    branch_code = session.execute(
        sa.select(models.branches.c.code).where(models.branches.c.id == branch_id)
    ).scalar_one_or_none()
    prefix = str(branch_code or "PILOTO").strip().upper()
    suffix = int(folio.rsplit("-", 1)[-1])
    while True:
        suffix += 1
        candidate = f"{prefix}-{suffix:06d}"
        existing = session.execute(
            sa.select(models.orders.c.id).where(
                models.orders.c.branch_id == branch_id,
                models.orders.c.folio == candidate,
            )
        ).first()
        if not existing:
            return candidate


def _sanitize_for_json(data: Any) -> Any:
    if isinstance(data, dict):
        return {k: _sanitize_for_json(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [_sanitize_for_json(v) for v in data]
    elif isinstance(data, datetime):
        return data.isoformat()
    elif isinstance(data, Decimal):
        return str(data)
    return data


def _audit(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    branch_id: str | None = BRANCH_ID,
    organization_id: str = ORGANIZATION_ID,
    actor_user_id: str | None = ADMIN_USER_ID,
) -> None:
    session.execute(
        models.audit_events.insert().values(
            id=_id(),
            organization_id=organization_id,
            branch_id=branch_id,
            actor_user_id=actor_user_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=_sanitize_for_json(payload),
            correlation_id=None,
            created_at=_now(),
        )
    )


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)


def update_user(
    session: Session,
    user_id: str,
    email: str | None = None,
    display_name: str | None = None,
    actor_user_id: str | None = None,
    role_id: str | None = None,
    password: str | None = None,
    branch_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    is_self_update = bool(actor_id and actor_id == user_id)
    role_change_requested = role_id is not None
    if role_change_requested or not is_self_update:
        require_permission(session, actor_id, "admin.manage")
    elif not actor_id:
        require_permission(session, actor_id, "admin.manage")

    update_data = {}
    if email is not None:
        update_data["email"] = email.strip().lower()
    if display_name is not None:
        update_data["display_name"] = display_name.strip()

    if update_data:
        update_data["updated_at"] = _now()
        session.execute(
            sa.update(models.users).where(models.users.c.id == user_id).values(**update_data)
        )

    if password is not None:
        p_val = password.strip()
        if p_val:
            _set_user_password(session, user_id, p_val, _now())
            session.execute(
                sa.update(models.users).where(models.users.c.id == user_id).values(status="active")
            )

    if role_id is not None:
        session.execute(sa.delete(models.user_roles).where(models.user_roles.c.user_id == user_id))
        if role_id:
            assign_user_role(session, user_id, role_id, branch_id, actor_id)

    _audit(
        session,
        action="user.updated",
        entity_type="user",
        entity_id=user_id,
        payload=update_data,
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": user_id, **update_data}


def delete_user(
    session: Session,
    user_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    session.execute(
        sa.update(models.users)
        .where(models.users.c.id == user_id)
        .values(status="suspended", updated_at=_now())
    )
    _audit(
        session,
        action="user.deleted",
        entity_type="user",
        entity_id=user_id,
        payload={"status": "suspended"},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": user_id, "status": "suspended"}


def update_branch(
    session: Session,
    branch_id: str,
    name: str | None = None,
    code: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")

    update_data = {}
    if name is not None:
        update_data["name"] = name.strip()
    if code is not None:
        update_data["code"] = code.strip()

    if update_data:
        update_data["updated_at"] = _now()
        session.execute(
            sa.update(models.branches)
            .where(models.branches.c.id == branch_id)
            .values(**update_data)
        )
        _audit(
            session,
            action="branch.updated",
            entity_type="branch",
            entity_id=branch_id,
            payload=update_data,
            actor_user_id=actor_id,
        )
        session.commit()
    return {"id": branch_id, **update_data}


def delete_branch(
    session: Session,
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")
    session.execute(
        sa.update(models.branches)
        .where(models.branches.c.id == branch_id)
        .values(status="inactive", updated_at=_now())
    )
    _audit(
        session,
        action="branch.deleted",
        entity_type="branch",
        entity_id=branch_id,
        payload={"status": "inactive"},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": branch_id, "status": "inactive"}


def update_product(
    session: Session,
    product_id: str,
    name: str | None = None,
    sku: str | None = None,
    price_cents: int | None = None,
    image_url: str | None = None,
    category_name: str | None = None,
    station: str | None = None,
    status: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    update_data = {}
    if name is not None:
        normalized_name = name.strip()
        if not is_uppercase_name(normalized_name):
            raise BusinessError("invalid_product_name", "Product name must be uppercase")
        update_data["name"] = normalized_name
    if sku is not None:
        normalized_sku = normalize_product_sku(sku)
        if not is_numeric_sku(normalized_sku):
            raise BusinessError("invalid_product_sku", "Product SKU must contain only digits")
        update_data["sku"] = normalized_sku
    if image_url is not None:
        update_data["image_url"] = image_url.strip() if image_url.strip() else None
    if station is not None:
        normalized_station = station.strip().lower()
        if normalized_station not in {"kitchen", "drinks", "packing"}:
            raise BusinessError("invalid_station", "Station must be kitchen, drinks or packing")
        update_data["station"] = normalized_station
    if status is not None:
        normalized_status = status.strip().lower()
        if normalized_status not in {"active", "inactive", "needs_review"}:
            raise BusinessError("invalid_product_status", "Product status is invalid")
        if normalized_status == "active":
            current_station = station
            if current_station is None:
                current_station = session.execute(
                    sa.select(models.products.c.station).where(models.products.c.id == product_id)
                ).scalar_one_or_none()
            if not current_station or current_station.strip().lower() == "unassigned":
                raise BusinessError("missing_product_station", "Assign a station before activation")
        update_data["status"] = normalized_status

    now = _now()
    if category_name is not None:
        normalized_category = category_name.strip()
        if not normalized_category or normalized_category != canonical_category_name(normalized_category):
            raise BusinessError("invalid_category_name", "Category name must be uppercase")
        category = _get_or_create_category(session, normalized_category, now)
        update_data["category_id"] = category["id"]
    if update_data:
        update_data["updated_at"] = now
        session.execute(
            sa.update(models.products)
            .where(models.products.c.id == product_id)
            .values(**update_data)
        )

    if price_cents is not None:
        price = {
            "id": _id(),
            "organization_id": ORGANIZATION_ID,
            "product_id": product_id,
            "price_cents": price_cents,
            "currency": "MXN",
            "valid_from": now,
            "valid_to": None,
            "created_at": now,
        }
        session.execute(
            sa.update(models.price_versions)
            .where(
                models.price_versions.c.product_id == product_id,
                models.price_versions.c.valid_to.is_(None),
            )
            .values(valid_to=now)
        )
        session.execute(models.price_versions.insert().values(**price))
        update_data["price_cents"] = price_cents

    if update_data or price_cents is not None:
        _audit(
            session,
            action="product.updated",
            entity_type="product",
            entity_id=product_id,
            payload=update_data,
            actor_user_id=actor_id,
        )
        session.commit()
    return {"id": product_id, **update_data}


def delete_product(
    session: Session,
    product_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    session.execute(
        sa.update(models.products)
        .where(models.products.c.id == product_id)
        .values(status="inactive", updated_at=_now())
    )
    _audit(
        session,
        action="product.deleted",
        entity_type="product",
        entity_id=product_id,
        payload={"status": "inactive"},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": product_id, "status": "inactive"}

def update_role(
    session: Session,
    role_id: str,
    name: str | None = None,
    scope: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")

    update_data = {}
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise BusinessError("invalid_role_name", "Role name cannot be empty")
        update_data["name"] = normalized_name

    if scope is not None:
        normalized_scope = scope.strip().lower()
        if normalized_scope not in {"organization", "branch"}:
            raise BusinessError("invalid_role_scope", "Role scope must be organization or branch")
        update_data["scope"] = normalized_scope

    if update_data:
        session.execute(
            sa.update(models.roles)
            .where(models.roles.c.id == role_id)
            .values(**update_data)
        )
        _audit(
            session,
            action="role.updated",
            entity_type="role",
            entity_id=role_id,
            payload=update_data,
            actor_user_id=actor_id,
        )
        session.commit()

    return {"id": role_id, **update_data}


def delete_role(
    session: Session,
    role_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")

    # Ensure role is not assigned to users
    in_use = session.execute(
        sa.select(models.user_roles).where(models.user_roles.c.role_id == role_id)
    ).first()
    if in_use:
        raise BusinessError("role_in_use", "Cannot delete role that is assigned to users")

    session.execute(
        sa.delete(models.role_permissions).where(models.role_permissions.c.role_id == role_id)
    )
    session.execute(
        sa.delete(models.roles).where(models.roles.c.id == role_id)
    )

    _audit(
        session,
        action="role.deleted",
        entity_type="role",
        entity_id=role_id,
        payload={},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": role_id, "status": "deleted"}


def update_role_permissions(
    session: Session,
    role_id: str,
    permission_ids: list[str],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")

    # Validate permissions exist
    existing_perms = session.execute(
        sa.select(models.permissions.c.id).where(models.permissions.c.id.in_(permission_ids))
    ).fetchall()
    valid_ids = {row.id for row in existing_perms}

    if len(valid_ids) != len(permission_ids):
        raise BusinessError("invalid_permission", "One or more permission IDs are invalid")

    # Delete old permissions
    session.execute(
        sa.delete(models.role_permissions).where(models.role_permissions.c.role_id == role_id)
    )

    # Insert new permissions
    if valid_ids:
        session.execute(
            sa.insert(models.role_permissions),
            [{"role_id": role_id, "permission_id": pid} for pid in valid_ids]
        )

    _audit(
        session,
        action="role.permissions_updated",
        entity_type="role",
        entity_id=role_id,
        payload={"permission_ids": list(valid_ids)},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": role_id, "permissions_count": len(valid_ids)}


def create_warehouse(
    session: Session,
    branch_id: str,
    name: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")

    normalized_name = name.strip()
    if not normalized_name:
        raise BusinessError("invalid_warehouse_name", "Warehouse name is required")

    # Check branch exists
    branch = session.execute(
        sa.select(models.branches).where(models.branches.c.id == branch_id)
    ).first()
    if not branch:
        raise BusinessError("invalid_branch", "Branch does not exist")

    # A branch can only have one warehouse currently per model constraint unique=True
    existing = session.execute(
        sa.select(models.warehouses).where(models.warehouses.c.branch_id == branch_id)
    ).first()
    if existing:
        raise BusinessError("warehouse_exists", "Branch already has a warehouse")

    warehouse_id = str(uuid4())
    now = _now()
    session.execute(
        sa.insert(models.warehouses).values(
            id=warehouse_id,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            name=normalized_name,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    _audit(
        session,
        action="warehouse.created",
        entity_type="warehouse",
        entity_id=warehouse_id,
        payload={"name": normalized_name, "branch_id": branch_id},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": warehouse_id, "name": normalized_name, "branch_id": branch_id}


def update_warehouse(
    session: Session,
    warehouse_id: str,
    name: str | None = None,
    status: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "admin.manage")

    update_data = {"updated_at": _now()}
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise BusinessError("invalid_warehouse_name", "Warehouse name cannot be empty")
        update_data["name"] = normalized_name

    if status is not None:
        if status not in {"active", "inactive"}:
            raise BusinessError("invalid_warehouse_status", "Status must be active or inactive")
        update_data["status"] = status

    session.execute(
        sa.update(models.warehouses)
        .where(models.warehouses.c.id == warehouse_id)
        .values(**update_data)
    )

    _audit(
        session,
        action="warehouse.updated",
        entity_type="warehouse",
        entity_id=warehouse_id,
        payload=update_data,
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": warehouse_id, **update_data}


def create_inventory_unit(
    session: Session,
    code: str,
    name: str,
    precision_scale: int = 0,
    dimension: str = "discrete",
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    normalized_code = code.strip().upper()
    normalized_name = name.strip()
    normalized_dimension = dimension.strip().lower()

    if not normalized_code or not normalized_name:
        raise BusinessError("invalid_unit", "Code and name are required")
    if normalized_dimension not in {"mass", "volume", "discrete", "commercial"}:
        raise BusinessError("invalid_unit_dimension", "Unit dimension is invalid")

    existing = session.execute(
        sa.select(models.inventory_units).where(
            models.inventory_units.c.organization_id == ORGANIZATION_ID,
            models.inventory_units.c.code == normalized_code
        )
    ).first()
    if existing:
        raise BusinessError("unit_exists", "Unit with this code already exists")

    unit_id = str(uuid4())
    session.execute(
        sa.insert(models.inventory_units).values(
            id=unit_id,
            organization_id=ORGANIZATION_ID,
            code=normalized_code,
            name=normalized_name,
            dimension=normalized_dimension,
            precision_scale=precision_scale,
            created_at=_now(),
        )
    )

    _audit(
        session,
        action="inventory_unit.created",
        entity_type="inventory_unit",
        entity_id=unit_id,
        payload={"code": normalized_code, "name": normalized_name},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": unit_id, "code": normalized_code, "name": normalized_name, "dimension": normalized_dimension}

def update_inventory_unit(
    session: Session,
    unit_id: str,
    name: str | None = None,
    precision_scale: int | None = None,
    dimension: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    update_data = {}
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise BusinessError("invalid_unit_name", "Name cannot be empty")
        update_data["name"] = normalized_name
    if precision_scale is not None:
        update_data["precision_scale"] = precision_scale
    if dimension is not None:
        normalized_dimension = dimension.strip().lower()
        if normalized_dimension not in {"mass", "volume", "discrete", "commercial"}:
            raise BusinessError("invalid_unit_dimension", "Unit dimension is invalid")
        update_data["dimension"] = normalized_dimension

    if update_data:
        session.execute(
            sa.update(models.inventory_units)
            .where(models.inventory_units.c.id == unit_id)
            .values(**update_data)
        )
        _audit(
            session,
            action="inventory_unit.updated",
            entity_type="inventory_unit",
            entity_id=unit_id,
            payload=update_data,
            actor_user_id=actor_id,
        )
        session.commit()
    return {"id": unit_id, **update_data}

def create_inventory_item(
    session: Session,
    name: str,
    sku: str,
    base_unit_id: str,
    item_type: str = "ingredient",
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    normalized_name = name.strip()
    normalized_sku = normalize_inventory_sku(sku)

    if not normalized_name:
        raise BusinessError("invalid_item", "Name is required")
    if not is_numeric_sku(normalized_sku):
        raise BusinessError("invalid_item_sku", "Inventory SKU must contain only digits")

    existing = session.execute(
        sa.select(models.inventory_items).where(
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.sku == normalized_sku
        )
    ).first()
    if existing:
        raise BusinessError("item_exists", "Item with this SKU already exists")

    item_id = str(uuid4())
    now = _now()
    session.execute(
        sa.insert(models.inventory_items).values(
            id=item_id,
            organization_id=ORGANIZATION_ID,
            name=normalized_name,
            sku=normalized_sku,
            base_unit_id=base_unit_id,
            item_type=item_type,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )

    _audit(
        session,
        action="inventory_item.created",
        entity_type="inventory_item",
        entity_id=item_id,
        payload={"sku": normalized_sku, "name": normalized_name},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": item_id, "name": normalized_name, "sku": normalized_sku}

def update_inventory_item(
    session: Session,
    item_id: str,
    name: str | None = None,
    base_unit_id: str | None = None,
    item_type: str | None = None,
    status: str | None = None,
    category_name: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    update_data = {"updated_at": _now()}
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name:
            raise BusinessError("invalid_item_name", "Name cannot be empty")
        update_data["name"] = normalized_name
    if base_unit_id is not None:
        update_data["base_unit_id"] = base_unit_id
    if item_type is not None:
        update_data["item_type"] = item_type
    if status is not None:
        update_data["status"] = status
    if category_name is not None:
        update_data["category_name"] = category_name.strip()[:120] or None

    session.execute(
        sa.update(models.inventory_items)
        .where(models.inventory_items.c.id == item_id)
        .values(**update_data)
    )
    _audit(
        session,
        action="inventory_item.updated",
        entity_type="inventory_item",
        entity_id=item_id,
        payload=update_data,
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": item_id, **update_data}


def create_category(
    session: Session,
    name: str,
    display_order: int = 0,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    normalized_name = name.strip()
    if not normalized_name or not is_uppercase_name(normalized_name):
        raise BusinessError("invalid_category", "Category name must be uppercase")

    existing = session.execute(
        sa.select(models.product_categories).where(
            models.product_categories.c.organization_id == ORGANIZATION_ID,
            models.product_categories.c.name == normalized_name,
            models.product_categories.c.status != "archived",
        )
    ).first()
    if existing:
        raise BusinessError("category_exists", "Category with this name already exists")

    cat_id = str(uuid4())
    now = _now()
    session.execute(
        sa.insert(models.product_categories).values(
            id=cat_id,
            organization_id=ORGANIZATION_ID,
            name=normalized_name,
            display_order=display_order,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    _audit(
        session,
        action="category.created",
        entity_type="category",
        entity_id=cat_id,
        payload={"name": normalized_name},
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": cat_id, "name": normalized_name}

def update_category(
    session: Session,
    category_id: str,
    name: str | None = None,
    display_order: int | None = None,
    status: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")

    update_data = {"updated_at": _now()}
    if name is not None:
        normalized_name = name.strip()
        if not normalized_name or not is_uppercase_name(normalized_name):
            raise BusinessError("invalid_category_name", "Category name must be uppercase")
        update_data["name"] = normalized_name
    if display_order is not None:
        update_data["display_order"] = display_order
    if status is not None:
        update_data["status"] = status

    session.execute(
        sa.update(models.product_categories)
        .where(models.product_categories.c.id == category_id)
        .values(**update_data)
    )
    _audit(
        session,
        action="category.updated",
        entity_type="category",
        entity_id=category_id,
        payload=update_data,
        actor_user_id=actor_id,
    )
    session.commit()
    return {"id": category_id, **update_data}

def update_product_recipe(
    session: Session,
    product_id: str,
    components: list[dict[str, Any]],
    yield_quantity: Any = 1,
    yield_unit_id: str = "",
    branch_id: str | None = None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    product = session.execute(sa.select(models.products.c.id).where(
        models.products.c.id == product_id,
        models.products.c.organization_id == ORGANIZATION_ID,
    )).scalar_one_or_none()
    if not product:
        raise BusinessError("product_not_found", "Product was not found")
    normalized_yield = _quantity(yield_quantity)
    if normalized_yield <= 0:
        raise BusinessError("invalid_recipe_yield", "Recipe yield must be positive")
    if not yield_unit_id:
        yield_unit_id = str(session.execute(sa.select(models.inventory_units.c.id).limit(1)).scalar_one())
    component_rows = _normalize_recipe_components(session, components)
    now = _now()
    max_version = session.execute(sa.select(sa.func.max(models.recipes.c.version)).where(
        models.recipes.c.product_id == product_id
    )).scalar() or 0
    recipe_id = _id()
    session.execute(
        sa.update(models.recipes)
        .where(
            models.recipes.c.product_id == product_id,
            models.recipes.c.status == "active",
            models.recipes.c.branch_id.is_(branch_id) if branch_id is None else models.recipes.c.branch_id == branch_id,
        )
        .values(status="retired", valid_to=now, updated_at=now)
    )
    recipe = {
        "id": recipe_id, "organization_id": ORGANIZATION_ID, "product_id": product_id,
        "output_item_id": None, "branch_id": branch_id, "recipe_type": "sale",
        "version": int(max_version) + 1, "status": "active", "yield_quantity": normalized_yield,
        "yield_unit_id": yield_unit_id, "valid_from": now, "valid_to": None,
        "created_at": now, "updated_at": now,
    }
    session.execute(models.recipes.insert().values(**recipe))
    for row in component_rows:
        session.execute(models.recipe_components.insert().values(recipe_id=recipe_id, **row))
    cost = calculate_recipe_cost(session, recipe_id, branch_id or BRANCH_ID, actor_id, persist=True)
    _audit(
        session,
        action="recipe.updated",
        entity_type="product",
        entity_id=product_id,
        payload={"recipe_id": recipe_id, "version": recipe["version"], "branch_id": branch_id},
        actor_user_id=actor_id,
    )
    session.commit()
    return {**recipe, "components": component_rows, "cost": cost}


def create_modifier_group(
    session: Session,
    product_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    product = session.execute(sa.select(models.products.c.id).where(
        models.products.c.id == product_id,
        models.products.c.organization_id == ORGANIZATION_ID,
        models.products.c.status == "active",
    )).scalar_one_or_none()
    if not product:
        raise BusinessError("product_not_found", "Product was not found")
    name = str(payload.get("name", "")).strip()
    minimum = int(payload.get("minimum_selections", 1 if payload.get("is_required") else 0))
    maximum = int(payload.get("maximum_selections", 1))
    required = bool(payload.get("is_required", minimum > 0))
    if not name or minimum < 0 or maximum < 1 or minimum > maximum or (required and minimum < 1):
        raise BusinessError("invalid_modifier_group", "Modifier group name and valid minimum/maximum are required")
    now = _now()
    group = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "product_id": product_id,
        "name": name, "is_required": required, "minimum_selections": minimum,
        "maximum_selections": maximum, "station": payload.get("station"),
        "display_order": int(payload.get("display_order", 0)), "status": "active",
        "created_at": now, "updated_at": now,
    }
    session.execute(models.modifier_groups.insert().values(**group))
    _audit(session, "modifier_group.created", "modifier_group", group["id"],
           {"product_id": product_id, "minimum": minimum, "maximum": maximum}, actor_user_id=actor_id)
    session.commit()
    return {**group, "options": []}


def create_modifier_option(
    session: Session,
    group_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    group = session.execute(sa.select(models.modifier_groups).where(
        models.modifier_groups.c.id == group_id,
        models.modifier_groups.c.status == "active",
    )).mappings().first()
    if not group:
        raise BusinessError("modifier_group_not_found", "Modifier group was not found")
    effect = str(payload.get("effect_type", "instruction")).lower()
    allowed = {"remove", "add", "substitute", "quantity", "variant", "instruction"}
    name = str(payload.get("name", "")).strip()
    affected = payload.get("affected_item_id")
    replacement = payload.get("replacement_item_id")
    remove_quantity = _quantity(payload.get("remove_quantity", 0))
    add_quantity = _quantity(payload.get("add_quantity", 0))
    if not name or effect not in allowed or remove_quantity < 0 or add_quantity < 0:
        raise BusinessError("invalid_modifier_option", "Modifier option fields are invalid")
    if effect in {"remove", "quantity", "substitute", "variant"} and not affected:
        raise BusinessError("modifier_affected_item_required", "Modifier requires an affected item")
    if effect in {"substitute", "variant"} and not replacement:
        raise BusinessError("modifier_replacement_item_required", "Substitution requires a replacement item")
    if effect == "add" and not (replacement or affected):
        raise BusinessError("modifier_added_item_required", "Add modifier requires an inventory item")
    item_ids = [str(item_id) for item_id in (affected, replacement) if item_id]
    if item_ids:
        found = set(session.execute(sa.select(models.inventory_items.c.id).where(
            models.inventory_items.c.id.in_(item_ids),
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.status == "active",
        )).scalars())
        if found != set(item_ids):
            raise BusinessError("modifier_item_not_found", "Modifier inventory item was not found")
    now = _now()
    option = {
        "id": _id(), "group_id": group_id, "name": name, "effect_type": effect,
        "price_delta_cents": int(payload.get("price_delta_cents", 0)),
        "affected_item_id": affected, "replacement_item_id": replacement,
        "remove_quantity": remove_quantity, "add_quantity": add_quantity,
        "inventory_effect": bool(payload.get("inventory_effect", effect != "instruction")),
        "kitchen_text": str(payload.get("kitchen_text") or name).strip(),
        "station": payload.get("station") or group["station"],
        "display_order": int(payload.get("display_order", 0)), "status": "active",
        "created_at": now, "updated_at": now,
    }
    session.execute(models.modifier_options.insert().values(**option))
    _audit(session, "modifier_option.created", "modifier_option", option["id"],
           {"group_id": group_id, "effect_type": effect}, actor_user_id=actor_id)
    session.commit()
    return option


INGREDIENT_VARIATION_GROUP = "Cambios de ingredientes"


def _ingredient_variation_labels(
    item_name: str, add_label: Any = None, remove_label: Any = None
) -> tuple[str, str]:
    if add_label is None or remove_label is None:
        raise BusinessError(
            "invalid_ingredient_variation_label",
            "Ingredient variation labels cannot be null",
        )
    item = item_name.strip().lower()
    add = str(add_label).strip() if add_label is not None else f"Con {item}"
    remove = str(remove_label).strip() if remove_label is not None else f"Sin {item}"
    if not add or not remove or len(add) > 120 or len(remove) > 120:
        raise BusinessError(
            "invalid_ingredient_variation_label",
            "Ingredient variation labels must be between 1 and 120 characters",
        )
    return add, remove


def create_ingredient_variation(
    session: Session, payload: dict[str, Any], actor_user_id: str | None = None
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    item_id = str(payload.get("inventory_item_id", "")).strip()
    item = (
        session.execute(
            sa.select(models.inventory_items.c.id, models.inventory_items.c.name).where(
                models.inventory_items.c.id == item_id,
                models.inventory_items.c.organization_id == ORGANIZATION_ID,
                models.inventory_items.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if not item:
        raise BusinessError(
            "ingredient_variation_item_not_found", "Ingredient inventory item was not found"
        )
    if session.execute(
        sa.select(models.ingredient_variations.c.id).where(
            models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
            models.ingredient_variations.c.inventory_item_id == item_id,
        )
    ).scalar_one_or_none():
        raise BusinessError(
            "ingredient_variation_exists", "An ingredient variation already exists for this item"
        )
    add_label, remove_label = _ingredient_variation_labels(
        str(item["name"]),
        payload["add_label"] if "add_label" in payload else f"Con {item['name'].strip().lower()}",
        payload["remove_label"] if "remove_label" in payload else f"Sin {item['name'].strip().lower()}",
    )
    now = _now()
    variation = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "inventory_item_id": item_id,
        "add_label": add_label,
        "remove_label": remove_label,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    session.execute(models.ingredient_variations.insert().values(**variation))
    _audit(
        session,
        "ingredient_variation.created",
        "ingredient_variation",
        variation["id"],
        {"inventory_item_id": item_id},
        actor_user_id=actor_id,
    )
    session.commit()
    return variation


def _ingredient_variation_summary_query() -> Any:
    return (
        sa.select(
            models.ingredient_variations,
            models.inventory_items.c.name.label("inventory_item_name"),
            models.inventory_items.c.sku.label("inventory_item_sku"),
            models.inventory_units.c.code.label("unit_code"),
            sa.func.count(models.ingredient_variation_products.c.id)
            .filter(models.ingredient_variation_products.c.status == "active")
            .label("related_products"),
            sa.func.count(models.ingredient_variation_products.c.id)
            .filter(
                models.ingredient_variation_products.c.status == "active",
                models.ingredient_variation_products.c.allow_add.is_(True),
            )
            .label("active_add_assignments"),
            sa.func.count(models.ingredient_variation_products.c.id)
            .filter(
                models.ingredient_variation_products.c.status == "active",
                models.ingredient_variation_products.c.allow_remove.is_(True),
            )
            .label("active_remove_assignments"),
        )
        .select_from(
            models.ingredient_variations.join(
                models.inventory_items,
                models.inventory_items.c.id == models.ingredient_variations.c.inventory_item_id,
            )
            .join(
                models.inventory_units,
                models.inventory_units.c.id == models.inventory_items.c.base_unit_id,
            )
            .outerjoin(
                models.ingredient_variation_products,
                models.ingredient_variation_products.c.variation_id
                == models.ingredient_variations.c.id,
            )
        )
        .group_by(
            models.ingredient_variations.c.id,
            models.inventory_items.c.name,
            models.inventory_items.c.sku,
            models.inventory_units.c.code,
        )
    )


def list_ingredient_variations(
    session: Session, search: str, status: str | None, actor_user_id: str | None = None
) -> list[dict[str, Any]]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    query = _ingredient_variation_summary_query().where(
        models.ingredient_variations.c.organization_id == ORGANIZATION_ID
    )
    if status in {"active", "archived"}:
        query = query.where(models.ingredient_variations.c.status == status)
    if search.strip():
        needle = f"%{search.strip().lower()}%"
        query = query.where(
            sa.or_(
                sa.func.lower(models.ingredient_variations.c.add_label).like(needle),
                sa.func.lower(models.ingredient_variations.c.remove_label).like(needle),
                sa.func.lower(models.inventory_items.c.name).like(needle),
                sa.func.lower(models.inventory_items.c.sku).like(needle),
            )
        )
    return [
        {**dict(row), "warnings": []}
        for row in session.execute(query.order_by(models.inventory_items.c.name)).mappings()
    ]


def get_ingredient_variation(
    session: Session, variation_id: str, actor_user_id: str | None = None
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    variation = (
        session.execute(
            _ingredient_variation_summary_query().where(
                models.ingredient_variations.c.id == variation_id,
                models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not variation:
        raise NotFoundError("ingredient_variation_not_found", "Ingredient variation was not found")
    rows = session.execute(
        sa.select(
            models.ingredient_variation_products,
            models.products.c.name.label("product_name"),
            models.products.c.sku.label("product_sku"),
            models.product_categories.c.name.label("category_name"),
        )
        .select_from(
            models.ingredient_variation_products.join(
                models.products,
                models.products.c.id == models.ingredient_variation_products.c.product_id,
            ).join(
                models.product_categories,
                models.product_categories.c.id == models.products.c.category_id,
            )
        )
        .where(
            models.ingredient_variation_products.c.variation_id == variation_id,
            models.products.c.organization_id == ORGANIZATION_ID,
        )
        .order_by(models.products.c.name)
    ).mappings()
    return {**dict(variation), "warnings": [], "assignments": [dict(row) for row in rows]}


def update_ingredient_variation(
    session: Session, variation_id: str, payload: dict[str, Any], actor_user_id: str | None = None
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    variation = (
        session.execute(
            sa.select(models.ingredient_variations).where(
                models.ingredient_variations.c.id == variation_id,
                models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not variation:
        raise NotFoundError("ingredient_variation_not_found", "Ingredient variation was not found")
    if "inventory_item_id" in payload:
        raise BusinessError(
            "ingredient_variation_item_immutable",
            "Create a new variation to change its inventory item",
        )
    allowed = {"add_label", "remove_label", "status"}
    if set(payload) - allowed or not payload:
        raise BusinessError(
            "invalid_ingredient_variation_update", "Only labels and status may be updated"
        )
    values: dict[str, Any] = {"updated_at": _now()}
    if "add_label" in payload or "remove_label" in payload:
        item_name = str(
            session.execute(
                sa.select(models.inventory_items.c.name).where(
                    models.inventory_items.c.id == variation["inventory_item_id"]
                )
            ).scalar_one()
        )
        add, remove = _ingredient_variation_labels(
            item_name,
            payload.get("add_label", variation["add_label"]),
            payload.get("remove_label", variation["remove_label"]),
        )
        values.update(add_label=add, remove_label=remove)
    if "status" in payload:
        if payload["status"] not in {"active", "archived"}:
            raise BusinessError(
                "invalid_ingredient_variation_status", "Status must be active or archived"
            )
        values["status"] = payload["status"]
    session.execute(
        models.ingredient_variations.update()
        .where(models.ingredient_variations.c.id == variation_id)
        .values(**values)
    )
    assignments = list(session.execute(sa.select(models.ingredient_variation_products).where(
        models.ingredient_variation_products.c.variation_id == variation_id
    )).mappings())
    if "add_label" in values or "remove_label" in values:
        for assignment in assignments:
            if assignment["add_option_id"]:
                session.execute(models.modifier_options.update().where(models.modifier_options.c.id == assignment["add_option_id"]).values(name=values.get("add_label", variation["add_label"]), kitchen_text=values.get("add_label", variation["add_label"]), updated_at=values["updated_at"]))
            if assignment["remove_option_id"]:
                session.execute(models.modifier_options.update().where(models.modifier_options.c.id == assignment["remove_option_id"]).values(name=values.get("remove_label", variation["remove_label"]), kitchen_text=values.get("remove_label", variation["remove_label"]), updated_at=values["updated_at"]))
    if values.get("status") == "archived":
        option_ids = [option_id for assignment in assignments for option_id in (assignment["add_option_id"], assignment["remove_option_id"]) if option_id]
        if option_ids:
            session.execute(models.modifier_options.update().where(models.modifier_options.c.id.in_(option_ids)).values(status="archived", updated_at=values["updated_at"]))
    if values.get("status") == "active" and variation["status"] == "archived":
        for assignment in assignments:
            if assignment["status"] == "active":
                option_ids = [
                    assignment["add_option_id"]
                    if assignment["allow_add"]
                    else None
                ]
                option_ids = [option_id for option_id in option_ids if option_id]
                if option_ids:
                    session.execute(models.modifier_options.update().where(models.modifier_options.c.id.in_(option_ids)).values(status="active", updated_at=values["updated_at"]))
    if values.get("status") in {"active", "archived"}:
        group_ids = session.execute(
            sa.select(models.modifier_options.c.group_id)
            .where(
                models.modifier_options.c.id.in_(
                    [
                        option_id
                        for assignment in assignments
                        for option_id in (
                            assignment["add_option_id"],
                            assignment["remove_option_id"],
                        )
                        if option_id
                    ]
                )
            )
        ).scalars()
        for group_id in set(group_ids):
            _recalculate_ingredient_group(session, group_id)
    _audit(
        session,
        "ingredient_variation.archived" if values.get("status") == "archived" else ("ingredient_variation.reactivated" if values.get("status") == "active" and variation["status"] == "archived" else "ingredient_variation.updated"),
        "ingredient_variation",
        variation_id,
        values,
        actor_user_id=actor_id,
    )
    session.commit()
    return {**dict(variation), **values}


def _assignment_values(payload: dict[str, Any]) -> dict[str, Any]:
    allow_add, allow_remove = payload.get("allow_add"), payload.get("allow_remove")
    if not isinstance(allow_add, bool) or not isinstance(allow_remove, bool):
        raise BusinessError("invalid_variation_action", "Variation actions must be booleans")
    if allow_remove or not allow_add:
        raise BusinessError(
            "ingredient_extra_add_only",
            "Ingredient extras only support the add action for new sales",
        )
    add_quantity, remove_quantity = (
        _variation_quantity(payload.get("add_quantity", 0)),
        _variation_quantity(payload.get("remove_quantity", 0)),
    )
    charge = payload.get("charge_additional")
    if not isinstance(charge, bool):
        raise BusinessError("invalid_variation_price", "Additional charge must be boolean")
    raw_price = payload.get("add_price_delta_cents", 0)
    if isinstance(raw_price, bool) or not isinstance(raw_price, int):
        raise BusinessError("invalid_variation_price", "Additional price must be an integer")
    price = raw_price
    if add_quantity <= 0 or remove_quantity != 0:
        raise BusinessError(
            "invalid_variation_quantity",
            "Ingredient extras require a positive add quantity and zero remove quantity",
        )
    if (charge and (not allow_add or price <= 0)) or (not charge and price != 0):
        raise BusinessError(
            "invalid_variation_price", "Price must be explicit only for an added ingredient"
        )
    return {
        "allow_add": allow_add,
        "allow_remove": allow_remove,
        "add_quantity": add_quantity,
        "remove_quantity": remove_quantity,
        "charge_additional": charge,
        "add_price_delta_cents": price,
    }


def _variation_quantity(value: Any) -> Decimal:
    if isinstance(value, (bool, float)):
        raise BusinessError("invalid_variation_quantity", "Quantity must use an exact decimal string")
    if not isinstance(value, (Decimal, int, str)):
        raise BusinessError("invalid_variation_quantity", "Quantity must use an exact decimal string")
    try:
        decimal_value = value if isinstance(value, Decimal) else Decimal(str(value))
        if not decimal_value.is_finite():
            raise InvalidOperation
        return decimal_value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError):
        raise BusinessError(
            "invalid_variation_quantity", "Quantity must be a finite exact decimal"
        ) from None


def _candidate_assignment_products(session: Session, payload: dict[str, Any]) -> list[str]:
    raw_product_ids, raw_category_ids = payload.get("product_ids", []), payload.get("category_ids", [])
    if not isinstance(raw_product_ids, list) or not isinstance(raw_category_ids, list):
        raise BusinessError("variation_assignment_targets_required", "product_ids and category_ids must be arrays")
    if any(not isinstance(value, str) or not value.strip() for value in raw_product_ids + raw_category_ids):
        raise BusinessError("invalid_variation_assignment_targets", "Targets must be non-empty string identifiers")
    product_ids = {value.strip() for value in raw_product_ids}
    category_ids = {value.strip() for value in raw_category_ids}
    if not product_ids and not category_ids:
        raise BusinessError("variation_assignment_targets_required", "At least one product or category is required")
    if category_ids:
        valid_categories = set(
            session.execute(
                sa.select(models.product_categories.c.id).where(
                    models.product_categories.c.id.in_(category_ids),
                    models.product_categories.c.organization_id == ORGANIZATION_ID,
                )
            ).scalars()
        )
        if valid_categories != category_ids:
            raise BusinessError(
                "invalid_variation_assignment_targets",
                "Categories must belong to the authorized organization",
            )
        product_ids.update(
            session.execute(
                sa.select(models.products.c.id).where(
                    models.products.c.category_id.in_(category_ids),
                    models.products.c.status == "active",
                    models.products.c.organization_id == ORGANIZATION_ID,
                )
            ).scalars()
        )
    return sorted(product_ids)


def _assignment_preview(
    session: Session,
    variation: dict[str, Any],
    payload: dict[str, Any],
    branch_id: str,
) -> list[dict[str, Any]]:
    _assignment_values(payload)
    ids = _candidate_assignment_products(session, payload)
    products = (
        session.execute(
            sa.select(models.products, models.product_categories.c.name.label("category_name"))
            .join(
                models.product_categories,
                models.products.c.category_id == models.product_categories.c.id,
            )
            .where(models.products.c.id.in_(ids), models.products.c.organization_id == ORGANIZATION_ID)
        ).mappings()
        if ids
        else []
    )
    by_id = {row["id"]: row for row in products}
    preview = []
    for product_id in ids:
        product = by_id.get(product_id)
        reason = None
        if not product or product["status"] != "active":
            reason = "product_inactive_or_missing"
        else:
            recipe = _active_recipe_components(session, product_id, branch_id)
            if not recipe:
                reason = "active_recipe_required"
        preview.append(
            {
                "product_id": product_id,
                "product_name": product["name"] if product else None,
                "sku": product["sku"] if product else None,
                "category": product["category_name"] if product else None,
                "compatible": reason is None,
                "reason": reason,
            }
        )
    return preview


def preview_ingredient_variation_assignments(
    session: Session, variation_id: str, payload: dict[str, Any], actor_user_id: str | None = None
) -> list[dict[str, Any]]:
    actor_id = _actor_user_id(actor_user_id)
    variation = get_ingredient_variation(session, variation_id, actor_id)
    branch_id = _ingredient_variation_branch(session, actor_id)
    try:
        preview = _assignment_preview(session, variation, payload, branch_id)
    except Exception:
        logger.exception(
            "ingredient_variation.preview.error variation_id=%s actor_id=%s branch_id=%s",
            variation_id,
            actor_id,
            branch_id,
        )
        raise
    logger.info(
        "ingredient_variation.preview variation_id=%s actor_id=%s branch_id=%s target_count=%s",
        variation_id,
        actor_id,
        branch_id,
        len(preview),
    )
    return preview


def _ingredient_variation_branch(session: Session, actor_id: str) -> str:
    """Resolve the active branch from the authenticated actor, never command input."""
    scoped_branch = authorize_branch_scope(session, actor_id, "catalog.manage")
    if scoped_branch:
        return scoped_branch
    return str(build_session_profile(session, actor_id)["active_branch"]["id"])


def _ingredient_group_is_owned(session: Session, group: dict[str, Any]) -> bool:
    """A named group is reusable only when every historical option is catalog-owned."""
    options = list(
        session.execute(
            sa.select(models.modifier_options.c.id)
            .where(models.modifier_options.c.group_id == group["id"])
        ).scalars()
    )
    if not options:
        return False
    linked = set(
        session.execute(
            sa.select(models.ingredient_variation_products.c.add_option_id).where(
                models.ingredient_variation_products.c.add_option_id.in_(options)
            ).union(
                sa.select(models.ingredient_variation_products.c.remove_option_id).where(
                    models.ingredient_variation_products.c.remove_option_id.in_(options)
                )
            )
        ).scalars()
    )
    return set(options) == linked


def _recalculate_ingredient_group(session: Session, group_id: str) -> None:
    """Keep the optional ingredient group hidden when it has no active options."""
    now = _now()
    active_count = session.execute(
        sa.select(sa.func.count())
        .select_from(models.modifier_options)
        .where(
            models.modifier_options.c.group_id == group_id,
            models.modifier_options.c.status == "active",
        )
    ).scalar_one()
    session.execute(
        models.modifier_groups.update()
        .where(models.modifier_groups.c.id == group_id)
        .values(
            maximum_selections=int(active_count),
            status="active" if active_count else "archived",
            updated_at=now,
        )
    )


def _ingredient_group(session: Session, product_id: str) -> dict[str, Any]:
    group = (
        session.execute(
            sa.select(models.modifier_groups).where(
                models.modifier_groups.c.product_id == product_id,
                models.modifier_groups.c.name == INGREDIENT_VARIATION_GROUP,
            )
        )
        .mappings()
        .first()
    )
    if group:
        group = dict(group)
        active_count = session.execute(
            sa.select(sa.func.count())
            .select_from(models.modifier_options)
            .where(
                models.modifier_options.c.group_id == group["id"],
                models.modifier_options.c.status == "active",
            )
        ).scalar_one()
        if (
            group["organization_id"] != ORGANIZATION_ID
            or group["product_id"] != product_id
            or group["is_required"]
            or group["minimum_selections"] != 0
            or group["status"] not in {"active", "archived"}
            or group["maximum_selections"] != int(active_count)
            or (group["status"] == "active") != bool(active_count)
            or not _ingredient_group_is_owned(session, group)
        ):
            raise BusinessError(
                "variation_group_conflict", "Ingredient variation group is incompatible"
            )
        return group
    now = _now()
    group = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "product_id": product_id,
        "name": INGREDIENT_VARIATION_GROUP,
        "is_required": False,
        "minimum_selections": 0,
        "maximum_selections": 1,
        "station": None,
        "display_order": 999,
        "status": "active",
        "created_at": now,
        "updated_at": now,
    }
    session.execute(models.modifier_groups.insert().values(**group))
    return group


def _sync_ingredient_assignment_options(
    session: Session, variation: dict[str, Any], assignment: dict[str, Any]
) -> dict[str, Any]:
    group = _ingredient_group(session, assignment["product_id"])
    now = _now()
    option_specs = (
        (
            "add",
            "add_option_id",
            variation["add_label"],
            assignment["allow_add"],
            assignment["add_quantity"],
            Decimal("0"),
            assignment["add_price_delta_cents"],
        ),
        (
            "remove",
            "remove_option_id",
            variation["remove_label"],
            assignment["allow_remove"],
            Decimal("0"),
            assignment["remove_quantity"],
            0,
        ),
    )
    updates: dict[str, Any] = {"updated_at": now}
    for effect, key, label, enabled, add_qty, remove_qty, price in option_specs:
        option_id = assignment.get(key)
        if not enabled:
            if option_id:
                session.execute(
                    models.modifier_options.update()
                    .where(models.modifier_options.c.id == option_id)
                    .values(status="archived", updated_at=now)
                )
            continue
        option = {
            "group_id": group["id"],
            "name": label,
            "effect_type": effect,
            "price_delta_cents": price,
            "affected_item_id": variation["inventory_item_id"],
            "replacement_item_id": None,
            "remove_quantity": remove_qty,
            "add_quantity": add_qty,
            "inventory_effect": True,
            "kitchen_text": label,
            "station": group["station"],
            "display_order": 0 if effect == "add" else 1,
            "status": "active",
            "updated_at": now,
        }
        if option_id:
            session.execute(
                models.modifier_options.update()
                .where(models.modifier_options.c.id == option_id)
                .values(**option)
            )
        else:
            option_id = _id()
            session.execute(
                models.modifier_options.insert().values(id=option_id, created_at=now, **option)
            )
            updates[key] = option_id
    session.execute(
        models.ingredient_variation_products.update()
        .where(models.ingredient_variation_products.c.id == assignment["id"])
        .values(**updates)
    )
    _recalculate_ingredient_group(session, group["id"])
    return {**assignment, **updates}


def apply_ingredient_variation_assignments(
    session: Session,
    variation_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
    actor_user_id: str | None = None,
    assignment_update: bool = False,
) -> list[dict[str, Any]]:
    actor_id = _actor_user_id(actor_user_id)
    variation = get_ingredient_variation(session, variation_id, actor_id)
    if variation["status"] != "active":
        raise BusinessError(
            "ingredient_variation_archived", "Archived variation cannot be assigned"
        )
    if not idempotency_key.strip():
        raise BusinessError("idempotency_key_required", "Assignment apply requires Idempotency-Key")
    values = _assignment_values(payload)
    targets = _candidate_assignment_products(session, payload)
    branch_id = _ingredient_variation_branch(session, actor_id)
    canonical_request = json.dumps({"variation_id": variation_id, "operation": "assignment_update" if assignment_update else "assignment_bulk_apply", "targets": targets, **{key: str(value) if isinstance(value, Decimal) else value for key, value in values.items()}}, sort_keys=True, separators=(",", ":"))
    request_hash = hashlib.sha256(canonical_request.encode()).hexdigest()
    key = idempotency_key.strip()
    command = session.execute(sa.select(models.ingredient_variation_commands).where(
        models.ingredient_variation_commands.c.idempotency_key == key
    )).mappings().first()
    if command:
        if command["organization_id"] != ORGANIZATION_ID or command["variation_id"] != variation_id or command["request_hash"] != request_hash:
            logger.warning(
                "ingredient_variation.apply.conflict variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
                variation_id,
                actor_id,
                branch_id,
                len(targets),
                key,
            )
            raise BusinessError("idempotency_conflict", "Idempotency key belongs to a different request")
        if command["status"] == "completed":
            logger.info(
                "ingredient_variation.apply.replay variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
                variation_id,
                actor_id,
                branch_id,
                len(targets),
                key,
            )
            return list(command["result"] or [])
        logger.warning(
            "ingredient_variation.apply.conflict variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
            variation_id,
            actor_id,
            branch_id,
            len(targets),
            key,
        )
        raise BusinessError("idempotency_conflict", "Idempotency request is still processing")
    preview = _assignment_preview(session, variation, payload, branch_id)
    incompatible = [row for row in preview if not row["compatible"]]
    if incompatible:
        raise BusinessError(
            "variation_assignment_incompatible", "All selected products must be compatible"
        )
    now = _now()
    rows = []
    updated_assignment_id: str | None = None
    try:
        session.execute(models.ingredient_variation_commands.insert().values(
            id=_id(), organization_id=ORGANIZATION_ID, variation_id=variation_id, actor_user_id=actor_id,
            idempotency_key=key, request_hash=request_hash, result=None, status="processing", created_at=now, updated_at=now,
        ))
        # Revalidate the effective branch recipe in the command transaction.
        preview = _assignment_preview(session, variation, payload, branch_id)
        incompatible = [row for row in preview if not row["compatible"]]
        if incompatible:
            raise BusinessError(
                "variation_assignment_incompatible",
                "All selected products must be compatible",
            )
        for product_id in [row["product_id"] for row in preview]:
            existing = (
                session.execute(
                    sa.select(models.ingredient_variation_products).where(
                        models.ingredient_variation_products.c.variation_id == variation_id,
                        models.ingredient_variation_products.c.product_id == product_id,
                    )
                )
                .mappings()
                .first()
            )
            assignment = {
                "id": existing["id"] if existing else _id(),
                "variation_id": variation_id,
                "product_id": product_id,
                **values,
                "status": "active",
                "updated_at": now,
            }
            if existing:
                updated_assignment_id = existing["id"]
                session.execute(
                    models.ingredient_variation_products.update()
                    .where(models.ingredient_variation_products.c.id == existing["id"])
                    .values(**assignment)
                )
                assignment = {**dict(existing), **assignment}
            else:
                assignment["created_at"] = now
                assignment["add_option_id"] = None
                assignment["remove_option_id"] = None
                session.execute(models.ingredient_variation_products.insert().values(**assignment))
            rows.append(_sync_ingredient_assignment_options(session, variation, assignment))
        audit_action = (
            "ingredient_variation.assignment.updated"
            if assignment_update and updated_assignment_id
            else "ingredient_variation.assignment.bulk_applied"
        )
        _audit(
            session,
            audit_action,
            "ingredient_variation_product" if updated_assignment_id else "ingredient_variation",
            updated_assignment_id or variation_id,
            {
                "products": len(rows),
                "idempotency_key": idempotency_key,
                "allow_add": values["allow_add"],
                "allow_remove": values["allow_remove"],
            },
            actor_user_id=actor_id,
        )
        session.execute(models.ingredient_variation_commands.update().where(
            models.ingredient_variation_commands.c.idempotency_key == key
        ).values(result=_sanitize_for_json(rows), status="completed", updated_at=_now()))
        session.commit()
        logger.info(
            "ingredient_variation.apply variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
            variation_id,
            actor_id,
            branch_id,
            len(rows),
            key,
        )
    except sa.exc.IntegrityError as exc:
        session.rollback()
        existing = session.execute(sa.select(models.ingredient_variation_commands).where(
            models.ingredient_variation_commands.c.idempotency_key == key
        )).mappings().first()
        if existing and existing["request_hash"] == request_hash and existing["status"] == "completed":
            logger.info(
                "ingredient_variation.apply.replay variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
                variation_id,
                actor_id,
                branch_id,
                len(targets),
                key,
            )
            return list(existing["result"] or [])
        logger.warning(
            "ingredient_variation.apply.conflict variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
            variation_id,
            actor_id,
            branch_id,
            len(targets),
            key,
        )
        raise BusinessError("idempotency_conflict", "Idempotency key belongs to a different request") from exc
    except Exception:
        session.rollback()
        logger.exception(
            "ingredient_variation.apply.error variation_id=%s actor_id=%s branch_id=%s target_count=%s idempotency_key=%s",
            variation_id,
            actor_id,
            branch_id,
            len(targets),
            key,
        )
        raise
    return _sanitize_for_json(rows)


def archive_ingredient_variation_assignment(
    session: Session, variation_id: str, product_id: str, actor_user_id: str | None = None
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    row = (
        session.execute(
            sa.select(models.ingredient_variation_products)
            .select_from(
                models.ingredient_variation_products.join(
                    models.ingredient_variations,
                    models.ingredient_variations.c.id
                    == models.ingredient_variation_products.c.variation_id,
                ).join(
                    models.products,
                    models.products.c.id == models.ingredient_variation_products.c.product_id,
                )
            )
            .where(
                models.ingredient_variation_products.c.variation_id == variation_id,
                models.ingredient_variation_products.c.product_id == product_id,
                models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
                models.products.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise NotFoundError(
            "ingredient_variation_assignment_not_found",
            "Ingredient variation assignment was not found",
        )
    now = _now()
    session.execute(
        models.ingredient_variation_products.update()
        .where(models.ingredient_variation_products.c.id == row["id"])
        .values(status="archived", updated_at=now)
    )
    group_ids = set(session.execute(
        sa.select(models.modifier_options.c.group_id).where(
            models.modifier_options.c.id.in_(
                [value for value in (row["add_option_id"], row["remove_option_id"]) if value]
            )
        )
    ).scalars())
    session.execute(
        models.modifier_options.update()
        .where(
            models.modifier_options.c.id.in_(
                [value for value in (row["add_option_id"], row["remove_option_id"]) if value]
            )
        )
        .values(status="archived", updated_at=now)
    )
    for group_id in group_ids:
        _recalculate_ingredient_group(session, group_id)
    _audit(
        session,
        "ingredient_variation.assignment.archived",
        "ingredient_variation_product",
        row["id"],
        {"variation_id": variation_id, "product_id": product_id},
        actor_user_id=actor_id,
    )
    session.commit()
    return {**dict(row), "status": "archived", "updated_at": now}


def list_branch_ingredient_variations(
    session: Session, actor_user_id: str, branch_id: str | None = None
) -> list[dict[str, Any]]:
    authorized_branch = _branch_administration_target(
        session, actor_user_id, "branch.admin.access", branch_id
    )
    require_permission(session, actor_user_id, "catalog.branch.manage", authorized_branch)
    rows = session.execute(
        sa.select(
            models.ingredient_variation_products.c.variation_id,
            models.ingredient_variation_products.c.product_id,
            models.inventory_items.c.name.label("inventory_item_name"),
            models.inventory_items.c.sku.label("inventory_item_sku"),
            models.inventory_units.c.code.label("unit_code"),
            models.products.c.name.label("product_name"),
            models.modifier_options.c.id.label("option_id"),
            models.modifier_options.c.name.label("name"),
            models.modifier_options.c.effect_type,
            models.modifier_options.c.status.label("central_status"),
            models.branch_modifier_options.c.is_enabled.label("override"),
        )
        .select_from(
            models.ingredient_variation_products.join(
                models.ingredient_variations,
                models.ingredient_variations.c.id
                == models.ingredient_variation_products.c.variation_id,
            ).join(
                models.products,
                models.products.c.id == models.ingredient_variation_products.c.product_id,
            )
            .join(
                models.inventory_items,
                models.inventory_items.c.id == models.ingredient_variations.c.inventory_item_id,
            )
            .join(
                models.inventory_units,
                models.inventory_units.c.id == models.inventory_items.c.base_unit_id,
            )
            .join(
                models.modifier_options,
                models.modifier_options.c.id
                == models.ingredient_variation_products.c.add_option_id,
            )
            .outerjoin(
                models.branch_modifier_options,
                sa.and_(
                    models.branch_modifier_options.c.option_id == models.modifier_options.c.id,
                    models.branch_modifier_options.c.branch_id == authorized_branch,
                ),
            )
        )
        .where(
            models.ingredient_variation_products.c.status == "active",
            models.ingredient_variation_products.c.allow_add.is_(True),
            models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
            models.ingredient_variations.c.status == "active",
            models.products.c.organization_id == ORGANIZATION_ID,
            models.products.c.status == "active",
            models.modifier_options.c.status == "active",
        )
    ).mappings()
    return [
        {
            **dict(row),
            "effective_enabled": row["central_status"] == "active" and row["override"] is not False,
        }
        for row in rows
    ]


def set_branch_ingredient_variation_option(
    session: Session, actor_user_id: str, option_id: str, action: str, branch_id: str | None = None
) -> dict[str, Any]:
    authorized_branch = _branch_administration_target(
        session, actor_user_id, "branch.admin.access", branch_id
    )
    require_permission(session, actor_user_id, "catalog.branch.manage", authorized_branch)
    option = (
        session.execute(
            sa.select(models.modifier_options.c.id, models.modifier_options.c.status)
            .select_from(
                models.modifier_options.join(
                    models.ingredient_variation_products,
                    models.ingredient_variation_products.c.add_option_id
                    == models.modifier_options.c.id,
                )
                .join(
                    models.ingredient_variations,
                    models.ingredient_variations.c.id
                    == models.ingredient_variation_products.c.variation_id,
                )
                .join(
                    models.products,
                    models.products.c.id == models.ingredient_variation_products.c.product_id,
                )
            )
            .where(
                models.modifier_options.c.id == option_id,
                models.modifier_options.c.status == "active",
                models.ingredient_variation_products.c.status == "active",
                models.ingredient_variation_products.c.allow_add.is_(True),
                models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
                models.ingredient_variations.c.status == "active",
                models.products.c.organization_id == ORGANIZATION_ID,
                models.products.c.status == "active",
            )
        )
        .mappings()
        .first()
    )
    if not option:
        raise NotFoundError(
            "ingredient_variation_option_not_found", "Ingredient variation option was not found"
        )
    if not option:
        raise BusinessError(
            "ingredient_variation_option_not_found", "Option is not an ingredient variation"
        )
    if action not in {"available", "unavailable", "inherit"}:
        raise BusinessError(
            "invalid_ingredient_variation_action",
            "Action must be available, unavailable or inherit",
        )
    if action == "inherit":
        session.execute(
            models.branch_modifier_options.delete().where(
                models.branch_modifier_options.c.branch_id == authorized_branch,
                models.branch_modifier_options.c.option_id == option_id,
            )
        )
        override = None
    else:
        override = action == "available"
        values = {
            "branch_id": authorized_branch,
            "option_id": option_id,
            "is_enabled": override,
            "price_delta_cents": None,
            "updated_at": _now(),
        }
        exists = session.execute(
            sa.select(models.branch_modifier_options.c.option_id).where(
                models.branch_modifier_options.c.branch_id == authorized_branch,
                models.branch_modifier_options.c.option_id == option_id,
            )
        ).scalar_one_or_none()
        if exists:
            session.execute(
                models.branch_modifier_options.update()
                .where(
                    models.branch_modifier_options.c.branch_id == authorized_branch,
                    models.branch_modifier_options.c.option_id == option_id,
                )
                .values(**values)
            )
        else:
            session.execute(models.branch_modifier_options.insert().values(**values))
    _audit(
        session,
        "ingredient_variation.branch_configured",
        "modifier_option",
        option_id,
        {"action": action, "override": override},
        branch_id=authorized_branch,
        actor_user_id=actor_user_id,
    )
    session.commit()
    return {
        "option_id": option_id,
        "branch_id": authorized_branch,
        "override": override,
        "effective_enabled": option["status"] == "active" and override is not False,
    }


PRESET_VARIATION_GROUP = "Variaciones y cambios"


def _normalized_variation_name(value: Any) -> str:
    name = str(value or "").strip()
    if not name or len(name) > 120:
        raise BusinessError("invalid_variation_note", "Variation note name is required and must be at most 120 characters")
    return name


def _variation_display_order(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise BusinessError("invalid_variation_display_order", "Variation note display order must be an integer")
    if value < -(2**31) or value > 2**31 - 1:
        raise BusinessError("invalid_variation_display_order", "Variation note display order is outside the supported range")
    return value


def _is_safe_preset_variation_group(session: Session, group: dict[str, Any]) -> bool:
    if group["status"] != "active" or group["is_required"] or group["minimum_selections"] != 0:
        return False
    if group["maximum_selections"] < 1:
        return False
    effects = set(session.execute(
        sa.select(models.modifier_options.c.effect_type).where(
            models.modifier_options.c.group_id == group["id"]
        )
    ).scalars())
    return effects <= {"preset_instruction"}


def _preset_variation_group(session: Session, product_id: str) -> dict[str, Any]:
    group = session.execute(
        sa.select(models.modifier_groups).where(
            models.modifier_groups.c.product_id == product_id,
            sa.func.lower(sa.func.trim(models.modifier_groups.c.name)) == PRESET_VARIATION_GROUP.lower(),
        )
    ).mappings().first()
    now = _now()
    if group:
        if not _is_safe_preset_variation_group(session, dict(group)):
            raise BusinessError(
                "variation_group_conflict",
                "The existing Variaciones y cambios group is not safe for preset variation notes",
            )
        return dict(group)
    group = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "product_id": product_id,
        "name": PRESET_VARIATION_GROUP, "is_required": False, "minimum_selections": 0,
        "maximum_selections": 1, "station": None, "display_order": 0, "status": "active",
        "created_at": now, "updated_at": now,
    }
    session.execute(models.modifier_groups.insert().values(**group))
    return group


def _sync_preset_variation_group_capacity(session: Session, group_id: str) -> None:
    group = session.execute(
        sa.select(models.modifier_groups).where(models.modifier_groups.c.id == group_id)
    ).mappings().first()
    if not group or not _is_safe_preset_variation_group(session, dict(group)):
        raise BusinessError("variation_group_conflict", "Preset variation group is not safe to synchronize")
    active_count = int(session.execute(
        sa.select(sa.func.count()).select_from(models.modifier_options).where(
            models.modifier_options.c.group_id == group_id,
            models.modifier_options.c.effect_type == "preset_instruction",
            models.modifier_options.c.status == "active",
        )
    ).scalar_one())
    session.execute(models.modifier_groups.update().where(models.modifier_groups.c.id == group_id).values(
        is_required=False,
        minimum_selections=0,
        maximum_selections=max(1, active_count),
        status="active",
        updated_at=_now(),
    ))


def create_variation_note(
    session: Session,
    product_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    product = session.execute(sa.select(models.products.c.id).where(
        models.products.c.id == product_id,
        models.products.c.organization_id == ORGANIZATION_ID,
    )).scalar_one_or_none()
    if not product:
        raise NotFoundError("product_not_found", "Product was not found")
    name = _normalized_variation_name(payload.get("name"))
    duplicate = session.execute(
        sa.select(models.modifier_options.c.id)
        .select_from(models.modifier_options.join(models.modifier_groups, models.modifier_options.c.group_id == models.modifier_groups.c.id))
        .where(
            models.modifier_groups.c.product_id == product_id,
            models.modifier_options.c.effect_type == "preset_instruction",
            sa.func.lower(sa.func.trim(models.modifier_options.c.name)) == name.lower(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if duplicate:
        raise BusinessError("variation_note_already_exists", "A variation note with this name already exists for the product")
    group = _preset_variation_group(session, product_id)
    now = _now()
    option = {
        "id": _id(), "group_id": group["id"], "name": name, "effect_type": "preset_instruction",
        "price_delta_cents": 0, "affected_item_id": None, "replacement_item_id": None,
        "remove_quantity": Decimal("0"), "add_quantity": Decimal("0"), "inventory_effect": False,
        "kitchen_text": name, "station": group["station"],
        "display_order": _variation_display_order(payload.get("display_order", 0)), "status": "active",
        "created_at": now, "updated_at": now,
    }
    session.execute(models.modifier_options.insert().values(**option))
    _sync_preset_variation_group_capacity(session, group["id"])
    _audit(session, "variation_note.created", "modifier_option", option["id"],
           {"product_id": product_id, "name": name, "display_order": option["display_order"]}, actor_user_id=actor_id)
    session.commit()
    return option


def update_variation_note(
    session: Session,
    option_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    option = session.execute(
        sa.select(models.modifier_options, models.modifier_groups.c.product_id)
        .select_from(models.modifier_options.join(models.modifier_groups, models.modifier_options.c.group_id == models.modifier_groups.c.id))
        .where(models.modifier_options.c.id == option_id, models.modifier_options.c.effect_type == "preset_instruction")
    ).mappings().first()
    if not option:
        raise NotFoundError("variation_note_not_found", "Variation note was not found")
    unknown = set(payload) - {"name", "display_order", "status"}
    if unknown:
        raise BusinessError("invalid_variation_note_update", "Only name, display_order and status may be updated")
    values: dict[str, Any] = {"updated_at": _now()}
    if "name" in payload:
        name = _normalized_variation_name(payload["name"])
        duplicate = session.execute(
            sa.select(models.modifier_options.c.id)
            .select_from(models.modifier_options.join(models.modifier_groups, models.modifier_options.c.group_id == models.modifier_groups.c.id))
            .where(
                models.modifier_groups.c.product_id == option["product_id"],
                models.modifier_options.c.effect_type == "preset_instruction",
                sa.func.lower(sa.func.trim(models.modifier_options.c.name)) == name.lower(),
                models.modifier_options.c.id != option_id,
            ).limit(1)
        ).scalar_one_or_none()
        if duplicate:
            raise BusinessError("variation_note_already_exists", "A variation note with this name already exists for the product")
        values.update(name=name, kitchen_text=name)
    if "display_order" in payload:
        values["display_order"] = _variation_display_order(payload["display_order"])
    if "status" in payload:
        status = str(payload["status"])
        if status not in {"active", "archived"}:
            raise BusinessError("invalid_variation_note_status", "Variation note status must be active or archived")
        values["status"] = status
    if len(values) == 1:
        raise BusinessError("invalid_variation_note_update", "At least one editable variation note field is required")
    session.execute(models.modifier_options.update().where(models.modifier_options.c.id == option_id).values(**values))
    _sync_preset_variation_group_capacity(session, option["group_id"])
    action = "variation_note.archived" if values.get("status") == "archived" else "variation_note.updated"
    if values.get("status") == "active" and option["status"] == "archived":
        action = "variation_note.reactivated"
    _audit(session, action, "modifier_option", option_id, values, actor_user_id=actor_id)
    session.commit()
    return {**dict(option), **values}


def list_variation_notes(
    session: Session, product_id: str, actor_user_id: str | None = None
) -> list[dict[str, Any]]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    rows = session.execute(
        sa.select(
            models.modifier_options.c.id, models.modifier_options.c.name, models.modifier_options.c.kitchen_text,
            models.modifier_options.c.display_order, models.modifier_options.c.status,
            models.modifier_groups.c.product_id, models.products.c.name.label("product_name"),
        ).select_from(
            models.modifier_options.join(models.modifier_groups, models.modifier_options.c.group_id == models.modifier_groups.c.id)
            .join(models.products, models.modifier_groups.c.product_id == models.products.c.id)
        ).where(
            models.modifier_groups.c.product_id == product_id,
            models.modifier_options.c.effect_type == "preset_instruction",
        ).order_by(models.modifier_options.c.display_order, models.modifier_options.c.name)
    ).mappings()
    return [dict(row) for row in rows]


def list_branch_variation_notes(
    session: Session, actor_user_id: str, branch_id: str | None = None
) -> list[dict[str, Any]]:
    authorized_branch = _branch_administration_target(session, actor_user_id, "branch.admin.access", branch_id)
    require_permission(session, actor_user_id, "catalog.branch.manage", authorized_branch)
    rows = session.execute(
        sa.select(
            models.products.c.id.label("product_id"), models.products.c.name.label("product_name"),
            models.modifier_options.c.id.label("option_id"), models.modifier_options.c.name.label("name"),
            models.modifier_options.c.display_order, models.modifier_options.c.status.label("central_status"),
            models.branch_modifier_options.c.is_enabled.label("override"),
        ).select_from(
            models.modifier_options.join(models.modifier_groups, models.modifier_options.c.group_id == models.modifier_groups.c.id)
            .join(models.products, models.modifier_groups.c.product_id == models.products.c.id)
            .outerjoin(models.branch_modifier_options, sa.and_(
                models.branch_modifier_options.c.option_id == models.modifier_options.c.id,
                models.branch_modifier_options.c.branch_id == authorized_branch,
            ))
        ).where(models.modifier_options.c.effect_type == "preset_instruction")
        .order_by(models.products.c.name, models.modifier_options.c.display_order, models.modifier_options.c.name)
    ).mappings()
    return [{**dict(row), "effective_enabled": row["central_status"] == "active" and row["override"] is not False} for row in rows]


def set_branch_variation_note(
    session: Session, actor_user_id: str, option_id: str, action: str, branch_id: str | None = None
) -> dict[str, Any]:
    authorized_branch = _branch_administration_target(session, actor_user_id, "branch.admin.access", branch_id)
    require_permission(session, actor_user_id, "catalog.branch.manage", authorized_branch)
    option = session.execute(sa.select(models.modifier_options.c.id, models.modifier_options.c.status).where(
        models.modifier_options.c.id == option_id,
        models.modifier_options.c.effect_type == "preset_instruction",
    )).mappings().first()
    if not option:
        raise NotFoundError("variation_note_not_found", "Variation note was not found")
    if action not in {"available", "unavailable", "inherit"}:
        raise BusinessError("invalid_variation_note_action", "Action must be available, unavailable or inherit")
    existing = session.execute(sa.select(models.branch_modifier_options.c.is_enabled).where(
        models.branch_modifier_options.c.branch_id == authorized_branch,
        models.branch_modifier_options.c.option_id == option_id,
    )).scalar_one_or_none()
    if action == "inherit":
        session.execute(models.branch_modifier_options.delete().where(
            models.branch_modifier_options.c.branch_id == authorized_branch,
            models.branch_modifier_options.c.option_id == option_id,
        ))
        override = None
    else:
        override = action == "available"
        values = {"branch_id": authorized_branch, "option_id": option_id, "is_enabled": override,
                  "price_delta_cents": None, "updated_at": _now()}
        if existing is None:
            session.execute(models.branch_modifier_options.insert().values(**values))
        else:
            session.execute(models.branch_modifier_options.update().where(
                models.branch_modifier_options.c.branch_id == authorized_branch,
                models.branch_modifier_options.c.option_id == option_id,
            ).values(**values))
    _audit(session, "variation_note.branch_configured", "modifier_option", option_id,
           {"branch_id": authorized_branch, "previous": existing, "override": override, "action": action},
           branch_id=authorized_branch, actor_user_id=actor_user_id)
    session.commit()
    return {"option_id": option_id, "branch_id": authorized_branch, "override": override,
            "effective_enabled": option["status"] == "active" and override is not False}


def set_branch_modifier_option(
    session: Session,
    option_id: str,
    branch_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.branch.manage", branch_id)
    if not session.execute(sa.select(models.modifier_options.c.id).where(
        models.modifier_options.c.id == option_id
    )).scalar_one_or_none():
        raise BusinessError("modifier_option_not_found", "Modifier option was not found")
    values = {
        "branch_id": branch_id, "option_id": option_id,
        "is_enabled": bool(payload.get("is_enabled", True)),
        "price_delta_cents": int(payload["price_delta_cents"]) if payload.get("price_delta_cents") is not None else None,
        "updated_at": _now(),
    }
    existing = session.execute(sa.select(models.branch_modifier_options).where(
        models.branch_modifier_options.c.branch_id == branch_id,
        models.branch_modifier_options.c.option_id == option_id,
    )).first()
    if existing:
        session.execute(sa.update(models.branch_modifier_options).where(
            models.branch_modifier_options.c.branch_id == branch_id,
            models.branch_modifier_options.c.option_id == option_id,
        ).values(**values))
    else:
        session.execute(models.branch_modifier_options.insert().values(**values))
    _audit(session, "modifier_option.branch_configured", "modifier_option", option_id,
           values, branch_id, actor_user_id=actor_id)
    session.commit()
    return values


def list_product_modifiers(
    session: Session,
    product_id: str,
    branch_id: str | None = None,
) -> list[dict[str, Any]]:
    actual_branch_id = branch_id or BRANCH_ID
    groups = [
        dict(row)
        for row in session.execute(
            sa.select(models.modifier_groups)
            .where(
                models.modifier_groups.c.product_id == product_id,
                models.modifier_groups.c.status == "active",
            )
            .order_by(models.modifier_groups.c.display_order, models.modifier_groups.c.name)
        ).mappings()
    ]
    if not groups:
        return []
    by_id = {group["id"]: {**group, "options": []} for group in groups}
    options = session.execute(
        sa.select(
            models.modifier_options,
            models.branch_modifier_options.c.is_enabled.label("branch_enabled"),
            models.branch_modifier_options.c.price_delta_cents.label("branch_price_delta_cents"),
        )
        .select_from(
            models.modifier_options.outerjoin(
                models.branch_modifier_options,
                sa.and_(
                    models.branch_modifier_options.c.option_id == models.modifier_options.c.id,
                    models.branch_modifier_options.c.branch_id == actual_branch_id,
                ),
            )
        )
        .where(
            models.modifier_options.c.group_id.in_(by_id.keys()),
            models.modifier_options.c.status == "active",
        )
        .order_by(models.modifier_options.c.display_order, models.modifier_options.c.name)
    ).mappings()
    option_rows = list(options)
    option_ids = [row["id"] for row in option_rows]
    ingredient_by_option: dict[str, dict[str, Any]] = {}
    legacy_remove_option_ids: set[str] = set()
    if option_ids:
        ingredient_rows = session.execute(
            sa.select(
                models.ingredient_variation_products.c.variation_id,
                models.ingredient_variation_products.c.add_option_id,
                models.ingredient_variation_products.c.remove_option_id,
                models.ingredient_variations.c.inventory_item_id,
                models.inventory_items.c.name.label("inventory_item_name"),
                models.inventory_units.c.code.label("unit_code"),
            )
            .select_from(
                models.ingredient_variation_products.join(
                    models.ingredient_variations,
                    models.ingredient_variations.c.id
                    == models.ingredient_variation_products.c.variation_id,
                )
                .join(
                    models.inventory_items,
                    models.inventory_items.c.id
                    == models.ingredient_variations.c.inventory_item_id,
                )
                .join(
                    models.inventory_units,
                    models.inventory_units.c.id == models.inventory_items.c.base_unit_id,
                )
            )
            .where(
                sa.or_(
                    models.ingredient_variation_products.c.add_option_id.in_(option_ids),
                    models.ingredient_variation_products.c.remove_option_id.in_(option_ids),
                ),
                models.ingredient_variation_products.c.status == "active",
                models.ingredient_variations.c.status == "active",
                models.ingredient_variations.c.organization_id == ORGANIZATION_ID,
            )
        ).mappings()
        for ingredient in ingredient_rows:
            ingredient = dict(ingredient)
            if ingredient["remove_option_id"]:
                legacy_remove_option_ids.add(ingredient["remove_option_id"])
            if ingredient["add_option_id"]:
                ingredient_by_option[ingredient["add_option_id"]] = {
                    **ingredient,
                    "action": "add",
                }
    for row in option_rows:
        # POS-VAR-003 preserves historical ingredient removals in the database,
        # but they cannot be offered in new sales.  This deliberately does not
        # hide unrelated remove/substitute modifier options.
        if row["id"] in legacy_remove_option_ids:
            continue
        if row["branch_enabled"] is False:
            continue
        option = dict(row)
        option["price_delta_cents"] = (
            0
            if row["effect_type"] == "preset_instruction"
            else (
                row["branch_price_delta_cents"]
                if row["branch_price_delta_cents"] is not None
                else row["price_delta_cents"]
            )
        )
        ingredient = ingredient_by_option.get(row["id"])
        if ingredient:
            option.update(
                {
                    "variation_kind": "ingredient_extra",
                    "variation_id": ingredient["variation_id"],
                    "action": "add",
                    "inventory_item_name": ingredient["inventory_item_name"],
                    "unit_code": ingredient["unit_code"],
                    "quantity": option["add_quantity"],
                }
            )
        by_id[row["group_id"]]["options"].append(option)
    return [
        group
        for group in by_id.values()
        if group["options"] or group["name"] != PRESET_VARIATION_GROUP
    ]


def create_production_recipe(
    session: Session,
    output_item_id: str,
    components: list[dict[str, Any]],
    yield_quantity: Any,
    yield_unit_id: str,
    branch_id: str | None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    output = session.execute(sa.select(models.inventory_items).where(
        models.inventory_items.c.id == output_item_id,
        models.inventory_items.c.organization_id == ORGANIZATION_ID,
        models.inventory_items.c.status == "active",
    )).mappings().first()
    if not output:
        raise BusinessError("output_item_not_found", "Production output item was not found")
    if output["item_type"] != "elaborated":
        raise BusinessError("output_item_must_be_elaborated", "Production recipe output must be an elaborated item")
    if yield_unit_id != output["base_unit_id"]:
        raise BusinessError("production_yield_unit_mismatch", "Production yield unit must match output base unit")
    normalized_yield = _quantity(yield_quantity)
    if normalized_yield <= 0:
        raise BusinessError("invalid_recipe_yield", "Recipe yield must be positive")
    component_rows = _normalize_recipe_components(session, components)
    _assert_no_production_recipe_cycle(session, output_item_id, [row["item_id"] for row in component_rows])
    now = _now()
    max_version = session.execute(sa.select(sa.func.max(models.recipes.c.version)).where(
        models.recipes.c.output_item_id == output_item_id
    )).scalar() or 0
    session.execute(sa.update(models.recipes).where(
        models.recipes.c.output_item_id == output_item_id,
        models.recipes.c.status == "active",
        models.recipes.c.branch_id.is_(branch_id) if branch_id is None else models.recipes.c.branch_id == branch_id,
    ).values(status="retired", valid_to=now, updated_at=now))
    recipe = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "product_id": None,
        "output_item_id": output_item_id, "branch_id": branch_id, "recipe_type": "production",
        "version": int(max_version) + 1, "status": "active", "yield_quantity": normalized_yield,
        "yield_unit_id": yield_unit_id, "valid_from": now, "valid_to": None,
        "created_at": now, "updated_at": now,
    }
    session.execute(models.recipes.insert().values(**recipe))
    for row in component_rows:
        session.execute(models.recipe_components.insert().values(recipe_id=recipe["id"], **row))
    cost = calculate_recipe_cost(session, recipe["id"], branch_id or BRANCH_ID, actor_id, persist=True)
    _audit(session, "production_recipe.created", "recipe", recipe["id"],
           {"output_item_id": output_item_id, "version": recipe["version"]}, branch_id=branch_id, actor_user_id=actor_id)
    session.commit()
    return {**recipe, "components": component_rows, "cost": cost}


def _normalize_recipe_components(
    session: Session,
    components: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not components:
        raise BusinessError("recipe_components_required", "Recipe requires at least one component")
    rows = []
    seen = set()
    for index, component in enumerate(components):
        item_id = str(component.get("item_id", ""))
        if item_id in seen:
            raise BusinessError("duplicate_recipe_component", "Recipe component cannot be duplicated")
        seen.add(item_id)
        item = session.execute(sa.select(models.inventory_items).where(
            models.inventory_items.c.id == item_id,
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.status == "active",
        )).mappings().first()
        if not item:
            raise BusinessError("recipe_component_not_found", "Recipe component item was not found")
        unit_id = str(component.get("unit_id") or item["base_unit_id"])
        if unit_id != item["base_unit_id"]:
            raise BusinessError("recipe_component_unit_mismatch", "Component unit must match item base unit")
        net = _quantity(component.get("net_quantity", component.get("quantity", 0)))
        if "waste_percent" in component:
            waste = _quantity(component["waste_percent"]) / Decimal("100")
        else:
            waste = _quantity(component.get("waste_rate", 0))
        if net <= 0 or waste < 0 or waste >= 1:
            raise BusinessError("invalid_recipe_component", "Net quantity must be positive and waste rate below one")
        gross = _quantity(net / (Decimal("1") - waste))
        rows.append({
            "item_id": item_id, "quantity_base_units": gross, "unit_id": unit_id,
            "net_quantity": net, "waste_rate": waste, "gross_quantity": gross,
            "sort_order": int(component.get("sort_order", index)), "notes": component.get("notes"),
        })
    return rows


def calculate_recipe_cost(
    session: Session,
    recipe_id: str,
    branch_id: str,
    actor_user_id: str,
    persist: bool = True,
) -> dict[str, Any]:
    recipe = session.execute(sa.select(models.recipes).where(models.recipes.c.id == recipe_id)).mappings().first()
    if not recipe:
        raise BusinessError("recipe_not_found", "Recipe was not found")
    warehouse_id = _branch_warehouse_id(session, branch_id)
    components = session.execute(sa.select(
        models.recipe_components,
        models.inventory_items.c.name.label("item_name"),
        models.inventory_units.c.code.label("unit_code"),
    ).select_from(
        models.recipe_components
        .join(models.inventory_items, models.recipe_components.c.item_id == models.inventory_items.c.id)
        .join(models.inventory_units, models.recipe_components.c.unit_id == models.inventory_units.c.id)
    ).where(models.recipe_components.c.recipe_id == recipe_id).order_by(models.recipe_components.c.sort_order)).mappings()
    before_waste = Decimal("0")
    total = Decimal("0")
    breakdown = []
    for component in components:
        average = session.execute(sa.select(models.inventory_cost_states.c.average_unit_cost).where(
            models.inventory_cost_states.c.branch_id == branch_id,
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == component["item_id"],
        )).scalar_one_or_none()
        unit_cost = _cost(average or 0)
        net_cost = _cost(Decimal(str(component["net_quantity"])) * unit_cost)
        gross_cost = _cost(Decimal(str(component["gross_quantity"])) * unit_cost)
        waste_cost = _cost(gross_cost - net_cost)
        before_waste += net_cost
        total += gross_cost
        breakdown.append(_sanitize_for_json({
            "item_id": component["item_id"], "item_name": component["item_name"],
            "unit_id": component["unit_id"], "unit_code": component["unit_code"],
            "net_quantity": component["net_quantity"], "gross_quantity": component["gross_quantity"],
            "waste_rate": component["waste_rate"], "unit_cost": unit_cost,
            "cost_before_waste": net_cost, "waste_cost": waste_cost, "total_cost": gross_cost,
        }))
    before_waste = _cost(before_waste)
    total = _cost(total)
    cost = {
        "id": _id(), "recipe_id": recipe_id, "branch_id": branch_id,
        "cost_before_waste": before_waste, "waste_cost": _cost(total - before_waste),
        "total_cost": total, "cost_per_yield_unit": _cost(total / Decimal(str(recipe["yield_quantity"]))),
        "breakdown": breakdown, "calculated_at": _now(), "calculated_by": actor_user_id,
    }
    if persist:
        session.execute(models.recipe_cost_calculations.insert().values(**cost))
    return cost


def _assert_no_production_recipe_cycle(
    session: Session,
    output_item_id: str,
    candidate_components: list[str],
) -> None:
    adjacency: dict[str, set[str]] = {}
    rows = session.execute(sa.select(
        models.recipes.c.output_item_id,
        models.recipe_components.c.item_id,
    ).select_from(models.recipes.join(
        models.recipe_components, models.recipes.c.id == models.recipe_components.c.recipe_id
    )).where(
        models.recipes.c.recipe_type == "production",
        models.recipes.c.status == "active",
        models.recipes.c.output_item_id.is_not(None),
    ))
    for parent, child in rows:
        adjacency.setdefault(str(parent), set()).add(str(child))
    adjacency[output_item_id] = set(candidate_components)

    def visit(item_id: str, path: set[str]) -> None:
        if item_id in path:
            raise BusinessError("recipe_cycle_detected", "Production recipe would create a cycle")
        for child in adjacency.get(item_id, set()):
            visit(child, path | {item_id})

    visit(output_item_id, set())


def create_production_batch(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    branch_id = str(payload.get("branch_id", ""))
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "production.manage", branch_id)
    recipe_id = str(payload.get("recipe_id", ""))
    recipe = session.execute(sa.select(models.recipes).where(
        models.recipes.c.id == recipe_id,
        models.recipes.c.recipe_type == "production",
        models.recipes.c.status == "active",
        sa.or_(models.recipes.c.branch_id == branch_id, models.recipes.c.branch_id.is_(None)),
    )).mappings().first()
    if not recipe:
        raise BusinessError("active_production_recipe_not_found", "Active production recipe was not found")
    planned = _quantity(payload.get("planned_quantity", recipe["yield_quantity"]))
    actual = _quantity(payload.get("actual_quantity", planned))
    actual_waste = _quantity(payload.get("actual_waste_quantity", 0))
    lot_code = str(payload.get("lot_code", "")).strip().upper()
    if not lot_code or planned <= 0 or actual <= 0 or actual_waste < 0:
        raise BusinessError("invalid_production_batch", "Lot and positive planned/actual quantities are required")
    now = _now()
    batch = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": branch_id,
        "warehouse_id": _branch_warehouse_id(session, branch_id), "recipe_id": recipe_id,
        "output_item_id": recipe["output_item_id"], "lot_code": lot_code,
        "planned_quantity": planned, "actual_quantity": actual,
        "actual_waste_quantity": actual_waste, "total_cost": 0, "unit_cost": 0,
        "status": "draft", "idempotency_key": None, "created_by": actor_id,
        "confirmed_by": None, "created_at": now, "confirmed_at": None,
    }
    session.execute(models.production_batches.insert().values(**batch))
    _audit(session, "production_batch.created", "production_batch", batch["id"],
           {"lot_code": lot_code, "recipe_id": recipe_id}, branch_id, actor_user_id=actor_id)
    session.commit()
    return get_production_batch(session, batch["id"])


def confirm_production_batch(
    session: Session,
    batch_id: str,
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Production confirmation requires idempotency key")
    batch = session.execute(sa.select(models.production_batches).where(
        models.production_batches.c.id == batch_id
    )).mappings().first()
    if not batch:
        raise BusinessError("production_batch_not_found", "Production batch was not found")
    require_permission(session, actor_id, "production.manage", batch["branch_id"])
    if batch["status"] == "confirmed":
        if batch["idempotency_key"] == key:
            return get_production_batch(session, batch_id)
        raise BusinessError("production_batch_already_confirmed", "Production batch was already confirmed")
    if batch["status"] != "draft":
        raise BusinessError("production_batch_not_confirmable", "Only draft batch can be confirmed")
    recipe = session.execute(sa.select(models.recipes).where(
        models.recipes.c.id == batch["recipe_id"]
    )).mappings().one()
    components = [dict(row) for row in session.execute(sa.select(models.recipe_components).where(
        models.recipe_components.c.recipe_id == batch["recipe_id"]
    ).order_by(models.recipe_components.c.sort_order)).mappings()]
    scale = _quantity(Decimal(str(batch["planned_quantity"])) / Decimal(str(recipe["yield_quantity"])))
    requirements = []
    total_cost = Decimal("0")
    for component in components:
        required = _quantity(Decimal(str(component["gross_quantity"])) * scale)
        available = _physical_inventory_quantity(
            session, batch["branch_id"], batch["warehouse_id"], component["item_id"]
        )
        if available < required:
            raise BusinessError("insufficient_production_inventory", "Production component inventory is insufficient")
        state = session.execute(sa.select(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == batch["branch_id"],
            models.inventory_cost_states.c.warehouse_id == batch["warehouse_id"],
            models.inventory_cost_states.c.item_id == component["item_id"],
        )).mappings().first()
        unit_cost = _cost(state["average_unit_cost"] if state else 0)
        component_cost = _cost(required * unit_cost)
        total_cost += component_cost
        requirements.append((component, required, available, unit_cost, component_cost, state))
    total_cost = _cost(total_cost)
    unit_cost = _cost(total_cost / Decimal(str(batch["actual_quantity"])))
    now = _now()
    for index, (component, required, available, input_unit_cost, component_cost, state) in enumerate(requirements):
        movement = {
            "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": batch["branch_id"],
            "warehouse_id": batch["warehouse_id"], "item_id": component["item_id"],
            "movement_type": "PRODUCTION_INPUT", "quantity_delta": -required,
            "unit_id": component["unit_id"], "unit_cost": input_unit_cost, "total_cost": -component_cost,
            "effective_at": now, "actor_user_id": actor_id, "document_type": "production_batch",
            "document_id": batch_id, "reference": batch["lot_code"], "reason": "Consumo de lote de produccion",
            "notes": None, "idempotency_key": f"{key}:input:{index}", "status": "confirmed",
            "reversal_of_id": None, "source_type": "production_batch", "source_id": batch_id, "created_at": now,
        }
        session.execute(models.inventory_movements.insert().values(**movement))
        if state:
            session.execute(sa.update(models.inventory_cost_states).where(
                models.inventory_cost_states.c.branch_id == batch["branch_id"],
                models.inventory_cost_states.c.warehouse_id == batch["warehouse_id"],
                models.inventory_cost_states.c.item_id == component["item_id"],
            ).values(quantity_on_hand=_quantity(available - required), updated_at=now))
        else:
            session.execute(models.inventory_cost_states.insert().values(
                branch_id=batch["branch_id"], warehouse_id=batch["warehouse_id"],
                item_id=component["item_id"], quantity_on_hand=_quantity(available - required),
                average_unit_cost=input_unit_cost, last_unit_cost=input_unit_cost,
                last_supplier_id=None, last_cost_at=now, updated_at=now,
            ))
    output_before = _physical_inventory_quantity(
        session, batch["branch_id"], batch["warehouse_id"], batch["output_item_id"]
    )
    output_state = session.execute(sa.select(models.inventory_cost_states).where(
        models.inventory_cost_states.c.branch_id == batch["branch_id"],
        models.inventory_cost_states.c.warehouse_id == batch["warehouse_id"],
        models.inventory_cost_states.c.item_id == batch["output_item_id"],
    )).mappings().first()
    output_average = _cost(output_state["average_unit_cost"] if output_state else 0)
    output_quantity = _quantity(batch["actual_quantity"])
    new_output_quantity = _quantity(output_before + output_quantity)
    new_output_average = unit_cost if output_before == 0 else _cost(
        ((output_before * output_average) + total_cost) / new_output_quantity
    )
    session.execute(models.inventory_movements.insert().values(
        id=_id(), organization_id=ORGANIZATION_ID, branch_id=batch["branch_id"],
        warehouse_id=batch["warehouse_id"], item_id=batch["output_item_id"],
        movement_type="PRODUCTION_OUTPUT", quantity_delta=output_quantity,
        unit_id=recipe["yield_unit_id"], unit_cost=unit_cost, total_cost=total_cost,
        effective_at=now, actor_user_id=actor_id, document_type="production_batch",
        document_id=batch_id, reference=batch["lot_code"], reason="Entrada de elaborado producido",
        notes=None, idempotency_key=f"{key}:output", status="confirmed", reversal_of_id=None,
        source_type="production_batch", source_id=batch_id, created_at=now,
    ))
    output_values = {
        "branch_id": batch["branch_id"], "warehouse_id": batch["warehouse_id"],
        "item_id": batch["output_item_id"], "quantity_on_hand": new_output_quantity,
        "average_unit_cost": new_output_average, "last_unit_cost": unit_cost,
        "last_supplier_id": None, "last_cost_at": now, "updated_at": now,
    }
    if output_state:
        session.execute(sa.update(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == batch["branch_id"],
            models.inventory_cost_states.c.warehouse_id == batch["warehouse_id"],
            models.inventory_cost_states.c.item_id == batch["output_item_id"],
        ).values(**output_values))
    else:
        session.execute(models.inventory_cost_states.insert().values(**output_values))
    session.execute(sa.update(models.production_batches).where(
        models.production_batches.c.id == batch_id
    ).values(
        status="confirmed", idempotency_key=key, total_cost=total_cost,
        unit_cost=unit_cost, confirmed_by=actor_id, confirmed_at=now,
    ))
    _audit(session, "production_batch.confirmed", "production_batch", batch_id,
           {"total_cost": str(total_cost), "unit_cost": str(unit_cost)}, batch["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_production_batch(session, batch_id)


def get_production_batch(session: Session, batch_id: str) -> dict[str, Any]:
    batch = session.execute(sa.select(models.production_batches).where(
        models.production_batches.c.id == batch_id
    )).mappings().first()
    if not batch:
        raise BusinessError("production_batch_not_found", "Production batch was not found")
    result = dict(batch)
    result["movements"] = [dict(row) for row in session.execute(sa.select(models.inventory_movements).where(
        models.inventory_movements.c.source_type == "production_batch",
        models.inventory_movements.c.source_id == batch_id,
    ).order_by(models.inventory_movements.c.created_at)).mappings()]
    return result


def list_production_batches(session: Session, branch_id: str) -> list[dict[str, Any]]:
    ids = session.execute(sa.select(models.production_batches.c.id).where(
        models.production_batches.c.branch_id == branch_id
    ).order_by(models.production_batches.c.created_at.desc())).scalars()
    return [get_production_batch(session, batch_id) for batch_id in ids]



def normalize_mexican_phone(value: str) -> str:
    digits = "".join(character for character in value if character.isdigit())
    if len(digits) == 10:
        return f"+52{digits}"
    if len(digits) == 12 and digits.startswith("52"):
        return f"+{digits}"
    raise BusinessError("invalid_phone", "Mexican phone must contain 10 digits")


def create_customer(
    session: Session,
    name: str,
    email: str | None,
    phones: list[dict[str, Any]],
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "orders.create", branch_id)
    normalized_name = name.strip()
    if not normalized_name:
        raise BusinessError("invalid_customer_name", "Customer name is required")
    now = _now()
    customer = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "name": normalized_name,
        "email": email.strip().lower() if email and email.strip() else None,
        "customer_type": "person",
        "customer_segment": None,
        "notes": None,
        "status": "active",
        "origin_branch_id": branch_id,
        "created_at": now,
        "updated_at": now,
    }
    phone_rows = []
    for index, phone in enumerate(phones):
        captured = str(phone.get("number", "")).strip()
        phone_rows.append({
            "id": _id(),
            "customer_id": customer["id"],
            "captured_number": captured,
            "normalized_number": normalize_mexican_phone(captured),
            "phone_type": str(phone.get("type", "mobile")),
            "is_primary": bool(phone.get("is_primary", index == 0)),
            "whatsapp_enabled": bool(phone.get("whatsapp_enabled", False)),
            "is_verified": False,
            "status": "active",
            "created_at": now,
            "updated_at": now,
        })
    if sum(1 for phone in phone_rows if phone["is_primary"]) > 1:
        raise BusinessError("multiple_primary_phones", "Only one phone can be primary")
    session.execute(models.customers.insert().values(**customer))
    if phone_rows:
        session.execute(models.customer_phones.insert(), phone_rows)
    _audit(
        session,
        action="customer.created",
        entity_type="customer",
        entity_id=customer["id"],
        payload={"name": normalized_name, "phone_count": len(phone_rows)},
        branch_id=branch_id,
        actor_user_id=actor_id,
    )
    session.commit()
    return {**customer, "phones": phone_rows, "addresses": []}


def add_customer_address(
    session: Session,
    customer_id: str,
    payload: dict[str, Any],
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "orders.create", branch_id)
    customer = session.execute(sa.select(models.customers.c.id).where(
        models.customers.c.id == customer_id,
        models.customers.c.organization_id == ORGANIZATION_ID,
        models.customers.c.status == "active",
        sa.or_(
            models.customers.c.origin_branch_id.is_(None),
            models.customers.c.origin_branch_id == branch_id,
        ),
    )).scalar_one_or_none()
    if not customer:
        raise BusinessError("customer_not_found", "Active customer was not found")
    required = ["alias", "street", "exterior_number", "neighborhood", "postal_code", "city", "municipality", "state"]
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise BusinessError("invalid_customer_address", "Address required fields are missing")
    now = _now()
    is_default = bool(payload.get("is_default", False))
    if is_default:
        session.execute(sa.update(models.customer_addresses).where(
            models.customer_addresses.c.customer_id == customer_id,
            models.customer_addresses.c.is_default.is_(True),
        ).values(is_default=False, updated_at=now))
    address = {
        "id": _id(), "customer_id": customer_id,
        "alias": str(payload["alias"]).strip(), "street": str(payload["street"]).strip(),
        "exterior_number": str(payload["exterior_number"]).strip(),
        "interior_number": str(payload.get("interior_number", "")).strip() or None,
        "neighborhood": str(payload["neighborhood"]).strip(), "postal_code": str(payload["postal_code"]).strip(),
        "city": str(payload["city"]).strip(), "municipality": str(payload["municipality"]).strip(),
        "state": str(payload["state"]).strip(), "country": str(payload.get("country", "MX")).upper(),
        "cross_streets": str(payload.get("cross_streets", "")).strip() or None,
        "references": str(payload.get("references", "")).strip() or None,
        "delivery_instructions": str(payload.get("delivery_instructions", "")).strip() or None,
        "latitude": payload.get("latitude"), "longitude": payload.get("longitude"),
        "delivery_zone_id": payload.get("delivery_zone_id"), "is_default": is_default,
        "status": "active", "last_used_at": None, "created_at": now, "updated_at": now,
    }
    session.execute(models.customer_addresses.insert().values(**address))
    _audit(session, "customer.address_added", "customer_address", address["id"],
           {"customer_id": customer_id, "alias": address["alias"]}, branch_id, actor_user_id=actor_id)
    session.commit()
    return address


def update_customer(
    session: Session,
    customer_id: str,
    payload: dict[str, Any],
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "orders.create", branch_id)
    current = session.execute(sa.select(models.customers).where(
        models.customers.c.id == customer_id,
        models.customers.c.organization_id == ORGANIZATION_ID,
    )).mappings().first()
    if not current:
        raise BusinessError("customer_not_found", "Customer was not found")
    updates: dict[str, Any] = {"updated_at": _now()}
    if "name" in payload:
        name = str(payload["name"]).strip()
        if not name:
            raise BusinessError("invalid_customer_name", "Customer name is required")
        updates["name"] = name
    if "email" in payload:
        email = str(payload.get("email") or "").strip().lower()
        updates["email"] = email or None
    if "customer_type" in payload:
        customer_type = str(payload["customer_type"]).lower()
        if customer_type not in {"person", "company"}:
            raise BusinessError("invalid_customer_type", "Customer type must be person or company")
        updates["customer_type"] = customer_type
    for field in ("customer_segment", "notes", "status"):
        if field in payload:
            updates[field] = payload[field]
    session.execute(sa.update(models.customers).where(models.customers.c.id == customer_id).values(**updates))
    _audit(session, "customer.updated", "customer", customer_id, updates, branch_id, actor_user_id=actor_id)
    session.commit()
    return {**dict(current), **updates}


def update_customer_address(
    session: Session,
    customer_id: str,
    address_id: str,
    payload: dict[str, Any],
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "orders.create", branch_id)
    current = session.execute(sa.select(models.customer_addresses).where(
        models.customer_addresses.c.id == address_id,
        models.customer_addresses.c.customer_id == customer_id,
    )).mappings().first()
    if not current:
        raise BusinessError("customer_address_not_found", "Customer address was not found")
    allowed = {
        "alias", "street", "exterior_number", "interior_number", "neighborhood", "postal_code",
        "city", "municipality", "state", "country", "cross_streets", "references",
        "delivery_instructions", "latitude", "longitude", "delivery_zone_id", "is_default", "status",
    }
    updates = {field: payload[field] for field in allowed if field in payload}
    for field in ("alias", "street", "exterior_number", "neighborhood", "postal_code", "city", "municipality", "state"):
        value = updates.get(field, current[field])
        if not str(value or "").strip():
            raise BusinessError("invalid_customer_address", "Address required fields are missing")
    now = _now()
    updates["updated_at"] = now
    if bool(updates.get("is_default", False)):
        session.execute(sa.update(models.customer_addresses).where(
            models.customer_addresses.c.customer_id == customer_id,
            models.customer_addresses.c.id != address_id,
            models.customer_addresses.c.is_default.is_(True),
        ).values(is_default=False, updated_at=now))
    session.execute(sa.update(models.customer_addresses).where(
        models.customer_addresses.c.id == address_id
    ).values(**updates))
    _audit(session, "customer.address_updated", "customer_address", address_id,
           {"customer_id": customer_id, "changes": updates}, branch_id, actor_user_id=actor_id)
    session.commit()
    return {**dict(current), **updates}


def upsert_customer_tax_profile(
    session: Session,
    customer_id: str,
    payload: dict[str, Any],
    branch_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "orders.create", branch_id)
    customer = session.execute(sa.select(models.customers.c.id).where(
        models.customers.c.id == customer_id,
        models.customers.c.organization_id == ORGANIZATION_ID,
    )).scalar_one_or_none()
    if not customer:
        raise BusinessError("customer_not_found", "Customer was not found")
    required = ("legal_name", "tax_id", "tax_regime", "fiscal_postal_code")
    if any(not str(payload.get(field, "")).strip() for field in required):
        raise BusinessError("invalid_tax_profile", "Fiscal name, RFC, regime and postal code are required")
    tax_id = str(payload["tax_id"]).strip().upper()
    if len(tax_id) not in {12, 13}:
        raise BusinessError("invalid_tax_id", "RFC must contain 12 or 13 characters")
    profile = {
        "customer_id": customer_id,
        "legal_name": str(payload["legal_name"]).strip(),
        "tax_id": tax_id,
        "tax_regime": str(payload["tax_regime"]).strip(),
        "fiscal_postal_code": str(payload["fiscal_postal_code"]).strip(),
        "cfdi_use": str(payload.get("cfdi_use", "")).strip() or None,
        "billing_email": str(payload.get("billing_email", "")).strip().lower() or None,
        "updated_at": _now(),
    }
    existing = session.execute(sa.select(models.customer_tax_profiles.c.customer_id).where(
        models.customer_tax_profiles.c.customer_id == customer_id
    )).scalar_one_or_none()
    if existing:
        session.execute(sa.update(models.customer_tax_profiles).where(
            models.customer_tax_profiles.c.customer_id == customer_id
        ).values(**profile))
    else:
        session.execute(models.customer_tax_profiles.insert().values(**profile))
    _audit(session, "customer.tax_profile_upserted", "customer", customer_id,
           {"tax_id": tax_id}, branch_id, actor_user_id=actor_id)
    session.commit()
    return profile


def list_customers(
    session: Session, phone: str | None = None, branch_id: str | None = None
) -> list[dict[str, Any]]:
    query = sa.select(models.customers).where(models.customers.c.organization_id == ORGANIZATION_ID)
    if branch_id:
        query = query.where(
            sa.or_(
                models.customers.c.origin_branch_id.is_(None),
                models.customers.c.origin_branch_id == branch_id,
            )
        )
    if phone:
        normalized = normalize_mexican_phone(phone)
        query = query.where(models.customers.c.id.in_(
            sa.select(models.customer_phones.c.customer_id).where(
                models.customer_phones.c.normalized_number == normalized,
                models.customer_phones.c.status == "active",
            )
        ))
    rows = session.execute(
        query.order_by(models.customers.c.name)
    ).mappings()
    result = []
    for row in rows:
        customer = dict(row)
        customer["phones"] = [dict(item) for item in session.execute(
            sa.select(models.customer_phones).where(models.customer_phones.c.customer_id == row["id"]).order_by(
                models.customer_phones.c.is_primary.desc(), models.customer_phones.c.created_at
            )
        ).mappings()]
        customer["addresses"] = [dict(item) for item in session.execute(
            sa.select(models.customer_addresses).where(
                models.customer_addresses.c.customer_id == row["id"],
                models.customer_addresses.c.status == "active",
            ).order_by(
                models.customer_addresses.c.is_default.desc(), models.customer_addresses.c.created_at
            )
        ).mappings()]
        tax_profile = session.execute(sa.select(models.customer_tax_profiles).where(
            models.customer_tax_profiles.c.customer_id == row["id"]
        )).mappings().first()
        customer["tax_profile"] = dict(tax_profile) if tax_profile else None
        customer["order_summary"] = get_customer_order_summary(session, str(row["id"]))
        result.append(customer)
    return result


def list_customers_page(
    session: Session,
    branch_id: str | None,
    query_text: str | None = None,
    phone: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    bounded_limit = min(max(limit, 1), 100)
    bounded_offset = max(offset, 0)
    criteria = [models.customers.c.organization_id == ORGANIZATION_ID]
    if branch_id:
        criteria.append(
            sa.or_(
                models.customers.c.origin_branch_id.is_(None),
                models.customers.c.origin_branch_id == branch_id,
            )
        )
    normalized_query = str(query_text or "").strip()
    if normalized_query:
        pattern = f"%{normalized_query}%"
        # Search by name, email, or phone (captured or normalized).
        phone_match_ids = sa.select(models.customer_phones.c.customer_id).where(
            sa.or_(
                models.customer_phones.c.captured_number.ilike(pattern),
                models.customer_phones.c.normalized_number.ilike(pattern),
            ),
            models.customer_phones.c.status == "active",
        )
        criteria.append(
            sa.or_(
                models.customers.c.name.ilike(pattern),
                models.customers.c.email.ilike(pattern),
                models.customers.c.id.in_(phone_match_ids),
            )
        )
    if phone:
        normalized_phone = normalize_mexican_phone(phone)
        criteria.append(
            models.customers.c.id.in_(
                sa.select(models.customer_phones.c.customer_id).where(
                    models.customer_phones.c.normalized_number == normalized_phone,
                    models.customer_phones.c.status == "active",
                )
            )
        )

    total = int(
        session.execute(sa.select(sa.func.count(models.customers.c.id)).where(*criteria)).scalar_one()
    )
    customer_rows = list(
        session.execute(
            sa.select(models.customers)
            .where(*criteria)
            .order_by(models.customers.c.name, models.customers.c.id)
            .limit(bounded_limit)
            .offset(bounded_offset)
        ).mappings()
    )
    customer_ids = [str(row["id"]) for row in customer_rows]
    if not customer_ids:
        return {"items": [], "total": total, "limit": bounded_limit, "offset": bounded_offset}

    phones_by_customer: dict[str, list[dict[str, Any]]] = {item: [] for item in customer_ids}
    for row in session.execute(
        sa.select(models.customer_phones)
        .where(models.customer_phones.c.customer_id.in_(customer_ids))
        .order_by(models.customer_phones.c.is_primary.desc(), models.customer_phones.c.created_at)
    ).mappings():
        phones_by_customer[str(row["customer_id"])].append(dict(row))

    addresses_by_customer: dict[str, list[dict[str, Any]]] = {item: [] for item in customer_ids}
    for row in session.execute(
        sa.select(models.customer_addresses)
        .where(
            models.customer_addresses.c.customer_id.in_(customer_ids),
            models.customer_addresses.c.status == "active",
        )
        .order_by(models.customer_addresses.c.is_default.desc(), models.customer_addresses.c.created_at)
    ).mappings():
        addresses_by_customer[str(row["customer_id"])].append(dict(row))

    tax_by_customer = {
        str(row["customer_id"]): dict(row)
        for row in session.execute(
            sa.select(models.customer_tax_profiles).where(
                models.customer_tax_profiles.c.customer_id.in_(customer_ids)
            )
        ).mappings()
    }
    summaries = {
        str(row["customer_id"]): {
            "order_count": int(row["order_count"] or 0),
            "last_order_at": row["last_order_at"],
            "average_ticket_cents": (
                int(row["total_cents"] or 0) // int(row["order_count"])
                if row["order_count"]
                else 0
            ),
            "frequent_products": [],
            "recent_orders": [],
        }
        for row in session.execute(
            sa.select(
                models.orders.c.customer_id,
                sa.func.count(models.orders.c.id).label("order_count"),
                sa.func.max(models.orders.c.created_at).label("last_order_at"),
                sa.func.coalesce(sa.func.sum(models.orders.c.total_cents), 0).label("total_cents"),
            )
            .where(
                models.orders.c.customer_id.in_(customer_ids),
                models.orders.c.status != "CANCELLED",
            )
            .group_by(models.orders.c.customer_id)
        ).mappings()
    }
    # Legacy address reference: recover the raw text from import records for
    # imported customers, without exposing raw_payload or cross-branch data.
    legacy_by_customer: dict[str, str | None] = {cid: None for cid in customer_ids}
    legacy_criteria = [
        models.legacy_import_records.c.target_entity_id.in_(customer_ids),
        models.legacy_import_records.c.entity_type == "customer",
        models.legacy_import_records.c.target_entity_type == "customer",
    ]
    if branch_id:
        legacy_criteria.append(models.legacy_import_batches.c.branch_id == branch_id)
    legacy_rows = session.execute(
        sa.select(
            models.legacy_import_records.c.target_entity_id,
            models.legacy_import_records.c.normalized_payload,
        )
        .select_from(
            models.legacy_import_records.join(
                models.legacy_import_batches,
                models.legacy_import_records.c.batch_id == models.legacy_import_batches.c.id,
            )
        )
        .where(*legacy_criteria)
    ).mappings()
    for row in legacy_rows:
        cid = str(row["target_entity_id"])
        if cid in legacy_by_customer:
            payload = row["normalized_payload"]
            reference = payload.get("legacy_address") if isinstance(payload, dict) else None
            legacy_by_customer[cid] = str(reference) if reference else None

    items = []
    for row in customer_rows:
        customer = dict(row)
        customer_id = str(row["id"])
        customer["phones"] = phones_by_customer[customer_id]
        customer["addresses"] = addresses_by_customer[customer_id]
        customer["legacy_address_reference"] = legacy_by_customer.get(customer_id)
        customer["tax_profile"] = tax_by_customer.get(customer_id)
        customer["order_summary"] = summaries.get(
            customer_id,
            {
                "order_count": 0,
                "last_order_at": None,
                "average_ticket_cents": 0,
                "frequent_products": [],
                "recent_orders": [],
            },
        )
        items.append(customer)
    return {"items": items, "total": total, "limit": bounded_limit, "offset": bounded_offset}


def get_customer_order_summary(session: Session, customer_id: str) -> dict[str, Any]:
    aggregate = session.execute(
        sa.select(
            sa.func.count(models.orders.c.id).label("order_count"),
            sa.func.max(models.orders.c.created_at).label("last_order_at"),
            sa.func.coalesce(sa.func.sum(models.orders.c.total_cents), 0).label("total_cents"),
        ).where(
            models.orders.c.customer_id == customer_id,
            models.orders.c.status != "CANCELLED",
        )
    ).mappings().one()
    order_count = int(aggregate["order_count"] or 0)
    frequent = session.execute(
        sa.select(
            models.order_lines.c.product_id,
            models.order_lines.c.product_name,
            sa.func.sum(models.order_lines.c.quantity).label("quantity"),
        )
        .select_from(models.order_lines.join(models.orders, models.order_lines.c.order_id == models.orders.c.id))
        .where(models.orders.c.customer_id == customer_id, models.orders.c.status != "CANCELLED")
        .group_by(models.order_lines.c.product_id, models.order_lines.c.product_name)
        .order_by(sa.func.sum(models.order_lines.c.quantity).desc())
        .limit(5)
    ).mappings()
    recent = session.execute(
        sa.select(
            models.orders.c.id, models.orders.c.folio, models.orders.c.order_type,
            models.orders.c.status, models.orders.c.total_cents, models.orders.c.created_at,
        ).where(models.orders.c.customer_id == customer_id)
        .order_by(models.orders.c.created_at.desc()).limit(5)
    ).mappings()
    return {
        "order_count": order_count,
        "last_order_at": aggregate["last_order_at"],
        "average_ticket_cents": int(aggregate["total_cents"] or 0) // order_count if order_count else 0,
        "frequent_products": [dict(row) for row in frequent],
        "recent_orders": [dict(row) for row in recent],
    }


def repeat_order(
    session: Session,
    order_id: str,
    register_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    original = session.execute(sa.select(models.orders).where(models.orders.c.id == order_id)).mappings().first()
    if not original:
        raise BusinessError("order_not_found", "Order was not found")
    lines = [dict(row) for row in session.execute(sa.select(
        models.order_lines.c.product_id, models.order_lines.c.quantity
    ).where(models.order_lines.c.order_id == order_id)).mappings()]
    address_snapshot = original["delivery_address_snapshot"] or {}
    delivery_address_id = address_snapshot.get("id") if isinstance(address_snapshot, dict) else None
    return create_local_order(
        session,
        lines,
        original["owner_name"],
        original["order_type"],
        original["branch_id"],
        register_id,
        actor_user_id,
        original["customer_id"],
        delivery_address_id,
    )


def create_supplier(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    code = str(payload.get("code", "")).strip().upper()
    commercial_name = str(payload.get("commercial_name", "")).strip()
    if not code or not commercial_name:
        raise BusinessError("invalid_supplier", "Supplier code and commercial name are required")
    tax_id = str(payload.get("tax_id", "")).strip().upper() or None
    duplicate = session.execute(sa.select(models.suppliers.c.id).where(
        models.suppliers.c.organization_id == ORGANIZATION_ID,
        sa.or_(models.suppliers.c.code == code, sa.and_(tax_id is not None, models.suppliers.c.tax_id == tax_id)),
    )).scalar_one_or_none()
    if duplicate:
        raise BusinessError("supplier_already_exists", "Supplier code or RFC already exists")
    now = _now()
    supplier = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "code": code,
        "commercial_name": commercial_name, "legal_name": payload.get("legal_name"), "tax_id": tax_id,
        "tax_regime": payload.get("tax_regime"), "fiscal_address": payload.get("fiscal_address"),
        "fiscal_postal_code": payload.get("fiscal_postal_code"), "municipality": payload.get("municipality"),
        "state": payload.get("state"), "country": str(payload.get("country", "MX")).upper(),
        "billing_email": str(payload.get("billing_email", "")).strip().lower() or None,
        "credit_days": int(payload.get("credit_days", 0)), "credit_limit": payload.get("credit_limit"),
        "currency": str(payload.get("currency", "MXN")).upper(), "minimum_amount": payload.get("minimum_amount"),
        "usual_lead_time_days": payload.get("usual_lead_time_days"),
        "delivery_days": list(payload.get("delivery_days", [])), "payment_methods": list(payload.get("payment_methods", [])),
        "accounting_reference": payload.get("accounting_reference"), "notes": payload.get("notes"),
        "status": "active", "created_at": now, "updated_at": now,
    }
    session.execute(models.suppliers.insert().values(**supplier))
    _audit(session, "supplier.created", "supplier", supplier["id"],
           {"code": code, "commercial_name": commercial_name}, branch_id=None, actor_user_id=actor_id)
    session.commit()
    return supplier


def add_supplier_contact(
    session: Session,
    supplier_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    supplier = session.execute(sa.select(models.suppliers.c.id).where(
        models.suppliers.c.id == supplier_id, models.suppliers.c.organization_id == ORGANIZATION_ID
    )).scalar_one_or_none()
    if not supplier:
        raise BusinessError("supplier_not_found", "Supplier was not found")
    name = str(payload.get("name", "")).strip()
    contact_type = str(payload.get("contact_type", "orders")).lower()
    if not name or contact_type not in {"orders", "billing", "collection", "general"}:
        raise BusinessError("invalid_supplier_contact", "Contact name and valid type are required")
    now = _now()
    contact = {
        "id": _id(), "supplier_id": supplier_id, "name": name,
        "position_area": payload.get("position_area"), "phone": payload.get("phone"),
        "whatsapp": payload.get("whatsapp"), "email": payload.get("email"), "contact_type": contact_type,
        "schedule": payload.get("schedule"), "primary_for_orders": bool(payload.get("primary_for_orders", False)),
        "primary_for_billing": bool(payload.get("primary_for_billing", False)),
        "primary_for_collection": bool(payload.get("primary_for_collection", False)),
        "notes": payload.get("notes"), "status": "active", "created_at": now, "updated_at": now,
    }
    for flag in ("primary_for_orders", "primary_for_billing", "primary_for_collection"):
        if contact[flag]:
            session.execute(sa.update(models.supplier_contacts).where(
                models.supplier_contacts.c.supplier_id == supplier_id,
                getattr(models.supplier_contacts.c, flag).is_(True),
            ).values(**{flag: False, "updated_at": now}))
    session.execute(models.supplier_contacts.insert().values(**contact))
    _audit(session, "supplier.contact_added", "supplier_contact", contact["id"],
           {"supplier_id": supplier_id, "contact_type": contact_type}, branch_id=None, actor_user_id=actor_id)
    session.commit()
    return contact


def set_supplier_branch_terms(
    session: Session,
    supplier_id: str,
    branch_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    supplier = session.execute(sa.select(models.suppliers.c.id).where(models.suppliers.c.id == supplier_id)).scalar_one_or_none()
    branch = session.execute(sa.select(models.branches.c.id).where(
        models.branches.c.id == branch_id, models.branches.c.organization_id == ORGANIZATION_ID
    )).scalar_one_or_none()
    if not supplier or not branch:
        raise BusinessError("supplier_or_branch_not_found", "Supplier and branch are required")
    terms = {
        "supplier_id": supplier_id, "branch_id": branch_id,
        "is_enabled": bool(payload.get("is_enabled", True)), "lead_time_days": payload.get("lead_time_days"),
        "minimum_amount": payload.get("minimum_amount"), "notes": payload.get("notes"), "updated_at": _now(),
    }
    existing = session.execute(sa.select(models.supplier_branch_terms.c.supplier_id).where(
        models.supplier_branch_terms.c.supplier_id == supplier_id,
        models.supplier_branch_terms.c.branch_id == branch_id,
    )).scalar_one_or_none()
    if existing:
        session.execute(sa.update(models.supplier_branch_terms).where(
            models.supplier_branch_terms.c.supplier_id == supplier_id,
            models.supplier_branch_terms.c.branch_id == branch_id,
        ).values(**terms))
    else:
        session.execute(models.supplier_branch_terms.insert().values(**terms))
    _audit(session, "supplier.branch_terms_set", "supplier", supplier_id,
           {"branch_id": branch_id, "is_enabled": terms["is_enabled"]}, branch_id, actor_user_id=actor_id)
    session.commit()
    return terms


def create_purchase_presentation(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    supplier_id = str(payload.get("supplier_id", ""))
    item_id = str(payload.get("item_id", ""))
    base_unit_id = str(payload.get("base_unit_id", ""))
    item = session.execute(sa.select(models.inventory_items).where(
        models.inventory_items.c.id == item_id, models.inventory_items.c.organization_id == ORGANIZATION_ID
    )).mappings().first()
    supplier = session.execute(sa.select(models.suppliers.c.id).where(
        models.suppliers.c.id == supplier_id, models.suppliers.c.status == "active"
    )).scalar_one_or_none()
    commercial_unit = session.execute(sa.select(models.inventory_units.c.id).where(
        models.inventory_units.c.id == str(payload.get("commercial_unit_id", ""))
    )).scalar_one_or_none()
    if not item or not supplier or not commercial_unit:
        raise BusinessError("presentation_reference_not_found", "Supplier, item and commercial unit are required")
    if base_unit_id != item["base_unit_id"]:
        raise BusinessError("invalid_base_unit", "Presentation base unit must match inventory item base unit")
    code = str(payload.get("code", "")).strip().upper()
    name = str(payload.get("name", "")).strip()
    usable = Decimal(str(payload.get("usable_content", "0")))
    base_yield = Decimal(str(payload.get("base_unit_yield", usable)))
    net_price = Decimal(str(payload.get("last_net_price", "0")))
    yield_percent = Decimal(str(payload.get("yield_percent", "1")))
    if not code or not name or usable <= 0 or base_yield <= 0 or net_price < 0:
        raise BusinessError("invalid_purchase_presentation", "Code, name, positive yield and nonnegative price are required")
    if yield_percent <= 0 or yield_percent > 1:
        raise BusinessError("invalid_yield_percent", "Yield percent must be greater than zero and at most one")
    cost_per_base = (net_price / usable).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    now = _now()
    presentation = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "supplier_id": supplier_id, "item_id": item_id,
        "code": code, "name": name, "package_type": str(payload.get("package_type", "package")),
        "commercial_quantity": Decimal(str(payload.get("commercial_quantity", "1"))),
        "commercial_unit_id": str(payload["commercial_unit_id"]), "base_unit_id": base_unit_id,
        "base_unit_yield": base_yield, "gross_content": payload.get("gross_content"),
        "net_content": payload.get("net_content"), "usable_content": usable, "yield_percent": yield_percent,
        "barcode": payload.get("barcode"), "tax_rate": Decimal(str(payload.get("tax_rate", "0"))),
        "last_net_price": net_price, "cost_per_base_unit": cost_per_base,
        "is_preferred": bool(payload.get("is_preferred", False)), "status": "active", "created_at": now, "updated_at": now,
    }
    session.execute(models.purchase_presentations.insert().values(**presentation))
    _record_supplier_price(session, presentation, actor_id, now)
    _audit(session, "purchase_presentation.created", "purchase_presentation", presentation["id"],
           {"code": code, "supplier_id": supplier_id, "item_id": item_id}, branch_id=None, actor_user_id=actor_id)
    session.commit()
    return presentation


def update_purchase_presentation_price(
    session: Session,
    presentation_id: str,
    net_price_value: Any,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    current = session.execute(sa.select(models.purchase_presentations).where(
        models.purchase_presentations.c.id == presentation_id
    )).mappings().first()
    if not current:
        raise BusinessError("purchase_presentation_not_found", "Purchase presentation was not found")
    net_price = Decimal(str(net_price_value))
    if net_price < 0:
        raise BusinessError("invalid_presentation_price", "Price cannot be negative")
    cost = (net_price / Decimal(str(current["usable_content"]))).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)
    now = _now()
    updated = {**dict(current), "last_net_price": net_price, "cost_per_base_unit": cost, "updated_at": now}
    session.execute(sa.update(models.purchase_presentations).where(
        models.purchase_presentations.c.id == presentation_id
    ).values(last_net_price=net_price, cost_per_base_unit=cost, updated_at=now))
    _record_supplier_price(session, updated, actor_id, now)
    _audit(session, "purchase_presentation.price_recorded", "purchase_presentation", presentation_id,
           {"net_price": str(net_price), "cost_per_base_unit": str(cost)}, branch_id=None, actor_user_id=actor_id)
    session.commit()
    return updated


def _record_supplier_price(session: Session, presentation: dict[str, Any], actor_id: str, now: datetime) -> None:
    session.execute(models.supplier_price_history.insert().values(
        id=_id(), presentation_id=presentation["id"], supplier_id=presentation["supplier_id"],
        net_price=presentation["last_net_price"], cost_per_base_unit=presentation["cost_per_base_unit"],
        currency="MXN", effective_at=now, recorded_by=actor_id, created_at=now,
    ))


def list_suppliers(session: Session) -> list[dict[str, Any]]:
    result = []
    rows = session.execute(sa.select(models.suppliers).where(
        models.suppliers.c.organization_id == ORGANIZATION_ID
    ).order_by(models.suppliers.c.commercial_name)).mappings()
    for row in rows:
        supplier = dict(row)
        supplier["contacts"] = [dict(item) for item in session.execute(sa.select(models.supplier_contacts).where(
            models.supplier_contacts.c.supplier_id == row["id"]
        )).mappings()]
        supplier["branch_terms"] = [dict(item) for item in session.execute(sa.select(models.supplier_branch_terms).where(
            models.supplier_branch_terms.c.supplier_id == row["id"]
        )).mappings()]
        result.append(supplier)
    return result


def list_purchase_presentations(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(sa.select(
        models.purchase_presentations,
        models.suppliers.c.commercial_name.label("supplier_name"),
        models.inventory_items.c.name.label("item_name"),
        models.inventory_units.c.code.label("base_unit_code"),
    ).select_from(
        models.purchase_presentations
        .join(models.suppliers, models.purchase_presentations.c.supplier_id == models.suppliers.c.id)
        .join(models.inventory_items, models.purchase_presentations.c.item_id == models.inventory_items.c.id)
        .join(models.inventory_units, models.purchase_presentations.c.base_unit_id == models.inventory_units.c.id)
    ).order_by(models.purchase_presentations.c.name)).mappings()
    result = []
    for row in rows:
        presentation = dict(row)
        presentation["price_history"] = [dict(item) for item in session.execute(
            sa.select(models.supplier_price_history).where(
                models.supplier_price_history.c.presentation_id == row["id"]
            ).order_by(models.supplier_price_history.c.effective_at)
        ).mappings()]
        result.append(presentation)
    return result


def create_purchase_document(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    branch_id = str(payload.get("branch_id", ""))
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "purchases.manage", branch_id)
    supplier_id = str(payload.get("supplier_id", ""))
    supplier = session.execute(sa.select(models.suppliers).where(
        models.suppliers.c.id == supplier_id,
        models.suppliers.c.organization_id == ORGANIZATION_ID,
        models.suppliers.c.status == "active",
    )).mappings().first()
    branch = session.execute(sa.select(models.branches.c.id).where(
        models.branches.c.id == branch_id,
        models.branches.c.organization_id == ORGANIZATION_ID,
        models.branches.c.status == "active",
    )).scalar_one_or_none()
    if not supplier or not branch:
        raise BusinessError("purchase_supplier_or_branch_not_found", "Active supplier and branch are required")
    terms = session.execute(sa.select(models.supplier_branch_terms).where(
        models.supplier_branch_terms.c.supplier_id == supplier_id,
        models.supplier_branch_terms.c.branch_id == branch_id,
    )).mappings().first()
    if terms and not terms["is_enabled"]:
        raise BusinessError("supplier_not_enabled_for_branch", "Supplier is disabled for this branch")
    document_type = str(payload.get("document_type", "receipt")).strip().lower()
    if document_type not in {"invoice", "receipt", "ticket", "note"}:
        raise BusinessError("invalid_purchase_document_type", "Purchase document type is invalid")
    folio = str(payload.get("folio", "")).strip()
    if not folio:
        raise BusinessError("purchase_folio_required", "Purchase document folio is required")
    freight = _money(payload.get("freight_total", "0"))
    if freight != 0:
        raise BusinessError("freight_cost_policy_required", "Freight allocation policy is not approved")
    raw_lines = list(payload.get("lines", []))
    if not raw_lines:
        raise BusinessError("purchase_lines_required", "Purchase requires at least one line")
    now = _now()
    document_id = _id()
    lines: list[dict[str, Any]] = []
    subtotal = Decimal("0")
    discount_total = Decimal("0")
    tax_total = Decimal("0")
    for raw in raw_lines:
        presentation = session.execute(sa.select(models.purchase_presentations).where(
            models.purchase_presentations.c.id == str(raw.get("presentation_id", "")),
            models.purchase_presentations.c.supplier_id == supplier_id,
            models.purchase_presentations.c.status == "active",
        )).mappings().first()
        if not presentation:
            raise BusinessError("purchase_presentation_not_found", "Active supplier presentation was not found")
        quantity = _quantity(raw.get("quantity", "0"))
        unit_price = _money(raw.get("unit_price", presentation["last_net_price"]))
        discount = _money(raw.get("discount", "0"))
        tax = _money(raw.get("tax", "0"))
        line_subtotal = _money(quantity * unit_price)
        if quantity <= 0 or unit_price < 0 or discount < 0 or discount > line_subtotal or tax < 0:
            raise BusinessError("invalid_purchase_line", "Purchase line quantities and amounts are invalid")
        base_quantity = _quantity(quantity * Decimal(str(presentation["base_unit_yield"])))
        inventory_cost = _money(line_subtotal - discount)
        cost_per_base = _cost(inventory_cost / base_quantity)
        line = {
            "id": _id(), "purchase_document_id": document_id,
            "presentation_id": presentation["id"], "item_id": presentation["item_id"],
            "presentation_snapshot": _sanitize_for_json(dict(presentation)),
            "presentation_quantity": quantity, "base_quantity": base_quantity,
            "unit_price": unit_price, "discount": discount, "tax": tax,
            "line_total": _money(inventory_cost + tax), "inventory_cost": inventory_cost,
            "cost_per_base_unit": cost_per_base, "created_at": now,
        }
        lines.append(line)
        subtotal += line_subtotal
        discount_total += discount
        tax_total += tax
    total = _money(subtotal - discount_total + tax_total)
    paid_from_cash = bool(payload.get("paid_from_cash", False))
    payment_method = str(payload.get("payment_method", "cash" if paid_from_cash else "other")).lower()
    if paid_from_cash and payment_method != "cash":
        raise BusinessError("cash_purchase_payment_mismatch", "Purchase paid from cash must use cash payment method")
    document_date = _parse_document_date(payload.get("document_date"), now)
    purchase = {
        "id": document_id, "organization_id": ORGANIZATION_ID, "branch_id": branch_id,
        "supplier_id": supplier_id, "document_type": document_type, "folio": folio,
        "document_date": document_date, "subtotal": _money(subtotal),
        "discount_total": _money(discount_total), "tax_total": _money(tax_total),
        "freight_total": freight, "total": total, "payment_method": payment_method,
        "paid_from_cash": paid_from_cash, "cash_movement_id": None,
        "evidence_url": payload.get("evidence_url"), "notes": payload.get("notes"),
        "status": "draft", "created_by": actor_id, "confirmed_by": None, "cancelled_by": None,
        "confirmation_idempotency_key": None, "cancellation_reason": None,
        "created_at": now, "confirmed_at": None, "cancelled_at": None,
    }
    session.execute(models.purchase_documents.insert().values(**purchase))
    session.execute(models.purchase_document_lines.insert(), lines)
    _audit(session, "purchase.created", "purchase_document", document_id,
           {"folio": folio, "supplier_id": supplier_id, "total": str(total)}, branch_id, actor_user_id=actor_id)
    session.commit()
    return {**purchase, "lines": lines}


def confirm_purchase_document(
    session: Session,
    purchase_id: str,
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Confirmation idempotency key is required")
    purchase = session.execute(sa.select(models.purchase_documents).where(
        models.purchase_documents.c.id == purchase_id
    )).mappings().first()
    if not purchase:
        raise BusinessError("purchase_not_found", "Purchase document was not found")
    require_permission(session, actor_id, "purchases.manage", purchase["branch_id"])
    if purchase["status"] == "confirmed":
        if purchase["confirmation_idempotency_key"] == key:
            return get_purchase_document(session, purchase_id)
        raise BusinessError("purchase_already_confirmed", "Purchase was already confirmed")
    if purchase["status"] != "draft":
        raise BusinessError("purchase_not_confirmable", "Only draft purchases can be confirmed")
    duplicate = session.execute(sa.select(models.purchase_documents.c.id).where(
        models.purchase_documents.c.confirmation_idempotency_key == key,
        models.purchase_documents.c.id != purchase_id,
    )).scalar_one_or_none()
    if duplicate:
        raise BusinessError("idempotency_key_conflict", "Idempotency key belongs to another purchase")
    lines = [dict(row) for row in session.execute(sa.select(models.purchase_document_lines).where(
        models.purchase_document_lines.c.purchase_document_id == purchase_id
    )).mappings()]
    warehouse_id = _branch_warehouse_id(session, purchase["branch_id"])
    # Validate every line before producing any externalized effect.
    for line in lines:
        physical = _physical_inventory_quantity(session, purchase["branch_id"], warehouse_id, line["item_id"])
        if physical < 0:
            raise BusinessError(
                "negative_inventory_cost_policy_required",
                "Cannot confirm receipt while physical inventory is negative",
            )
    now = _now()
    cash_movement = None
    if purchase["paid_from_cash"]:
        require_permission(session, actor_id, "cash.withdraw", purchase["branch_id"])
        shift = get_open_cash_shift(session, branch_id=purchase["branch_id"])
        if not shift:
            raise BusinessError("cash_shift_required", "Open cash shift is required for cash purchase")
        amount_cents = int((_money(purchase["total"]) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        cash_movement = {
            "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": purchase["branch_id"],
            "cash_shift_id": shift["id"], "movement_type": "withdrawal", "amount_cents": amount_cents,
            "reason_code": "SUPPLY_PURCHASE", "reason": "Compra de insumos",
            "source_type": "purchase", "source_id": purchase_id, "actor_user_id": actor_id,
            "idempotency_key": f"{key}:cash", "status": "confirmed", "reversal_of_id": None, "created_at": now,
        }
        session.execute(models.cash_movements.insert().values(**cash_movement))
    movements = []
    cost_states = []
    for index, line in enumerate(lines):
        current_quantity = _physical_inventory_quantity(
            session, purchase["branch_id"], warehouse_id, line["item_id"]
        )
        state = session.execute(sa.select(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == purchase["branch_id"],
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == line["item_id"],
        )).mappings().first()
        current_average = _cost(state["average_unit_cost"]) if state else Decimal("0")
        entry_quantity = _quantity(line["base_quantity"])
        entry_cost = _money(line["inventory_cost"])
        new_quantity = _quantity(current_quantity + entry_quantity)
        new_average = _cost(entry_cost / entry_quantity) if current_quantity == 0 else _cost(
            ((current_quantity * current_average) + entry_cost) / new_quantity
        )
        movement = {
            "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": purchase["branch_id"],
            "warehouse_id": warehouse_id, "item_id": line["item_id"], "movement_type": "PURCHASE_RECEIPT",
            "quantity_delta": entry_quantity, "unit_id": line["presentation_snapshot"]["base_unit_id"],
            "unit_cost": line["cost_per_base_unit"], "total_cost": entry_cost, "effective_at": purchase["document_date"],
            "actor_user_id": actor_id, "document_type": purchase["document_type"], "document_id": purchase_id,
            "reference": purchase["folio"], "reason": "Recepcion de compra directa", "notes": purchase["notes"],
            "idempotency_key": f"{key}:inventory:{index}", "status": "confirmed", "reversal_of_id": None,
            "source_type": "purchase", "source_id": purchase_id, "created_at": now,
        }
        session.execute(models.inventory_movements.insert().values(**movement))
        state_values = {
            "branch_id": purchase["branch_id"], "warehouse_id": warehouse_id, "item_id": line["item_id"],
            "quantity_on_hand": new_quantity, "average_unit_cost": new_average,
            "last_unit_cost": line["cost_per_base_unit"], "last_supplier_id": purchase["supplier_id"],
            "last_cost_at": now, "updated_at": now,
        }
        if state:
            session.execute(sa.update(models.inventory_cost_states).where(
                models.inventory_cost_states.c.branch_id == purchase["branch_id"],
                models.inventory_cost_states.c.warehouse_id == warehouse_id,
                models.inventory_cost_states.c.item_id == line["item_id"],
            ).values(**state_values))
        else:
            session.execute(models.inventory_cost_states.insert().values(**state_values))
        session.execute(sa.update(models.purchase_presentations).where(
            models.purchase_presentations.c.id == line["presentation_id"]
        ).values(last_net_price=line["unit_price"], updated_at=now))
        presentation_for_history = {
            "id": line["presentation_id"], "supplier_id": purchase["supplier_id"],
            "last_net_price": line["unit_price"],
            "cost_per_base_unit": _cost(_money(line["unit_price"]) / Decimal(str(line["presentation_snapshot"]["usable_content"]))),
        }
        _record_supplier_price(session, presentation_for_history, actor_id, now)
        movements.append(movement)
        cost_states.append(state_values)
    session.execute(sa.update(models.purchase_documents).where(
        models.purchase_documents.c.id == purchase_id
    ).values(
        status="confirmed", confirmed_by=actor_id, confirmed_at=now,
        cash_movement_id=cash_movement["id"] if cash_movement else None,
        confirmation_idempotency_key=key,
    ))
    _audit(session, "purchase.confirmed", "purchase_document", purchase_id,
           {"movement_ids": [item["id"] for item in movements], "cash_movement_id": cash_movement["id"] if cash_movement else None},
           purchase["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_purchase_document(session, purchase_id)


def cancel_purchase_document(
    session: Session,
    purchase_id: str,
    reason: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    purchase = session.execute(sa.select(models.purchase_documents).where(
        models.purchase_documents.c.id == purchase_id
    )).mappings().first()
    if not purchase:
        raise BusinessError("purchase_not_found", "Purchase document was not found")
    require_permission(session, actor_id, "purchases.manage", purchase["branch_id"])
    normalized_reason = reason.strip()
    if not normalized_reason:
        raise BusinessError("purchase_cancellation_reason_required", "Cancellation reason is required")
    if purchase["status"] == "cancelled":
        return get_purchase_document(session, purchase_id)
    if purchase["status"] == "draft":
        now = _now()
        session.execute(sa.update(models.purchase_documents).where(
            models.purchase_documents.c.id == purchase_id
        ).values(status="cancelled", cancelled_by=actor_id, cancelled_at=now, cancellation_reason=normalized_reason))
        _audit(session, "purchase.cancelled", "purchase_document", purchase_id,
               {"reason": normalized_reason, "draft": True}, purchase["branch_id"], actor_user_id=actor_id)
        session.commit()
        return get_purchase_document(session, purchase_id)
    if purchase["status"] != "confirmed":
        raise BusinessError("purchase_not_cancellable", "Purchase cannot be cancelled")
    receipts = [dict(row) for row in session.execute(sa.select(models.inventory_movements).where(
        models.inventory_movements.c.source_type == "purchase",
        models.inventory_movements.c.source_id == purchase_id,
        models.inventory_movements.c.movement_type == "PURCHASE_RECEIPT",
    )).mappings()]
    warehouse_id = _branch_warehouse_id(session, purchase["branch_id"])
    for receipt in receipts:
        physical = _physical_inventory_quantity(session, purchase["branch_id"], warehouse_id, receipt["item_id"])
        if physical - _quantity(receipt["quantity_delta"]) < 0:
            raise BusinessError("purchase_reversal_insufficient_stock", "Received stock was already consumed or transferred")
    now = _now()
    for index, receipt in enumerate(receipts):
        current_quantity = _physical_inventory_quantity(session, purchase["branch_id"], warehouse_id, receipt["item_id"])
        state = session.execute(sa.select(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == purchase["branch_id"],
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == receipt["item_id"],
        )).mappings().first()
        current_average = _cost(state["average_unit_cost"]) if state else Decimal("0")
        removed_quantity = _quantity(receipt["quantity_delta"])
        new_quantity = _quantity(current_quantity - removed_quantity)
        remaining_value = _money((current_quantity * current_average) - _money(receipt["total_cost"]))
        if remaining_value < 0:
            raise BusinessError("purchase_reversal_cost_conflict", "Purchase reversal would create negative inventory value")
        new_average = Decimal("0") if new_quantity == 0 else _cost(remaining_value / new_quantity)
        reversal = {
            **{key: receipt[key] for key in ("organization_id", "branch_id", "warehouse_id", "item_id", "unit_id")},
            "id": _id(), "movement_type": "PURCHASE_REVERSAL", "quantity_delta": -removed_quantity,
            "unit_cost": receipt["unit_cost"], "total_cost": -_money(receipt["total_cost"]), "effective_at": now,
            "actor_user_id": actor_id, "document_type": purchase["document_type"], "document_id": purchase_id,
            "reference": purchase["folio"], "reason": normalized_reason, "notes": None,
            "idempotency_key": f"purchase-cancel:{purchase_id}:inventory:{index}", "status": "confirmed",
            "reversal_of_id": receipt["id"], "source_type": "purchase_cancellation", "source_id": purchase_id, "created_at": now,
        }
        session.execute(models.inventory_movements.insert().values(**reversal))
        session.execute(sa.update(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == purchase["branch_id"],
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == receipt["item_id"],
        ).values(quantity_on_hand=new_quantity, average_unit_cost=new_average, updated_at=now))
    if purchase["cash_movement_id"]:
        original_cash = session.execute(sa.select(models.cash_movements).where(
            models.cash_movements.c.id == purchase["cash_movement_id"]
        )).mappings().one()
        session.execute(models.cash_movements.insert().values(
            id=_id(), organization_id=ORGANIZATION_ID, branch_id=purchase["branch_id"],
            cash_shift_id=original_cash["cash_shift_id"], movement_type="cash_reversal",
            amount_cents=original_cash["amount_cents"], reason_code="PURCHASE_CANCELLATION",
            reason=normalized_reason, source_type="purchase_cancellation", source_id=purchase_id,
            actor_user_id=actor_id, idempotency_key=f"purchase-cancel:{purchase_id}:cash",
            status="confirmed", reversal_of_id=original_cash["id"], created_at=now,
        ))
    session.execute(sa.update(models.purchase_documents).where(
        models.purchase_documents.c.id == purchase_id
    ).values(status="cancelled", cancelled_by=actor_id, cancelled_at=now, cancellation_reason=normalized_reason))
    _audit(session, "purchase.cancelled", "purchase_document", purchase_id,
           {"reason": normalized_reason, "receipt_count": len(receipts)}, purchase["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_purchase_document(session, purchase_id)


def get_purchase_document(session: Session, purchase_id: str) -> dict[str, Any]:
    purchase = session.execute(sa.select(models.purchase_documents).where(
        models.purchase_documents.c.id == purchase_id
    )).mappings().first()
    if not purchase:
        raise BusinessError("purchase_not_found", "Purchase document was not found")
    result = dict(purchase)
    result["lines"] = [dict(row) for row in session.execute(sa.select(models.purchase_document_lines).where(
        models.purchase_document_lines.c.purchase_document_id == purchase_id
    )).mappings()]
    result["inventory_movements"] = [dict(row) for row in session.execute(sa.select(models.inventory_movements).where(
        sa.or_(
            sa.and_(models.inventory_movements.c.source_type == "purchase", models.inventory_movements.c.source_id == purchase_id),
            sa.and_(models.inventory_movements.c.source_type == "purchase_cancellation", models.inventory_movements.c.source_id == purchase_id),
        )
    ).order_by(models.inventory_movements.c.created_at)).mappings()]
    result["cash_movements"] = [dict(row) for row in session.execute(sa.select(models.cash_movements).where(
        models.cash_movements.c.source_id == purchase_id
    ).order_by(models.cash_movements.c.created_at)).mappings()]
    return result


def list_purchase_documents(session: Session, branch_id: str) -> list[dict[str, Any]]:
    ids = session.execute(sa.select(models.purchase_documents.c.id).where(
        models.purchase_documents.c.branch_id == branch_id
    ).order_by(models.purchase_documents.c.created_at.desc())).scalars()
    return [get_purchase_document(session, purchase_id) for purchase_id in ids]


def list_cash_movements(session: Session, branch_id: str) -> list[dict[str, Any]]:
    rows = session.execute(sa.select(models.cash_movements).where(
        models.cash_movements.c.branch_id == branch_id
    ).order_by(models.cash_movements.c.created_at.desc())).mappings()
    return [dict(row) for row in rows]


def list_inventory_cost_states(session: Session, branch_id: str) -> list[dict[str, Any]]:
    rows = session.execute(sa.select(
        models.inventory_cost_states,
        models.inventory_items.c.name.label("item_name"),
        models.inventory_items.c.sku.label("item_sku"),
        models.inventory_units.c.code.label("unit_code"),
    ).select_from(
        models.inventory_cost_states
        .join(models.inventory_items, models.inventory_cost_states.c.item_id == models.inventory_items.c.id)
        .join(models.inventory_units, models.inventory_items.c.base_unit_id == models.inventory_units.c.id)
    ).where(models.inventory_cost_states.c.branch_id == branch_id)).mappings()
    return [dict(row) for row in rows]


def create_waste_reason(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    code = str(payload.get("code", "")).strip().upper().replace(" ", "_")
    name = str(payload.get("name", "")).strip()
    classification = str(payload.get("classification", "other")).strip().lower()
    if not code or not name or not classification:
        raise BusinessError("invalid_waste_reason", "Waste reason code, name and classification are required")
    now = _now()
    reason = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "code": code, "name": name,
        "classification": classification, "display_order": int(payload.get("display_order", 0)),
        "status": "active", "created_at": now, "updated_at": now,
    }
    session.execute(models.waste_reasons.insert().values(**reason))
    _audit(session, "waste_reason.created", "waste_reason", reason["id"],
           {"code": code, "classification": classification}, branch_id=None, actor_user_id=actor_id)
    session.commit()
    return reason


def update_waste_reason(
    session: Session,
    reason_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "catalog.manage")
    existing = session.execute(sa.select(models.waste_reasons).where(
        models.waste_reasons.c.id == reason_id,
        models.waste_reasons.c.organization_id == ORGANIZATION_ID,
    )).mappings().first()
    if not existing:
        raise BusinessError("waste_reason_not_found", "Waste reason was not found")
    values: dict[str, Any] = {"updated_at": _now()}
    for field in ("name", "classification", "status"):
        if field in payload:
            value = str(payload[field]).strip()
            if not value:
                raise BusinessError("invalid_waste_reason", "Waste reason fields cannot be empty")
            values[field] = value.lower() if field in {"classification", "status"} else value
    if "display_order" in payload:
        values["display_order"] = int(payload["display_order"])
    session.execute(sa.update(models.waste_reasons).where(
        models.waste_reasons.c.id == reason_id
    ).values(**values))
    _audit(session, "waste_reason.updated", "waste_reason", reason_id, values,
           branch_id=None, actor_user_id=actor_id)
    session.commit()
    return {**dict(existing), **values}


def list_waste_reasons(session: Session, include_inactive: bool = False) -> list[dict[str, Any]]:
    query = sa.select(models.waste_reasons).where(
        models.waste_reasons.c.organization_id == ORGANIZATION_ID
    )
    if not include_inactive:
        query = query.where(models.waste_reasons.c.status == "active")
    rows = session.execute(query.order_by(
        models.waste_reasons.c.display_order, models.waste_reasons.c.name
    )).mappings()
    return [dict(row) for row in rows]


def create_waste_record(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    branch_id = str(payload.get("branch_id", ""))
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "inventory.waste", branch_id)
    item_id = str(payload.get("item_id", ""))
    item = session.execute(sa.select(models.inventory_items).where(
        models.inventory_items.c.id == item_id,
        models.inventory_items.c.organization_id == ORGANIZATION_ID,
        models.inventory_items.c.status == "active",
    )).mappings().first()
    if not item:
        raise BusinessError("waste_item_not_found", "Waste inventory item was not found")
    unit_id = str(payload.get("unit_id") or item["base_unit_id"])
    if unit_id != item["base_unit_id"]:
        raise BusinessError("waste_unit_mismatch", "Waste unit must match item base unit")
    reason_id = str(payload.get("reason_id", ""))
    reason = session.execute(sa.select(models.waste_reasons).where(
        models.waste_reasons.c.id == reason_id,
        models.waste_reasons.c.organization_id == ORGANIZATION_ID,
        models.waste_reasons.c.status == "active",
    )).mappings().first()
    if not reason:
        raise BusinessError("active_waste_reason_not_found", "Active waste reason was not found")
    quantity = _quantity(payload.get("quantity", 0))
    stage = str(payload.get("stage", "")).strip().lower()
    evidence = payload.get("evidence", [])
    notes = str(payload.get("notes", "")).strip() or None
    if quantity <= 0 or not stage:
        raise BusinessError("invalid_waste_record", "Positive quantity and stage are required")
    if not isinstance(evidence, list) or len(evidence) > 10 or any(
        not isinstance(value, str) or not value.strip() or len(value) > 1000 for value in evidence
    ):
        raise BusinessError("invalid_waste_evidence", "Waste evidence must be a list of at most ten references")
    if notes and len(notes) > 600:
        raise BusinessError("invalid_waste_notes", "Waste notes exceed 600 characters")
    now = _now()
    record = {
        "id": _id(), "organization_id": ORGANIZATION_ID, "branch_id": branch_id,
        "warehouse_id": _branch_warehouse_id(session, branch_id), "item_id": item_id,
        "unit_id": unit_id, "reason_id": reason_id, "stage": stage, "quantity": quantity,
        "unit_cost": 0, "total_cost": 0,
        "effective_at": _parse_document_date(payload.get("effective_at"), now),
        "evidence": [value.strip() for value in evidence], "notes": notes, "status": "draft",
        "created_by": actor_id, "confirmed_by": None, "reversed_by": None,
        "movement_id": None, "reversal_movement_id": None,
        "confirmation_idempotency_key": None, "reversal_idempotency_key": None,
        "reversal_reason": None, "created_at": now, "confirmed_at": None, "reversed_at": None,
    }
    session.execute(models.waste_records.insert().values(**record))
    _audit(session, "waste.created", "waste", record["id"],
           {"item_id": item_id, "quantity": str(quantity), "reason_id": reason_id, "stage": stage},
           branch_id, actor_user_id=actor_id)
    session.commit()
    return get_waste_record(session, record["id"])


def confirm_waste_record(
    session: Session,
    waste_id: str,
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Waste confirmation requires idempotency key")
    record = session.execute(sa.select(models.waste_records).where(
        models.waste_records.c.id == waste_id
    )).mappings().first()
    if not record:
        raise BusinessError("waste_not_found", "Waste record was not found")
    require_permission(session, actor_id, "inventory.waste", record["branch_id"])
    if record["status"] in {"confirmed", "reversed"}:
        if record["confirmation_idempotency_key"] == key:
            return get_waste_record(session, waste_id)
        raise BusinessError("waste_already_confirmed", "Waste record was already confirmed")
    if record["status"] != "draft":
        raise BusinessError("waste_not_confirmable", "Only draft waste can be confirmed")
    quantity = _quantity(record["quantity"])
    available = _physical_inventory_quantity(
        session, record["branch_id"], record["warehouse_id"], record["item_id"]
    )
    if available < quantity:
        raise BusinessError("insufficient_waste_inventory", "Waste quantity exceeds physical inventory")
    state = session.execute(sa.select(models.inventory_cost_states).where(
        models.inventory_cost_states.c.branch_id == record["branch_id"],
        models.inventory_cost_states.c.warehouse_id == record["warehouse_id"],
        models.inventory_cost_states.c.item_id == record["item_id"],
    )).mappings().first()
    unit_cost = _cost(state["average_unit_cost"] if state else 0)
    total_cost = _cost(quantity * unit_cost)
    now = _now()
    movement_id = _id()
    session.execute(models.inventory_movements.insert().values(
        id=movement_id, organization_id=ORGANIZATION_ID, branch_id=record["branch_id"],
        warehouse_id=record["warehouse_id"], item_id=record["item_id"],
        movement_type="WASTE_REAL", quantity_delta=-quantity, unit_id=record["unit_id"],
        unit_cost=unit_cost, total_cost=-total_cost, effective_at=record["effective_at"],
        actor_user_id=actor_id, document_type="waste", document_id=waste_id,
        reference=None, reason=f"Merma real: {record['reason_id']}", notes=record["notes"],
        idempotency_key=key, status="confirmed", reversal_of_id=None,
        source_type="waste", source_id=waste_id, created_at=now,
    ))
    _set_inventory_cost_quantity(
        session, record["branch_id"], record["warehouse_id"], record["item_id"],
        _quantity(available - quantity), unit_cost, now,
    )
    session.execute(sa.update(models.waste_records).where(
        models.waste_records.c.id == waste_id
    ).values(
        status="confirmed", unit_cost=unit_cost, total_cost=total_cost,
        confirmed_by=actor_id, movement_id=movement_id,
        confirmation_idempotency_key=key, confirmed_at=now,
    ))
    _audit(session, "waste.confirmed", "waste", waste_id,
           {"movement_id": movement_id, "quantity": str(quantity), "total_cost": str(total_cost)},
           record["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_waste_record(session, waste_id)


def reverse_waste_record(
    session: Session,
    waste_id: str,
    reason: str,
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    normalized_reason = reason.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Waste reversal requires idempotency key")
    if not normalized_reason:
        raise BusinessError("waste_reversal_reason_required", "Waste reversal reason is required")
    record = session.execute(sa.select(models.waste_records).where(
        models.waste_records.c.id == waste_id
    )).mappings().first()
    if not record:
        raise BusinessError("waste_not_found", "Waste record was not found")
    require_permission(session, actor_id, "inventory.waste", record["branch_id"])
    if record["status"] == "reversed":
        if record["reversal_idempotency_key"] == key:
            return get_waste_record(session, waste_id)
        raise BusinessError("waste_already_reversed", "Waste record was already reversed")
    if record["status"] != "confirmed" or not record["movement_id"]:
        raise BusinessError("waste_not_reversible", "Only confirmed waste can be reversed")
    now = _now()
    quantity = _quantity(record["quantity"])
    unit_cost = _cost(record["unit_cost"])
    total_cost = _cost(record["total_cost"])
    reversal_id = _id()
    session.execute(models.inventory_movements.insert().values(
        id=reversal_id, organization_id=ORGANIZATION_ID, branch_id=record["branch_id"],
        warehouse_id=record["warehouse_id"], item_id=record["item_id"],
        movement_type="WASTE_REVERSAL", quantity_delta=quantity, unit_id=record["unit_id"],
        unit_cost=unit_cost, total_cost=total_cost, effective_at=now,
        actor_user_id=actor_id, document_type="waste", document_id=waste_id,
        reference=record["movement_id"], reason=normalized_reason, notes=None,
        idempotency_key=key, status="confirmed", reversal_of_id=record["movement_id"],
        source_type="waste_reversal", source_id=waste_id, created_at=now,
    ))
    available = _physical_inventory_quantity(
        session, record["branch_id"], record["warehouse_id"], record["item_id"]
    )
    _set_inventory_cost_quantity(
        session, record["branch_id"], record["warehouse_id"], record["item_id"],
        available, unit_cost, now,
    )
    session.execute(sa.update(models.waste_records).where(
        models.waste_records.c.id == waste_id
    ).values(
        status="reversed", reversed_by=actor_id, reversal_movement_id=reversal_id,
        reversal_idempotency_key=key, reversal_reason=normalized_reason, reversed_at=now,
    ))
    _audit(session, "waste.reversed", "waste", waste_id,
           {"movement_id": reversal_id, "reversal_of_id": record["movement_id"], "reason": normalized_reason},
           record["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_waste_record(session, waste_id)


def _set_inventory_cost_quantity(
    session: Session,
    branch_id: str,
    warehouse_id: str,
    item_id: str,
    quantity: Decimal,
    unit_cost: Decimal,
    now: datetime,
) -> None:
    existing = session.execute(sa.select(models.inventory_cost_states).where(
        models.inventory_cost_states.c.branch_id == branch_id,
        models.inventory_cost_states.c.warehouse_id == warehouse_id,
        models.inventory_cost_states.c.item_id == item_id,
    )).mappings().first()
    if existing:
        session.execute(sa.update(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == branch_id,
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == item_id,
        ).values(quantity_on_hand=quantity, updated_at=now))
    else:
        session.execute(models.inventory_cost_states.insert().values(
            branch_id=branch_id, warehouse_id=warehouse_id, item_id=item_id,
            quantity_on_hand=quantity, average_unit_cost=unit_cost, last_unit_cost=unit_cost,
            last_supplier_id=None, last_cost_at=now, updated_at=now,
        ))


def get_waste_record(session: Session, waste_id: str) -> dict[str, Any]:
    record = session.execute(sa.select(
        models.waste_records,
        models.inventory_items.c.name.label("item_name"),
        models.inventory_items.c.sku.label("item_sku"),
        models.inventory_units.c.code.label("unit_code"),
        models.waste_reasons.c.code.label("reason_code"),
        models.waste_reasons.c.name.label("reason_name"),
        models.waste_reasons.c.classification.label("reason_classification"),
    ).select_from(
        models.waste_records
        .join(models.inventory_items, models.waste_records.c.item_id == models.inventory_items.c.id)
        .join(models.inventory_units, models.waste_records.c.unit_id == models.inventory_units.c.id)
        .join(models.waste_reasons, models.waste_records.c.reason_id == models.waste_reasons.c.id)
    ).where(models.waste_records.c.id == waste_id)).mappings().first()
    if not record:
        raise BusinessError("waste_not_found", "Waste record was not found")
    result = dict(record)
    movement_ids = [value for value in (record["movement_id"], record["reversal_movement_id"]) if value]
    result["movements"] = [dict(row) for row in session.execute(sa.select(
        models.inventory_movements
    ).where(models.inventory_movements.c.id.in_(movement_ids)).order_by(
        models.inventory_movements.c.created_at
    )).mappings()] if movement_ids else []
    return result


def list_waste_records(session: Session, branch_id: str) -> list[dict[str, Any]]:
    ids = session.execute(sa.select(models.waste_records.c.id).where(
        models.waste_records.c.branch_id == branch_id
    ).order_by(models.waste_records.c.created_at.desc())).scalars()
    return [get_waste_record(session, waste_id) for waste_id in ids]


def create_inventory_transfer(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    source_branch_id = str(payload.get("source_branch_id", ""))
    destination_branch_id = str(payload.get("destination_branch_id", ""))
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "inventory.transfer.send", source_branch_id)
    if not source_branch_id or not destination_branch_id or source_branch_id == destination_branch_id:
        raise BusinessError("invalid_transfer_branches", "Transfer source and destination must be different branches")
    branch_rows = [dict(row) for row in session.execute(sa.select(
        models.branches.c.id, models.branches.c.code
    ).where(
        models.branches.c.id.in_([source_branch_id, destination_branch_id]),
        models.branches.c.organization_id == ORGANIZATION_ID,
        models.branches.c.status == "active",
    )).mappings()]
    if {row["id"] for row in branch_rows} != {source_branch_id, destination_branch_id}:
        raise BusinessError("transfer_branch_not_found", "Active transfer branches were not found")
    requested_lines = list(payload.get("lines", []))
    if not requested_lines:
        raise BusinessError("transfer_lines_required", "Transfer requires at least one line")
    seen = set()
    now = _now()
    line_rows = []
    for line in requested_lines:
        item_id = str(line.get("item_id", ""))
        if not item_id or item_id in seen:
            raise BusinessError("duplicate_transfer_item", "Transfer item cannot be empty or duplicated")
        seen.add(item_id)
        item = session.execute(sa.select(models.inventory_items).where(
            models.inventory_items.c.id == item_id,
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.status == "active",
        )).mappings().first()
        if not item:
            raise BusinessError("transfer_item_not_found", "Transfer item was not found")
        unit_id = str(line.get("unit_id") or item["base_unit_id"])
        quantity = _quantity(line.get("quantity", 0))
        if unit_id != item["base_unit_id"] or quantity <= 0:
            raise BusinessError("invalid_transfer_line", "Transfer quantity must be positive in item base unit")
        line_rows.append({
            "id": _id(), "item_id": item_id, "unit_id": unit_id,
            "requested_quantity": quantity, "sent_quantity": 0, "received_quantity": 0,
            "difference_quantity": 0, "unit_cost": 0, "sent_total_cost": 0,
            "received_total_cost": 0, "difference_cost": 0, "difference_reason": None,
            "condition": None, "notes": str(line.get("notes", "")).strip() or None,
            "out_movement_id": None, "in_movement_id": None, "created_at": now,
        })
    source_code = next(row["code"] for row in branch_rows if row["id"] == source_branch_id)
    transfer_id = _id()
    transfer = {
        "id": transfer_id, "organization_id": ORGANIZATION_ID,
        "source_branch_id": source_branch_id,
        "source_warehouse_id": _branch_warehouse_id(session, source_branch_id),
        "destination_branch_id": destination_branch_id,
        "destination_warehouse_id": _branch_warehouse_id(session, destination_branch_id),
        "folio": f"TRF-{source_code}-{uuid4().hex[:8].upper()}", "status": "draft",
        "notes": str(payload.get("notes", "")).strip() or None, "cancellation_reason": None,
        "created_by": actor_id, "sent_by": None, "received_by": None, "cancelled_by": None,
        "send_idempotency_key": None, "receive_idempotency_key": None,
        "created_at": now, "sent_at": None, "received_at": None, "cancelled_at": None,
    }
    session.execute(models.inventory_transfers.insert().values(**transfer))
    session.execute(models.inventory_transfer_lines.insert(), [
        {**line, "transfer_id": transfer_id} for line in line_rows
    ])
    _audit(session, "inventory_transfer.created", "inventory_transfer", transfer_id,
           {"destination_branch_id": destination_branch_id, "line_count": len(line_rows)},
           source_branch_id, actor_user_id=actor_id)
    session.commit()
    return get_inventory_transfer(session, transfer_id)


def send_inventory_transfer(
    session: Session,
    transfer_id: str,
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Transfer send requires idempotency key")
    transfer = session.execute(sa.select(models.inventory_transfers).where(
        models.inventory_transfers.c.id == transfer_id
    )).mappings().first()
    if not transfer:
        raise BusinessError("transfer_not_found", "Inventory transfer was not found")
    require_permission(session, actor_id, "inventory.transfer.send", transfer["source_branch_id"])
    if transfer["status"] in {"sent", "received", "received_with_difference"}:
        if transfer["send_idempotency_key"] == key:
            return get_inventory_transfer(session, transfer_id)
        raise BusinessError("transfer_already_sent", "Inventory transfer was already sent")
    if transfer["status"] != "draft":
        raise BusinessError("transfer_not_sendable", "Only draft transfer can be sent")
    lines = [dict(row) for row in session.execute(sa.select(
        models.inventory_transfer_lines
    ).where(models.inventory_transfer_lines.c.transfer_id == transfer_id)).mappings()]
    requirements = []
    for line in lines:
        quantity = _quantity(line["requested_quantity"])
        available = _physical_inventory_quantity(
            session, transfer["source_branch_id"], transfer["source_warehouse_id"], line["item_id"]
        )
        if available < quantity:
            raise BusinessError("insufficient_transfer_inventory", "Transfer item exceeds physical inventory")
        state = session.execute(sa.select(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == transfer["source_branch_id"],
            models.inventory_cost_states.c.warehouse_id == transfer["source_warehouse_id"],
            models.inventory_cost_states.c.item_id == line["item_id"],
        )).mappings().first()
        unit_cost = _cost(state["average_unit_cost"] if state else 0)
        requirements.append((line, quantity, available, unit_cost, _cost(quantity * unit_cost)))
    now = _now()
    for index, (line, quantity, available, unit_cost, total_cost) in enumerate(requirements):
        movement_id = _id()
        session.execute(models.inventory_movements.insert().values(
            id=movement_id, organization_id=ORGANIZATION_ID,
            branch_id=transfer["source_branch_id"], warehouse_id=transfer["source_warehouse_id"],
            item_id=line["item_id"], movement_type="TRANSFER_OUT", quantity_delta=-quantity,
            unit_id=line["unit_id"], unit_cost=unit_cost, total_cost=-total_cost,
            effective_at=now, actor_user_id=actor_id, document_type="inventory_transfer",
            document_id=transfer_id, reference=transfer["folio"], reason="Envío de traspaso",
            notes=line["notes"], idempotency_key=f"{key}:out:{index}", status="confirmed",
            reversal_of_id=None, source_type="inventory_transfer", source_id=transfer_id, created_at=now,
        ))
        _set_inventory_cost_quantity(
            session, transfer["source_branch_id"], transfer["source_warehouse_id"], line["item_id"],
            _quantity(available - quantity), unit_cost, now,
        )
        session.execute(sa.update(models.inventory_transfer_lines).where(
            models.inventory_transfer_lines.c.id == line["id"]
        ).values(
            sent_quantity=quantity, unit_cost=unit_cost, sent_total_cost=total_cost,
            out_movement_id=movement_id,
        ))
    session.execute(sa.update(models.inventory_transfers).where(
        models.inventory_transfers.c.id == transfer_id
    ).values(status="sent", sent_by=actor_id, send_idempotency_key=key, sent_at=now))
    _audit(session, "inventory_transfer.sent", "inventory_transfer", transfer_id,
           {"folio": transfer["folio"], "line_count": len(lines)},
           transfer["source_branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_inventory_transfer(session, transfer_id)


def receive_inventory_transfer(
    session: Session,
    transfer_id: str,
    received_lines: list[dict[str, Any]],
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Transfer receipt requires idempotency key")
    transfer = session.execute(sa.select(models.inventory_transfers).where(
        models.inventory_transfers.c.id == transfer_id
    )).mappings().first()
    if not transfer:
        raise BusinessError("transfer_not_found", "Inventory transfer was not found")
    require_permission(session, actor_id, "inventory.transfer.receive", transfer["destination_branch_id"])
    if transfer["status"] in {"received", "received_with_difference"}:
        if transfer["receive_idempotency_key"] == key:
            return get_inventory_transfer(session, transfer_id)
        raise BusinessError("transfer_already_received", "Inventory transfer was already received")
    if transfer["status"] != "sent":
        raise BusinessError("transfer_not_receivable", "Only sent transfer can be received")
    stored_lines = [dict(row) for row in session.execute(sa.select(
        models.inventory_transfer_lines
    ).where(models.inventory_transfer_lines.c.transfer_id == transfer_id)).mappings()]
    received_by_id = {str(line.get("line_id", "")): line for line in received_lines}
    if set(received_by_id) != {line["id"] for line in stored_lines}:
        raise BusinessError("transfer_receipt_lines_mismatch", "Receipt must provide every transfer line exactly once")
    resolutions = []
    has_difference = False
    for line in stored_lines:
        receipt = received_by_id[line["id"]]
        sent = _quantity(line["sent_quantity"])
        received = _quantity(receipt.get("received_quantity", 0))
        if received < 0 or received > sent:
            raise BusinessError("invalid_transfer_received_quantity", "Received quantity must be between zero and sent quantity")
        difference = _quantity(sent - received)
        difference_reason = str(receipt.get("difference_reason", "")).strip() or None
        condition = str(receipt.get("condition", "good")).strip().lower()
        if difference > 0 and not difference_reason:
            raise BusinessError("transfer_difference_reason_required", "Transfer difference requires a reason")
        has_difference = has_difference or difference > 0
        destination_quantity = _physical_inventory_quantity(
            session, transfer["destination_branch_id"], transfer["destination_warehouse_id"], line["item_id"]
        )
        if destination_quantity < 0:
            raise BusinessError("negative_inventory_cost_policy_required", "Destination has negative physical inventory")
        destination_state = session.execute(sa.select(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == transfer["destination_branch_id"],
            models.inventory_cost_states.c.warehouse_id == transfer["destination_warehouse_id"],
            models.inventory_cost_states.c.item_id == line["item_id"],
        )).mappings().first()
        resolutions.append((
            line, received, difference, difference_reason, condition,
            destination_quantity, destination_state,
            _cost(received * _cost(line["unit_cost"])),
            _cost(difference * _cost(line["unit_cost"])),
        ))
    now = _now()
    for index, (line, received, difference, difference_reason, condition, destination_quantity, destination_state, received_cost, difference_cost) in enumerate(resolutions):
        movement_id = None
        if received > 0:
            movement_id = _id()
            session.execute(models.inventory_movements.insert().values(
                id=movement_id, organization_id=ORGANIZATION_ID,
                branch_id=transfer["destination_branch_id"], warehouse_id=transfer["destination_warehouse_id"],
                item_id=line["item_id"], movement_type="TRANSFER_IN", quantity_delta=received,
                unit_id=line["unit_id"], unit_cost=line["unit_cost"], total_cost=received_cost,
                effective_at=now, actor_user_id=actor_id, document_type="inventory_transfer",
                document_id=transfer_id, reference=transfer["folio"], reason="Recepción de traspaso",
                notes=difference_reason, idempotency_key=f"{key}:in:{index}", status="confirmed",
                reversal_of_id=None, source_type="inventory_transfer", source_id=transfer_id, created_at=now,
            ))
            _apply_transfer_destination_cost(
                session, transfer["destination_branch_id"], transfer["destination_warehouse_id"],
                line["item_id"], destination_quantity, destination_state,
                received, _cost(line["unit_cost"]), received_cost, now,
            )
        session.execute(sa.update(models.inventory_transfer_lines).where(
            models.inventory_transfer_lines.c.id == line["id"]
        ).values(
            received_quantity=received, difference_quantity=difference,
            received_total_cost=received_cost, difference_cost=difference_cost,
            difference_reason=difference_reason, condition=condition,
            notes=str(received_by_id[line["id"]].get("notes", "")).strip() or line["notes"],
            in_movement_id=movement_id,
        ))
    final_status = "received_with_difference" if has_difference else "received"
    session.execute(sa.update(models.inventory_transfers).where(
        models.inventory_transfers.c.id == transfer_id
    ).values(
        status=final_status, received_by=actor_id,
        receive_idempotency_key=key, received_at=now,
    ))
    _audit(session, "inventory_transfer.received", "inventory_transfer", transfer_id,
           {"status": final_status, "folio": transfer["folio"]},
           transfer["destination_branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_inventory_transfer(session, transfer_id)


def _apply_transfer_destination_cost(
    session: Session,
    branch_id: str,
    warehouse_id: str,
    item_id: str,
    current_quantity: Decimal,
    current_state: dict[str, Any] | None,
    received_quantity: Decimal,
    received_unit_cost: Decimal,
    received_cost: Decimal,
    now: datetime,
) -> None:
    current_average = _cost(current_state["average_unit_cost"] if current_state else 0)
    new_quantity = _quantity(current_quantity + received_quantity)
    new_average = received_unit_cost if current_quantity == 0 else _cost(
        ((current_quantity * current_average) + received_cost) / new_quantity
    )
    values = {
        "quantity_on_hand": new_quantity, "average_unit_cost": new_average,
        "last_unit_cost": received_unit_cost, "last_supplier_id": None,
        "last_cost_at": now, "updated_at": now,
    }
    if current_state:
        session.execute(sa.update(models.inventory_cost_states).where(
            models.inventory_cost_states.c.branch_id == branch_id,
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == item_id,
        ).values(**values))
    else:
        session.execute(models.inventory_cost_states.insert().values(
            branch_id=branch_id, warehouse_id=warehouse_id, item_id=item_id, **values
        ))


def cancel_inventory_transfer(
    session: Session,
    transfer_id: str,
    reason: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    normalized_reason = reason.strip()
    transfer = session.execute(sa.select(models.inventory_transfers).where(
        models.inventory_transfers.c.id == transfer_id
    )).mappings().first()
    if not transfer:
        raise BusinessError("transfer_not_found", "Inventory transfer was not found")
    require_permission(session, actor_id, "inventory.transfer.send", transfer["source_branch_id"])
    if transfer["status"] != "draft":
        raise BusinessError("transfer_not_cancellable", "Only draft transfer can be cancelled")
    if not normalized_reason:
        raise BusinessError("transfer_cancellation_reason_required", "Transfer cancellation reason is required")
    now = _now()
    session.execute(sa.update(models.inventory_transfers).where(
        models.inventory_transfers.c.id == transfer_id
    ).values(
        status="cancelled", cancellation_reason=normalized_reason,
        cancelled_by=actor_id, cancelled_at=now,
    ))
    _audit(session, "inventory_transfer.cancelled", "inventory_transfer", transfer_id,
           {"reason": normalized_reason}, transfer["source_branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_inventory_transfer(session, transfer_id)


def get_inventory_transfer(session: Session, transfer_id: str) -> dict[str, Any]:
    transfer = session.execute(sa.select(
        models.inventory_transfers,
        models.branches.c.name.label("source_branch_name"),
    ).select_from(models.inventory_transfers.join(
        models.branches, models.inventory_transfers.c.source_branch_id == models.branches.c.id
    )).where(models.inventory_transfers.c.id == transfer_id)).mappings().first()
    if not transfer:
        raise BusinessError("transfer_not_found", "Inventory transfer was not found")
    destination_name = session.execute(sa.select(models.branches.c.name).where(
        models.branches.c.id == transfer["destination_branch_id"]
    )).scalar_one()
    result = {**dict(transfer), "destination_branch_name": destination_name}
    result["lines"] = [dict(row) for row in session.execute(sa.select(
        models.inventory_transfer_lines,
        models.inventory_items.c.name.label("item_name"),
        models.inventory_items.c.sku.label("item_sku"),
        models.inventory_units.c.code.label("unit_code"),
    ).select_from(
        models.inventory_transfer_lines
        .join(models.inventory_items, models.inventory_transfer_lines.c.item_id == models.inventory_items.c.id)
        .join(models.inventory_units, models.inventory_transfer_lines.c.unit_id == models.inventory_units.c.id)
    ).where(models.inventory_transfer_lines.c.transfer_id == transfer_id).order_by(
        models.inventory_items.c.name
    )).mappings()]
    movement_ids = [
        movement_id for line in result["lines"]
        for movement_id in (line["out_movement_id"], line["in_movement_id"]) if movement_id
    ]
    result["movements"] = [dict(row) for row in session.execute(sa.select(
        models.inventory_movements
    ).where(models.inventory_movements.c.id.in_(movement_ids)).order_by(
        models.inventory_movements.c.created_at
    )).mappings()] if movement_ids else []
    return result


def list_inventory_transfers(session: Session, branch_id: str) -> list[dict[str, Any]]:
    ids = session.execute(sa.select(models.inventory_transfers.c.id).where(sa.or_(
        models.inventory_transfers.c.source_branch_id == branch_id,
        models.inventory_transfers.c.destination_branch_id == branch_id,
    )).order_by(models.inventory_transfers.c.created_at.desc())).scalars()
    return [get_inventory_transfer(session, transfer_id) for transfer_id in ids]


def create_physical_count_session(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    branch_id = str(payload.get("branch_id", ""))
    actor_id = _actor_user_id(actor_user_id)
    require_permission(session, actor_id, "inventory.count", branch_id)
    active = session.execute(sa.select(models.physical_count_sessions.c.id).where(
        models.physical_count_sessions.c.branch_id == branch_id,
        models.physical_count_sessions.c.status.in_(["counting", "submitted", "approved"]),
    )).scalar_one_or_none()
    if active:
        raise BusinessError("active_physical_count_exists", "Branch already has an active physical count")
    requested_ids = [str(item_id) for item_id in payload.get("item_ids", []) if item_id]
    if len(requested_ids) != len(set(requested_ids)):
        raise BusinessError("duplicate_count_item", "Physical count item cannot be duplicated")
    item_query = sa.select(models.inventory_items).where(
        models.inventory_items.c.organization_id == ORGANIZATION_ID,
        models.inventory_items.c.status == "active",
    )
    if requested_ids:
        item_query = item_query.where(models.inventory_items.c.id.in_(requested_ids))
    items = [dict(row) for row in session.execute(item_query.order_by(
        models.inventory_items.c.name
    )).mappings()]
    if not items or (requested_ids and {item["id"] for item in items} != set(requested_ids)):
        raise BusinessError("physical_count_items_not_found", "Active physical count items were not found")
    warehouse_id = _branch_warehouse_id(session, branch_id)
    now = _now()
    count_id = _id()
    branch_code = session.execute(sa.select(models.branches.c.code).where(
        models.branches.c.id == branch_id,
        models.branches.c.organization_id == ORGANIZATION_ID,
        models.branches.c.status == "active",
    )).scalar_one_or_none()
    if not branch_code:
        raise BusinessError("count_branch_not_found", "Active count branch was not found")
    count = {
        "id": count_id, "organization_id": ORGANIZATION_ID, "branch_id": branch_id,
        "warehouse_id": warehouse_id, "folio": f"CNT-{branch_code}-{uuid4().hex[:8].upper()}",
        "status": "counting", "scope": "selected" if requested_ids else "all_active",
        "notes": str(payload.get("notes", "")).strip() or None, "cancellation_reason": None,
        "created_by": actor_id, "submitted_by": None, "approved_by": None,
        "closed_by": None, "cancelled_by": None, "approval_idempotency_key": None,
        "snapshot_at": now, "created_at": now, "submitted_at": None,
        "approved_at": None, "closed_at": None, "cancelled_at": None,
    }
    lines = []
    for item in items:
        theoretical = _physical_inventory_quantity(session, branch_id, warehouse_id, item["id"])
        average = session.execute(sa.select(models.inventory_cost_states.c.average_unit_cost).where(
            models.inventory_cost_states.c.branch_id == branch_id,
            models.inventory_cost_states.c.warehouse_id == warehouse_id,
            models.inventory_cost_states.c.item_id == item["id"],
        )).scalar_one_or_none()
        unit_cost = _cost(average or 0)
        lines.append({
            "id": _id(), "session_id": count_id, "item_id": item["id"],
            "unit_id": item["base_unit_id"], "theoretical_quantity": theoretical,
            "snapshot_unit_cost": unit_cost, "snapshot_value": _cost(theoretical * unit_cost),
            "counted_quantity": None, "snapshot_difference": None,
            "approval_ledger_quantity": None, "adjustment_quantity": None,
            "adjustment_unit_cost": None, "adjustment_cost": None,
            "adjustment_movement_id": None, "captured_by": None, "captured_at": None,
            "notes": None,
        })
    session.execute(models.physical_count_sessions.insert().values(**count))
    session.execute(models.physical_count_lines.insert(), lines)
    _audit(session, "physical_count.created", "physical_count", count_id,
           {"folio": count["folio"], "scope": count["scope"], "line_count": len(lines)},
           branch_id, actor_user_id=actor_id)
    session.commit()
    return get_physical_count_session(session, count_id)


def capture_physical_count_line(
    session: Session,
    count_id: str,
    line_id: str,
    quantity: Any,
    notes: str | None,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    count = session.execute(sa.select(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    )).mappings().first()
    if not count:
        raise BusinessError("physical_count_not_found", "Physical count was not found")
    require_permission(session, actor_id, "inventory.count", count["branch_id"])
    if count["status"] != "counting":
        raise BusinessError("physical_count_not_editable", "Only counting session can be captured")
    line = session.execute(sa.select(models.physical_count_lines.c.id).where(
        models.physical_count_lines.c.id == line_id,
        models.physical_count_lines.c.session_id == count_id,
    )).scalar_one_or_none()
    if not line:
        raise BusinessError("physical_count_line_not_found", "Physical count line was not found")
    counted = _quantity(quantity)
    normalized_notes = str(notes or "").strip() or None
    if counted < 0:
        raise BusinessError("invalid_counted_quantity", "Counted quantity cannot be negative")
    if normalized_notes and len(normalized_notes) > 600:
        raise BusinessError("invalid_count_notes", "Count line notes exceed 600 characters")
    now = _now()
    session.execute(sa.update(models.physical_count_lines).where(
        models.physical_count_lines.c.id == line_id
    ).values(
        counted_quantity=counted, captured_by=actor_id, captured_at=now, notes=normalized_notes,
    ))
    _audit(session, "physical_count.line_captured", "physical_count", count_id,
           {"line_id": line_id, "counted_quantity": str(counted)},
           count["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_physical_count_session(session, count_id)


def submit_physical_count_session(
    session: Session,
    count_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    count = session.execute(sa.select(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    )).mappings().first()
    if not count:
        raise BusinessError("physical_count_not_found", "Physical count was not found")
    require_permission(session, actor_id, "inventory.count", count["branch_id"])
    if count["status"] != "counting":
        raise BusinessError("physical_count_not_submittable", "Only counting session can be submitted")
    lines = [dict(row) for row in session.execute(sa.select(
        models.physical_count_lines
    ).where(models.physical_count_lines.c.session_id == count_id)).mappings()]
    if any(line["counted_quantity"] is None for line in lines):
        raise BusinessError("physical_count_incomplete", "Every physical count line must be captured")
    for line in lines:
        difference = _quantity(
            Decimal(str(line["counted_quantity"])) - Decimal(str(line["theoretical_quantity"]))
        )
        session.execute(sa.update(models.physical_count_lines).where(
            models.physical_count_lines.c.id == line["id"]
        ).values(snapshot_difference=difference))
    now = _now()
    session.execute(sa.update(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    ).values(status="submitted", submitted_by=actor_id, submitted_at=now))
    _audit(session, "physical_count.submitted", "physical_count", count_id,
           {"line_count": len(lines)}, count["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_physical_count_session(session, count_id)


def approve_physical_count_session(
    session: Session,
    count_id: str,
    idempotency_key: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    key = idempotency_key.strip()
    if not key:
        raise BusinessError("idempotency_key_required", "Physical count approval requires idempotency key")
    count = session.execute(sa.select(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    )).mappings().first()
    if not count:
        raise BusinessError("physical_count_not_found", "Physical count was not found")
    require_permission(session, actor_id, "inventory.count", count["branch_id"])
    if count["status"] in {"approved", "closed"}:
        if count["approval_idempotency_key"] == key:
            return get_physical_count_session(session, count_id)
        raise BusinessError("physical_count_already_approved", "Physical count was already approved")
    if count["status"] != "submitted":
        raise BusinessError("physical_count_not_approvable", "Only submitted physical count can be approved")
    lines = [dict(row) for row in session.execute(sa.select(
        models.physical_count_lines
    ).where(models.physical_count_lines.c.session_id == count_id)).mappings()]
    resolutions = []
    for line in lines:
        ledger_quantity = _physical_inventory_quantity(
            session, count["branch_id"], count["warehouse_id"], line["item_id"]
        )
        adjustment = _quantity(Decimal(str(line["counted_quantity"])) - ledger_quantity)
        average = session.execute(sa.select(models.inventory_cost_states.c.average_unit_cost).where(
            models.inventory_cost_states.c.branch_id == count["branch_id"],
            models.inventory_cost_states.c.warehouse_id == count["warehouse_id"],
            models.inventory_cost_states.c.item_id == line["item_id"],
        )).scalar_one_or_none()
        unit_cost = _cost(average or line["snapshot_unit_cost"] or 0)
        resolutions.append((line, ledger_quantity, adjustment, unit_cost, _cost(adjustment * unit_cost)))
    now = _now()
    for index, (line, ledger_quantity, adjustment, unit_cost, adjustment_cost) in enumerate(resolutions):
        movement_id = None
        if adjustment != 0:
            movement_id = _id()
            session.execute(models.inventory_movements.insert().values(
                id=movement_id, organization_id=ORGANIZATION_ID, branch_id=count["branch_id"],
                warehouse_id=count["warehouse_id"], item_id=line["item_id"],
                movement_type="COUNT_ADJUSTMENT", quantity_delta=adjustment,
                unit_id=line["unit_id"], unit_cost=unit_cost, total_cost=adjustment_cost,
                effective_at=now, actor_user_id=actor_id, document_type="physical_count",
                document_id=count_id, reference=count["folio"], reason="Conciliación de conteo físico",
                notes=line["notes"], idempotency_key=f"{key}:line:{index}", status="confirmed",
                reversal_of_id=None, source_type="physical_count", source_id=count_id, created_at=now,
            ))
        _set_inventory_cost_quantity(
            session, count["branch_id"], count["warehouse_id"], line["item_id"],
            _quantity(line["counted_quantity"]), unit_cost, now,
        )
        session.execute(sa.update(models.physical_count_lines).where(
            models.physical_count_lines.c.id == line["id"]
        ).values(
            approval_ledger_quantity=ledger_quantity, adjustment_quantity=adjustment,
            adjustment_unit_cost=unit_cost, adjustment_cost=adjustment_cost,
            adjustment_movement_id=movement_id,
        ))
    session.execute(sa.update(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    ).values(
        status="approved", approved_by=actor_id,
        approval_idempotency_key=key, approved_at=now,
    ))
    _audit(session, "physical_count.approved", "physical_count", count_id,
           {"adjustment_count": sum(1 for _, _, adjustment, _, _ in resolutions if adjustment != 0)},
           count["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_physical_count_session(session, count_id)


def close_physical_count_session(
    session: Session,
    count_id: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    count = session.execute(sa.select(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    )).mappings().first()
    if not count:
        raise BusinessError("physical_count_not_found", "Physical count was not found")
    require_permission(session, actor_id, "inventory.count", count["branch_id"])
    if count["status"] == "closed":
        return get_physical_count_session(session, count_id)
    if count["status"] != "approved":
        raise BusinessError("physical_count_not_closable", "Only approved physical count can be closed")
    now = _now()
    session.execute(sa.update(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    ).values(status="closed", closed_by=actor_id, closed_at=now))
    _audit(session, "physical_count.closed", "physical_count", count_id,
           {"folio": count["folio"]}, count["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_physical_count_session(session, count_id)


def cancel_physical_count_session(
    session: Session,
    count_id: str,
    reason: str,
    actor_user_id: str | None = None,
) -> dict[str, Any]:
    actor_id = _actor_user_id(actor_user_id)
    normalized_reason = reason.strip()
    count = session.execute(sa.select(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    )).mappings().first()
    if not count:
        raise BusinessError("physical_count_not_found", "Physical count was not found")
    require_permission(session, actor_id, "inventory.count", count["branch_id"])
    if count["status"] != "counting":
        raise BusinessError("physical_count_not_cancellable", "Only counting session can be cancelled")
    if not normalized_reason:
        raise BusinessError("physical_count_cancellation_reason_required", "Count cancellation reason is required")
    now = _now()
    session.execute(sa.update(models.physical_count_sessions).where(
        models.physical_count_sessions.c.id == count_id
    ).values(
        status="cancelled", cancellation_reason=normalized_reason,
        cancelled_by=actor_id, cancelled_at=now,
    ))
    _audit(session, "physical_count.cancelled", "physical_count", count_id,
           {"reason": normalized_reason}, count["branch_id"], actor_user_id=actor_id)
    session.commit()
    return get_physical_count_session(session, count_id)


def get_physical_count_session(session: Session, count_id: str) -> dict[str, Any]:
    count = session.execute(sa.select(
        models.physical_count_sessions,
        models.branches.c.name.label("branch_name"),
    ).select_from(models.physical_count_sessions.join(
        models.branches, models.physical_count_sessions.c.branch_id == models.branches.c.id
    )).where(models.physical_count_sessions.c.id == count_id)).mappings().first()
    if not count:
        raise BusinessError("physical_count_not_found", "Physical count was not found")
    blind = count["status"] == "counting"
    lines = []
    for row in session.execute(sa.select(
        models.physical_count_lines,
        models.inventory_items.c.name.label("item_name"),
        models.inventory_items.c.sku.label("item_sku"),
        models.inventory_units.c.code.label("unit_code"),
    ).select_from(
        models.physical_count_lines
        .join(models.inventory_items, models.physical_count_lines.c.item_id == models.inventory_items.c.id)
        .join(models.inventory_units, models.physical_count_lines.c.unit_id == models.inventory_units.c.id)
    ).where(models.physical_count_lines.c.session_id == count_id).order_by(
        models.inventory_items.c.name
    )).mappings():
        line = dict(row)
        if blind:
            for field in (
                "theoretical_quantity", "snapshot_unit_cost", "snapshot_value", "snapshot_difference",
                "approval_ledger_quantity", "adjustment_quantity", "adjustment_unit_cost", "adjustment_cost",
            ):
                line.pop(field, None)
        lines.append(line)
    movement_ids = [line["adjustment_movement_id"] for line in lines if line.get("adjustment_movement_id")]
    result = {**dict(count), "blind": blind, "lines": lines}
    result["movements"] = [dict(row) for row in session.execute(sa.select(
        models.inventory_movements
    ).where(models.inventory_movements.c.id.in_(movement_ids)).order_by(
        models.inventory_movements.c.created_at
    )).mappings()] if movement_ids else []
    return result


def list_physical_count_sessions(session: Session, branch_id: str) -> list[dict[str, Any]]:
    ids = session.execute(sa.select(models.physical_count_sessions.c.id).where(
        models.physical_count_sessions.c.branch_id == branch_id
    ).order_by(models.physical_count_sessions.c.created_at.desc())).scalars()
    return [get_physical_count_session(session, count_id) for count_id in ids]


def _physical_inventory_quantity(session: Session, branch_id: str, warehouse_id: str, item_id: str) -> Decimal:
    value = session.execute(sa.select(sa.func.coalesce(sa.func.sum(models.inventory_movements.c.quantity_delta), 0)).where(
        models.inventory_movements.c.branch_id == branch_id,
        models.inventory_movements.c.warehouse_id == warehouse_id,
        models.inventory_movements.c.item_id == item_id,
        models.inventory_movements.c.movement_type.notin_(["SALE_RESERVATION", "RESERVATION_RELEASE"]),
    )).scalar_one()
    return _quantity(value)


def _money(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _quantity(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _cost(value: Any) -> Decimal:
    return Decimal(str(value)).quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def _parse_document_date(value: Any, fallback: datetime) -> datetime:
    if value is None or value == "":
        return fallback
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _resolve_order_customer_snapshots(
    session: Session,
    customer_id: str | None,
    delivery_address_id: str | None,
    order_type: str,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not customer_id:
        if delivery_address_id:
            raise BusinessError("customer_required", "Address cannot be used without a customer")
        return None, None
    customer = session.execute(sa.select(models.customers).where(
        models.customers.c.id == customer_id,
        models.customers.c.organization_id == ORGANIZATION_ID,
        models.customers.c.status == "active",
    )).mappings().first()
    if not customer:
        raise BusinessError("customer_not_found", "Active customer was not found")
    phones = [dict(row) for row in session.execute(sa.select(models.customer_phones).where(
        models.customer_phones.c.customer_id == customer_id,
        models.customer_phones.c.status == "active",
    )).mappings()]
    customer_snapshot = _sanitize_for_json({
        "id": customer["id"], "name": customer["name"], "email": customer["email"], "phones": phones,
    })
    address_snapshot = None
    if delivery_address_id:
        address = session.execute(sa.select(models.customer_addresses).where(
            models.customer_addresses.c.id == delivery_address_id,
            models.customer_addresses.c.customer_id == customer_id,
            models.customer_addresses.c.status == "active",
        )).mappings().first()
        if not address:
            raise BusinessError("customer_address_mismatch", "Address does not belong to customer")
        address_snapshot = _sanitize_for_json(dict(address))
    if order_type.lower() == "delivery" and not address_snapshot:
        raise BusinessError("delivery_address_required", "Delivery order requires a customer address")
    return customer_snapshot, address_snapshot


# ---------------------------------------------------------------------------
# Branch administration (BA-001)
# ---------------------------------------------------------------------------


def build_session_profile(session: Session, actor_id: str, branch_id: str | None = None) -> dict:
    """Build the authenticated session profile from the database.

    Loads the actor's roles, permissions, scope and active branch from
    PostgreSQL. Does NOT rely on client-supplied role/permission state.
    Never exposes credentials.
    """
    actor = _actor_user_id(actor_id)
    user = session.execute(
        sa.select(models.users).where(
            models.users.c.id == actor,
            models.users.c.organization_id == ORGANIZATION_ID,
        )
    ).mappings().first()
    if not user:
        raise AuthorizationError("actor_required", "Actor authentication is required")
    if user["status"] != "active":
        raise AuthorizationError("user_inactive", "User is not active")

    role_rows = list(session.execute(
        sa.select(
            models.roles.c.id,
            models.roles.c.name,
            models.roles.c.scope,
            models.user_roles.c.branch_id,
        )
        .select_from(
            models.user_roles.join(models.roles, models.user_roles.c.role_id == models.roles.c.id)
        )
        .where(
            models.user_roles.c.user_id == actor,
            models.roles.c.organization_id == ORGANIZATION_ID,
        )
        .order_by(models.roles.c.name, models.user_roles.c.branch_id)
    ).mappings())
    if not role_rows:
        raise AuthorizationError("actor_not_authorized", "Actor is not authorized")

    roles_list = [
        {
            "id": row["id"],
            "name": row["name"],
            "scope": row["scope"],
            "branch_id": row["branch_id"],
        }
        for row in role_rows
    ]
    has_org_scope = any(row["scope"] == "organization" for row in role_rows)
    if has_org_scope:
        allowed_branch_ids = _active_organization_branch_ids(session)
    else:
        assigned_ids = {str(row["branch_id"]) for row in role_rows if row["branch_id"]}
        allowed_branch_ids = [
            branch
            for branch in _active_organization_branch_ids(session)
            if branch in assigned_ids
        ]
    if not allowed_branch_ids:
        raise AuthorizationError("actor_not_authorized", "Actor has no active branch scope")

    active_branch = _resolve_active_branch(
        session,
        requested_branch_id=branch_id,
        allowed_branch_ids=allowed_branch_ids,
    )
    active_branch_id = str(active_branch["id"])
    effective_role_ids = {
        str(row["id"])
        for row in role_rows
        if row["scope"] == "organization" or row["branch_id"] == active_branch_id
    }

    permission_rows = session.execute(
        sa.select(models.permissions.c.code)
        .select_from(
            models.role_permissions.join(
                models.permissions,
                models.role_permissions.c.permission_id == models.permissions.c.id,
            )
        )
        .where(models.role_permissions.c.role_id.in_(effective_role_ids))
    ).mappings()
    permissions = sorted({row["code"] for row in permission_rows})
    assigned_branch_id = None if has_org_scope else active_branch_id

    return {
        "user": {
            "id": user["id"],
            "email": user["email"],
            "display_name": user["display_name"],
            "status": user["status"],
        },
        "roles": [
            {**r, "branch_id": r["branch_id"] or None} for r in roles_list
        ],
        "permissions": permissions,
        "scope": {
            "level": "organization" if has_org_scope else "branch",
            "assigned_branch_id": assigned_branch_id,
            "allowed_branch_ids": allowed_branch_ids,
        },
        "active_branch": active_branch,
    }


def _resolve_active_branch(
    session: Session,
    requested_branch_id: str | None,
    allowed_branch_ids: list[str],
) -> dict:
    """Resolve the active branch for a session profile."""
    if requested_branch_id and requested_branch_id not in allowed_branch_ids:
        raise AuthorizationError(
            "permission_denied", "Actor does not have access to the requested branch"
        )
    target_id = requested_branch_id or allowed_branch_ids[0]
    detail = _branch_detail(session, target_id)
    if not detail:
        raise AuthorizationError(
            "permission_denied", "Actor does not have access to the requested branch"
        )
    return detail


def _active_organization_branch_ids(session: Session) -> list[str]:
    return [
        str(branch_id)
        for branch_id in session.execute(
            sa.select(models.branches.c.id)
            .where(
                models.branches.c.organization_id == ORGANIZATION_ID,
                models.branches.c.status == "active",
            )
            .order_by(models.branches.c.code)
        ).scalars()
    ]


def _branch_detail(session: Session, branch_id: str) -> dict | None:
    row = session.execute(
        sa.select(
            models.branches.c.id,
            models.branches.c.name,
            models.branches.c.code,
            models.branches.c.timezone,
            models.branches.c.status,
            models.business_units.c.id.label("bu_id"),
            models.business_units.c.name.label("bu_name"),
            models.business_units.c.code.label("bu_code"),
            models.business_units.c.unit_type.label("bu_unit_type"),
            models.legal_entities.c.id.label("le_id"),
            models.legal_entities.c.name.label("le_name"),
            models.warehouses.c.id.label("wh_id"),
            models.warehouses.c.name.label("wh_name"),
        )
        .select_from(
            models.branches.join(
                models.business_units,
                models.branches.c.business_unit_id == models.business_units.c.id,
            )
            .join(
                models.legal_entities,
                models.branches.c.legal_entity_id == models.legal_entities.c.id,
            )
            .outerjoin(
                models.warehouses,
                models.warehouses.c.branch_id == models.branches.c.id,
            )
        )
        .where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == ORGANIZATION_ID,
            models.branches.c.status == "active",
        )
    ).mappings().first()
    if not row:
        return None
    return {
        "id": row["id"],
        "name": row["name"],
        "code": row["code"],
        "timezone": row["timezone"],
        "status": row["status"],
        "business_unit": {
            "id": row["bu_id"],
            "name": row["bu_name"],
            "code": row["bu_code"],
            "unit_type": row["bu_unit_type"],
        },
        "legal_entity": {"id": row["le_id"], "name": row["le_name"]},
        "warehouse": {"id": row["wh_id"], "name": row["wh_name"]} if row["wh_id"] else None,
    }


def get_branch_context(session: Session, actor_id: str, branch_id: str | None = None) -> dict:
    """Return branch context (branch + business_unit + legal_entity + warehouse).

    A Supervisor is always fixed to their assigned branch; a corporate admin
    may select any active authorized branch.
    """
    authorized_branch = _branch_administration_target(
        session, actor_id, "branch.admin.access", branch_id
    )
    detail = _branch_detail(session, authorized_branch)
    if detail is None:
        raise AuthorizationError("permission_denied", "Branch is not authorized")
    return detail


def _branch_administration_target(
    session: Session,
    actor_id: str,
    permission_code: str,
    branch_id: str | None,
) -> str:
    authorized_branch = authorize_branch_scope(
        session, actor_id, permission_code, branch_id
    )
    if authorized_branch:
        return authorized_branch
    profile = build_session_profile(session, actor_id, branch_id)
    return str(profile["active_branch"]["id"])


def list_branch_staff(session: Session, actor_id: str, branch_id: str | None = None) -> list[dict]:
    """List users assigned to the authorized branch. Read-only, no credentials."""
    authorized_branch = _branch_administration_target(
        session, actor_id, "branch.staff.read", branch_id
    )
    rows = session.execute(
        sa.select(
            models.users.c.id,
            models.users.c.email,
            models.users.c.display_name,
            models.users.c.status,
            models.roles.c.name.label("role_name"),
            models.roles.c.scope.label("role_scope"),
            models.user_roles.c.branch_id,
        )
        .select_from(
            models.user_roles.join(models.users, models.user_roles.c.user_id == models.users.c.id)
            .join(models.roles, models.user_roles.c.role_id == models.roles.c.id)
        )
        .where(
            models.user_roles.c.branch_id == authorized_branch,
            models.users.c.organization_id == ORGANIZATION_ID,
            models.roles.c.organization_id == ORGANIZATION_ID,
        )
        .order_by(models.users.c.display_name)
    ).mappings()
    by_user: dict[str, dict] = {}
    for row in rows:
        uid = row["id"]
        if uid not in by_user:
            by_user[uid] = {
                "id": uid,
                "email": row["email"],
                "display_name": row["display_name"],
                "status": row["status"],
                "roles": [],
            }
        by_user[uid]["roles"].append(
            {"name": row["role_name"], "scope": row["role_scope"], "branch_id": row["branch_id"]}
        )
    return list(by_user.values())


def list_branch_admin_catalog_products(
    session: Session, actor_id: str, branch_id: str | None = None
) -> list[dict]:
    """List central products with effective availability for the branch.

    Products without a price appear as ``sellable: false``. Absence of a local
    override means ``has_local_override: False`` (inherits central availability).
    """
    authorized_branch = _branch_administration_target(
        session, actor_id, "branch.admin.access", branch_id
    )

    rows = session.execute(
        sa.select(
            models.products.c.id,
            models.products.c.name,
            models.products.c.sku,
            models.products.c.status,
            models.products.c.station,
            models.products.c.catalog_scope,
            models.products.c.source_branch_id,
            models.product_categories.c.name.label("category_name"),
            models.price_versions.c.price_cents,
            models.branch_product_availability.c.is_available,
        )
        .select_from(
            models.products.join(
                models.product_categories,
                models.products.c.category_id == models.product_categories.c.id,
            )
            .outerjoin(
                models.price_versions,
                sa.and_(
                    models.price_versions.c.product_id == models.products.c.id,
                    models.price_versions.c.valid_to.is_(None),
                ),
            )
            .outerjoin(
                models.branch_product_availability,
                sa.and_(
                    models.branch_product_availability.c.product_id == models.products.c.id,
                    models.branch_product_availability.c.branch_id == authorized_branch,
                ),
            )
        )
        .where(
            models.products.c.organization_id == ORGANIZATION_ID,
            models.products.c.status != "archived",
        )
        .where(
            sa.or_(
                models.products.c.catalog_scope == "organization",
                models.products.c.source_branch_id == authorized_branch,
            )
        )
        .order_by(models.products.c.name)
    ).mappings()
    result = []
    for row in rows:
        has_override = row["is_available"] is not None
        central_active = row["status"] == "active"
        effective = central_active and (row["is_available"] if has_override else True)
        has_price = row["price_cents"] is not None and row["price_cents"] > 0
        result.append(
            {
                "id": row["id"],
                "name": row["name"],
                "sku": row["sku"],
                "status": row["status"],
                "station": row["station"],
                "category": row["category_name"],
                "category_name": row["category_name"],
                "price_cents": row["price_cents"],
                "sellable": central_active and effective and has_price,
                "effective_availability": effective,
                "has_local_override": has_override,
                "availability_source": "branch_override" if has_override else "central",
                "catalog_scope": row.get("catalog_scope", "organization"),
                "source_branch_id": row.get("source_branch_id"),
            }
        )
    return result


def set_branch_product_availability(
    session: Session,
    actor_id: str,
    product_id: str,
    action: str,
    branch_id: str | None = None,
) -> dict:
    """Set per-branch product availability (available / unavailable / inherit).

    ``inherit`` removes the local override so the central availability applies.
    Only modifies ``branch_product_availability``; never touches products,
    categories or price_versions. Records an audit event with old/new values.
    """
    authorized_branch = _branch_administration_target(
        session, actor_id, "catalog.branch.manage", branch_id
    )
    if action not in ("available", "unavailable", "inherit"):
        raise BusinessError(
            "invalid_availability_action",
            "Action must be available, unavailable or inherit",
        )

    product = session.execute(
        sa.select(
            models.products.c.id,
            models.products.c.name,
            models.products.c.status,
        ).where(
            models.products.c.id == product_id,
            models.products.c.organization_id == ORGANIZATION_ID,
        )
    ).mappings().first()
    if not product:
        raise NotFoundError("product_not_found", "Product not found")

    existing = session.execute(
        sa.select(models.branch_product_availability).where(
            models.branch_product_availability.c.branch_id == authorized_branch,
            models.branch_product_availability.c.product_id == product_id,
        )
    ).mappings().first()
    previous_value = existing["is_available"] if existing else None

    now = _now()
    if action == "inherit":
        if existing:
            session.execute(
                models.branch_product_availability.delete().where(
                    models.branch_product_availability.c.branch_id == authorized_branch,
                    models.branch_product_availability.c.product_id == product_id,
                )
            )
        new_value = None
    else:
        new_value = action == "available"
        if existing:
            session.execute(
                models.branch_product_availability.update()
                .where(
                    models.branch_product_availability.c.branch_id == authorized_branch,
                    models.branch_product_availability.c.product_id == product_id,
                )
                .values(is_available=new_value, updated_at=now)
            )
        else:
            session.execute(
                models.branch_product_availability.insert().values(
                    branch_id=authorized_branch,
                    product_id=product_id,
                    is_available=new_value,
                    updated_at=now,
                )
            )

    _audit(
        session,
        action="branch_product_availability.updated",
        entity_type="product",
        entity_id=product_id,
        payload={
            "branch_id": authorized_branch,
            "product_name": product["name"],
            "previous": previous_value,
            "new": new_value,
            "requested_action": action,
        },
        branch_id=authorized_branch,
        actor_user_id=_actor_user_id(actor_id),
    )
    session.commit()
    central_active = product["status"] == "active"
    effective_availability = central_active and (
        new_value if new_value is not None else True
    )
    return {
        "product_id": product_id,
        "branch_id": authorized_branch,
        "effective_availability": effective_availability,
        "has_local_override": action != "inherit",
        "availability_source": "central" if action == "inherit" else "branch_override",
        "previous": previous_value,
    }
