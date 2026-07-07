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

    now = _now()
    session.execute(
        models.cash_shifts.update()
        .where(models.cash_shifts.c.id == shift["id"])
        .values(status="CLOSED", closed_at=now)
    )
    _audit(
        session,
        action="cash_shift.closed",
        entity_type="cash_shift",
        entity_id=shift["id"],
        payload={"register_code": register_code},
    )
    session.commit()
    shift["status"] = "CLOSED"
    shift["closed_at"] = now
    return shift


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
    _audit(
        session,
        action="order.accepted",
        entity_type="order",
        entity_id=order_id,
        payload={"folio": folio, "product_id": product_id, "quantity": quantity},
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
        payload={"from": current, "to": target},
    )
    session.commit()
    updated = session.execute(
        sa.select(models.production_tasks).where(models.production_tasks.c.id == task_id)
    ).mappings().one()
    return dict(updated)


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
) -> None:
    session.execute(
        models.audit_events.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            branch_id=BRANCH_ID,
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
