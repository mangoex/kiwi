"""CORTE-CIEGO-001 Phases 3, 5 & 6: Owner alerts inbox, recipient delegation, and channel retry."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.blind_cash_phase2_schema import ensure_phase2_tables
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock

ALERT_TYPES = frozenset(
    {
        "cash_cut_difference",
        "order_discount_courtesy_cancellation",
        "inventory_below_minimum",
        "product_margin_below_threshold",
        "high_waste",
        "consumption_variance",
        "lot_expiring_soon",
        "order_delayed",
        "ticket_reprint",
        "cash_drawer_no_sale_open",
    }
)

ALERT_DATASET_MAP: dict[str, str] = {
    "cash_cut_difference": "cash.cuts",
    "order_discount_courtesy_cancellation": "sales",
    "inventory_below_minimum": "reconciliation",
    "product_margin_below_threshold": "reconciliation",
    "high_waste": "reconciliation",
    "consumption_variance": "reconciliation",
    "lot_expiring_soon": "reconciliation",
    "order_delayed": "sales",
    "ticket_reprint": "sales",
    "cash_drawer_no_sale_open": "cash.shifts",
}

ChannelSender = Callable[[dict[str, Any]], None]
_channel_sender: ChannelSender | None = None


def set_alert_channel_sender(sender: ChannelSender | None) -> None:
    """Configure or reset the external notification channel adapter (for tests or runtime)."""
    global _channel_sender
    _channel_sender = sender


def emit_owner_alert(
    session: Session,
    *,
    branch_id: str,
    alert_type: str,
    severity: str,
    title: str,
    payload: dict[str, Any],
    resource_type: str | None = None,
    resource_id: str | None = None,
    dedupe_key: str | None = None,
    source_type: str | None = None,
    source_id: str | None = None,
    dedup_key: str | None = None,
    summary: str | None = None,
    organization_id: str | None = None,
) -> dict[str, Any]:
    """Persist an Owner alert idempotently and attempt non-blocking channel delivery."""
    ensure_phase2_tables(session)
    org_id = organization_id or ops.ORGANIZATION_ID
    r_type = resource_type or source_type or "resource"
    r_id = resource_id or source_id or ""
    d_key = dedupe_key or dedup_key or f"{alert_type}:{branch_id}:{r_id}"
    full_payload = {**payload, **({"summary": summary} if summary else {})}
    if alert_type not in ALERT_TYPES:
        raise ops.BusinessError("alert_type_invalid", f"Unsupported alert type: {alert_type}")
    dataset = ALERT_DATASET_MAP.get(alert_type, "reconciliation")
    table = models.owner_alerts
    existing = (
        session.execute(
            sa.select(table).where(
                table.c.organization_id == org_id,
                table.c.dedupe_key == d_key,
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return dict(existing)

    now = ops._now()
    alert_id = ops._id()
    delivery_status = "SENT"
    delivery_attempts = 1
    last_error: str | None = None

    if _channel_sender is not None:
        try:
            _channel_sender(
                {
                    "id": alert_id,
                    "organization_id": org_id,
                    "branch_id": branch_id,
                    "alert_type": alert_type,
                    "severity": severity,
                    "resource_type": r_type,
                    "resource_id": r_id,
                    "title": title,
                    "payload": full_payload,
                }
            )
        except Exception as exc:
            # Channel failure must never block or roll back the domain operation (CC-D06).
            delivery_status = "FAILED_RETRYING"
            last_error = str(exc)[:450] or "channel_delivery_failed"

    row = {
        "id": alert_id,
        "organization_id": org_id,
        "branch_id": branch_id,
        "alert_type": alert_type,
        "severity": severity,
        "dataset": dataset,
        "resource_type": r_type,
        "resource_id": r_id,
        "dedupe_key": d_key,
        "title": title,
        "payload": full_payload,
        "delivery_status": delivery_status,
        "delivery_attempts": delivery_attempts,
        "last_delivery_error": last_error,
        "created_at": now,
        "updated_at": now,
        "acknowledged_at": None,
        "acknowledged_by_user_id": None,
    }
    session.execute(table.insert().values(**row))
    return row


def record_discount_or_cancellation_alert(
    session: Session,
    *,
    branch_id: str,
    order_id: str,
    event_kind: str,
    actor_user_id: str,
    supervisor_user_id: str | None,
    reason: str,
    amount_cents: int,
    dedupe_suffix: str = "",
) -> dict[str, Any]:
    """Emit Phase 3 alert for order discount, courtesy, amendment, or cancellation."""
    if event_kind not in {"discount", "courtesy", "amendment", "cancellation"}:
        raise ops.BusinessError("alert_event_kind_invalid", "Invalid order alert event kind")
    suffix = f":{dedupe_suffix}" if dedupe_suffix else ""
    return emit_owner_alert(
        session,
        branch_id=branch_id,
        alert_type="order_discount_courtesy_cancellation",
        severity="warning" if event_kind in {"discount", "amendment"} else "critical",
        resource_type="order",
        resource_id=order_id,
        dedupe_key=f"order_exc:{order_id}:{event_kind}{suffix}",
        title=f"Alerta de {event_kind} en pedido {order_id}",
        payload={
            "order_id": order_id,
            "event_kind": event_kind,
            "actor_user_id": actor_user_id,
            "supervisor_user_id": supervisor_user_id,
            "reason": reason,
            "amount_cents": int(amount_cents),
        },
    )


def retry_pending_alerts(
    session: Session,
    actor: str,
    *,
    branch_id: str | None = None,
) -> dict[str, Any]:
    """Retry alerts in PENDING or FAILED_RETRYING state without duplicating events."""
    ensure_phase2_tables(session)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    version = authority._begin()
    if not authority._owner(version):
        deny()

    table = models.owner_alerts
    query = sa.select(table).where(
        table.c.organization_id == ops.ORGANIZATION_ID,
        table.c.delivery_status.in_(("PENDING", "FAILED_RETRYING")),
    )
    if branch_id is not None:
        authority._branches([branch_id])
        query = query.where(table.c.branch_id == branch_id)

    rows = list(session.execute(query.order_by(table.c.created_at, table.c.id)).mappings())
    sent_count = 0
    failed_count = 0
    now = ops._now()

    for row in rows:
        attempts = int(row["delivery_attempts"]) + 1
        status = "SENT"
        error: str | None = None
        if _channel_sender is not None:
            try:
                _channel_sender(dict(row))
            except Exception as exc:
                status = "FAILED_RETRYING"
                error = str(exc)[:450] or "channel_delivery_failed"
        if status == "SENT":
            sent_count += 1
        else:
            failed_count += 1
        session.execute(
            table.update()
            .where(table.c.id == row["id"], table.c.organization_id == ops.ORGANIZATION_ID)
            .values(
                delivery_status=status,
                delivery_attempts=attempts,
                last_delivery_error=error,
                updated_at=now,
            )
        )
    session.commit()
    return {
        "retried_count": len(rows),
        "sent_count": sent_count,
        "failed_count": failed_count,
    }


def configure_alert_recipient(
    session: Session,
    actor: str,
    *,
    branch_id: str,
    user_id: str,
    alert_type: str,
    channel: str = "in_app",
    is_active: bool = True,
) -> dict[str, Any]:
    """Owner-only designation of a delegate recipient for a specific branch and alert type."""
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    version = authority._begin()
    if not authority._owner(version):
        deny()
    authority._branches([branch_id])
    if alert_type not in ALERT_TYPES:
        raise ops.BusinessError("alert_type_invalid", f"Unsupported alert type: {alert_type}")
    if channel not in {"in_app", "whatsapp", "webhook"}:
        raise ops.BusinessError("alert_channel_invalid", "Unsupported alert channel")

    table = models.owner_alert_recipients
    existing = (
        session.execute(
            sa.select(table).where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.branch_id == branch_id,
                table.c.user_id == user_id,
                table.c.alert_type == alert_type,
                table.c.channel == channel,
            )
        )
        .mappings()
        .first()
    )
    now = ops._now()
    if existing is not None:
        session.execute(
            table.update().where(table.c.id == existing["id"]).values(is_active=is_active)
        )
        session.commit()
        return {**dict(existing), "is_active": is_active}

    row = {
        "id": ops._id(),
        "organization_id": ops.ORGANIZATION_ID,
        "branch_id": branch_id,
        "user_id": user_id,
        "alert_type": alert_type,
        "channel": channel,
        "is_active": is_active,
        "created_by_user_id": actor,
        "created_at": now,
    }
    session.execute(table.insert().values(**row))
    session.commit()
    return row


def list_owner_alerts(
    session: Session,
    actor: str,
    *,
    branch_id: str,
    alert_type: str | None = None,
) -> list[dict[str, Any]]:
    """Return alerts authorized for Owner or an explicitly designated delegate with active scope."""
    ensure_phase2_tables(session)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    version = authority._begin()
    authority._branches([branch_id])
    is_owner = authority._owner(version)

    table = models.owner_alerts
    query = sa.select(table).where(
        table.c.organization_id == ops.ORGANIZATION_ID,
        table.c.branch_id == branch_id,
    )
    if alert_type is not None:
        query = query.where(table.c.alert_type == alert_type)

    rows = [
        dict(row)
        for row in session.execute(query.order_by(table.c.created_at.desc(), table.c.id)).mappings()
    ]
    if is_owner:
        return rows

    # A delegate requires BOTH active financial dataset grant AND explicit recipient designation.
    recipients = models.owner_alert_recipients
    designated_types: set[str] = set(
        session.scalars(
            sa.select(recipients.c.alert_type).where(
                recipients.c.organization_id == ops.ORGANIZATION_ID,
                recipients.c.branch_id == branch_id,
                recipients.c.user_id == actor,
                recipients.c.is_active.is_(True),
            )
        ).all()
    )
    if not designated_types:
        deny()
    if alert_type is not None and alert_type not in designated_types:
        deny()

    required_datasets = {
        ALERT_DATASET_MAP.get(t, "reconciliation")
        for t in ({alert_type} if alert_type is not None else designated_types)
    }
    authority.require_financial([(branch_id, ds) for ds in required_datasets])
    return [row for row in rows if row["alert_type"] in designated_types]


def acknowledge_owner_alert(
    session: Session,
    actor: str,
    alert_id: str,
) -> dict[str, Any]:
    """Acknowledge an alert (Owner only)."""
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    version = authority._begin()
    if not authority._owner(version):
        deny()

    table = models.owner_alerts
    row = (
        session.execute(
            sa.select(table).where(
                table.c.id == alert_id,
                table.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ops.NotFoundError("owner_alert_not_found", "Owner alert was not found")

    now = ops._now()
    session.execute(
        table.update()
        .where(table.c.id == alert_id, table.c.organization_id == ops.ORGANIZATION_ID)
        .values(
            delivery_status="ACKNOWLEDGED",
            acknowledged_at=now,
            acknowledged_by_user_id=actor,
            updated_at=now,
        )
    )
    session.commit()
    return {
        **dict(row),
        "delivery_status": "ACKNOWLEDGED",
        "acknowledged_at": now,
        "acknowledged_by_user_id": actor,
        "updated_at": now,
    }
