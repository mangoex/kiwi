"""Corporate category mutations with atomic CAS, audit and scoped replay."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from . import models
from .admin_catalog import _require_corporate_catalog
from .operations import ORGANIZATION_ID, BusinessError, NotFoundError, _audit, _now


def require_category_authority(session: Session, actor_user_id: str) -> str:
    return _require_corporate_catalog(session, actor_user_id)


def category_command(
    session: Session,
    actor_user_id: str,
    payload: dict[str, Any],
    *,
    category_id: str | None = None,
    idempotency_key: str | None = None,
    commit: bool = True,
    new_category_id: str | None = None,
) -> dict[str, Any]:
    """Legacy callers omit CAS inputs but still serialize, version and audit changes."""
    try:
        actor_id = require_category_authority(session, actor_user_id)
        if set(payload) - {
            "name",
            "display_order",
            "status",
            "classification_code",
            "expected_version",
        }:
            raise BusinessError("invalid_category", "Unknown category fields")
        modern = "classification_code" in payload or "expected_version" in payload
        expected = payload.get("expected_version")
        if modern and (type(expected) is not int or expected < 0):
            raise BusinessError("category_version_conflict", "Expected version must be an integer")
        if modern and (not isinstance(idempotency_key, str) or not idempotency_key.strip()):
            raise BusinessError("idempotency_key_required", "Idempotency-Key is required")
        key = idempotency_key or str(uuid4())
        if len(key) > 200:
            raise BusinessError("invalid_idempotency_key", "Idempotency key is too long")
        # A single organization lock serializes commands against rollout publication too.
        session.execute(
            sa.select(models.organizations.c.id)
            .where(models.organizations.c.id == ORGANIZATION_ID)
            .with_for_update()
        ).scalar_one()
        operation = "category.update" if category_id else "category.create"
        digest = hashlib.sha256(
            json.dumps(
                {"category_id": category_id, "payload": payload},
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
            ).encode()
        ).hexdigest()
        commands = models.category_configuration_commands
        previous = (
            session.execute(
                sa.select(commands).where(
                    commands.c.organization_id == ORGANIZATION_ID,
                    commands.c.actor_user_id == actor_id,
                    commands.c.operation == operation,
                    commands.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest:
                raise BusinessError("idempotency_key_conflict", "Key used for another request")
            result = dict(previous["result"])
            if commit:
                session.commit()
            return result
        table = models.product_categories
        before = None
        if category_id:
            row = (
                session.execute(
                    sa.select(table)
                    .where(table.c.id == category_id, table.c.organization_id == ORGANIZATION_ID)
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise NotFoundError("category_not_found", "Category not found")
            before = dict(row)
        version = before["configuration_version"] if before else 0
        if modern and expected != version:
            raise BusinessError("category_version_conflict", "Category has changed")
        name = payload.get("name", before["name"] if before else "")
        if (
            not isinstance(name, str)
            or not name.strip()
            or ((not before or "name" in payload) and name.strip() != name.strip().upper())
            or len(name.strip()) > 120
        ):
            raise BusinessError(
                "invalid_category_name" if category_id else "invalid_category",
                "Category name must be uppercase",
            )
        status = payload.get("status", before["status"] if before else "active")
        if not isinstance(status, str) or status not in {"active", "inactive", "archived"}:
            raise BusinessError("invalid_category", "Invalid status")
        order = payload.get("display_order", before["display_order"] if before else 0)
        if type(order) is not int or not 0 <= order <= 100000:
            raise BusinessError("invalid_category", "Invalid display order")
        classification = payload.get(
            "classification_code", before["classification_code"] if before else None
        )
        if classification is not None and classification not in ("food", "drinks", "other"):
            raise BusinessError("invalid_classification", "Invalid classification")
        from .catalog_classification_rollout import require_category_write_allowed

        require_category_write_allowed(session, classification, status)
        target_id = category_id or new_category_id or str(uuid4())
        normalized_name = name.strip() if not before or "name" in payload else name
        duplicate = session.scalar(
            sa.select(table.c.id).where(
                table.c.organization_id == ORGANIZATION_ID,
                table.c.name == normalized_name,
                table.c.id != target_id,
            )
        )
        if duplicate:
            raise BusinessError("category_exists", "Category with this name already exists")
        now = _now()
        values = {
            "name": normalized_name,
            "display_order": order,
            "status": status,
            "classification_code": classification,
            "configuration_version": version + 1,
            "updated_at": now,
        }
        if before:
            changed = session.execute(
                sa.update(table)
                .where(
                    table.c.id == target_id,
                    table.c.organization_id == ORGANIZATION_ID,
                    table.c.configuration_version == version,
                )
                .values(**values)
            )
            if cast(CursorResult[Any], changed).rowcount != 1:
                raise BusinessError("category_version_conflict", "Category has changed")
        else:
            session.execute(
                table.insert().values(
                    id=target_id, organization_id=ORGANIZATION_ID, created_at=now, **values
                )
            )
        result = {"id": target_id, **{k: v for k, v in values.items() if k != "updated_at"}}
        _audit(
            session,
            "category.updated" if before else "category.created",
            "category",
            target_id,
            {"before": before, "after": result, "correlation": key},
            branch_id=None,
            actor_user_id=actor_id,
        )
        session.execute(
            commands.insert().values(
                id=str(uuid4()),
                organization_id=ORGANIZATION_ID,
                actor_user_id=actor_id,
                operation=operation,
                idempotency_key=key,
                request_hash=digest,
                result=result,
                created_at=now,
            )
        )
        if commit:
            session.commit()
        return result
    except Exception:
        session.rollback()
        raise
