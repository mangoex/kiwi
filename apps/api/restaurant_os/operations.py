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
