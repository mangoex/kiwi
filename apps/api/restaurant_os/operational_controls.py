"""Phase 6 — Remaining operational alerts and controls (CORTE-CIEGO-001)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.blind_cash_phase2_schema import ensure_phase2_tables
from restaurant_os.owner_alerts import emit_owner_alert

FEFO_EXPIRY_ALERT_DAYS = 3
DEFAULT_HIGH_WASTE_THRESHOLD_MXN = Decimal("500.00")
DEFAULT_CONSUMPTION_VARIANCE_PCT = Decimal("10.00")
DEFAULT_ORDER_DELAY_MINUTES = 25


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _iso(value: datetime) -> str:
    return _ensure_utc(value).isoformat()


def evaluate_high_waste_alerts(
    session: Session,
    branch_id: str,
    *,
    threshold_cost_mxn: Decimal = DEFAULT_HIGH_WASTE_THRESHOLD_MXN,
    threshold_quantity: Decimal | None = None,
) -> list[dict[str, Any]]:
    """Emit Owner alerts for confirmed waste records exceeding cost or quantity thresholds."""
    ensure_phase2_tables(session)
    rows = (
        session.execute(
            sa.select(
                models.waste_records.c.id,
                models.waste_records.c.item_id,
                models.waste_records.c.quantity,
                models.waste_records.c.total_cost,
                models.waste_records.c.stage,
                models.waste_records.c.effective_at,
                models.inventory_items.c.name.label("item_name"),
            )
            .select_from(
                models.waste_records.join(
                    models.inventory_items,
                    models.inventory_items.c.id == models.waste_records.c.item_id,
                )
            )
            .where(
                models.waste_records.c.organization_id == ops.ORGANIZATION_ID,
                models.waste_records.c.branch_id == branch_id,
                models.waste_records.c.status == "confirmed",
            )
            .order_by(models.waste_records.c.effective_at.desc())
        )
        .mappings()
        .all()
    )

    emitted: list[dict[str, Any]] = []
    for row in rows:
        qty = Decimal(str(row["quantity"]))
        cost = Decimal(str(row["total_cost"]))
        over_cost = cost >= threshold_cost_mxn
        over_qty = threshold_quantity is not None and qty >= threshold_quantity
        if not (over_cost or over_qty):
            continue
        wid = str(row["id"])
        alert = emit_owner_alert(
            session,
            branch_id=branch_id,
            alert_type="high_waste",
            severity="warning",
            title=f"Merma alta registrada: {row['item_name']}",
            summary=(
                f"Merma confirmada de {qty.quantize(Decimal('0.01'))} "
                f"(${cost.quantize(Decimal('0.01'))} MXN) en etapa {row['stage']}."
            ),
            source_type="waste_record",
            source_id=wid,
            dedup_key=f"high_waste:{branch_id}:{wid}",
            payload={
                "branch_id": branch_id,
                "waste_record_id": wid,
                "item_id": str(row["item_id"]),
                "item_name": str(row["item_name"]),
                "quantity": str(qty.quantize(Decimal("0.01"))),
                "total_cost_mxn": str(cost.quantize(Decimal("0.01"))),
                "stage": str(row["stage"]),
            },
        )
        emitted.append(alert)
    session.commit()
    return emitted


def evaluate_consumption_variance_alerts(
    session: Session,
    branch_id: str,
    *,
    variance_threshold_pct: Decimal = DEFAULT_CONSUMPTION_VARIANCE_PCT,
) -> list[dict[str, Any]]:
    """Compare real vs. theoretical consumption per item and emit Owner alerts when variance exceeds
    threshold.
    """
    ensure_phase2_tables(session)
    snapshots = (
        session.execute(
            sa.select(models.order_line_consumption_snapshots.c.components).where(
                models.order_line_consumption_snapshots.c.branch_id == branch_id
            )
        )
        .scalars()
        .all()
    )

    theoretical_by_item: dict[str, Decimal] = {}
    for comp_list in snapshots:
        if not isinstance(comp_list, list):
            continue
        for comp in comp_list:
            if not isinstance(comp, dict):
                continue
            iid = str(comp.get("item_id") or "")
            if not iid:
                continue
            qty_raw = (
                comp.get("gross_quantity") or comp.get("quantity") or comp.get("net_quantity") or 0
            )
            theoretical_by_item[iid] = theoretical_by_item.get(iid, Decimal("0")) + Decimal(
                str(qty_raw)
            )

    movement_rows = (
        session.execute(
            sa.select(
                models.inventory_movements.c.item_id,
                sa.func.coalesce(
                    sa.func.sum(sa.func.abs(models.inventory_movements.c.quantity_delta)), 0
                ).label("real_qty"),
            )
            .where(
                models.inventory_movements.c.organization_id == ops.ORGANIZATION_ID,
                models.inventory_movements.c.branch_id == branch_id,
                models.inventory_movements.c.status == "confirmed",
                models.inventory_movements.c.movement_type.in_(
                    (
                        "SALE_CONSUMPTION",
                        "PRODUCTION_CONSUMPTION",
                        "PHYSICAL_COUNT_ADJUSTMENT",
                        "WASTE",
                    )
                ),
                models.inventory_movements.c.quantity_delta < 0,
            )
            .group_by(models.inventory_movements.c.item_id)
        )
        .mappings()
        .all()
    )

    real_by_item: dict[str, Decimal] = {
        str(r["item_id"]): Decimal(str(r["real_qty"])) for r in movement_rows
    }

    all_items = sorted(set(theoretical_by_item.keys()) | set(real_by_item.keys()))
    emitted: list[dict[str, Any]] = []

    for item_id in all_items:
        theo = theoretical_by_item.get(item_id, Decimal("0"))
        real = real_by_item.get(item_id, Decimal("0"))
        if theo <= Decimal("0"):
            continue
        variance_qty = real - theo
        variance_pct = (abs(variance_qty) / theo * Decimal("100")).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if variance_pct < variance_threshold_pct:
            continue

        item_name = str(
            session.scalar(
                sa.select(models.inventory_items.c.name).where(
                    models.inventory_items.c.id == item_id
                )
            )
            or item_id
        )
        alert = emit_owner_alert(
            session,
            branch_id=branch_id,
            alert_type="consumption_variance",
            severity="warning",
            title=f"Variación de consumo real vs. teórico: {item_name}",
            summary=(
                f"Variación de {variance_pct}% en {item_name} "
                f"(teórico {theo.quantize(Decimal('0.01'))}, "
                f"real {real.quantize(Decimal('0.01'))})."
            ),
            source_type="inventory_item",
            source_id=item_id,
            dedup_key=f"consumption_variance:{branch_id}:{item_id}:{theo}:{real}",
            payload={
                "branch_id": branch_id,
                "item_id": item_id,
                "item_name": item_name,
                "theoretical_quantity": str(theo.quantize(Decimal("0.01"))),
                "real_quantity": str(real.quantize(Decimal("0.01"))),
                "variance_quantity": str(variance_qty.quantize(Decimal("0.01"))),
                "variance_pct": str(variance_pct),
            },
        )
        emitted.append(alert)

    session.commit()
    return emitted


def evaluate_expiring_lots(
    session: Session,
    branch_id: str,
    *,
    lots: list[dict[str, Any]] | None = None,
    reference_now: datetime | None = None,
) -> dict[str, Any]:
    """Order lots by FEFO (first-expired, first-out) and emit Owner alerts for lots expiring in <= 3
    days.
    """
    ensure_phase2_tables(session)
    now = reference_now or ops._now()
    candidate_lots: list[dict[str, Any]] = []

    if lots is not None:
        for entry in lots:
            exp_raw = entry["expires_at"]
            exp_dt = (
                datetime.fromisoformat(exp_raw)
                if isinstance(exp_raw, str)
                else _ensure_utc(exp_raw)
            )
            candidate_lots.append(
                {
                    "lot_code": str(entry["lot_code"]),
                    "item_id": str(entry["item_id"]),
                    "item_name": str(entry.get("item_name") or entry["item_id"]),
                    "available_quantity": Decimal(str(entry.get("available_quantity", "1"))),
                    "expires_at": _ensure_utc(exp_dt),
                }
            )
    else:
        batch_rows = (
            session.execute(
                sa.select(
                    models.production_batches.c.id,
                    models.production_batches.c.lot_code,
                    models.production_batches.c.output_item_id,
                    models.production_batches.c.actual_quantity,
                    models.production_batches.c.confirmed_at,
                    models.production_batches.c.created_at,
                    models.inventory_items.c.name.label("item_name"),
                )
                .select_from(
                    models.production_batches.join(
                        models.inventory_items,
                        models.inventory_items.c.id == models.production_batches.c.output_item_id,
                    )
                )
                .where(
                    models.production_batches.c.organization_id == ops.ORGANIZATION_ID,
                    models.production_batches.c.branch_id == branch_id,
                    models.production_batches.c.status == "confirmed",
                    models.production_batches.c.actual_quantity > 0,
                )
            )
            .mappings()
            .all()
        )
        for b in batch_rows:
            base_dt = _ensure_utc(b["confirmed_at"] or b["created_at"])
            candidate_lots.append(
                {
                    "lot_code": str(b["lot_code"]),
                    "item_id": str(b["output_item_id"]),
                    "item_name": str(b["item_name"]),
                    "available_quantity": Decimal(str(b["actual_quantity"])),
                    "expires_at": base_dt + timedelta(days=FEFO_EXPIRY_ALERT_DAYS),
                }
            )

    candidate_lots.sort(key=lambda item: (item["expires_at"], item["lot_code"]))
    fefo_lots: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []

    for lot in candidate_lots:
        if lot["available_quantity"] <= Decimal("0"):
            continue
        delta_seconds = (lot["expires_at"] - now).total_seconds()
        days_remaining = Decimal(str(delta_seconds / 86400)).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        expiring_soon = delta_seconds <= FEFO_EXPIRY_ALERT_DAYS * 86400
        lot_view = {
            "branch_id": branch_id,
            "lot_code": lot["lot_code"],
            "item_id": lot["item_id"],
            "item_name": lot["item_name"],
            "available_quantity": str(lot["available_quantity"].quantize(Decimal("0.01"))),
            "expires_at": _iso(lot["expires_at"]),
            "days_remaining": str(days_remaining),
            "expiring_soon": expiring_soon,
        }
        fefo_lots.append(lot_view)
        if expiring_soon:
            alert = emit_owner_alert(
                session,
                branch_id=branch_id,
                alert_type="lot_expiring_soon",
                severity="warning" if delta_seconds >= 0 else "critical",
                title=(
                    f"Lote por caducar (FEFO <= {FEFO_EXPIRY_ALERT_DAYS} días): {lot['lot_code']}"
                ),
                summary=(
                    f"El lote {lot['lot_code']} de {lot['item_name']} vence el "
                    f"{_iso(lot['expires_at'])} ({days_remaining} días)."
                ),
                source_type="lot",
                source_id=lot["lot_code"],
                dedup_key=f"lot_expiring:{branch_id}:{lot['lot_code']}:{_iso(lot['expires_at'])}",
                payload=lot_view,
            )
            alerts.append(alert)

    session.commit()
    return {
        "branch_id": branch_id,
        "fefo_lots": fefo_lots,
        "alerts": alerts,
    }


def evaluate_delayed_orders(
    session: Session,
    branch_id: str,
    *,
    threshold_minutes: int = DEFAULT_ORDER_DELAY_MINUTES,
    reference_now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Detect active orders exceeding preparation/delivery time threshold and emit Owner alerts."""
    ensure_phase2_tables(session)
    now = reference_now or ops._now()
    cutoff = now - timedelta(minutes=threshold_minutes)
    rows = (
        session.execute(
            sa.select(
                models.orders.c.id,
                models.orders.c.folio,
                models.orders.c.status,
                models.orders.c.order_type,
                models.orders.c.created_at,
                models.orders.c.accepted_at,
            ).where(
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
                models.orders.c.branch_id == branch_id,
                models.orders.c.status.in_(("CREATED", "ACCEPTED", "IN_PREPARATION", "READY")),
            )
        )
        .mappings()
        .all()
    )

    emitted: list[dict[str, Any]] = []
    for row in rows:
        anchor = _ensure_utc(row["accepted_at"] or row["created_at"])
        if anchor > cutoff:
            continue
        elapsed_minutes = int((now - anchor).total_seconds() // 60)
        oid = str(row["id"])
        alert = emit_owner_alert(
            session,
            branch_id=branch_id,
            alert_type="order_delayed",
            severity="warning",
            title=f"Pedido demorado: {row['folio']}",
            summary=(
                f"El pedido {row['folio']} ({row['status']}) acumula {elapsed_minutes} min "
                f"(umbral {threshold_minutes} min)."
            ),
            source_type="order",
            source_id=oid,
            dedup_key=f"order_delayed:{branch_id}:{oid}:{threshold_minutes}",
            payload={
                "branch_id": branch_id,
                "order_id": oid,
                "folio": str(row["folio"]),
                "status": str(row["status"]),
                "elapsed_minutes": elapsed_minutes,
                "threshold_minutes": threshold_minutes,
            },
        )
        emitted.append(alert)
    session.commit()
    return emitted


def authorize_and_reprint_ticket(
    session: Session,
    actor_user_id: str,
    order_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Reprint an order ticket with supervisor step-up, reprint counter, and zero sales duplication
    (CC-D12).
    """
    ensure_phase2_tables(session)
    order = (
        session.execute(
            sa.select(models.orders).where(
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
                models.orders.c.id == order_id,
            )
        )
        .mappings()
        .first()
    )
    if order is None:
        raise ops.NotFoundError("order_not_found", "Pedido no encontrado.")

    branch_id = str(order["branch_id"])
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 3:
        raise ops.BusinessError(
            "ticket_reprint_reason_required",
            "El motivo de reimpresión de ticket es obligatorio.",
        )

    supervisor_secret = str(payload.get("supervisor_code_or_password") or "").strip()
    supervisor_identity = str(payload.get("supervisor_identity") or "").strip() or None
    step_up = ops.authorize_supervisor_step_up(
        session,
        supervisor_code_or_password=supervisor_secret,
        branch_id=branch_id,
        permission_code="orders.exceptions.authorize",
        supervisor_identity=supervisor_identity,
    )
    supervisor_user_id = str(step_up["supervisor_user_id"])

    prior_reprints = int(
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.operational_control_events)
            .where(
                models.operational_control_events.c.organization_id == ops.ORGANIZATION_ID,
                models.operational_control_events.c.branch_id == branch_id,
                models.operational_control_events.c.control_type == "ticket_reprint",
                models.operational_control_events.c.resource_id == order_id,
            )
        )
        or 0
    )
    reprint_number = prior_reprints + 1
    now = ops._now()
    event_id = ops._id()

    session.execute(
        models.operational_control_events.insert().values(
            id=event_id,
            organization_id=ops.ORGANIZATION_ID,
            branch_id=branch_id,
            control_type="ticket_reprint",
            resource_id=order_id,
            actor_user_id=actor_user_id,
            supervisor_user_id=supervisor_user_id,
            sequence_number=reprint_number,
            reason=reason,
            metadata_json={
                "order_id": order_id,
                "cash_shift_id": order["cash_shift_id"],
                "folio": str(order["folio"]),
                "reprint_number": reprint_number,
                "duplicates_sale": False,
            },
            created_at=now,
        )
    )
    ops._audit(
        session,
        action="order.ticket_reprinted",
        entity_type="order",
        entity_id=order_id,
        payload={
            "branch_id": branch_id,
            "folio": str(order["folio"]),
            "reprint_number": reprint_number,
            "reason": reason,
            "authorizer_user_id": supervisor_user_id,
        },
        actor_user_id=actor_user_id,
        branch_id=branch_id,
    )
    emit_owner_alert(
        session,
        branch_id=branch_id,
        alert_type="ticket_reprint",
        severity="info" if reprint_number == 1 else "warning",
        title=f"Reimpresión #{reprint_number} de ticket: {order['folio']}",
        summary=(
            f"Ticket del pedido {order['folio']} reimpreso (#{reprint_number}) con autorización "
            f"de encargado. Motivo: {reason}."
        ),
        source_type="order",
        source_id=order_id,
        dedup_key=f"ticket_reprint:{order_id}:{reprint_number}",
        payload={
            "branch_id": branch_id,
            "order_id": order_id,
            "folio": str(order["folio"]),
            "reprint_number": reprint_number,
            "actor_user_id": actor_user_id,
            "authorizer_user_id": supervisor_user_id,
            "reason": reason,
            "duplicates_sale": False,
        },
    )
    session.commit()
    return {
        "event_id": event_id,
        "order_id": order_id,
        "branch_id": branch_id,
        "folio": str(order["folio"]),
        "reprint_number": reprint_number,
        "is_reprint": True,
        "duplicates_sale": False,
        "authorized_by_user_id": supervisor_user_id,
        "reason": reason,
        "reprinted_at": _iso(now),
    }


def open_cash_drawer_no_sale(
    session: Session,
    actor_user_id: str,
    shift_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Open the cash drawer without a sale, requiring supervisor step-up, reason, audit, and Owner
    alert.
    """
    ensure_phase2_tables(session)
    shift = (
        session.execute(
            sa.select(models.cash_shifts).where(
                models.cash_shifts.c.organization_id == ops.ORGANIZATION_ID,
                models.cash_shifts.c.id == shift_id,
            )
        )
        .mappings()
        .first()
    )
    if shift is None:
        raise ops.NotFoundError("cash_shift_not_found", "Turno de caja no encontrado.")

    branch_id = str(shift["branch_id"])
    reason = str(payload.get("reason") or "").strip()
    if len(reason) < 3:
        raise ops.BusinessError(
            "drawer_open_reason_required",
            "El motivo de apertura de cajón sin venta es obligatorio.",
        )

    supervisor_secret = str(payload.get("supervisor_code_or_password") or "").strip()
    supervisor_identity = str(payload.get("supervisor_identity") or "").strip() or None
    step_up = ops.authorize_supervisor_step_up(
        session,
        supervisor_code_or_password=supervisor_secret,
        branch_id=branch_id,
        permission_code="cash.user_cut.finalize",
        supervisor_identity=supervisor_identity,
    )
    supervisor_user_id = str(step_up["supervisor_user_id"])

    prior_opens = int(
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.operational_control_events)
            .where(
                models.operational_control_events.c.organization_id == ops.ORGANIZATION_ID,
                models.operational_control_events.c.branch_id == branch_id,
                models.operational_control_events.c.control_type == "cash_drawer_no_sale_open",
                models.operational_control_events.c.resource_id == shift_id,
            )
        )
        or 0
    )
    sequence_number = prior_opens + 1
    now = ops._now()
    event_id = ops._id()

    session.execute(
        models.operational_control_events.insert().values(
            id=event_id,
            organization_id=ops.ORGANIZATION_ID,
            branch_id=branch_id,
            control_type="cash_drawer_no_sale_open",
            resource_id=shift_id,
            actor_user_id=actor_user_id,
            supervisor_user_id=supervisor_user_id,
            sequence_number=sequence_number,
            reason=reason,
            metadata_json={
                "cash_shift_id": shift_id,
                "register_code": str(shift["register_code"]),
                "sequence_number": sequence_number,
            },
            created_at=now,
        )
    )
    ops._audit(
        session,
        action="cash_drawer.opened_no_sale",
        entity_type="cash_shift",
        entity_id=shift_id,
        payload={
            "branch_id": branch_id,
            "register_code": str(shift["register_code"]),
            "sequence_number": sequence_number,
            "reason": reason,
            "authorizer_user_id": supervisor_user_id,
        },
        actor_user_id=actor_user_id,
        branch_id=branch_id,
    )
    emit_owner_alert(
        session,
        branch_id=branch_id,
        alert_type="cash_drawer_no_sale_open",
        severity="warning",
        title=f"Apertura de cajón sin venta ({shift['register_code']})",
        summary=(
            f"Apertura #{sequence_number} de cajón sin venta en caja {shift['register_code']}. "
            f"Motivo: {reason}."
        ),
        source_type="cash_shift",
        source_id=shift_id,
        dedup_key=f"drawer_no_sale:{shift_id}:{sequence_number}",
        payload={
            "branch_id": branch_id,
            "cash_shift_id": shift_id,
            "register_code": str(shift["register_code"]),
            "sequence_number": sequence_number,
            "actor_user_id": actor_user_id,
            "authorizer_user_id": supervisor_user_id,
            "reason": reason,
        },
    )
    session.commit()
    return {
        "event_id": event_id,
        "cash_shift_id": shift_id,
        "branch_id": branch_id,
        "register_code": str(shift["register_code"]),
        "sequence_number": sequence_number,
        "authorized_by_user_id": supervisor_user_id,
        "reason": reason,
        "opened_at": _iso(now),
    }
