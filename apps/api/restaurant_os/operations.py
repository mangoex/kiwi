from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ADMIN_USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
DEFAULT_REGISTER = "CAJA-01"


class BusinessError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def get_open_cash_shift(
    session: Session,
    register_code: str = DEFAULT_REGISTER,
) -> dict[str, Any] | None:
    row = session.execute(
        sa.select(models.cash_shifts)
        .where(
            models.cash_shifts.c.branch_id == BRANCH_ID,
            models.cash_shifts.c.register_code == register_code,
            models.cash_shifts.c.status == "OPEN",
        )
        .order_by(models.cash_shifts.c.opened_at.desc())
        .limit(1)
    ).mappings().first()
    return dict(row) if row else None


def create_role(session: Session, name: str, scope: str = "branch") -> dict[str, Any]:
    normalized_name = name.strip()
    normalized_scope = scope.strip().lower()
    if not normalized_name:
        raise BusinessError("invalid_role_name", "Role name is required")
    if normalized_scope not in {"organization", "branch"}:
        raise BusinessError("invalid_role_scope", "Role scope must be organization or branch")

    existing = session.execute(
        sa.select(models.roles).where(
            models.roles.c.organization_id == ORGANIZATION_ID,
            sa.func.lower(models.roles.c.name) == normalized_name.lower(),
        )
    ).mappings().first()
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
    _audit(
        session,
        action="role.created",
        entity_type="role",
        entity_id=role["id"],
        payload={"name": normalized_name, "scope": normalized_scope},
    )
    session.commit()
    return role


def create_user(session: Session, email: str, display_name: str) -> dict[str, Any]:
    normalized_email = email.strip().lower()
    normalized_name = display_name.strip()
    if "@" not in normalized_email or "." not in normalized_email.split("@")[-1]:
        raise BusinessError("invalid_user_email", "User email is invalid")
    if not normalized_name:
        raise BusinessError("invalid_display_name", "Display name is required")

    existing = session.execute(
        sa.select(models.users).where(models.users.c.email == normalized_email)
    ).mappings().first()
    if existing:
        raise BusinessError("user_already_exists", "User already exists")

    now = _now()
    user = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "email": normalized_email,
        "display_name": normalized_name,
        "status": "invited",
        "created_at": now,
        "updated_at": now,
    }
    session.execute(models.users.insert().values(**user))
    _audit(
        session,
        action="user.invited",
        entity_type="user",
        entity_id=user["id"],
        payload={"email": normalized_email, "display_name": normalized_name},
    )
    session.commit()
    return user


def create_branch(session: Session, name: str, code: str) -> dict[str, Any]:
    normalized_name = name.strip()
    normalized_code = code.strip().upper()
    if not normalized_name:
        raise BusinessError("invalid_branch_name", "Branch name is required")
    if not normalized_code:
        raise BusinessError("invalid_branch_code", "Branch code is required")

    existing = session.execute(
        sa.select(models.branches).where(
            models.branches.c.organization_id == ORGANIZATION_ID,
            models.branches.c.code == normalized_code,
        )
    ).mappings().first()
    if existing:
        raise BusinessError("branch_already_exists", "Branch code already exists")

    legal_entity_id = session.execute(
        sa.select(models.legal_entities.c.id)
        .where(models.legal_entities.c.organization_id == ORGANIZATION_ID)
        .limit(1)
    ).scalar_one()
    now = _now()
    branch = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "legal_entity_id": legal_entity_id,
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
        payload={"name": normalized_name, "code": normalized_code, "warehouse_id": warehouse["id"]},
        branch_id=branch["id"],
    )
    session.commit()
    return {**branch, "warehouse": warehouse}


