"""Metadata-only order browsing. Individual monetary detail has separate authority."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from restaurant_os import models
from restaurant_os.cash_views import Projection


class OrderAccountOperationalV2(Projection):
    id: str
    folio: str
    branch_id: str
    cash_shift_id: str | None
    register_code: str | None
    status: str
    service_type: str
    created_at: datetime
    customer_label: str | None
    is_public_intent: bool
    version: int


def account_columns(*, intent: bool = False) -> list[Any]:
    table = models.public_order_intents if intent else models.orders
    fields = (
        ("id", "branch_id", "public_reference", "status", "order_type", "created_at", "version")
        if intent
        else (
            "id",
            "branch_id",
            "cash_shift_id",
            "folio",
            "status",
            "order_type",
            "created_at",
            "owner_name",
            "version",
        )
    )
    return [
        *(table.c[name] for name in fields),
        table.c.customer_snapshot["name"].as_string().label("customer_label"),
        *([] if intent else [models.cash_shifts.c.register_code]),
    ]


def operational_account(
    row: Mapping[str, Any],
    policy_version: int,
    *,
    intent: bool = False,
) -> dict[str, Any]:
    return OrderAccountOperationalV2(
        id=str(row["id"]),
        folio=f"WEB-{row['public_reference'][-6:]}" if intent else row["folio"],
        branch_id=row["branch_id"],
        cash_shift_id=None if intent else row["cash_shift_id"],
        register_code="WEB" if intent else row["register_code"],
        status="PENDING" if intent else row["status"],
        service_type=row["order_type"],
        created_at=row["created_at"],
        customer_label=row["customer_label"] or (None if intent else row["owner_name"]),
        is_public_intent=intent,
        version=int(row["version"]),
        policy_version=policy_version,
    ).model_dump(mode="json")
