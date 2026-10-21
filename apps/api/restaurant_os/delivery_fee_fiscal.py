"""A delivery concept is independent of food; missing food tax evidence stays closed."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.delivery_fee import fee_table_available
from restaurant_os.operations import BusinessError


def service_item(snapshot: dict[str, Any], emitter_id: str) -> dict[str, Any] | None:
    if snapshot["charged_cents"] == 0:
        return None
    tariff = snapshot["tariff"]
    mapping = tariff.get("fiscal_mapping") or {}
    if (
        mapping.get("emitter_id") != emitter_id
        or not mapping.get("product_key")
        or not mapping.get("unit_key")
    ):
        raise BusinessError(
            "delivery_fiscal_mapping_required",
            "Approved delivery fiscal mapping is required for this issuer",
        )
    return {
        "quantity": 1,
        "product": {
            "description": f"Servicio de entrega a domicilio · {tariff['name']}",
            "product_key": mapping["product_key"],
            "unit_key": mapping["unit_key"],
            "price": Decimal(snapshot["charged_cents"]) / 100,
            "tax_included": True,
            "taxes": [{"type": "IVA", "rate": Decimal(tariff["tax_rate"])}],
        },
    }


def payment_charge(session: Session, order_id: str) -> dict[str, Any] | None:
    if not fee_table_available(session, "delivery_sale_snapshots"):
        return None
    snapshot = session.scalar(
        sa.select(models.delivery_sale_snapshots.c.snapshot).where(
            models.delivery_sale_snapshots.c.order_id == order_id
        )
    )
    if snapshot is None:
        return None
    correction = session.scalar(
        sa.select(models.order_corrections.c.after_snapshot)
        .where(models.order_corrections.c.order_id == order_id)
        .order_by(
            models.order_corrections.c.applied_at.desc(), models.order_corrections.c.id.desc()
        )
        .limit(1)
    )
    return dict(correction["delivery_charge"] if correction else snapshot)


def reject_aggregate_receipt(session: Session, order_ids: list[str]) -> None:
    """The legacy aggregate has no canonical food tax concepts. Never hide a delivery fee in it."""
    if not fee_table_available(session, "delivery_sale_snapshots"):
        return
    present = session.scalar(
        sa.select(models.delivery_sale_snapshots.c.id)
        .where(models.delivery_sale_snapshots.c.order_id.in_(order_ids))
        .limit(1)
    )
    if present is not None:
        raise BusinessError(
            "fiscal_concept_snapshot_required",
            "Exact food and delivery concepts must be prepared before issuance",
        )