def create_product(
    session: Session,
    name: str,
    sku: str,
    category_name: str,
    station: str,
    price_cents: int,
) -> dict[str, Any]:
    normalized_name = name.strip()
    normalized_sku = sku.strip().upper()
    normalized_category = category_name.strip()
    normalized_station = station.strip().lower()
    if not normalized_name:
        raise BusinessError("invalid_product_name", "Product name is required")
    if not normalized_sku:
        raise BusinessError("invalid_product_sku", "Product SKU is required")
    if not normalized_category:
        raise BusinessError("invalid_category_name", "Category name is required")
    if normalized_station not in {"kitchen", "drinks", "packing"}:
        raise BusinessError("invalid_station", "Station must be kitchen, drinks or packing")
    if price_cents <= 0:
        raise BusinessError("invalid_price", "Price must be positive")

    existing = session.execute(
        sa.select(models.products).where(
            models.products.c.organization_id == ORGANIZATION_ID,
            models.products.c.sku == normalized_sku,
        )
    ).mappings().first()
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
) -> dict[str, Any]:
    normalized_item_id = item_id.strip()
    normalized_reason = reason.strip() or "Saldo inicial"
    if quantity_base_units <= 0:
        raise BusinessError("invalid_inventory_quantity", "Inventory quantity must be positive")

    item = session.execute(
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
    ).mappings().first()
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
    )
    session.commit()
    return {**movement, "item_name": item["name"], "unit_code": item["unit_code"]}


def assign_user_role(
    session: Session,
    user_id: str,
    role_id: str,
    branch_id: str | None = None,
) -> dict[str, Any]:
    user = session.execute(
        sa.select(models.users).where(models.users.c.id == user_id)
    ).mappings().first()
    if not user:
        raise BusinessError("user_not_found", "User was not found")
    role = session.execute(
        sa.select(models.roles).where(models.roles.c.id == role_id)
    ).mappings().first()
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

    existing = session.execute(
        sa.select(models.user_roles).where(
            models.user_roles.c.user_id == user_id,
            models.user_roles.c.role_id == role_id,
            models.user_roles.c.branch_id.is_(normalized_branch_id)
            if normalized_branch_id is None
            else models.user_roles.c.branch_id == normalized_branch_id,
        )
    ).mappings().first()
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
    )
    session.commit()
    return assignment


def open_cash_shift(
    session: Session,
    opening_cash_cents: int,
    register_code: str = DEFAULT_REGISTER,
) -> dict[str, Any]:
    if get_open_cash_shift(session, register_code):
        raise BusinessError("cash_shift_already_open", "Register already has an open shift")
    if opening_cash_cents < 0:
        raise BusinessError("invalid_opening_cash", "Opening cash cannot be negative")

    now = _now()
    shift = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": BRANCH_ID,
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
    )
    session.commit()
    return shift


def close_cash_shift(session: Session, register_code: str = DEFAULT_REGISTER) -> dict[str, Any]:
    shift = get_open_cash_shift(session, register_code)
    if not shift:
        raise BusinessError("cash_shift_not_open", "Register does not have an open shift")

    return close_cash_shift_with_cut(
        session,
        counted_cash_cents=_cash_summary_for_shift(session, shift)["expected_cash_cents"],
        register_code=register_code,
    )


def close_cash_shift_with_cut(
    session: Session,
    counted_cash_cents: int,
    register_code: str = DEFAULT_REGISTER,
) -> dict[str, Any]:
    shift = get_open_cash_shift(session, register_code)
    if not shift:
        raise BusinessError("cash_shift_not_open", "Register does not have an open shift")
    if counted_cash_cents < 0:
        raise BusinessError("invalid_counted_cash", "Counted cash cannot be negative")

    now = _now()
    summary = _cash_summary_for_shift(session, shift)
    cut = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": BRANCH_ID,
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
    )
    session.commit()
    shift["status"] = "CLOSED"
    shift["closed_at"] = now
    return {**shift, "cut": cut}


