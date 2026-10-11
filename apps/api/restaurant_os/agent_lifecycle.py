"""Transactional projection of canonical human decisions into external-agent operations."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models


def _id() -> str:
    return str(uuid4())


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def record_agent_resource_transition(
    session: Session,
    resource_id: str,
    status: str,
    *,
    reason_code: str | None = None,
    occurred_at: datetime | None = None,
) -> None:
    """Update linked agent operations and callback outbox in the caller's transaction."""
    now = occurred_at or datetime.now(timezone.utc)
    operations = (
        session.execute(
            sa.select(models.external_agent_commands)
            .where(models.external_agent_commands.c.resource_id == resource_id)
            .with_for_update()
        )
        .mappings()
        .all()
    )
    for row in operations:
        if row["status"] == status and row["reason_code"] == reason_code:
            continue
        session.execute(
            sa.update(models.external_agent_commands)
            .where(models.external_agent_commands.c.id == row["id"])
            .values(status=status, reason_code=reason_code, updated_at=now)
        )
        integration = (
            session.execute(
                sa.select(
                    models.external_agent_integrations.c.callback_url,
                    models.external_agent_integrations.c.callback_key_id,
                ).where(models.external_agent_integrations.c.id == row["integration_id"])
            )
            .mappings()
            .first()
        )
        if not integration or not integration["callback_url"]:
            continue
        event_id = _id()
        session.execute(
            models.external_agent_callback_outbox.insert().values(
                id=_id(),
                operation_id=row["id"],
                event_id=event_id,
                destination=integration["callback_url"],
                key_id=integration["callback_key_id"],
                payload=_json(
                    {
                        "event_id": event_id,
                        "event_type": "agent.operation.status_changed",
                        "occurred_at": now,
                        "operation_id": row["id"],
                        "operation_type": row["operation_type"],
                        "status": status,
                        "reason_code": reason_code,
                    }
                ),
                status="PENDING",
                attempt_count=0,
                next_attempt_at=now,
                leased_until=None,
                last_error_code=None,
                created_at=now,
                updated_at=now,
            )
        )
