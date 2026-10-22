"""Human diagnostic metadata; original webhook bodies remain ingestion evidence."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_financial_schemas import FinancialRecord
from restaurant_os.financial_authority import deny, governance_lock

PROVIDERS = frozenset({"UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP"})
STATUSES = ("received", "processed", "failed", "error", "rejected")


class IntegrationLogMetadataV2(FinancialRecord):
    schema_version: Literal[2] = 2
    projection: Literal["operational"] = "operational"
    id: str
    provider: Literal["UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP"]
    status: Literal["received", "processed", "failed", "error", "rejected", "unknown"]
    created_at: datetime
    processed_at: datetime | None


def _authorize(session: Session, organization: str, actor: str | None) -> bool:
    # The central application's administrative permission evaluator is tenant-bound.
    if organization != ops.ORGANIZATION_ID or not actor:
        deny()
    governance_lock(session, organization)
    current = session.scalar(
        sa.select(models.users.c.id)
        .where(
            models.users.c.id == actor,
            models.users.c.organization_id == organization,
            models.users.c.status == "active",
        )
        .with_for_update(read=True)
    )
    if current is None:
        deny()
    assert actor is not None
    ops.require_permission(session, actor, "admin.manage")
    policy = models.blind_cash_policy_revisions
    # Logs lack resolved branch provenance. Once protected, a suspended policy
    # cannot turn this organization-wide list back into an original-payload export.
    return (
        session.scalar(
            sa.select(policy.c.branch_id)
            .where(
                policy.c.organization_id == organization,
                policy.c.event == "activated",
            )
            .limit(1)
        )
        is not None
    )


def list_logs(
    session: Session, organization: str, provider: str, limit: int, actor: str | None
) -> list[dict[str, Any]]:
    try:
        protected = _authorize(session, organization, actor)
        if provider not in PROVIDERS or not 1 <= limit <= 200:
            raise ops.BusinessError("integration_logs_query_invalid", "Invalid log query")
        table = models.integration_webhook_logs
        query = sa.select(table)
        if protected:
            query = sa.select(
                table.c.id,
                table.c.provider,
                table.c.created_at,
                table.c.processed_at,
                sa.case((table.c.status.in_(STATUSES), table.c.status), else_="unknown").label(
                    "status"
                ),
            )
        rows = session.execute(
            query.where(
                table.c.organization_id == organization,
                table.c.provider == provider,
            )
            .order_by(table.c.created_at.desc(), table.c.id.desc())
            .limit(limit)
        ).mappings()
        result = [
            IntegrationLogMetadataV2.model_validate(row).model_dump(mode="json")
            if protected
            else dict(row)
            for row in rows
        ]
        ops._audit(
            session,
            "integration.logs.read",
            "integration",
            provider,
            {"provider": provider},
            branch_id=None,
            organization_id=organization,
            actor_user_id=actor,
        )
        session.commit()
        if _authorize(session, organization, actor) != protected:
            raise ops.BusinessError(
                "cash_authorization_changed", "Policy changed during log delivery"
            )
        return result
    except Exception:
        session.rollback()
        raise
