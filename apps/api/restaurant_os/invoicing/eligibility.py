"""Read an exact, immutable payment projection before reserving a fiscal intention."""

from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import BusinessError, NotFoundError


@dataclass(frozen=True)
class FiscalPaymentSnapshot:
    order_id: str
    order_version: int
    total_cents: int
    paid_cents: int
    currency: str
    payment_ids: tuple[str, ...]
    correction_ids: tuple[str, ...]
    adjustment_ids: tuple[str, ...]


def payment_snapshot(
    session: Session, organization_id: str, branch_id: str, order_id: str
) -> FiscalPaymentSnapshot:
    order = (
        session.execute(
            sa.select(models.orders)
            .where(
                models.orders.c.id == order_id,
                models.orders.c.organization_id == organization_id,
                models.orders.c.branch_id == branch_id,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not order:
        raise NotFoundError("fiscal_order_not_found", "Order not found")
    if order["status"] == "CANCELLED":
        raise BusinessError("fiscal_order_cancelled", "Cancelled orders cannot be invoiced")
    if type(order["total_cents"]) is not int or type(order["version"]) is not int:
        raise BusinessError("fiscal_payment_evidence_invalid", "Order source requires review")
    payments = list(
        session.execute(
            sa.select(models.payments)
            .where(
                models.payments.c.order_id == order_id,
                models.payments.c.organization_id == organization_id,
                models.payments.c.branch_id == branch_id,
                models.payments.c.currency == order["currency"],
                models.payments.c.status == "CONFIRMED",
            )
            .order_by(models.payments.c.id)
            .with_for_update()
        ).mappings()
    )
    payment_ids = tuple(str(row["id"]) for row in payments)
    if any(type(row["amount_cents"]) is not int or row["amount_cents"] < 0 for row in payments):
        raise BusinessError("fiscal_payment_evidence_invalid", "Payment source requires review")
    original_paid = sum(row["amount_cents"] for row in payments)
    corrections = list(
        session.execute(
            sa.select(models.order_corrections)
            .where(
                models.order_corrections.c.order_id == order_id,
            )
            .order_by(models.order_corrections.c.applied_at, models.order_corrections.c.id)
            .with_for_update()
        ).mappings()
    )
    adjustments = (
        list(
            session.execute(
                sa.select(models.order_payment_adjustments)
                .where(
                    models.order_payment_adjustments.c.correction_id.in_(
                        [row["id"] for row in corrections]
                    ),
                )
                .order_by(models.order_payment_adjustments.c.id)
                .with_for_update()
            ).mappings()
        )
        if corrections
        else []
    )
    by_correction = {str(row["correction_id"]): row for row in adjustments}
    for correction in corrections:
        adjustment = by_correction.get(str(correction["id"]))
        delta = correction["settlement_delta_cents"]
        after = correction["after_snapshot"]
        if (
            correction["organization_id"] != organization_id
            or correction["branch_id"] != branch_id
            or correction["currency"] != order["currency"]
            or correction["status"] != "APPLIED"
            or type(correction["corrected_total_cents"]) is not int
            or type(delta) is not int
            or int(correction["resulting_order_version"]) > int(order["version"])
            or not isinstance(after, dict)
            or type(after.get("total_cents")) is not int
            or after["total_cents"] != correction["corrected_total_cents"]
            or delta != correction["corrected_total_cents"] - original_paid
            or (delta == 0 and adjustment is not None)
            or (
                delta != 0
                and (
                    adjustment is None
                    or adjustment["original_payment_id"] not in payment_ids
                    or adjustment["currency"] != order["currency"]
                    or adjustment["status"] != "CONFIRMED"
                    or type(adjustment["amount_cents"]) is not int
                    or adjustment["amount_cents"] != abs(delta)
                    or adjustment["adjustment_type"] != ("CHARGE" if delta > 0 else "REFUND")
                )
            )
        ):
            raise BusinessError(
                "fiscal_payment_evidence_invalid", "Payment correction evidence requires review"
            )
    total = int(corrections[-1]["corrected_total_cents"] if corrections else order["total_cents"])
    paid = original_paid + sum(
        int(row["amount_cents"]) * (1 if row["adjustment_type"] == "CHARGE" else -1)
        for row in adjustments
    )
    if not payments or paid < total:
        raise BusinessError("fiscal_order_not_fully_paid", "A fully paid order is required")
    return FiscalPaymentSnapshot(
        order_id=order_id,
        order_version=int(order["version"]),
        total_cents=total,
        paid_cents=paid,
        currency=str(order["currency"]),
        payment_ids=payment_ids,
        correction_ids=tuple(str(row["id"]) for row in corrections),
        adjustment_ids=tuple(str(row["id"]) for row in adjustments),
    )
