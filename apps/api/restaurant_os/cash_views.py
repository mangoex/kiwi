"""F1-05 cash projections. Authority precedes monetary queries and materialization."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Generic, Literal, TypeVar

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, field_validator
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import (
    CashShiftFinancialV2,
    FinancialRecord,
    UserCashCutFinancialV2,
)
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock


class Projection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    projection: Literal["operational"] = "operational"
    schema_version: Literal[2] = 2
    policy_version: int

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


class CashCommandReceiptV2(Projection):
    command_id: str
    resource_id: str
    action: str
    status: str
    version: int
    accepted_at: datetime
    replay: bool
    correlation_id: str


class CashShiftOperationalV2(Projection):
    id: str
    organization_id: str
    branch_id: str
    register_id: str
    responsible_user_id: str | None
    status: str
    opened_at: datetime
    closed_at: datetime | None
    version: int
    closure_id: str | None


class UserCashCutOperationalV2(Projection):
    id: str
    organization_id: str
    branch_id: str
    cash_shift_id: str
    register_id: str
    responsible_user_id: str
    capturer_user_id: str | None
    status: str
    version: int
    created_at: datetime
    counted_at: datetime | None
    finalized_at: datetime | None


class OwnDeclarationV2(FinancialRecord):
    resource_id: str
    projection: Literal["own_declaration"] = "own_declaration"
    schema_version: Literal[2] = 2
    policy_version: int
    counted_cash_cents: int
    counted_at: datetime


class CurrentShiftV2(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cash_shift: CashShiftOperationalV2 | None


CashItemT = TypeVar("CashItemT", bound=BaseModel)


class CashPageV2(BaseModel, Generic[CashItemT]):
    model_config = ConfigDict(extra="forbid")
    items: list[CashItemT]
    next_cursor: str | None


SHIFT_FIELDS = (
    "id",
    "organization_id",
    "branch_id",
    "register_code",
    "cashier_user_id",
    "status",
    "opened_at",
    "closed_at",
    "created_at",
)
CUT_FIELDS = (
    "id",
    "organization_id",
    "branch_id",
    "cash_shift_id",
    "register_code_snapshot",
    "cashier_user_id",
    "timezone",
    "period_start",
    "period_end",
    "status",
    "version",
    "created_by_user_id",
    "finalized_by_user_id",
    "created_at",
    "counted_at",
    "finalized_at",
)
CUT_MONEY = (
    "opening_cash_cents",
    "cash_payment_cents",
    "deposit_cents",
    "withdrawal_cents",
    "expected_cash_cents",
    "counted_cash_cents",
    "difference_cents",
    "tolerance_cents",
)
SUMMARY_FIELDS = (
    "sales_total_cents",
    "payment_total_cents",
    "cash_payment_cents",
    "opening_cash_cents",
    "expected_cash_cents",
    "deposit_cents",
    "withdrawal_cents",
    "excluded_movement_count",
    "confirmed_payment_count",
    "closed_order_count",
)
OPERATION_FIELDS = (
    "id",
    "cash_cut_id",
    "operation_type",
    "operation_id",
    "signed_amount_cents",
    "occurred_at",
)
COMPENSATION_FIELDS = (
    "id",
    "cash_cut_id",
    "reopen_request_id",
    "corrected_counted_cash_cents",
    "expected_cash_cents",
    "tolerance_cents",
    "corrected_difference_cents",
    "difference_delta_cents",
    "created_by_user_id",
    "created_at",
)


def selected(table: sa.Table, names: tuple[str, ...]) -> Any:
    return sa.select(*(table.c[name] for name in names))


def fields(row: Mapping[Any, Any], names: tuple[str, ...]) -> dict[str, Any]:
    return {name: row[name] for name in names if name in row}


class CashViews:
    def __init__(self, session: Session, actor: str) -> None:
        self.session, self.actor = session, actor
        self.authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)

    def metadata(self, kind: str, resource_id: str) -> dict[str, Any]:
        # Read only identity/scope before authorization, never a financial row.
        self.authority._begin()
        table = models.cash_shifts if kind == "shift" else models.user_cash_cuts
        row = (
            self.session.execute(
                selected(table, ("id", "branch_id", "cashier_user_id")).where(
                    table.c.organization_id == ops.ORGANIZATION_ID, table.c.id == resource_id
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise ops.NotFoundError("cash_resource_not_found", "Cash resource was not found")
        return dict(row)

    def revision(self, branch: str) -> int:
        revision = self.authority.policy_revision(branch)
        if revision is None:
            raise ops.BusinessError("cash_policy_not_active", "Cash policy is not active")
        return revision

    def branch_reader(self, branch: str) -> bool:
        version = self.authority._begin()
        return self.authority._owner(version) or self.authority._explicit(
            "cash.user_cut.finalize",
            branch,
        )

    def require_cut_read(self, meta: Mapping[Any, Any]) -> None:
        branch = str(meta["branch_id"])
        self.authority.require_capability("cash.user_cut.operational.read", branch)
        if meta["cashier_user_id"] != self.actor and not self.branch_reader(branch):
            # A substitute may consult their own declaration/receipt, not other cuts.
            capturer = self.capturer(str(meta["id"]))
            if capturer != self.actor:
                deny()

    def capturer(self, cut_id: str) -> str | None:
        commands = models.user_cash_cut_commands
        actor = self.session.scalar(
            sa.select(commands.c.actor_user_id)
            .where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.cash_cut_id == cut_id,
                commands.c.command_type == "count",
            )
            .order_by(commands.c.created_at, commands.c.id)
            .limit(1)
        )
        return str(actor) if actor is not None else None

    def shift_projection(self, row: Mapping[Any, Any], revision: int) -> dict[str, Any]:
        closure_id = self.session.scalar(
            sa.select(models.cash_shift_closures.c.id).where(
                models.cash_shift_closures.c.organization_id == ops.ORGANIZATION_ID,
                models.cash_shift_closures.c.cash_shift_id == row["id"],
            )
        )
        return CashShiftOperationalV2(
            id=row["id"],
            organization_id=row["organization_id"],
            branch_id=row["branch_id"],
            register_id=row["register_code"],
            responsible_user_id=row["cashier_user_id"],
            status=row["status"],
            opened_at=row["opened_at"],
            closed_at=row["closed_at"],
            version=2 if row["closed_at"] else 1,
            closure_id=closure_id,
            policy_version=revision,
        ).model_dump(mode="json")

    def cut_projection(self, row: Mapping[Any, Any], revision: int) -> dict[str, Any]:
        return UserCashCutOperationalV2(
            id=row["id"],
            organization_id=row["organization_id"],
            branch_id=row["branch_id"],
            cash_shift_id=row["cash_shift_id"],
            register_id=row["register_code_snapshot"],
            responsible_user_id=row["cashier_user_id"],
            capturer_user_id=self.capturer(row["id"]),
            status=row["status"],
            version=row["version"],
            created_at=row["created_at"],
            counted_at=row["counted_at"],
            finalized_at=row["finalized_at"],
            policy_version=revision,
        ).model_dump(mode="json")

    def detail(self, kind: str, resource_id: str, *, financial: bool = False) -> dict[str, Any]:
        meta = self.metadata(kind, resource_id)
        branch = str(meta["branch_id"])
        revision = self.revision(branch)
        if financial:
            self.authority.require_financial(
                [(branch, f"cash.{'shifts' if kind == 'shift' else 'cuts'}")]
            )
        elif kind == "shift":
            self.authority.require_capability("cash.shift.read", branch)
        else:
            self.require_cut_read(meta)
        table = models.cash_shifts if kind == "shift" else models.user_cash_cuts
        names: tuple[str, ...] = SHIFT_FIELDS if kind == "shift" else CUT_FIELDS
        if financial:
            names += ("opening_cash_cents",) if kind == "shift" else CUT_MONEY
        row = (
            self.session.execute(
                selected(table, names).where(
                    table.c.organization_id == ops.ORGANIZATION_ID,
                    table.c.id == resource_id,
                )
            )
            .mappings()
            .one()
        )
        if not financial:
            return (
                self.shift_projection(row, revision)
                if kind == "shift"
                else self.cut_projection(row, revision)
            )
        result: dict[str, Any] = {
            "projection": "financial",
            "schema_version": 2,
            "policy_version": revision,
            "cash_shift" if kind == "shift" else "cash_cut": fields(row, names),
        }
        if kind == "shift":
            closure = (
                self.session.execute(
                    selected(
                        models.cash_shift_closures,
                        (
                            "id",
                            "closed_at",
                            "closed_by_user_id",
                            "summary_snapshot",
                        ),
                    ).where(
                        models.cash_shift_closures.c.organization_id == ops.ORGANIZATION_ID,
                        models.cash_shift_closures.c.cash_shift_id == resource_id,
                    )
                )
                .mappings()
                .first()
            )
            result["closure"] = (
                None
                if closure is None
                else {
                    **fields(closure, ("id", "closed_at", "closed_by_user_id")),
                    "summary_snapshot": fields(closure["summary_snapshot"], SUMMARY_FIELDS),
                }
            )
            result["current_summary"] = fields(
                ops._cash_summary_for_shift(self.session, dict(row)),
                SUMMARY_FIELDS,
            )
        else:
            for key, child, columns in (
                ("operations", models.user_cash_cut_operations, OPERATION_FIELDS),
                ("compensations", models.user_cash_cut_compensations, COMPENSATION_FIELDS),
            ):
                result[key] = [
                    fields(item, columns)
                    for item in self.session.execute(
                        selected(child, columns)
                        .where(
                            child.c.organization_id == ops.ORGANIZATION_ID,
                            child.c.cash_cut_id == resource_id,
                        )
                        .order_by(child.c.id)
                    ).mappings()
                ]
        schema = CashShiftFinancialV2 if kind == "shift" else UserCashCutFinancialV2
        return schema.model_validate(result).model_dump(mode="json", exclude_unset=True)

    def list_resources(
        self,
        kind: str,
        branch: str | None,
        *,
        financial: bool = False,
        limit: int = 50,
        cursor: str | None = None,
        register_id: str | None = None,
    ) -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise ops.BusinessError("cash_list_invalid", "limit must be 1..100")
        self.authority._begin()
        branches = (
            [branch]
            if branch
            else list(
                self.session.scalars(
                    sa.select(
                        models.branches.c.id,
                    ).where(models.branches.c.organization_id == ops.ORGANIZATION_ID)
                )
            )
        )
        # Authorize the full requested scope even on empty pages; never partial coverage.
        for scoped in sorted(branches):
            self.revision(scoped)
        if financial:
            self.authority.require_financial(
                [(scoped, f"cash.{'shifts' if kind == 'shift' else 'cuts'}") for scoped in branches]
            )
        else:
            for scoped in sorted(branches):
                self.authority.require_capability(
                    "cash.shift.read" if kind == "shift" else "cash.user_cut.operational.read",
                    scoped,
                )
        table = models.cash_shifts if kind == "shift" else models.user_cash_cuts
        query = sa.select(table.c.id).where(
            table.c.organization_id == ops.ORGANIZATION_ID,
            table.c.branch_id.in_(branches),
        )
        if kind == "cut" and not financial:
            branch_readers = [scoped for scoped in branches if self.branch_reader(scoped)]
            commands = models.user_cash_cut_commands
            query = query.where(
                sa.or_(
                    table.c.branch_id.in_(branch_readers),
                    table.c.cashier_user_id == self.actor,
                    sa.exists(
                        sa.select(commands.c.id).where(
                            commands.c.organization_id == ops.ORGANIZATION_ID,
                            commands.c.cash_cut_id == table.c.id,
                            commands.c.command_type == "count",
                            commands.c.actor_user_id == self.actor,
                        )
                    ),
                )
            )
        if register_id:
            column = table.c.register_code if kind == "shift" else table.c.register_code_snapshot
            query = query.where(column == register_id)
        if cursor:
            query = query.where(table.c.id > cursor)
        ids: list[str] = list(self.session.scalars(query.order_by(table.c.id).limit(limit + 1)))
        page_schema: type[BaseModel]
        if financial:
            page_schema = (
                CashPageV2[CashShiftFinancialV2]
                if kind == "shift"
                else CashPageV2[UserCashCutFinancialV2]
            )
        else:
            page_schema = (
                CashPageV2[CashShiftOperationalV2]
                if kind == "shift"
                else CashPageV2[UserCashCutOperationalV2]
            )
        return page_schema.model_validate(
            {
                "items": [self.detail(kind, item, financial=financial) for item in ids[:limit]],
                "next_cursor": ids[limit - 1] if len(ids) > limit else None,
            }
        ).model_dump(mode="json", exclude_unset=True)

    def current_shift(self, branch: str, register_id: str) -> dict[str, Any]:
        self.revision(branch)
        self.authority.require_capability("cash.shift.read", branch)
        table = models.cash_shifts
        row = (
            self.session.execute(
                selected(table, SHIFT_FIELDS)
                .where(
                    table.c.organization_id == ops.ORGANIZATION_ID,
                    table.c.branch_id == branch,
                    table.c.register_code == register_id,
                )
                .order_by(table.c.opened_at.desc(), table.c.id.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        return CurrentShiftV2.model_validate(
            {
                "cash_shift": self.shift_projection(row, self.revision(branch)) if row else None,
            }
        ).model_dump(mode="json")

    def declaration(self, cut_id: str) -> dict[str, Any]:
        meta = self.metadata("cut", cut_id)
        revision = self.revision(str(meta["branch_id"]))
        self.require_cut_read(meta)
        if self.capturer(cut_id) != self.actor:
            deny()
        table = models.user_cash_cuts
        row = (
            self.session.execute(
                selected(table, ("counted_cash_cents", "counted_at")).where(table.c.id == cut_id)
            )
            .mappings()
            .one()
        )
        return OwnDeclarationV2(
            resource_id=cut_id,
            policy_version=revision,
            counted_cash_cents=row["counted_cash_cents"],
            counted_at=row["counted_at"],
        ).model_dump(mode="json")


def active_revision(session: Session, branch: str) -> int | None:
    """Internal policy probe; caller retains governance lock, never grants authority."""
    from restaurant_os.financial_authority import protected_policy_revision

    return protected_policy_revision(session, ops.ORGANIZATION_ID, branch)


def require_cut_action(session: Session, actor: str, branch: str, action: str) -> None:
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    if active_revision(session, branch) is not None:
        FinancialAuthority(session, actor, ops.ORGANIZATION_ID).require_capability(action, branch)
    else:
        legacy = (
            "cash.user_cut.create"
            if action
            in {
                "cash.user_cut.capture",
                "cash.user_cut.finalize",
            }
            else action
        )
        ops.authorize_branch_scope(session, actor, legacy, branch)
