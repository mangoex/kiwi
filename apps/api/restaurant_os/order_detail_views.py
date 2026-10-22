"""Closed per-order monetary view, excluding raw history, recipes and audit payloads."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import Field, ValidationError

from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.order_read_authority import OrderReadContext


class OrderContextV2(FinancialRecord):
    source_kind: Literal[
        "financial", "order_acceptance", "order_amendment", "delivery_assignment", "approved_reopen"
    ]
    source_id: str
    order_version: int
    authorization_version: int


class OrderModifierV2(FinancialRecord):
    group_id: str | None = None
    group_name: str | None = None
    option_id: str
    option_name: str | None = None
    kind: str | None = None
    effect_type: str | None = None
    selection_kind: str | None = None
    portions: int | None = None
    text: str | None = None
    comment_preset_id: str | None = None
    extra_id: str | None = None
    portion_count: int | None = None
    portion_quantity: Decimal | None = None
    sale_price_cents_per_portion: int | None = None
    price_delta_cents: int | None = None
    applied_price_delta_cents: int | None = None
    catalog_price_delta_cents: int | None = None
    included: bool | None = None
    kitchen_text: str | None = None
    station: str | None = None
    component_product_id: str | None = None
    component_product_name: str | None = None
    component_quantity: Decimal | None = None


class OrderLineV2(FinancialRecord):
    id: str
    order_id: str
    product_id: str
    product_name: str
    quantity: int
    unit_price_cents: int
    line_total_cents: int
    modifier_total_cents: int
    station: str
    line_notes: str | None = None
    status: str
    revision: int = 1
    family_id_snapshot: str | None = None
    family_name_snapshot: str | None = None
    selected_modifiers: list[OrderModifierV2]


class OrderPaymentV2(FinancialRecord):
    id: str
    method: str
    status: str
    amount_cents: int
    currency: str
    confirmed_at: datetime


class OrderTaskV2(FinancialRecord):
    id: str
    order_line_id: str
    station: str
    status: str
    product_name: str
    quantity: int
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None


class OrderDeliveryV2(FinancialRecord):
    id: str
    driver_id: str
    driver_name_snapshot: str
    status: str
    assigned_at: datetime


class OrderDeliverySelectionV2(FinancialRecord):
    mode: Literal["AUTO", "REMOVED", "SELECTED"]
    tariff_id: str | None = None


class OrderChargeV2(FinancialRecord):
    selection: OrderDeliverySelectionV2
    state: str
    list_cents: int
    charged_cents: int
    net_cents: int
    tax_cents: int
    eligible_subtotal_cents: int
    free_threshold_cents: int | None
    currency: str
    tariff_name: str | None


class OrderDetailV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["order"] = "order"
    policy_version: int
    read_context: OrderContextV2
    id: str
    branch_id: str
    cash_shift_id: str | None
    folio: str
    channel: str
    status: str
    order_type: str
    version: int
    total_cents: int
    currency: str
    customer_label: str | None
    customer_phone: str | None = None
    delivery_address: str | None = None
    delivery_notes: str | None = None
    payment_method_intent: str | None = None
    payment_status: str
    editable: bool
    edit_block_reason: str | None
    reopen_eligible: bool
    active_reopen_request_status: str | None
    created_at: datetime
    lines: list[OrderLineV2] = Field(default_factory=list)
    payments: list[OrderPaymentV2] = Field(default_factory=list)
    production_tasks: list[OrderTaskV2] = Field(default_factory=list)
    delivery_assignment: OrderDeliveryV2 | None
    delivery_charge: OrderChargeV2 | None


def project_order_detail(raw: dict[str, Any], context: OrderReadContext) -> dict[str, Any]:
    def fields(model: type[FinancialRecord], data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise ops.BusinessError("order_projection_unavailable", "Order detail is unavailable")
        return {name: data[name] for name in model.model_fields if name in data}

    lines = []
    for line in raw["lines"]:
        projected = fields(OrderLineV2, line)
        modifiers = line.get("selected_modifiers", [])
        if not isinstance(modifiers, list):
            raise ops.BusinessError("order_projection_unavailable", "Order detail is unavailable")
        projected["selected_modifiers"] = [
            fields(OrderModifierV2, modifier) for modifier in modifiers
        ]
        lines.append(projected)
    data = fields(OrderDetailV2, raw)
    charge = raw.get("delivery_charge")
    assignment = raw.get("delivery_assignment")
    tariff = charge.get("tariff") if isinstance(charge, dict) else None
    if tariff is not None and not isinstance(tariff, dict):
        raise ops.BusinessError("order_projection_unavailable", "Order detail is unavailable")
    data.update(
        policy_version=context.policy_version,
        version=context.order_version,
        read_context={
            "source_kind": context.source_kind,
            "source_id": context.source_id,
            "order_version": context.order_version,
            "authorization_version": context.authorization_version,
        },
        lines=lines,
        payments=[fields(OrderPaymentV2, payment) for payment in raw.get("payments", [])],
        production_tasks=[fields(OrderTaskV2, task) for task in raw.get("production_tasks", [])],
        delivery_assignment=fields(OrderDeliveryV2, assignment) if assignment else None,
        delivery_charge={
            **fields(OrderChargeV2, charge),
            "tariff_name": tariff.get("name") if tariff else None,
        }
        if charge
        else None,
    )
    try:
        return OrderDetailV2.model_validate(data).model_dump(mode="json")
    except ValidationError:
        # Pydantic's diagnostic includes captured input. Do not expose that payload
        # in a transport exception or substitute defaults for a malformed receipt.
        raise ops.BusinessError(
            "order_projection_unavailable", "Order detail is unavailable"
        ) from None