def create_local_order(session: Session, product_id: str, quantity: int = 1) -> dict[str, Any]:
    if quantity <= 0:
        raise BusinessError("invalid_quantity", "Quantity must be positive")

    shift = get_open_cash_shift(session)
    if not shift:
        raise BusinessError("cash_shift_required", "Open cash shift is required")

    product = _get_available_product(session, product_id)
    if not product:
        raise BusinessError("product_unavailable", "Product is unavailable")

    now = _now()
    order_id = _id()
    order_line_id = _id()
    total_cents = int(product["price_cents"]) * quantity
    folio = _next_folio(session)
    order = {
        "id": order_id,
        "organization_id": ORGANIZATION_ID,
        "branch_id": BRANCH_ID,
        "cash_shift_id": shift["id"],
        "folio": folio,
        "channel": "POS",
        "status": "ACCEPTED",
        "total_cents": total_cents,
        "currency": product["currency"],
        "created_at": now,
        "accepted_at": now,
    }
    line = {
        "id": order_line_id,
        "order_id": order_id,
        "product_id": product["id"],
        "product_name": product["name"],
        "quantity": quantity,
        "unit_price_cents": product["price_cents"],
        "line_total_cents": total_cents,
        "station": product["station"],
        "created_at": now,
    }
    task = {
        "id": _id(),
        "organization_id": ORGANIZATION_ID,
        "branch_id": BRANCH_ID,
        "order_id": order_id,
        "order_line_id": order_line_id,
        "station": product["station"],
        "status": "PENDING",
        "product_name": product["name"],
        "quantity": quantity,
        "created_at": now,
        "started_at": None,
        "completed_at": None,
    }

    session.execute(models.orders.insert().values(**order))
    session.execute(models.order_lines.insert().values(**line))
    session.execute(
        models.order_events.insert().values(
            id=_id(),
            order_id=order_id,
            event_type="ORDER_ACCEPTED",
            payload={"folio": folio, "total_cents": total_cents},
            created_at=now,
        )
    )
    session.execute(models.production_tasks.insert().values(**task))
    reservation_movements = _record_recipe_inventory_movements(
        session,
        product_id=product["id"],
        product_name=product["name"],
        quantity=quantity,
        movement_type="SALE_RESERVATION",
        sign=-1,
        reason=f"Reserva por pedido {folio}",
        source_type="order",
        source_id=order_id,
        created_at=now,
    )
    _audit(
        session,
        action="order.accepted",
        entity_type="order",
        entity_id=order_id,
        payload={
            "folio": folio,
            "product_id": product_id,
            "quantity": quantity,
            "inventory_reservations": len(reservation_movements),
        },
    )
    session.commit()
    return {**order, "lines": [line], "production_tasks": [task]}


def list_recent_orders(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
        sa.select(models.orders)
        .where(models.orders.c.branch_id == BRANCH_ID)
        .order_by(models.orders.c.created_at.desc())
        .limit(20)
    ).mappings()
    return [dict(row) for row in rows]


