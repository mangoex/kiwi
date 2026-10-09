"""Online confirmation intent; persisted document and cash links identify replays."""

from collections import Counter
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import BusinessError


def original_effects(
    session: Session, purchase: Any
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Validate immutable originals before replaying or compensating a confirmed purchase."""
    from restaurant_os.operations import _branch_warehouse_id, _cost, _money, _quantity
    from restaurant_os.purchase_workspace import validate_purchase_payment

    validate_purchase_payment(purchase["payment_method"], purchase["paid_from_cash"])
    warehouse = _branch_warehouse_id(session, purchase["branch_id"])
    lines = (
        session.execute(
            sa.select(models.purchase_document_lines).where(
                models.purchase_document_lines.c.purchase_document_id == purchase["id"]
            )
        )
        .mappings()
        .all()
    )
    receipts = [
        dict(row)
        for row in session.execute(
            sa.select(models.inventory_movements).where(
                models.inventory_movements.c.movement_type == "PURCHASE_RECEIPT",
                sa.or_(
                    models.inventory_movements.c.source_id == purchase["id"],
                    models.inventory_movements.c.document_id == purchase["id"],
                ),
            )
        ).mappings()
    ]
    valid = bool(lines) and all(
        row["organization_id"] == purchase["organization_id"]
        and row["branch_id"] == purchase["branch_id"]
        and row["warehouse_id"] == warehouse
        and row["document_id"] == purchase["id"]
        and row["document_type"] == purchase["document_type"]
        and row["source_id"] == purchase["id"]
        and row["source_type"] == "purchase"
        and row["status"] == "confirmed"
        and row["reversal_of_id"] is None
        and row["actor_user_id"] == purchase["confirmed_by"]
        for row in receipts
    )
    if not all(
        isinstance(line["presentation_snapshot"], dict)
        and line["presentation_snapshot"].get("base_unit_id")
        for line in lines
    ):
        raise BusinessError(
            "purchase_effect_integrity_conflict", "Purchase line snapshot is inconsistent"
        )
    expected = Counter(
        (
            line["item_id"],
            line["presentation_snapshot"]["base_unit_id"],
            _quantity(line["base_quantity"]),
            _cost(line["cost_per_base_unit"]),
            _money(line["inventory_cost"]),
        )
        for line in lines
    )
    actual = Counter(
        (
            row["item_id"],
            row["unit_id"],
            _quantity(row["quantity_delta"]),
            _cost(row["unit_cost"]),
            _money(row["total_cost"]),
        )
        for row in receipts
    )
    valid = valid and actual == expected
    cash_rows = (
        session.execute(
            sa.select(models.cash_movements).where(
                sa.or_(
                    models.cash_movements.c.id == purchase["cash_movement_id"],
                    sa.and_(
                        models.cash_movements.c.source_id == purchase["id"],
                        sa.func.lower(models.cash_movements.c.source_type) == "purchase",
                    ),
                )
            )
        )
        .mappings()
        .all()
    )
    cash = next((row for row in cash_rows if row["id"] == purchase["cash_movement_id"]), None)
    if purchase["paid_from_cash"]:
        shift = (
            session.execute(
                sa.select(models.cash_shifts).where(
                    models.cash_shifts.c.id == (cash["cash_shift_id"] if cash else None)
                )
            )
            .mappings()
            .first()
        )
        valid = (
            valid
            and len(cash_rows) == 1
            and cash is not None
            and shift is not None
            and (
                cash["organization_id"] == purchase["organization_id"]
                and cash["branch_id"] == purchase["branch_id"]
                and cash["source_id"] == purchase["id"]
                and str(cash["source_type"]).upper() == "PURCHASE"
                and cash["movement_type"] == "withdrawal"
                and cash["status"] == "confirmed"
                and cash["amount_cents"]
                == int(
                    (_money(purchase["total"]) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
                )
                and cash["reversal_of_id"] is None
                and cash["compensates_movement_id"] is None
                and cash["actor_user_id"] == purchase["confirmed_by"]
                and shift["organization_id"] == purchase["organization_id"]
                and shift["branch_id"] == purchase["branch_id"]
            )
        )
    else:
        valid = valid and purchase["cash_movement_id"] is None and not cash_rows
    if not valid:
        raise BusinessError(
            "purchase_effect_integrity_conflict", "Purchase original effects are inconsistent"
        )
    return receipts, dict(cash) if cash is not None else None


def context_values(
    purchase: Any, body: dict[str, Any] | None, register_id: str | None
) -> tuple[str, str | None]:
    context = body or {}
    allowed = {"branch_id", "register_id", "expected_cash_shift_id", "idempotency_key"}
    if set(context) - allowed:
        raise BusinessError("workspace_payload_invalid", "Invalid confirmation fields")
    for field in context:
        value = context[field]
        bound = 180 if field == "idempotency_key" else (32 if field == "register_id" else 36)
        if not isinstance(value, str) or not value.strip() or len(value) > bound:
            raise BusinessError("workspace_payload_invalid", "Invalid confirmation context")
    register = context.get("register_id", register_id or "").strip()
    expected = context.get("expected_cash_shift_id")
    if "branch_id" in context:
        if context["branch_id"] != purchase["branch_id"]:
            raise BusinessError("purchase_cash_context_changed", "Purchase branch changed")
        if purchase["paid_from_cash"]:
            if not register or expected is None:
                raise BusinessError("workspace_payload_invalid", "Reviewed cash shift is required")
        elif "register_id" in context or expected is not None:
            raise BusinessError("workspace_payload_invalid", "Non-cash purchase cannot select cash")
    elif expected is not None:
        raise BusinessError("workspace_payload_invalid", "Reviewed branch is required")
    return register, expected


def verify_replay(
    session: Session, purchase: Any, actor: str, register: str, expected: str | None
) -> None:
    if purchase["confirmed_by"] != actor:
        raise BusinessError("idempotency_key_conflict", "Confirmation actor does not match")
    original_effects(session, purchase)
    if not purchase["paid_from_cash"]:
        return
    original = (
        session.execute(
            sa.select(models.cash_movements.c.cash_shift_id, models.cash_shifts.c.register_code)
            .join(
                models.cash_shifts, models.cash_shifts.c.id == models.cash_movements.c.cash_shift_id
            )
            .where(models.cash_movements.c.id == purchase["cash_movement_id"])
        )
        .mappings()
        .first()
    )
    if (
        not original
        or register != original["register_code"]
        or (expected is not None and expected != original["cash_shift_id"])
    ):
        raise BusinessError("idempotency_key_conflict", "Confirmation cash context does not match")
