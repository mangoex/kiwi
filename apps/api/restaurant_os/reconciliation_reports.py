from __future__ import annotations

import io
from datetime import datetime, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import openpyxl
import sqlalchemy as sa
from openpyxl.styles import Border, Font, PatternFill, Side
from sqlalchemy.orm import Session

from . import models
from .operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _id,
    authorize_branch_scope,
    require_permission,
)

UTC = timezone.utc


def _reconciliation_wire_value(value: Any) -> Any:
    """HTTP v2 preserves exact money as canonical decimal strings; no float conversion."""
    if isinstance(value, Decimal):
        return format(value, ".2f")
    if isinstance(value, dict):
        return {key: _reconciliation_wire_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_reconciliation_wire_value(item) for item in value]
    return value


def reconciliation_wire(value: dict[str, Any]) -> dict[str, Any]:
    return {key: _reconciliation_wire_value(item) for key, item in value.items()}


def _validate_purchase_cash_link(
    session: Session, purchase: Any, movement: Any, *, manual_compensation: bool = False
) -> None:
    """Descriptions must identify the exact immutable effect, including its reversal."""
    original = (
        session.execute(
            sa.select(models.cash_movements).where(
                models.cash_movements.c.id == purchase["cash_movement_id"],
            )
        )
        .mappings()
        .first()
    )
    shift = (
        session.execute(
            sa.select(models.cash_shifts).where(
                models.cash_shifts.c.id == movement["cash_shift_id"],
            )
        )
        .mappings()
        .first()
    )
    reversal = str(movement["source_type"]).upper() == "PURCHASE_CANCELLATION"
    links = [movement[field] for field in ("reversal_of_id", "compensates_movement_id")]
    valid = (
        purchase["payment_method"] == "cash"
        and purchase["paid_from_cash"]
        and original is not None
        and shift is not None
        and original["organization_id"] == purchase["organization_id"]
        and original["branch_id"] == purchase["branch_id"]
        and original["source_id"] == purchase["id"]
        and str(original["source_type"]).upper() == "PURCHASE"
        and original["movement_type"] == "withdrawal"
        and original["status"] == "confirmed"
        and original["reversal_of_id"] is None
        and original["compensates_movement_id"] is None
        and _compensation_count(session, original["id"]) <= 1
        and original["amount_cents"] == _purchase_total_cents(purchase["total"])
        and movement["amount_cents"] == original["amount_cents"]
        and movement["cash_shift_id"] == original["cash_shift_id"]
        and shift["organization_id"] == purchase["organization_id"]
        and shift["branch_id"] == purchase["branch_id"]
        and movement["movement_type"] == ("deposit" if reversal else "withdrawal")
        and (
            (
                (manual_compensation or purchase["cancelled_at"] is not None)
                and any(links)
                and all(link is None or link == original["id"] for link in links)
            )
            if reversal
            else movement["id"] == original["id"] and not any(links)
        )
    )
    if not valid:
        raise BusinessError(
            "reconciliation_integrity_conflict", "Purchase cash link is inconsistent"
        )


def _compensation_count(session: Session, original_id: str) -> int:
    return int(
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.cash_movements)
            .where(
                models.cash_movements.c.status == "confirmed",
                sa.or_(
                    models.cash_movements.c.reversal_of_id == original_id,
                    models.cash_movements.c.compensates_movement_id == original_id,
                ),
            )
        )
        or 0
    )


def _expense_cash_category(session: Session, movement: Any, branch_id: str) -> tuple[str, int]:
    doc = (
        session.execute(
            sa.select(models.expense_documents).where(
                models.expense_documents.c.id == movement["source_id"],
                models.expense_documents.c.organization_id == ORGANIZATION_ID,
                models.expense_documents.c.branch_id == branch_id,
            )
        )
        .mappings()
        .first()
    )
    original = (
        session.execute(
            sa.select(models.cash_movements).where(
                models.cash_movements.c.id == (doc["cash_movement_id"] if doc else None)
            )
        )
        .mappings()
        .first()
    )
    reversal = str(movement["source_type"]).upper() == "EXPENSE_CANCELLATION"
    links = [movement[field] for field in ("reversal_of_id", "compensates_movement_id")]
    valid = (
        doc is not None
        and original is not None
        and doc["confirmed_at"] is not None
        and doc["payment_method"] == "cash"
        and original["organization_id"] == ORGANIZATION_ID
        and original["branch_id"] == branch_id
        and original["source_id"] == doc["id"]
        and original["source_type"] == "EXPENSE"
        and original["status"] == "confirmed"
        and original["movement_type"] == "withdrawal"
        and original["reversal_of_id"] is None
        and original["compensates_movement_id"] is None
        and original["amount_cents"] == doc["total_cents"]
        and movement["amount_cents"] == original["amount_cents"]
        and movement["cash_shift_id"] == original["cash_shift_id"]
        and _compensation_count(session, original["id"]) <= 1
        and isinstance(doc["concept_snapshot"], dict)
        and bool(doc["concept_snapshot"].get("name"))
        and (
            (
                doc["compensation_movement_id"] == movement["id"]
                and doc["cancelled_at"] is not None
                and movement["movement_type"] == "deposit"
                and any(links)
                and all(link is None or link == original["id"] for link in links)
            )
            if reversal
            else movement["id"] == original["id"] and not any(links)
        )
    )
    if not valid or doc is None:
        raise BusinessError(
            "reconciliation_integrity_conflict", "Expense cash link is inconsistent"
        )
    return str(doc["concept_snapshot"]["name"]), int(movement["amount_cents"]) * (
        -1 if reversal else 1
    )


