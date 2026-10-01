"""Durable purchase creation receipts; domain, audit and command share one commit."""

from __future__ import annotations

import hashlib
import json
import logging
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    BusinessError,
    _acquire_idempotency_lock,
    _actor_user_id,
    _begin_cash_shift_serialization,
    _create_purchase_document,
    _id,
    _now,
    _sanitize_for_json,
    authorize_branch_scope,
)
from restaurant_os.purchase_workspace import preview_purchase, require_explicit_purchase_prices

logger = logging.getLogger(__name__)


def _identity_conflict(exc: IntegrityError) -> bool:
    constraint = getattr(getattr(exc.orig, "diag", None), "constraint_name", None)
    return constraint == "uq_purchase_document_identity" or (
        "UNIQUE constraint failed: purchase_documents.branch_id, "
        "purchase_documents.supplier_id, purchase_documents.document_type, "
        "purchase_documents.folio"
    ) in str(exc.orig)


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
        identity = json.dumps(
            [
                branch_id,
                payload.get("supplier_id"),
                str(payload.get("document_type", "receipt")).strip().lower(),
                str(payload.get("folio", "")).strip(),
            ],
            separators=(",", ":"),
        )
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
