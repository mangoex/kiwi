"""Durable purchase creation receipts; domain, audit and command share one commit."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    _acquire_idempotency_lock,
    _actor_user_id,
    _audit,
    _begin_cash_shift_serialization,
    _create_purchase_document,
    _id,
    _now,
    _sanitize_for_json,
    _serialize_purchase_branch,
    authorize_branch_scope,
    get_purchase_document,
)
from restaurant_os.purchase_workspace import (
    prepare_purchase,
    preview_purchase,
    require_explicit_purchase_prices,
)

logger = logging.getLogger(__name__)


def _identity_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return constraint == "uq_purchase_document_identity" or (
        "UNIQUE constraint failed: purchase_documents.branch_id, "
        "purchase_documents.supplier_id, purchase_documents.document_type, "
        "purchase_documents.folio"
    ) in str(exc.orig)


def _document_identity(branch_id: str, payload: dict[str, Any]) -> str:
    # Match prepare_purchase normalization before acquiring any presentation locks.
    return json.dumps(
        [
            branch_id,
            str(payload.get("supplier_id", "")),
            str(payload.get("document_type", "receipt")).strip().lower(),
            str(payload.get("folio", "")).strip(),
        ],
        separators=(",", ":"),
    )


def execute_purchase_creation(
    session: Session,
    payload: dict[str, Any],
    actor_user_id: str | None,
    key_value: str | None,
    reviewed_fingerprint: str | None = None,
) -> dict[str, Any]:
    if key_value is None:
        # Explicit transition compatibility for cached clients. The new editor always sends a key.
        try:
            return _create_purchase_document(session, payload, actor_user_id)
        except IntegrityError as exc:
            session.rollback()
            if _identity_conflict(exc):
                raise BusinessError(
                    "purchase_document_identity_conflict", "Supplier document already exists"
                ) from exc
            raise
    key = key_value.strip()
    if not 8 <= len(key) <= 180:
        raise BusinessError(
            "purchase_creation_key_invalid", "Idempotency-Key requires 8 to 180 chars"
        )
    branch_id = str(payload.get("branch_id") or "")
    actor = _actor_user_id(actor_user_id)
    digest = hashlib.sha256(
        json.dumps(
            {"payload": payload, "preview": reviewed_fingerprint},
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    try:
        _begin_cash_shift_serialization(session)
        authorize_branch_scope(session, actor, "purchases.manage", branch_id)
        _acquire_idempotency_lock(session, "purchase-create-command", key)
        commands = models.purchase_create_commands
        previous = (
            session.execute(
                sa.select(commands).where(
                    commands.c.organization_id == ORGANIZATION_ID,
                    commands.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if (
                previous["actor_user_id"] != actor
                or previous["branch_id"] != branch_id
                or previous["request_hash"] != digest
            ):
                raise BusinessError(
                    "purchase_creation_idempotency_conflict",
                    "Creation key is bound to another request",
                )
            result = dict(previous["result"])
            session.commit()
            logger.info(
                "purchase.workspace.command",
                extra={
                    "operation": "purchase.create",
                    "result": "replay",
                },
            )
            return result
        identity = _document_identity(branch_id, payload)
        _acquire_idempotency_lock(session, "purchase-document-identity", identity)
        existing_document = session.scalar(
            sa.select(models.purchase_documents.c.id).where(
                models.purchase_documents.c.organization_id == ORGANIZATION_ID,
                models.purchase_documents.c.branch_id == branch_id,
                models.purchase_documents.c.supplier_id == str(payload.get("supplier_id", "")),
                models.purchase_documents.c.document_type
                == str(payload.get("document_type", "receipt")).strip().lower(),
                models.purchase_documents.c.folio == str(payload.get("folio", "")).strip(),
            )
        )
        if existing_document:
            raise BusinessError(
                "purchase_document_identity_conflict",
                "This supplier document is already registered",
            )
        require_explicit_purchase_prices(payload)
        if reviewed_fingerprint is not None:
            presentation_ids = sorted(
                {
                    str(line.get("presentation_id", ""))
                    for line in payload.get("lines", [])
                    if isinstance(line, dict)
                }
            )
            session.execute(
                sa.select(models.purchase_presentations.c.id)
                .where(
                    models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
                    models.purchase_presentations.c.id.in_(presentation_ids),
                )
                .order_by(models.purchase_presentations.c.id)
                .with_for_update()
            ).all()
            current = preview_purchase(session, payload, actor)["context_fingerprint"]
            if reviewed_fingerprint != current:
                raise BusinessError("purchase_preview_changed", "Re-read and review current values")
        result = _create_purchase_document(session, payload, actor, commit=False)
        session.execute(
            commands.insert().values(
                id=_id(),
                organization_id=ORGANIZATION_ID,
                branch_id=branch_id,
                actor_user_id=actor,
                idempotency_key=key,
                request_hash=digest,
                purchase_id=result["id"],
                result=_sanitize_for_json(result),
                created_at=_now(),
            )
        )
        session.commit()
        logger.info(
            "purchase.workspace.command",
            extra={
                "operation": "purchase.create",
                "result": "completed",
            },
        )
        return dict(_sanitize_for_json(result))
    except IntegrityError as exc:
        session.rollback()
        if _identity_conflict(exc):
            logger.info(
                "purchase.workspace.command",
                extra={
                    "operation": "purchase.create",
                    "result": "rejected",
                    "code": "purchase_document_identity_conflict",
                },
            )
            raise BusinessError(
                "purchase_document_identity_conflict", "Supplier document already exists"
            ) from exc
        raise
    except Exception as exc:
        session.rollback()
        logger.info(
            "purchase.workspace.command",
            extra={
                "operation": "purchase.create",
                "result": "rejected",
                "code": exc.code if isinstance(exc, BusinessError) else "internal_error",
            },
        )
        raise


def _purchase_snapshot(session: Session, purchase: dict[str, Any]) -> dict[str, Any]:
    lines = [
        dict(row)
        for row in session.execute(
            sa.select(models.purchase_document_lines)
            .where(models.purchase_document_lines.c.purchase_document_id == purchase["id"])
            .order_by(models.purchase_document_lines.c.id)
        ).mappings()
    ]
    return cast(dict[str, Any], _sanitize_for_json({**purchase, "lines": lines}))


def _snapshot_hash(snapshot: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


_LINE_BUSINESS_FIELDS = (
    "presentation_id",
    "item_id",
    "presentation_snapshot",
    "presentation_quantity",
    "base_quantity",
    "unit_price",
    "discount",
    "tax",
    "line_total",
    "inventory_cost",
    "cost_per_base_unit",
)


def _business_line_snapshot(lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [
        cast(
            dict[str, Any],
            _sanitize_for_json({field: line.get(field) for field in _LINE_BUSINESS_FIELDS}),
        )
        for line in lines
    ]
    return sorted(
        normalized,
        key=lambda line: json.dumps(line, sort_keys=True, separators=(",", ":"), default=str),
    )


def execute_purchase_update(
    session: Session,
    purchase_id: str,
    payload: dict[str, Any],
    actor_user_id: str | None,
    key_value: str | None,
    reviewed_fingerprint: str | None = None,
) -> dict[str, Any]:
    key = (key_value or "").strip()
    if not 8 <= len(key) <= 180:
        raise BusinessError(
            "purchase_update_key_invalid", "Idempotency-Key requires 8 to 180 chars"
        )
    raw_version = payload.get("expected_version")
    if isinstance(raw_version, bool) or not isinstance(raw_version, int) or raw_version < 1:
        raise BusinessError("purchase_version_invalid", "A positive expected_version is required")
    expected_version = raw_version
    update_payload = {name: value for name, value in payload.items() if name != "expected_version"}
    require_explicit_purchase_prices(update_payload)
    branch_id = str(update_payload.get("branch_id") or "")
    actor = _actor_user_id(actor_user_id)
    digest = hashlib.sha256(
        json.dumps(
            {
                "purchase_id": purchase_id,
                "expected_version": expected_version,
                "payload": update_payload,
                "preview": reviewed_fingerprint,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode()
    ).hexdigest()
    try:
        _begin_cash_shift_serialization(session)
        authorize_branch_scope(session, actor, "purchases.manage", branch_id)
        _acquire_idempotency_lock(session, "purchase-update-command", key)
        commands = models.purchase_update_commands
        previous = (
            session.execute(
                sa.select(commands).where(
                    commands.c.organization_id == ORGANIZATION_ID,
                    commands.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if (
                previous["actor_user_id"] != actor
                or previous["branch_id"] != branch_id
                or previous["purchase_id"] != purchase_id
                or previous["expected_version"] != expected_version
                or previous["request_hash"] != digest
            ):
                raise BusinessError(
                    "purchase_update_idempotency_conflict",
                    "Update key is bound to another request",
                )
            session.commit()
            logger.info(
                "purchase.workspace.command",
                extra={"operation": "purchase.update", "result": "replay"},
            )
            return dict(previous["result"])

        _serialize_purchase_branch(session, purchase_id, actor)
        purchase = (
            session.execute(
                sa.select(models.purchase_documents)
                .where(
                    models.purchase_documents.c.id == purchase_id,
                    models.purchase_documents.c.organization_id == ORGANIZATION_ID,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if not purchase:
            raise BusinessError("purchase_not_found", "Purchase document was not found")
        if purchase["branch_id"] != branch_id:
            raise BusinessError("purchase_branch_immutable", "Purchase branch cannot be changed")
        if purchase["status"] != "draft":
            raise BusinessError("purchase_not_editable", "Only draft purchases can be edited")
        if purchase["version"] != expected_version:
            raise BusinessError(
                "purchase_version_conflict", "Purchase version changed; review again"
            )

        # Creation also locks identity before presentations. Reversing that order
        # deadlocks when creation and editing compete for the same supplier folio.
        _acquire_idempotency_lock(
            session, "purchase-document-identity", _document_identity(branch_id, update_payload)
        )
        presentation_ids = sorted(
            {
                str(line.get("presentation_id", ""))
                for line in update_payload.get("lines", [])
                if isinstance(line, dict)
            }
        )
        session.execute(
            sa.select(models.purchase_presentations.c.id)
            .where(
                models.purchase_presentations.c.organization_id == ORGANIZATION_ID,
                models.purchase_presentations.c.id.in_(presentation_ids),
            )
            .order_by(models.purchase_presentations.c.id)
            .with_for_update()
        ).all()
        current_preview = preview_purchase(session, update_payload, actor)["context_fingerprint"]
        if reviewed_fingerprint is None or reviewed_fingerprint != current_preview:
            raise BusinessError("purchase_preview_changed", "Re-read and review current values")
        prepared = prepare_purchase(session, update_payload, actor)
        before = _purchase_snapshot(session, dict(purchase))
        duplicate = session.scalar(
            sa.select(models.purchase_documents.c.id).where(
                models.purchase_documents.c.organization_id == ORGANIZATION_ID,
                models.purchase_documents.c.branch_id == branch_id,
                models.purchase_documents.c.supplier_id == prepared["supplier_id"],
                models.purchase_documents.c.document_type == prepared["document_type"],
                models.purchase_documents.c.folio == prepared["folio"],
                models.purchase_documents.c.id != purchase_id,
            )
        )
        if duplicate:
            raise BusinessError(
                "purchase_document_identity_conflict",
                "This supplier document is already registered",
            )
        next_version = expected_version + 1
        now = _now()
        values = {
            "supplier_id": prepared["supplier_id"],
            "document_type": prepared["document_type"],
            "folio": prepared["folio"],
            "document_date": prepared["document_date"],
            "delivered_by_name": prepared["delivered_by_name"],
            "subtotal": prepared["subtotal"],
            "discount_total": prepared["discount_total"],
            "tax_total": prepared["tax_total"],
            "freight_total": prepared["freight_total"],
            "total": prepared["total"],
            "payment_method": prepared["payment_method"],
            "paid_from_cash": prepared["paid_from_cash"],
            "evidence_url": prepared["evidence_url"],
            "notes": prepared["notes"],
            "version": next_version,
        }
        changed_fields = sorted(
            field
            for field, value in values.items()
            if field != "version"
            and _sanitize_for_json(purchase.get(field)) != _sanitize_for_json(value)
        )
        session.execute(
            sa.delete(models.purchase_document_lines).where(
                models.purchase_document_lines.c.purchase_document_id == purchase_id
            )
        )
        session.execute(
            models.purchase_document_lines.insert(),
            [
                {"id": _id(), "purchase_document_id": purchase_id, **line, "created_at": now}
                for line in prepared["lines"]
            ],
        )
        transitioned = session.execute(
            sa.update(models.purchase_documents)
            .where(
                models.purchase_documents.c.id == purchase_id,
                models.purchase_documents.c.status == "draft",
                models.purchase_documents.c.version == expected_version,
            )
            .values(**values)
        )
        if cast(CursorResult[Any], transitioned).rowcount != 1:
            raise BusinessError(
                "purchase_version_conflict", "Purchase version changed; review again"
            )
        after = get_purchase_document(session, purchase_id)
        after_purchase = (
            session.execute(
                sa.select(models.purchase_documents).where(
                    models.purchase_documents.c.id == purchase_id
                )
            )
            .mappings()
            .one()
        )
        after_snapshot = _purchase_snapshot(session, dict(after_purchase))
        if _snapshot_hash({"lines": _business_line_snapshot(before["lines"])}) != _snapshot_hash(
            {"lines": _business_line_snapshot(after_snapshot["lines"])}
        ):
            changed_fields.append("lines")
        _audit(
            session,
            "purchase.updated",
            "purchase_document",
            purchase_id,
            {
                "previous_version": expected_version,
                "version": next_version,
                "changed_fields": sorted(set(changed_fields)),
                "previous_line_count": len(before["lines"]),
                "line_count": len(after["lines"]),
                "previous_total": before["total"],
                "total": after["total"],
                "before_hash": _snapshot_hash(before),
                "after_hash": _snapshot_hash(after_snapshot),
            },
            branch_id,
            actor_user_id=actor,
        )
        result = _sanitize_for_json(after)
        session.execute(
            commands.insert().values(
                id=_id(),
                organization_id=ORGANIZATION_ID,
                branch_id=branch_id,
                actor_user_id=actor,
                purchase_id=purchase_id,
                idempotency_key=key,
                request_hash=digest,
                expected_version=expected_version,
                result=result,
                created_at=now,
            )
        )
        session.commit()
        logger.info(
            "purchase.workspace.command",
            extra={"operation": "purchase.update", "result": "completed"},
        )
        return dict(result)
    except IntegrityError as exc:
        session.rollback()
        if _identity_conflict(exc):
            raise BusinessError(
                "purchase_document_identity_conflict", "Supplier document already exists"
            ) from exc
        raise
    except Exception as exc:
        session.rollback()
        logger.info(
            "purchase.workspace.command",
            extra={
                "operation": "purchase.update",
                "result": "rejected",
                "code": exc.code if isinstance(exc, BusinessError) else "internal_error",
            },
        )
        raise