def _purchase_total_cents(value: Decimal) -> int:
    return int((Decimal(str(value)) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _branch_day_bounds_utc(
    session: Session, branch_id: str, date_str: str
) -> tuple[datetime, datetime]:
    branch = (
        session.execute(
            sa.select(models.branches.c.timezone).where(
                models.branches.c.id == branch_id,
                models.branches.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not branch:
        raise BusinessError("branch_not_found", "Branch not found")
    tz_name = branch["timezone"]
    try:
        tz = ZoneInfo(str(tz_name))
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise BusinessError(
            "report_timezone_invalid", "La zona horaria de la sucursal no es válida"
        ) from exc

    dt = _report_date(date_str)
    local_start = datetime(dt.year, dt.month, dt.day, 0, 0, 0, 0, tzinfo=tz)
    local_end = local_start + timedelta(days=1)
    return local_start.astimezone(UTC), local_end.astimezone(UTC)


def _report_date(value: str) -> datetime:
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
        if parsed.strftime("%Y-%m-%d") != value or parsed.year == 9999:
            raise ValueError("Invalid report date")
        return parsed
    except ValueError as exc:
        raise BusinessError("report_period_invalid", "El período del reporte no es válido") from exc


def _ledger_projection(
    session: Session,
    branch_id: str,
    payment_population: sa.ColumnElement[bool],
    movement_population: sa.ColumnElement[bool],
    initial_cash_cents: int = 0,
) -> dict[str, Any]:
    """One classifier for both populations; ledger effects are never counted twice."""
    # 3. Orders and Payments
    payments = (
        session.execute(
            sa.select(
                models.payments.c.id,
                models.payments.c.order_id,
                models.payments.c.method,
                models.payments.c.amount_cents,
                models.payments.c.status,
                models.payments.c.organization_id,
                models.payments.c.branch_id,
                models.payments.c.cash_shift_id,
                models.payments.c.created_at,
                models.orders.c.id.label("scoped_order_id"),
                models.orders.c.folio.label("order_folio"),
                models.orders.c.owner_name.label("order_owner_name"),
                models.orders.c.customer_snapshot.label("order_customer_snapshot"),
                models.orders.c.total_cents.label("order_total_cents"),
            )
            .select_from(
                models.payments.outerjoin(
                    models.orders,
                    sa.and_(
                        models.payments.c.order_id == models.orders.c.id,
                        models.orders.c.organization_id == ORGANIZATION_ID,
                        models.orders.c.branch_id == branch_id,
                    ),
                )
            )
            .where(
                models.payments.c.branch_id == branch_id,
                models.payments.c.organization_id == ORGANIZATION_ID,
                models.payments.c.status == "CONFIRMED",
                payment_population,
            )
        )
        .mappings()
        .all()
    )

    card_payments_cents = 0
    transfer_payments_cents = 0
    cash_sales_cents = 0
    credit_sales_cents = 0
    transfers_breakdown: list[dict[str, Any]] = []
    credit_clients_breakdown: list[dict[str, Any]] = []

    _validate_event_shifts(session, payments, branch_id)
    for p in payments:
        _integrity(p["scoped_order_id"] == p["order_id"])
        amount = p["amount_cents"]
        method = (p["method"] or "").lower()
        cust_snap = p.get("order_customer_snapshot") or {}
        cust_name = cust_snap.get("name") or p.get("order_owner_name") or "Cliente General"
        cust_phone = cust_snap.get("phone") or "—"
        folio = p.get("order_folio") or f"T-{p['id'][:6].upper()}"

        if method in ("card", "credit_card", "debit_card"):
            card_payments_cents += amount
        elif method in ("transfer", "bank_transfer", "spei"):
            transfer_payments_cents += amount
            transfers_breakdown.append(
                {
                    "ticket_folio": folio,
                    "customer_name": cust_name,
                    "customer_phone": cust_phone,
                    "amount": Decimal(amount) / 100,
                }
            )
        elif method in ("credit", "customer_credit"):
            credit_sales_cents += amount
            credit_clients_breakdown.append(
                {
                    "ticket_folio": folio,
                    "customer_name": cust_name,
                    "customer_phone": cust_phone,
                    "amount": Decimal(amount) / 100,
                }
            )
        elif method == "cash":
            cash_sales_cents += amount
        else:
            raise BusinessError(
                "reconciliation_payment_method_unknown", "Confirmed payment method is unknown"
            )

    total_sales_with_tax_cents = (
        card_payments_cents + transfer_payments_cents + cash_sales_cents + credit_sales_cents
    )

    # 4. Provider breakdown classifies the cash ledger; documents add descriptions only.
    suppliers_breakdown: list[dict[str, Any]] = []
    supplier_expenses_cents = 0

    # 5. Cash movements (Gastos fijos, Retiros, Depósitos)
    movements = (
        session.execute(
            sa.select(
                models.cash_movements.c.id,
                models.cash_movements.c.organization_id,
                models.cash_movements.c.branch_id,
                models.cash_movements.c.cash_shift_id,
                models.cash_movements.c.created_at,
                models.cash_movements.c.concept_id,
                models.cash_movements.c.concept_version_id,
                models.cash_movements.c.movement_type,
                models.cash_movements.c.amount_cents,
                models.cash_movements.c.reason,
                models.cash_movements.c.reference,
                models.cash_movements.c.concept_snapshot,
                models.cash_movements.c.source_type,
                models.cash_movements.c.source_id,
                models.cash_movements.c.reversal_of_id,
                models.cash_movements.c.compensates_movement_id,
                models.cash_movement_concept_versions.c.name.label("concept_name"),
                models.cash_movement_concepts.c.code.label("concept_code"),
                models.cash_movement_concepts.c.id.label("scoped_concept_id"),
                models.cash_movement_concept_versions.c.id.label("scoped_concept_version_id"),
            )
            .select_from(
                models.cash_movements.outerjoin(
                    models.cash_movement_concepts,
                    sa.and_(
                        models.cash_movements.c.concept_id == models.cash_movement_concepts.c.id,
                        models.cash_movement_concepts.c.organization_id == ORGANIZATION_ID,
                    ),
                ).outerjoin(
                    models.cash_movement_concept_versions,
                    sa.and_(
                        models.cash_movements.c.concept_version_id
                        == models.cash_movement_concept_versions.c.id,
                        models.cash_movement_concept_versions.c.concept_id
                        == models.cash_movement_concepts.c.id,
                    ),
                )
            )
            .where(
                models.cash_movements.c.branch_id == branch_id,
                models.cash_movements.c.organization_id == ORGANIZATION_ID,
                models.cash_movements.c.status == "confirmed",
                movement_population,
            )
        )
        .mappings()
        .all()
    )

    fixed_expenses_breakdown: list[dict[str, Any]] = []
    withdrawals_breakdown: list[dict[str, Any]] = []
    fixed_expenses_cents = 0
    cash_withdrawals_cents = 0
    cash_deposits_cents = 0

    fix_idx = 1
    w_idx = 1
    _validate_event_shifts(session, movements, branch_id)
    for row in movements:
        m: dict[str, Any] = dict(row)
        if m["concept_id"] is not None or m["concept_version_id"] is not None:
            _integrity(
                m["concept_id"] is not None
                and m["concept_version_id"] is not None
                and m["concept_id"] == m["scoped_concept_id"]
                and m["concept_version_id"] == m["scoped_concept_version_id"]
            )
        mtype = m["movement_type"]
        amt = m["amount_cents"]
        source = str(m["source_type"] or "").lower()
        manual_purchase_compensation = False
        if source == "compensation":
            links = [m[field] for field in ("reversal_of_id", "compensates_movement_id")]
            original_id = next((link for link in links if link), None)
            original = (
                session.execute(
                    sa.select(models.cash_movements).where(
                        models.cash_movements.c.id == original_id
                    )
                )
                .mappings()
                .first()
            )
            if (
                not original
                or not original_id
                or any(link is not None and link != original_id for link in links)
                or original["organization_id"] != ORGANIZATION_ID
                or original["branch_id"] != branch_id
                or original["cash_shift_id"] != m["cash_shift_id"]
                or original["status"] != "confirmed"
                or original["movement_type"] not in {"deposit", "withdrawal"}
                or original["amount_cents"] != amt
                or original["reversal_of_id"] is not None
                or original["compensates_movement_id"] is not None
                or mtype
                != ("deposit" if original["movement_type"] == "withdrawal" else "withdrawal")
                or _compensation_count(session, original_id) != 1
            ):
                raise BusinessError(
                    "reconciliation_integrity_conflict", "Cash compensation link is inconsistent"
                )
            original_source = str(original["source_type"] or "").lower()
            if original_source == "expense":
                raise BusinessError(
                    "reconciliation_integrity_conflict",
                    "Expense requires its document compensation",
                )
            if original_source == "purchase":
                # Classification only; the immutable source remains COMPENSATION.
                m = {
                    **m,
                    "source_type": "PURCHASE_CANCELLATION",
                    "source_id": original["source_id"],
                }
                source = "purchase_cancellation"
                manual_purchase_compensation = True
        if source in {"purchase", "purchase_cancellation"}:
            purchase = (
                session.execute(
                    sa.select(models.purchase_documents).where(
                        models.purchase_documents.c.id == m["source_id"],
                        models.purchase_documents.c.organization_id == ORGANIZATION_ID,
                        models.purchase_documents.c.branch_id == branch_id,
                        models.purchase_documents.c.confirmed_at.is_not(None),
                    )
                )
                .mappings()
                .first()
            )
            if not purchase or mtype != ("withdrawal" if source == "purchase" else "deposit"):
                raise BusinessError(
                    "reconciliation_integrity_conflict", "Purchase cash link is inconsistent"
                )
            _validate_purchase_cash_link(
                session, purchase, m, manual_compensation=manual_purchase_compensation
            )
            supplier = (
                session.execute(
                    sa.select(models.suppliers).where(
                        models.suppliers.c.id == purchase["supplier_id"],
                        models.suppliers.c.organization_id == ORGANIZATION_ID,
                    )
                )
                .mappings()
                .first()
            )
            if not supplier:
                raise BusinessError(
                    "reconciliation_integrity_conflict", "Purchase supplier link is inconsistent"
                )
            signed = amt if mtype == "withdrawal" else -amt
            supplier_expenses_cents += signed
            suppliers_breakdown.append(
                {
                    "no": len(suppliers_breakdown) + 1,
                    "provider_name": supplier["commercial_name"],
                    "amount": Decimal(signed) / 100,
                    "observations": f"Folio: {purchase['folio']} ({purchase['document_type']})",
                    "movement_id": m["id"],
                    "purchase_id": purchase["id"],
                }
            )
            continue
        if source in {"expense", "expense_cancellation"}:
            cname, signed = _expense_cash_category(session, m, branch_id)
            fixed_expenses_cents += signed
            fixed_expenses_breakdown.append(
                {
                    "no": fix_idx,
                    "expense_type": cname,
                    "amount": Decimal(signed) / 100,
                    "observations": m["reason"],
                    "movement_id": m["id"],
                    "expense_id": m["source_id"],
                }
            )
            fix_idx += 1
            continue
        cname = m["concept_name"] or (m["concept_snapshot"] or {}).get("name") or "Gasto Operativo"
        if mtype == "withdrawal":
            is_vault = str(m["source_type"] or "").upper() != "EXPENSE" and (
                "retiro" in cname.lower()
                or "boveda" in cname.lower()
                or "caja fuerte" in cname.lower()
            )
            if is_vault:
                cash_withdrawals_cents += amt
                withdrawals_breakdown.append(
                    {
                        "no": w_idx,
                        "folio": f"RET-{m['id'][:6].upper()}",
                        "amount": Decimal(amt) / 100,
                        "recipient_name": m["reference"] or m["reason"] or "Encargado / Bóveda",
                    }
                )
                w_idx += 1
            else:
                fixed_expenses_cents += amt
                fixed_expenses_breakdown.append(
                    {
                        "no": fix_idx,
                        "expense_type": cname,
                        "amount": Decimal(amt) / 100,
                        "observations": m["reason"] or "Gasto menor de sucursal",
                    }
                )
                fix_idx += 1
        elif mtype in {"deposit", "cash_reversal"}:
            cash_deposits_cents += amt
        else:
            raise BusinessError(
                "cash_ledger_unknown_type", "Confirmed cash movement type is unknown"
            )

    # 6. Calculations (Exact Balance Formula)
    expected_cash_cents = (
        initial_cash_cents
        + cash_sales_cents
        + cash_deposits_cents
        - (supplier_expenses_cents + fixed_expenses_cents + cash_withdrawals_cents)
    )

    return {
        "balance": {
            "initial_cash": Decimal(initial_cash_cents) / 100,
            "total_sales_with_tax": Decimal(total_sales_with_tax_cents) / 100,
            "card_payments": Decimal(card_payments_cents) / 100,
            "transfer_payments": Decimal(transfer_payments_cents) / 100,
            "credit_sales": Decimal(credit_sales_cents) / 100,
            "cash_sales": Decimal(cash_sales_cents) / 100,
            "supplier_expenses": Decimal(supplier_expenses_cents) / 100,
            "fixed_expenses": Decimal(fixed_expenses_cents) / 100,
            "cash_withdrawals": Decimal(cash_withdrawals_cents) / 100,
            "cash_deposits": Decimal(cash_deposits_cents) / 100,
            "expected_cash_in_register": Decimal(expected_cash_cents) / 100,
        },
        "suppliers_breakdown": suppliers_breakdown,
        "fixed_expenses_breakdown": fixed_expenses_breakdown,
        "transfers_breakdown": transfers_breakdown,
        "credit_clients_breakdown": credit_clients_breakdown,
        "withdrawals_breakdown": withdrawals_breakdown,
    }


def _utc(value: datetime) -> datetime:
    # SQLite stores UTC timestamps without their offset; PostgreSQL preserves it.
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _integrity(condition: bool) -> None:
    if not condition:
        raise BusinessError(
            "reconciliation_integrity_conflict", "Cash report population is inconsistent"
        )


def _validate_event_shifts(session: Session, effects: Any, branch_id: str) -> None:
    if not effects:
        return
    shifts = {
        shift["id"]: shift
        for shift in session.execute(
            sa.select(models.cash_shifts).where(
                models.cash_shifts.c.id.in_({effect["cash_shift_id"] for effect in effects})
            )
        ).mappings()
    }
    for effect in effects:
        shift = shifts.get(effect["cash_shift_id"])
        if shift is None:
            raise BusinessError("reconciliation_integrity_conflict", "Cash event shift is missing")
        _integrity(shift["organization_id"] == ORGANIZATION_ID and shift["branch_id"] == branch_id)
        _integrity(shift["status"] in {"OPEN", "CLOSED", "OPERATIVELY_CLOSED"})
        _integrity(_utc(effect["created_at"]) >= _utc(shift["opened_at"]))
        if shift["status"] != "OPEN":
            _integrity(shift["closed_at"] is not None)
            _integrity(_utc(effect["created_at"]) <= _utc(shift["closed_at"]))


def _shift_projection(
    session: Session, branch_id: str, shift: Any
) -> tuple[dict[str, Any], int | None, bool]:
    sid = shift["id"]
    closure = (
        session.execute(
            sa.select(models.cash_shift_closures).where(
                models.cash_shift_closures.c.cash_shift_id == sid
            )
        )
        .mappings()
        .first()
    )
    cut = (
        session.execute(
            sa.select(models.cash_shift_cuts).where(models.cash_shift_cuts.c.cash_shift_id == sid)
        )
        .mappings()
        .first()
    )
    state = shift["status"]
    _integrity(state in {"OPEN", "OPERATIVELY_CLOSED", "CLOSED"})
    frozen = state != "OPEN"
    if frozen:
        _integrity(shift["closed_at"] is not None)
        _integrity(
            (state == "OPERATIVELY_CLOSED" and closure is not None and cut is None)
            or (state == "CLOSED" and cut is not None and closure is None)
        )
    else:
        _integrity(closure is None and cut is None and shift["closed_at"] is None)
    for artifact in (closure, cut):
        if artifact is not None:
            _integrity(
                artifact["organization_id"] == ORGANIZATION_ID
                and artifact["branch_id"] == branch_id
            )
            when = artifact["closed_at"] if artifact is closure else artifact["created_at"]
            _integrity(_utc(when) == _utc(shift["closed_at"]))
    if closure is not None:
        _integrity(closure["register_code_snapshot"] == shift["register_code"])
    if cut is not None:
        _integrity(cut["status"] == "FINAL")

    payments = (
        session.execute(
            sa.select(models.payments).where(
                models.payments.c.cash_shift_id == sid, models.payments.c.status == "CONFIRMED"
            )
        )
        .mappings()
        .all()
    )
    movements = (
        session.execute(
            sa.select(models.cash_movements).where(
                models.cash_movements.c.cash_shift_id == sid,
                models.cash_movements.c.status == "confirmed",
            )
        )
        .mappings()
        .all()
    )
    for effect in (*payments, *movements):
        _integrity(
            effect["organization_id"] == ORGANIZATION_ID and effect["branch_id"] == branch_id
        )
        _integrity(_utc(effect["created_at"]) >= _utc(shift["opened_at"]))
        if frozen:
            _integrity(_utc(effect["created_at"]) <= _utc(shift["closed_at"]))
    projection = _ledger_projection(
        session,
        branch_id,
        models.payments.c.cash_shift_id == sid,
        models.cash_movements.c.cash_shift_id == sid,
        int(shift["opening_cash_cents"]),
    )
    bal = projection["balance"]
    raw_deposits = sum(
        int(m["amount_cents"])
        for m in movements
        if m["movement_type"] in {"deposit", "cash_reversal"}
    )
    raw_withdrawals = sum(
        int(m["amount_cents"]) for m in movements if m["movement_type"] == "withdrawal"
    )
    expected = int(bal["expected_cash_in_register"] * 100)
    counted = None
    if frozen:
        if closure is not None:
            candidate = closure["summary_snapshot"]
            if not isinstance(candidate, dict):
                raise BusinessError(
                    "reconciliation_integrity_conflict", "Closure snapshot is invalid"
                )
            snapshot: dict[str, Any] = candidate
        elif cut is not None:
            snapshot = dict(cut)
        else:
            raise BusinessError("reconciliation_integrity_conflict", "Closure snapshot is missing")
        cash_key = "cash_payment_cents" if closure is not None else "cash_payment_total_cents"
        checks = {
            "opening_cash_cents": int(shift["opening_cash_cents"]),
            cash_key: int(bal["cash_sales"] * 100),
            "expected_cash_cents": expected,
            "sales_total_cents": int(bal["total_sales_with_tax"] * 100),
            "payment_total_cents": int(bal["total_sales_with_tax"] * 100),
        }
        if closure is not None:
            checks.update(deposit_cents=raw_deposits, withdrawal_cents=raw_withdrawals)
        for key, value in checks.items():
            stored = snapshot.get(key)
            _integrity(type(stored) is int and stored == value)
        # The immutable artifact, never an inferred count, owns the closed expected balance.
        bal["expected_cash_in_register"] = Decimal(snapshot["expected_cash_cents"]) / 100
        if cut is not None:
            counted = cut["counted_cash_cents"]
            _integrity(
                type(counted) is int
                and counted >= 0
                and type(cut["difference_cents"]) is int
                and cut["difference_cents"] == counted - expected
            )
    return projection, counted, frozen


def _physical_count(counted: list[str], pending: list[str]) -> dict[str, Any]:
    return {
        "status": "PENDING" if pending else "COUNTED" if counted else "EMPTY",
        "counted_shift_ids": counted,
        "pending_shift_ids": pending,
    }


def get_branch_daily_reconciliation(
    session: Session,
    branch_id: str,
    date_str: str,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Version 2: whole-shift balances and calendar event activity are distinct."""
    if actor_id:
        authorize_branch_scope(session, actor_id, "dashboard.read", branch_id)
    branch = (
        session.execute(
            sa.select(models.branches).where(
                models.branches.c.id == branch_id,
                models.branches.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not branch:
        raise BusinessError("branch_not_found", "Branch not found")
    start_utc, end_utc = _branch_day_bounds_utc(session, branch_id, date_str)
    shifts = (
        session.execute(
            sa.select(models.cash_shifts)
            .where(
                models.cash_shifts.c.organization_id == ORGANIZATION_ID,
                models.cash_shifts.c.branch_id == branch_id,
                models.cash_shifts.c.opened_at >= start_utc,
                models.cash_shifts.c.opened_at < end_utc,
            )
            .order_by(models.cash_shifts.c.opened_at, models.cash_shifts.c.id)
            .with_for_update(read=True)
        )
        .mappings()
        .all()
    )
    result = _ledger_projection(session, branch_id, sa.false(), sa.false())
    counted_ids: list[str] = []
    pending_ids: list[str] = []
    frozen_ids: list[str] = []
    counted_cents = 0
    for shift in shifts:
        projection, counted, frozen = _shift_projection(session, branch_id, shift)
        for key, value in projection["balance"].items():
            result["balance"][key] += value
        for key in projection:
            if key != "balance":
                result[key].extend(projection[key])
        if counted is None:
            pending_ids.append(shift["id"])
        else:
            counted_ids.append(shift["id"])
            counted_cents += counted
        if frozen:
            frozen_ids.append(shift["id"])
    for key in ("suppliers_breakdown", "fixed_expenses_breakdown", "withdrawals_breakdown"):
        for index, row in enumerate(result[key], 1):
            row["no"] = index
    physical = _physical_count(counted_ids, pending_ids)
    actual = Decimal(counted_cents) / 100 if physical["status"] == "COUNTED" else None
    result["balance"].update(
        physical_cash_count=actual,
        difference=actual - result["balance"]["expected_cash_in_register"]
        if actual is not None
        else None,
    )
    activity = _ledger_projection(
        session,
        branch_id,
        sa.and_(models.payments.c.created_at >= start_utc, models.payments.c.created_at < end_utc),
        sa.and_(
            models.cash_movements.c.created_at >= start_utc,
            models.cash_movements.c.created_at < end_utc,
        ),
    )
    activity_totals = activity.pop("balance")
    for key in ("initial_cash", "expected_cash_in_register"):
        activity_totals.pop(key)
    # 7. Persistent Audit record lookup
    audit_row = (
        session.execute(
            sa.select(models.reconciliation_audit_logs).where(
                models.reconciliation_audit_logs.c.branch_id == branch_id,
                models.reconciliation_audit_logs.c.organization_id == ORGANIZATION_ID,
                models.reconciliation_audit_logs.c.date == date_str,
            )
        )
        .mappings()
        .first()
    )

    if audit_row:
        audit = {
            "reviewed": bool(audit_row["reviewed"]),
            "audited_by_user_id": audit_row["audited_by_user_id"],
            "audited_at": audit_row["audited_at"].isoformat() if audit_row["audited_at"] else None,
            "notes": audit_row["notes"],
        }
    else:
        audit = {
            "reviewed": False,
            "audited_by_user_id": None,
            "audited_at": None,
            "notes": None,
        }

    return {
        "contract_version": 2,
        "branch_id": branch_id,
        "branch_name": branch["name"],
        "date": date_str,
        **result,
        "physical_count": physical,
        "population": {
            "kind": "shifts_opened",
            "timezone": branch["timezone"],
            "from_utc": start_utc.isoformat(),
            "to_utc": end_utc.isoformat(),
            "shift_ids": [shift["id"] for shift in shifts],
            "frozen_shift_ids": frozen_ids,
            "breakdown_basis": "verified_ledger",
        },
        "activity": {
            "kind": "calendar_events",
            "timezone": branch["timezone"],
            "from_utc": start_utc.isoformat(),
            "to_utc": end_utc.isoformat(),
            "totals": activity_totals,
            **activity,
        },
        "audit": audit,
    }


def get_multi_branch_consolidated_report(
    session: Session,
    date_from_str: str,
    date_to_str: str,
    branch_id: str | None = None,
    actor_id: str | None = None,
) -> dict[str, Any]:
    """Aggregates daily reconciliations across all or selected branches."""
    if actor_id:
        branch_id = authorize_branch_scope(session, actor_id, "dashboard.read", branch_id)

    branches_query = sa.select(models.branches).where(
        models.branches.c.organization_id == ORGANIZATION_ID
    )
    if branch_id:
        branches_query = branches_query.where(models.branches.c.id == branch_id)
    branches = session.execute(branches_query).mappings().all()

    supplier_totals: dict[str, Decimal] = {}
    fixed_expense_totals: dict[str, Decimal] = {}
    branch_summaries: list[dict[str, Any]] = []

    total_sales = Decimal("0")
    total_cards = Decimal("0")
    total_transfers = Decimal("0")
    total_credits = Decimal("0")
    total_suppliers = Decimal("0")
    total_fixed = Decimal("0")
    total_withdrawals = Decimal("0")
    total_expected = Decimal("0")
    physical_total = Decimal("0")
    counted_ids: list[str] = []
    pending_ids: list[str] = []
    activity_totals: dict[str, Decimal] = dict.fromkeys(
        (
            "total_sales_with_tax",
            "card_payments",
            "transfer_payments",
            "credit_sales",
            "cash_sales",
            "supplier_expenses",
            "fixed_expenses",
            "cash_withdrawals",
            "cash_deposits",
        ),
        Decimal("0"),
    )

    # Parse date range
    dt_from = _report_date(date_from_str)
    dt_to = _report_date(date_to_str)
    if dt_from > dt_to:
        raise BusinessError("report_period_invalid", "Date range is inverted")
    curr = dt_from
    days = []
    while curr <= dt_to:
        days.append(curr.strftime("%Y-%m-%d"))
        curr += timedelta(days=1)

    for b in branches:
        b_id = b["id"]
        b_name = b["name"]
        b_sales = Decimal("0")
        b_expenses = Decimal("0")
        for day in days:
            rep = get_branch_daily_reconciliation(session, b_id, day, actor_id)
            bal = rep["balance"]
            b_sales += bal["total_sales_with_tax"]
            b_expenses += bal["supplier_expenses"] + bal["fixed_expenses"]
            total_sales += bal["total_sales_with_tax"]
            total_cards += bal["card_payments"]
            total_transfers += bal["transfer_payments"]
            total_credits += bal["credit_sales"]
            total_suppliers += bal["supplier_expenses"]
            total_fixed += bal["fixed_expenses"]
            total_withdrawals += bal["cash_withdrawals"]
            total_expected += bal["expected_cash_in_register"]
            counted_ids.extend(rep["physical_count"]["counted_shift_ids"])
            pending_ids.extend(rep["physical_count"]["pending_shift_ids"])
            if bal["physical_cash_count"] is not None:
                physical_total += bal["physical_cash_count"]
            for key, value in rep["activity"]["totals"].items():
                activity_totals[key] = activity_totals.get(key, Decimal("0")) + value

            for sup in rep["suppliers_breakdown"]:
                sname = sup["provider_name"]
                supplier_totals[sname] = supplier_totals.get(sname, Decimal("0")) + sup["amount"]

            for fexp in rep["fixed_expenses_breakdown"]:
                ename = fexp["expense_type"]
                fixed_expense_totals[ename] = (
                    fixed_expense_totals.get(ename, Decimal("0")) + fexp["amount"]
                )

        branch_summaries.append(
            {
                "branch_id": b_id,
                "branch_name": b_name,
                "total_sales": b_sales,
                "total_expenses": b_expenses,
            }
        )

    physical = _physical_count(counted_ids, pending_ids)
    actual = physical_total if physical["status"] == "COUNTED" else None
    return {
        "contract_version": 2,
        "population": {
            "kind": "shifts_opened",
            "date_from": date_from_str,
            "date_to": date_to_str,
            "shift_ids": counted_ids + pending_ids,
            "breakdown_basis": "verified_ledger",
        },
        "physical_count": physical,
        "activity": {
            "kind": "calendar_events",
            "date_from": date_from_str,
            "date_to": date_to_str,
            "totals": activity_totals,
        },
        "date_from": date_from_str,
        "date_to": date_to_str,
        "branches": branch_summaries,
        "supplier_totals": supplier_totals,
        "fixed_expense_totals": fixed_expense_totals,
        "summary": {
            "total_sales": total_sales,
            "total_cards": total_cards,
            "total_transfers": total_transfers,
            "total_credits": total_credits,
            "total_suppliers": total_suppliers,
            "total_fixed": total_fixed,
            "total_withdrawals": total_withdrawals,
            "total_expected_cash": total_expected,
            "physical_cash_count": actual,
            "difference": actual - total_expected if actual is not None else None,
        },
    }


def update_reconciliation_audit_status(
    session: Session,
    branch_id: str,
    date_str: str,
    reviewed: bool,
    notes: str | None = None,
    auditor_id: str | None = None,
) -> dict[str, Any]:
    """Records persistent auditor validation state in database."""
    if auditor_id:
        try:
            authorize_branch_scope(session, auditor_id, "audit.read", branch_id)
        except AuthorizationError:
            try:
                authorize_branch_scope(session, auditor_id, "branch.admin.access", branch_id)
            except AuthorizationError:
                require_permission(session, auditor_id, "admin.manage", branch_id)

    now = datetime.now(timezone.utc)
    existing = (
        session.execute(
            sa.select(models.reconciliation_audit_logs).where(
                models.reconciliation_audit_logs.c.branch_id == branch_id,
                models.reconciliation_audit_logs.c.date == date_str,
            )
        )
        .mappings()
        .first()
    )

    if existing:
        session.execute(
            models.reconciliation_audit_logs.update()
            .where(models.reconciliation_audit_logs.c.id == existing["id"])
            .values(
                reviewed=bool(reviewed),
                audited_by_user_id=auditor_id or "admin-user",
                notes=notes or "",
                audited_at=now,
                updated_at=now,
            )
        )
    else:
        session.execute(
            models.reconciliation_audit_logs.insert().values(
                id=_id(),
                organization_id=ORGANIZATION_ID,
                branch_id=branch_id,
                date=date_str,
                reviewed=bool(reviewed),
                audited_by_user_id=auditor_id or "admin-user",
                notes=notes or "",
                audited_at=now,
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()

    return {
        "branch_id": branch_id,
        "date": date_str,
        "reviewed": bool(reviewed),
        "audited_by_user_id": auditor_id or "admin-user",
        "audited_at": now.isoformat(),
        "notes": notes or "",
    }


def export_reconciliation_workbook(
    session: Session,
    branch_id: str,
    month: int,
    year: int,
    actor_id: str | None = None,
) -> io.BytesIO:
    """Generates standard Excel (.xlsx) matching the structure of Kiwi Multi-Branch Cuts."""
    if actor_id:
        authorize_branch_scope(session, actor_id, "dashboard.read", branch_id)
    if not 1 <= month <= 12 or not 1 <= year <= 9998:
        raise BusinessError("report_period_invalid", "El mes o año del reporte no es válido")

    wb = openpyxl.Workbook()
    # Sheet 1: Resumen
    ws_resumen = wb.worksheets[0]
    ws_resumen.title = "Resumen"

    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="10B981", end_color="10B981", fill_type="solid")
    border = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    ws_resumen["A1"] = f"BALANCE CONSOLIDADO MENSUAL ({month:02d}/{year})"
    ws_resumen["A1"].font = Font(name="Calibri", size=14, bold=True)
    ws_resumen["A2"] = (
        "Saldo de turnos por fecha de apertura local; ledger completo o cierre congelado"
    )

    headers = [
        "Concepto",
        "Monto Total ($)",
    ]
    for col_idx, h in enumerate(headers, 1):
        cell = ws_resumen.cell(3, col_idx, h)
        cell.font = header_font
        cell.fill = header_fill

    # Calculate month total
    date_from = f"{year}-{month:02d}-01"
    next_m = month + 1 if month < 12 else 1
    next_y = year if month < 12 else year + 1
    last_day = (datetime(next_y, next_m, 1) - timedelta(days=1)).day
    date_to = f"{year}-{month:02d}-{last_day:02d}"

    rep = get_multi_branch_consolidated_report(session, date_from, date_to, branch_id, actor_id)
    summary = rep["summary"]

    rows = [
        ("Ventas Totales con Impuestos", summary["total_sales"]),
        ("(-) Pagos con Tarjeta", summary["total_cards"]),
        ("(-) Ingresos por Transferencias", summary["total_transfers"]),
        ("(-) Clientes a Crédito", summary["total_credits"]),
        ("(-) Pago a Proveedores en Efectivo", summary["total_suppliers"]),
        ("(-) Gastos Fijos en Efectivo", summary["total_fixed"]),
        ("(-) Retiros en Efectivo a Bóveda", summary["total_withdrawals"]),
        ("(=) Efectivo Neto Esperado", summary["total_expected_cash"]),
        ("Arqueo físico del conjunto de turnos", summary["physical_cash_count"]),
        ("Diferencia contado menos esperado", summary["difference"]),
    ]

    for r_idx, (lbl, val) in enumerate(rows, 4):
        ws_resumen.cell(r_idx, 1, lbl).border = border
        c = ws_resumen.cell(r_idx, 2, val)
        c.border = border
        c.number_format = '"$"#,##0.00'

    ws_resumen["A14"] = "Estado de arqueo"
    ws_resumen["B14"] = {
        "PENDING": "Pendiente de arqueo",
        "COUNTED": "Conteo completo",
        "EMPTY": "Sin turnos",
    }[rep["physical_count"]["status"]]
    ws_resumen.column_dimensions["A"].width = 95
    ws_resumen.column_dimensions["B"].width = 24
    ws_activity = wb.create_sheet(title="Actividad calendario")
    ws_activity.append(["Actividad por fecha de evento local", f"{date_from} a {date_to}"])
    ws_activity.append(["Independiente del saldo por apertura; no es arqueo ni existencia actual"])
    ws_activity.append(["Concepto", "Monto ($)"])
    activity_labels = {
        "total_sales_with_tax": "Cobros totales",
        "card_payments": "Tarjetas",
        "transfer_payments": "Transferencias",
        "credit_sales": "Crédito",
        "cash_sales": "Cobros cash",
        "supplier_expenses": "Proveedores cash netos",
        "fixed_expenses": "Gastos cash netos",
        "cash_withdrawals": "Retiros a bóveda",
        "cash_deposits": "Depósitos",
    }
    for key, value in rep["activity"]["totals"].items():
        ws_activity.append([activity_labels[key], value])
        ws_activity.cell(ws_activity.max_row, 2).number_format = '"$"#,##0.00'
    ws_activity.column_dimensions["A"].width = 90
    ws_activity.column_dimensions["B"].width = 26
    # Sheet 2: Master
    ws_master = wb.create_sheet(title="Master")
    ws_master["A1"] = "PLANTILLA DE CORTE DIARIO KIWI"
    ws_master["A1"].font = Font(name="Calibri", size=12, bold=True)

    out = io.BytesIO()
    wb.save(out)
    out.seek(0)
    return out
