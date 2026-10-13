"""Commit private fiscal preparation; this module never dispatches to a provider."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    _audit,
    _authority_governance_lock,
    require_permission,
)

from .authority import require_branch_permission
from .crypto import seal, unseal
from .eligibility import payment_snapshot
from .emitters import configuration_for_branch

MAX_TOTAL_CENTS = 2147483647
MAX_ENVELOPE_CHARS = 65536
ACTIVE_STATES = ("pending", "processing", "unknown", "needs_review")
RECEIVER_LIMITS = {
    "rfc": 13,
    "legal_name": 200,
    "zip": 10,
    "tax_system": 10,
    "use": 10,
    "payment_form": 10,
    "payment_method": 10,
}


def _receiver(value: Any) -> dict[str, str]:
    if (
        not isinstance(value, dict)
        or set(value) - (set(RECEIVER_LIMITS) | {"email"})
        or set(RECEIVER_LIMITS) - set(value)
    ):
        raise BusinessError(
            "fiscal_receiver_invalid", "Explicit fiscal receiver fields are required"
        )
    result: dict[str, str] = {}
    for field, limit in {**RECEIVER_LIMITS, "email": 254}.items():
        if field not in value:
            continue
        text = value[field]
        if (
            not isinstance(text, str)
            or not text.strip()
            or len(text) > limit
            or any(ord(char) < 32 for char in text)
        ):
            raise BusinessError("fiscal_receiver_invalid", "Fiscal receiver field is invalid")
        result[field] = text.strip()
    result["rfc"] = result["rfc"].upper()
    return result


def _hash(request: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(
            request,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _context(row: dict[str, Any]) -> str:
    return (
        ":".join(
            str(row[field])
            for field in (
                "organization_id",
                "branch_id",
                "actor_user_id",
                "id",
                "operation",
                "emitter_configuration_id",
                "emitter_configuration_version",
                "external_key",
                "provider",
            )
        )
        + ":fiscal-command-payment-snapshot/v1"
    )


def read_private_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    """Internal only: caller must already hold authority on the command's resource."""
    try:
        snapshot = unseal(row["snapshot_ciphertext"], _context(row))
        request = snapshot["request"]
        if (
            snapshot.get("schema") != "fiscal-command-payment/v1"
            or not isinstance(request, dict)
            or _hash(request) != row["request_hash"]
            or any(
                request[field] != row[field]
                for field in (
                    "organization_id",
                    "branch_id",
                    "actor_user_id",
                    "operation",
                )
            )
            or snapshot["configuration"]
            != {
                "id": row["emitter_configuration_id"],
                "version": row["emitter_configuration_version"],
                "legal_entity_id": row["legal_entity_id"],
            }
        ):
            raise ValueError("snapshot mismatch")
        return snapshot
    except (RuntimeError, KeyError, ValueError, TypeError):
        raise BusinessError(
            "fiscal_snapshot_unavailable", "Fiscal snapshot requires review"
        ) from None


def _public(session: Session, row: dict[str, Any]) -> dict[str, Any]:
    snapshot = read_private_snapshot(row)
    if row["dispatch_ready"] is not False or row["state"] != "pending":
        raise BusinessError(
            "fiscal_snapshot_unavailable", "Payment preparation is not dispatch evidence"
        )
    links = list(
        session.execute(
            sa.select(models.fiscal_command_orders)
            .where(models.fiscal_command_orders.c.command_id == row["id"])
            .order_by(models.fiscal_command_orders.c.order_id)
        ).mappings()
    )
    sources = snapshot["payments"]
    expected_ids = snapshot["request"]["order_ids"]
    outbox = (
        session.execute(
            sa.select(models.fiscal_command_outbox).where(
                models.fiscal_command_outbox.c.command_id == row["id"]
            )
        )
        .mappings()
        .first()
    )
    reserved_ids: list[str] = list(
        session.execute(
            sa.select(models.fiscal_order_reservations.c.order_id)
            .where(models.fiscal_order_reservations.c.command_id == row["id"])
            .order_by(models.fiscal_order_reservations.c.order_id)
        ).scalars()
    )
    if (
        outbox is None
        or outbox["event_type"] != "fiscal.issue.prepare"
        or (row["state"] in ACTIVE_STATES and reserved_ids != expected_ids)
    ):
        raise BusinessError(
            "fiscal_snapshot_unavailable", "Fiscal intention evidence requires review"
        )
    if (
        [link["order_id"] for link in links] != expected_ids
        or [source["order_id"] for source in sources] != expected_ids
        or sum(source["total_cents"] for source in sources) != row["total_cents"]
        or any(
            any(
                link[field] != source[field]
                for field in (
                    "order_id",
                    "order_version",
                    "total_cents",
                    "paid_cents",
                    "currency",
                )
            )
            or link["currency"] != row["currency"]
            for link, source in zip(links, sources, strict=True)
        )
    ):
        raise BusinessError("fiscal_snapshot_unavailable", "Fiscal links require review")
    result = {
        field: row[field]
        for field in (
            "id",
            "branch_id",
            "operation",
            "state",
            "dispatch_ready",
            "total_cents",
            "currency",
        )
    }
    for field in ("created_at", "updated_at"):
        timestamp: datetime = row[field]
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        result[field] = timestamp.astimezone(timezone.utc).isoformat()
    result["order_ids"] = expected_ids
    return result


