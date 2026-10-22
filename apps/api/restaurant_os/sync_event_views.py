"""Human synchronization diagnostics exclude the original transport payload."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import Projection
from restaurant_os.financial_authority import FinancialAuthority, deny


class SyncEventOperationalV2(Projection):
    id: str
    branch_id: str
    sync_command_id: str
    checkpoint: int
    occurred_at: datetime


def human_sync_events(
    session: Session,
    organization: str,
    branch: str,
    after_checkpoint: int,
    actor: str,
    legacy: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    try:
        if organization != ops.ORGANIZATION_ID:
            deny()
        authority = FinancialAuthority(session, actor, organization)
        version = authority._begin()
        revision = authority.policy_revision(branch)
        ops.authorize_branch_scope(session, actor, "sync.events.read", branch)
        if revision is None:
            return legacy()
        if after_checkpoint < 0:
            raise ops.BusinessError("sync_checkpoint_invalid", "Invalid checkpoint")
        table, commands = models.sync_events, models.sync_commands
        rows = session.execute(
            sa.select(
                table.c.id,
                table.c.branch_id,
                table.c.sync_command_id,
                table.c.checkpoint,
                table.c.occurred_at,
            )
            .select_from(
                table.join(
                    commands,
                    sa.and_(
                        table.c.sync_command_id == commands.c.id,
                        table.c.organization_id == commands.c.organization_id,
                        table.c.branch_id == commands.c.branch_id,
                    ),
                )
            )
            .where(
                table.c.organization_id == organization,
                table.c.branch_id == branch,
                table.c.checkpoint > after_checkpoint,
            )
            .order_by(table.c.checkpoint, table.c.id)
            .limit(100)
        ).mappings()
        result = [
            SyncEventOperationalV2.model_validate({**row, "policy_version": revision}).model_dump(
                mode="json"
            )
            for row in rows
        ]
        ops._audit(
            session,
            "sync.events.read",
            "branch",
            branch,
            {"after_checkpoint": after_checkpoint, "policy_version": revision},
            branch_id=branch,
            actor_user_id=actor,
        )
        session.commit()
        authority._begin(expected_version=version)
        ops.authorize_branch_scope(session, actor, "sync.events.read", branch)
        if authority.policy_revision(branch) != revision:
            raise ops.BusinessError("cash_authorization_changed", "Refresh current authority")
        return result
    except Exception:
        session.rollback()
        raise
