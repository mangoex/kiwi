"""Closed financial response schemas; new fields require an explicit contract decision."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class FinancialRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def utc_timestamp(cls, value: Any) -> Any:
        if isinstance(value, datetime):
            return (
                value.replace(tzinfo=timezone.utc)
                if value.tzinfo is None
                else value.astimezone(timezone.utc)
            )
        return value


class CashSummaryV2(FinancialRecord):
    # Old snapshots may omit fields. exclude_unset preserves that historical absence.
    sales_total_cents: int | None = None
    payment_total_cents: int | None = None
    cash_payment_cents: int | None = None
    opening_cash_cents: int | None = None
    expected_cash_cents: int | None = None
    deposit_cents: int | None = None
    withdrawal_cents: int | None = None
    excluded_movement_count: int | None = None
    confirmed_payment_count: int | None = None
    closed_order_count: int | None = None


class FinancialShiftV2(FinancialRecord):
    id: str
    organization_id: str
    branch_id: str
    register_code: str
    cashier_user_id: str | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    created_at: datetime
    opening_cash_cents: int


class FinancialClosureV2(FinancialRecord):
    id: str
    closed_at: datetime
    closed_by_user_id: str
    summary_snapshot: CashSummaryV2


class FinancialCutV2(FinancialRecord):
    id: str
    organization_id: str
    branch_id: str
    cash_shift_id: str
    register_code_snapshot: str
    cashier_user_id: str
    timezone: str
    period_start: datetime
    period_end: datetime
    status: str
    version: int
    created_by_user_id: str
    finalized_by_user_id: str | None
    created_at: datetime
    counted_at: datetime | None
    finalized_at: datetime | None
    opening_cash_cents: int
    cash_payment_cents: int | None
    deposit_cents: int | None
    withdrawal_cents: int | None
    expected_cash_cents: int | None
    counted_cash_cents: int | None
    difference_cents: int | None
    tolerance_cents: int


class CutOperationV2(FinancialRecord):
    id: str
    cash_cut_id: str
    operation_type: str
    operation_id: str
    signed_amount_cents: int
    occurred_at: datetime


class CutCompensationV2(FinancialRecord):
    id: str
    cash_cut_id: str
    reopen_request_id: str
    corrected_counted_cash_cents: int
    expected_cash_cents: int
    tolerance_cents: int
    corrected_difference_cents: int
    difference_delta_cents: int
    created_by_user_id: str
    created_at: datetime


class FinancialProjection(FinancialRecord):
    projection: Literal["financial"]
    schema_version: Literal[2]
    policy_version: int


class CashShiftFinancialV2(FinancialProjection):
    cash_shift: FinancialShiftV2
    closure: FinancialClosureV2 | None
    current_summary: CashSummaryV2


class UserCashCutFinancialV2(FinancialProjection):
    cash_cut: FinancialCutV2
    operations: list[CutOperationV2]
    compensations: list[CutCompensationV2]


class CashShiftSummaryFinancialV2(FinancialProjection):
    resource_id: str
    closure: FinancialClosureV2 | None
    current_summary: CashSummaryV2