def prepare_issue(
    session: Session,
    organization_id: str,
    branch_id: str | None,
    order_ids: Any,
    receiver: Any,
    *,
    actor: str,
    idempotency_key: Any,
    branch_context: str | None = None,
) -> dict[str, Any]:
    """Own the transaction; capture evidence without assuming fiscal concept/tax sufficiency."""
    try:
        _authority_governance_lock(session)
        # Branch deletion takes this physical organization lock, not the governance advisory lock.
        session.execute(
            sa.select(models.organizations.c.id)
            .where(
                models.organizations.c.id == ORGANIZATION_ID,
            )
            .with_for_update(key_share=True)
        ).scalar_one_or_none()
        session.execute(
            sa.select(models.users.c.id)
            .where(
                models.users.c.id == actor,
                models.users.c.organization_id == ORGANIZATION_ID,
            )
            .with_for_update(key_share=True)
        ).scalar_one_or_none()
        require_permission(session, actor, "invoicing.issue", None)
        if organization_id != ORGANIZATION_ID:
            require_branch_permission(
                session, actor, organization_id, branch_id or "", "invoicing.issue", branch_context
            )
        if (
            not isinstance(idempotency_key, str)
            or not 1 <= len(idempotency_key) <= 128
            or any(ord(char) < 33 or ord(char) > 126 for char in idempotency_key)
        ):
            raise BusinessError("fiscal_idempotency_key_invalid", "A stable fiscal key is required")
        if (
            not isinstance(order_ids, list)
            or not order_ids
            or any(not isinstance(value, str) or not value for value in order_ids)
            or len(set(order_ids)) != len(order_ids)
        ):
            raise BusinessError("fiscal_order_set_invalid", "Unique order IDs are required")
        normalized = _receiver(receiver)
        existing = (
            session.execute(
                sa.select(models.fiscal_commands)
                .where(
                    models.fiscal_commands.c.organization_id == organization_id,
                    models.fiscal_commands.c.actor_user_id == actor,
                    models.fiscal_commands.c.operation == "issue",
                    models.fiscal_commands.c.idempotency_key == idempotency_key,
                )
                .with_for_update(key_share=True)
            )
            .mappings()
            .first()
        )
        if existing:
            selected = str(existing["branch_id"])
        else:
            branches: set[str] = set(
                session.execute(
                    sa.select(models.orders.c.branch_id).where(
                        models.orders.c.organization_id == organization_id,
                        models.orders.c.id.in_(order_ids),
                    )
                ).scalars()
            )
            if len(branches) != 1:
                raise BusinessError("fiscal_order_set_invalid", "Orders must share one branch")
            selected = str(next(iter(branches)))
        branch = (
            session.execute(
                sa.select(models.branches)
                .where(
                    models.branches.c.id == selected,
                    models.branches.c.organization_id == organization_id,
                )
                .with_for_update(key_share=True)
            )
            .mappings()
            .first()
        )
        require_branch_permission(
            session, actor, organization_id, selected, "invoicing.issue", branch_context
        )
        if branch_id is not None and branch_id != selected:
            raise BusinessError("fiscal_branch_mismatch", "Selected orders must share the branch")
        request = {
            "organization_id": organization_id,
            "branch_id": selected,
            "actor_user_id": actor,
            "operation": "issue",
            "order_ids": sorted(order_ids),
            "receiver": normalized,
        }
        request_hash = _hash(request)
        if existing:
            row = dict(existing)
            if request_hash != row["request_hash"]:
                raise BusinessError(
                    "fiscal_idempotency_conflict", "Fiscal intention payload changed"
                )
            result = _public(session, row)
            _audit(
                session,
                action="invoicing.command.replayed",
                entity_type="fiscal_command",
                entity_id=row["id"],
                actor_user_id=actor,
                branch_id=selected,
                payload={"state": row["state"]},
            )
            session.commit()
            return result
        if branch is None:
            raise BusinessError("fiscal_branch_mismatch", "Fiscal branch requires review")
        session.execute(
            sa.select(models.legal_entities.c.id)
            .where(
                models.legal_entities.c.id == branch["legal_entity_id"],
                models.legal_entities.c.organization_id == organization_id,
            )
            .with_for_update(key_share=True)
        ).scalar_one()
        session.execute(
            sa.select(models.fiscal_emitter_configurations.c.id)
            .where(
                models.fiscal_emitter_configurations.c.legal_entity_id == branch["legal_entity_id"],
                models.fiscal_emitter_configurations.c.organization_id == organization_id,
            )
            .with_for_update(key_share=True)
        ).scalar_one_or_none()
        configuration = configuration_for_branch(session, organization_id, selected)
        payments = [
            payment_snapshot(session, organization_id, selected, identifier)
            for identifier in sorted(order_ids)
        ]
        currencies = {payment.currency for payment in payments}
        total = sum(payment.total_cents for payment in payments)
        if len(currencies) != 1:
            raise BusinessError("fiscal_currency_mismatch", "Orders must share currency")
        if not 0 <= total <= MAX_TOTAL_CENTS or any(
            payment.paid_cents > 9223372036854775807 for payment in payments
        ):
            raise BusinessError("fiscal_amount_out_of_range", "Fiscal amount requires review")
        reserved = session.scalar(
            sa.select(models.fiscal_order_reservations.c.order_id)
            .where(
                models.fiscal_order_reservations.c.order_id.in_(order_ids),
            )
            .limit(1)
        )
        active_link = session.scalar(
            sa.select(models.fiscal_command_orders.c.order_id)
            .join(
                models.fiscal_commands,
                models.fiscal_commands.c.id == models.fiscal_command_orders.c.command_id,
            )
            .where(
                models.fiscal_command_orders.c.order_id.in_(order_ids),
                models.fiscal_commands.c.state.in_(ACTIVE_STATES),
            )
            .limit(1)
        )
        if reserved or active_link:
            raise BusinessError("fiscal_order_reserved", "An unresolved fiscal intention exists")
        now = datetime.now(timezone.utc)
        identifier = str(uuid4())
        row = {
            "id": identifier,
            "organization_id": organization_id,
            "branch_id": selected,
            "legal_entity_id": branch["legal_entity_id"],
            "actor_user_id": actor,
            "operation": "issue",
            "idempotency_key": idempotency_key,
            "request_hash": request_hash,
            "provider": "facturapi",
            "external_key": "restaurantos-" + identifier,
            "emitter_configuration_id": configuration["id"],
            "emitter_configuration_version": configuration["version"],
            "state": "pending",
            "dispatch_ready": False,
            "total_cents": total,
            "currency": next(iter(currencies)),
            "created_at": now,
            "updated_at": now,
        }
        snapshot = {
            "schema": "fiscal-command-payment/v1",
            "request": request,
            "payments": [asdict(payment) for payment in payments],
            "configuration": {
                "id": configuration["id"],
                "version": configuration["version"],
                "legal_entity_id": branch["legal_entity_id"],
            },
        }
        row["snapshot_ciphertext"] = seal(snapshot, _context(row))
        if len(row["snapshot_ciphertext"]) > MAX_ENVELOPE_CHARS:
            raise BusinessError(
                "fiscal_snapshot_too_large", "Fiscal snapshot exceeds storage limit"
            )
        session.execute(models.fiscal_commands.insert().values(**row))
        for payment in payments:
            session.execute(
                models.fiscal_command_orders.insert().values(
                    command_id=identifier,
                    organization_id=organization_id,
                    branch_id=selected,
                    **{
                        field: getattr(payment, field)
                        for field in (
                            "order_id",
                            "order_version",
                            "total_cents",
                            "paid_cents",
                            "currency",
                        )
                    },
                )
            )
            session.execute(
                models.fiscal_order_reservations.insert().values(
                    order_id=payment.order_id,
                    command_id=identifier,
                )
            )
        session.execute(
            models.fiscal_command_outbox.insert().values(
                command_id=identifier,
                event_type="fiscal.issue.prepare",
                created_at=now,
            )
        )
        _audit(
            session,
            action="invoicing.command.prepared",
            entity_type="fiscal_command",
            entity_id=identifier,
            actor_user_id=actor,
            branch_id=selected,
            payload={"state": "pending", "order_count": len(payments), "dispatch_ready": False},
        )
        result = _public(session, row)
        session.commit()
        return result
    except sa.exc.SQLAlchemyError:
        session.rollback()
        raise BusinessError(
            "fiscal_persistence_unavailable", "Fiscal preparation requires retry"
        ) from None
    except Exception:
        session.rollback()
        raise