def cancel_order(
    session: Session,
    order_id: str,
    reason: str = "Cancelacion solicitada en POS",
    classification: str | None = None,
) -> dict[str, Any]:
    normalized_reason = reason.strip() or "Cancelacion solicitada en POS"
    normalized_classification = (classification or "").strip().lower()
    order = session.execute(
        sa.select(models.orders).where(models.orders.c.id == order_id)
    ).mappings().first()
    if not order:
        raise BusinessError("order_not_found", "Order was not found")
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
                _record_recipe_inventory_movements(
                    session,
                    product_id=line["product_id"],
                    product_name=line["product_name"],
                    quantity=int(line["quantity"]),
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
                _record_recipe_inventory_movements(
                    session,
                    product_id=line["product_id"],
                    product_name=line["product_name"],
                    quantity=int(line["quantity"]),
                    movement_type=movement_type,
                    sign=sign,
                    reason=(
                        f"Cancelacion producida {order['folio']} "
                        f"clasificada como {movement_type}"
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
) -> dict[str, Any]:
    method_normalized = method.lower()
    if method_normalized not in {"cash", "card", "transfer"}:
        raise BusinessError("invalid_payment_method", "Payment method is not supported")
    if amount_cents <= 0:
        raise BusinessError("invalid_payment_amount", "Payment amount must be positive")

    order = session.execute(
        sa.select(models.orders).where(models.orders.c.id == order_id)
    ).mappings().first()
    if not order:
        raise BusinessError("order_not_found", "Order was not found")
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
        "branch_id": BRANCH_ID,
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
    )
    session.commit()
    return {**payment, "order_status": "CLOSED", "print_jobs": print_jobs}


def list_payments(session: Session) -> list[dict[str, Any]]:
    rows = session.execute(
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
        .where(models.payments.c.branch_id == BRANCH_ID)
        .order_by(models.payments.c.created_at.desc())
        .limit(50)
    ).mappings()
    return [dict(row) for row in rows]


def get_cash_shift_summary(
    session: Session,
    register_code: str = DEFAULT_REGISTER,
) -> dict[str, Any]:
    shift = get_open_cash_shift(session, register_code)
    if shift:
        return {
            "cash_shift": shift,
            "cut": None,
            "summary": _cash_summary_for_shift(session, shift),
        }

    row = session.execute(
        sa.select(models.cash_shifts)
        .where(
            models.cash_shifts.c.branch_id == BRANCH_ID,
            models.cash_shifts.c.register_code == register_code,
        )
        .order_by(models.cash_shifts.c.opened_at.desc())
        .limit(1)
    ).mappings().first()
    if not row:
        return {"cash_shift": None, "cut": None, "summary": None}

    shift = dict(row)
    cut = session.execute(
        sa.select(models.cash_shift_cuts).where(
            models.cash_shift_cuts.c.cash_shift_id == shift["id"]
        )
    ).mappings().first()
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
    job = session.execute(
        sa.select(models.print_jobs).where(models.print_jobs.c.id == job_id)
    ).mappings().first()
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
    updated = session.execute(
        sa.select(models.print_jobs).where(models.print_jobs.c.id == job_id)
    ).mappings().one()
    return dict(updated)


def receive_sync_command(session: Session, envelope: dict[str, Any]) -> dict[str, Any]:
    _validate_sync_envelope(envelope)
    idempotency_key = str(envelope["idempotency_key"])

    existing = session.execute(
        sa.select(models.sync_commands).where(
            models.sync_commands.c.idempotency_key == idempotency_key
        )
    ).mappings().first()
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
        )
        .select_from(
            models.production_tasks.join(
                models.orders,
                models.production_tasks.c.order_id == models.orders.c.id,
            )
        )
        .where(models.production_tasks.c.branch_id == BRANCH_ID)
        .order_by(models.production_tasks.c.created_at.desc())
        .limit(50)
    ).mappings()
    return [dict(row) for row in rows]


