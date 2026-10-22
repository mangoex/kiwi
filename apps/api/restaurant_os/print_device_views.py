"""Scoped print transport: list metadata, claim, then download one assigned payload."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import Field, ValidationError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import governance_lock, protected_policy_revision
from restaurant_os.order_detail_views import OrderChargeV2, OrderModifierV2


def denied() -> None:
    raise ops.AuthorizationError("device_scope_denied", "Print work is not assigned to this device")


def policy_revision(session: Session, organization: str, branch: str) -> int | None:
    governance_lock(session, organization)
    return protected_policy_revision(session, organization, branch)


def policy_active(session: Session, organization: str, branch: str) -> bool:
    return policy_revision(session, organization, branch) is not None


def require_device(session: Session, device: str | None, organization: str, branch: str) -> None:
    """Lock persisted credential and active scope through materialization/effect."""
    governance_lock(session, organization)
    credential = (
        session.execute(
            sa.select(models.device_credentials)
            .join(
                models.branches,
                sa.and_(
                    models.branches.c.id == models.device_credentials.c.branch_id,
                    models.branches.c.organization_id
                    == models.device_credentials.c.organization_id,
                ),
            )
            .join(
                models.organizations, models.organizations.c.id == models.branches.c.organization_id
            )
            .where(
                models.device_credentials.c.id == device,
                models.device_credentials.c.organization_id == organization,
                models.device_credentials.c.branch_id == branch,
                models.device_credentials.c.capability == "print.agent",
                models.device_credentials.c.revoked_at.is_(None),
                models.branches.c.status == "active",
                models.organizations.c.status == "active",
            )
            .with_for_update(read=True)
        )
        .mappings()
        .first()
    )
    expiry = credential["expires_at"] if credential else None
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if credential is None or expiry is None or expiry <= ops._now():
        denied()


class KitchenModifier(FinancialRecord):
    option_id: str
    option_name: str | None = None
    group_name: str | None = None
    kind: str | None = None
    effect_type: str | None = None
    selection_kind: str | None = None
    portions: int | None = None
    portion_count: int | None = None
    portion_quantity: Decimal | None = None
    text: str | None = None
    kitchen_text: str | None = None
    station: str | None = None
    component_product_name: str | None = None
    component_quantity: Decimal | None = None


class KitchenLine(FinancialRecord):
    product_name: str
    quantity: int
    station: str
    line_notes: str | None = None
    selected_modifiers: list[KitchenModifier]


class TicketLine(FinancialRecord):
    product_name: str
    quantity: int
    station: str
    line_notes: str | None = None
    line_total_cents: int
    selected_modifiers: list[OrderModifierV2]


class KitchenPayload(FinancialRecord):
    copy_kind: Literal["kitchen"] = Field(alias="copy")
    folio: str
    lines: list[KitchenLine]


class Tender(FinancialRecord):
    received_cents: int
    change_cents: int
    shortfall_cents: int
    can_confirm: bool


class TicketPayload(FinancialRecord):
    copy_kind: Literal["customer"] = Field(alias="copy")
    folio: str
    total_cents: int
    payment_id: str
    cash_tender: Tender | None = None
    delivery_charge: OrderChargeV2 | None = None
    lines: list[TicketLine]


class QueuedPrintWork(FinancialRecord):
    schema_version: Literal[2] = 2
    attempt_id: str
    print_job_id: str
    created_at: datetime
    job_type: str
    target: str


def _fields(model: type[FinancialRecord], value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ops.BusinessError("print_payload_unavailable", "Print snapshot is unavailable")
    keys = [field.alias or key for key, field in model.model_fields.items()]
    return {key: value[key] for key in keys if key in value}


def project_payload(kind: str, raw: Any) -> dict[str, Any]:
    if kind not in {"ticket", "kitchen"}:
        raise ops.BusinessError("print_payload_unavailable", "Unsupported print job")
    model = TicketPayload if kind == "ticket" else KitchenPayload
    line_model = TicketLine if kind == "ticket" else KitchenLine
    modifier_model = OrderModifierV2 if kind == "ticket" else KitchenModifier
    value = _fields(model, raw)
    try:
        if not isinstance(value.get("lines"), list):
            raise ValueError("invalid lines")
        lines = []
        for raw_line in value["lines"]:
            line = _fields(line_model, raw_line)
            if not isinstance(line.get("selected_modifiers"), list):
                raise ValueError("invalid modifiers")
            line["selected_modifiers"] = [
                _fields(modifier_model, item) for item in line["selected_modifiers"]
            ]
            lines.append(line)
        value["lines"] = lines
        if kind == "ticket":
            if value.get("cash_tender") is not None:
                value["cash_tender"] = _fields(Tender, value["cash_tender"])
            charge = value.get("delivery_charge")
            if charge is not None:
                projected = _fields(OrderChargeV2, charge)
                tariff = charge.get("tariff")
                if tariff is not None and not isinstance(tariff, dict):
                    raise ValueError("invalid tariff")
                projected["tariff_name"] = tariff.get("name") if tariff else None
                value["delivery_charge"] = projected
        return model(**value).model_dump(mode="json", exclude_unset=True, by_alias=True)
    except (ValidationError, ValueError):
        raise ops.BusinessError(
            "print_payload_unavailable", "Print snapshot is unavailable"
        ) from None


def queued_metadata(
    session: Session, device: str | None, organization: str, branch: str
) -> list[dict[str, Any]]:
    require_device(session, device, organization, branch)
    attempts, jobs = models.print_attempts, models.print_jobs
    rows = session.execute(
        sa.select(
            attempts.c.id.label("attempt_id"),
            attempts.c.print_job_id,
            attempts.c.created_at,
            jobs.c.job_type,
            jobs.c.target,
        )
        .join(
            jobs,
            sa.and_(
                jobs.c.id == attempts.c.print_job_id,
                jobs.c.organization_id == attempts.c.organization_id,
                jobs.c.branch_id == attempts.c.branch_id,
            ),
        )
        .where(
            attempts.c.organization_id == organization,
            attempts.c.branch_id == branch,
            attempts.c.status == "QUEUED",
            jobs.c.status == "QUEUED",
        )
        .order_by(attempts.c.created_at, attempts.c.id)
        .limit(100)
    ).mappings()
    return [QueuedPrintWork(**dict(row)).model_dump(mode="json") for row in rows]


def _assigned(
    session: Session, attempt: str, device: str, organization: str, branch: str
) -> dict[str, Any]:
    require_device(session, device, organization, branch)
    attempts, jobs = models.print_attempts, models.print_jobs
    # Match claim/ack/fail writers: attempt before job, never a planner-dependent join lock.
    assigned_job = session.scalar(
        sa.select(attempts.c.print_job_id)
        .where(
            attempts.c.id == attempt,
            attempts.c.organization_id == organization,
            attempts.c.branch_id == branch,
            attempts.c.status == "CLAIMED",
            attempts.c.claimed_by_device_id == device,
        )
        .with_for_update(read=True)
    )
    if assigned_job is None:
        denied()
    row = (
        session.execute(
            sa.select(jobs.c.id, jobs.c.job_type, jobs.c.target)
            .where(
                jobs.c.id == assigned_job,
                jobs.c.organization_id == organization,
                jobs.c.branch_id == branch,
                jobs.c.status == "CLAIMED",
            )
            .with_for_update(read=True)
        )
        .mappings()
        .first()
    )
    if row is None:
        denied()
    assert row is not None
    return dict(row)


def assigned_payload(
    session: Session, attempt: str, device: str, organization: str, branch: str
) -> dict[str, Any]:
    revision = policy_revision(session, organization, branch)
    if revision is None:
        raise ops.BusinessError(
            "cash_policy_not_active", "Scoped print delivery requires active policy"
        )
    job = _assigned(session, attempt, device, organization, branch)
    raw = session.scalar(
        sa.select(models.print_jobs.c.payload).where(
            models.print_jobs.c.id == job["id"],
            models.print_jobs.c.organization_id == organization,
            models.print_jobs.c.branch_id == branch,
        )
    )
    payload = project_payload(job["job_type"], raw)
    ops._audit(
        session,
        "print_attempt.payload_read",
        "print_attempt",
        attempt,
        {"device_id": device, "print_job_id": job["id"], "job_type": job["job_type"]},
        branch_id=branch,
        organization_id=organization,
        actor_user_id=None,
    )
    session.commit()
    # Audit confirmation released the locks; current assignment and credential must still hold.
    if policy_revision(session, organization, branch) != revision:
        raise ops.BusinessError(
            "cash_authorization_changed", "Print policy changed during delivery"
        )
    _assigned(session, attempt, device, organization, branch)
    return {
        "schema_version": 2,
        "attempt_id": attempt,
        "print_job_id": job["id"],
        "job_type": job["job_type"],
        "target": job["target"],
        "payload": payload,
    }