def advance_kds_task(session: Session, task_id: str, status: str) -> dict[str, Any]:
    target = status.upper()
    task = session.execute(
        sa.select(models.production_tasks).where(models.production_tasks.c.id == task_id)
    ).mappings().first()
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
        order_line = session.execute(
            sa.select(models.order_lines).where(models.order_lines.c.id == task["order_line_id"])
        ).mappings().one()
        _record_recipe_inventory_movements(
            session,
            product_id=order_line["product_id"],
            product_name=order_line["product_name"],
            quantity=int(order_line["quantity"]),
            movement_type="RESERVATION_RELEASE",
            sign=1,
            reason=f"Libera reserva por tarea {task_id}",
            source_type="production_task",
            source_id=task_id,
            created_at=now,
        )
        consumption_movements = _record_recipe_inventory_movements(
            session,
            product_id=order_line["product_id"],
            product_name=order_line["product_name"],
            quantity=int(order_line["quantity"]),
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
    updated = session.execute(
        sa.select(models.production_tasks).where(models.production_tasks.c.id == task_id)
    ).mappings().one()
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
    expected_cash = int(shift["opening_cash_cents"]) + cash_payment_total
    return {
        "sales_total_cents": sales_total,
        "payment_total_cents": payment_total,
        "cash_payment_total_cents": cash_payment_total,
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
    row = session.execute(
        sa.select(models.sync_events).where(models.sync_events.c.sync_command_id == command_id)
    ).mappings().one()
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


def _get_available_product(session: Session, product_id: str) -> dict[str, Any] | None:
    price = (
        sa.select(
            models.price_versions.c.product_id,
            models.price_versions.c.price_cents,
            models.price_versions.c.currency,
        )
        .where(models.price_versions.c.valid_to.is_(None))
        .subquery()
    )
    row = session.execute(
        sa.select(
            models.products.c.id,
            models.products.c.name,
            models.products.c.station,
            price.c.price_cents,
            price.c.currency,
        )
        .select_from(
            models.products.join(price, models.products.c.id == price.c.product_id).join(
                models.branch_product_availability,
                models.products.c.id == models.branch_product_availability.c.product_id,
            )
        )
        .where(
            models.products.c.id == product_id,
            models.products.c.status == "active",
            models.branch_product_availability.c.branch_id == BRANCH_ID,
            models.branch_product_availability.c.is_available.is_(True),
        )
    ).mappings().first()
    return dict(row) if row else None


def _get_or_create_category(
    session: Session,
    category_name: str,
    created_at: datetime,
) -> dict[str, Any]:
    row = session.execute(
        sa.select(models.product_categories).where(
            models.product_categories.c.organization_id == ORGANIZATION_ID,
            sa.func.lower(models.product_categories.c.name) == category_name.lower(),
        )
    ).mappings().first()
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
) -> list[dict[str, Any]]:
    warehouse_id = _branch_warehouse_id(session)
    components = _active_recipe_components(session, product_id)
    movements: list[dict[str, Any]] = []
    for component in components:
        component_quantity = int(component["quantity_base_units"]) * quantity
        movement = {
            "id": _id(),
            "organization_id": ORGANIZATION_ID,
            "branch_id": BRANCH_ID,
            "warehouse_id": warehouse_id,
            "item_id": component["item_id"],
            "movement_type": movement_type,
            "quantity_delta": sign * component_quantity,
            "unit_id": component["unit_id"],
            "reason": reason,
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


def _active_recipe_components(session: Session, product_id: str) -> list[dict[str, Any]]:
    active_recipe_id = (
        sa.select(models.recipes.c.id)
        .where(
            models.recipes.c.product_id == product_id,
            models.recipes.c.status == "active",
        )
        .order_by(models.recipes.c.version.desc())
        .limit(1)
        .scalar_subquery()
    )
    rows = session.execute(
        sa.select(
            models.recipe_components.c.item_id,
            models.recipe_components.c.quantity_base_units,
            models.inventory_items.c.name.label("item_name"),
            models.inventory_items.c.base_unit_id.label("unit_id"),
            models.inventory_units.c.code.label("unit_code"),
        )
        .select_from(
            models.recipe_components.join(
                models.inventory_items,
                models.recipe_components.c.item_id == models.inventory_items.c.id,
            ).join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
            )
        )
        .where(models.recipe_components.c.recipe_id == active_recipe_id)
        .order_by(models.inventory_items.c.name)
    ).mappings()
    return [dict(row) for row in rows]


def _branch_warehouse_id(session: Session) -> str:
    return str(
        session.execute(
            sa.select(models.warehouses.c.id)
            .where(
                models.warehouses.c.branch_id == BRANCH_ID,
                models.warehouses.c.status == "active",
            )
            .limit(1)
        ).scalar_one()
    )


def _next_folio(session: Session) -> str:
    count = int(
        session.execute(
            sa.select(sa.func.count())
            .select_from(models.orders)
            .where(models.orders.c.branch_id == BRANCH_ID)
        ).scalar_one()
    )
    return f"PILOTO-{count + 1:06d}"


def _audit(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    payload: dict[str, Any],
    branch_id: str = BRANCH_ID,
    organization_id: str = ORGANIZATION_ID,
) -> None:
    session.execute(
        models.audit_events.insert().values(
            id=_id(),
            organization_id=organization_id,
            branch_id=branch_id,
            actor_user_id=ADMIN_USER_ID,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=payload,
            correlation_id=None,
            created_at=_now(),
        )
    )


def _id() -> str:
    return str(uuid4())


def _now() -> datetime:
    return datetime.now(UTC)
