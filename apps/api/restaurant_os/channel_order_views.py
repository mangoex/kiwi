"""Human channel inboxes use the same metadata boundary as operational accounts."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Literal

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import FinancialAuthority, deny
from restaurant_os.order_operational_views import (
    OrderAccountOperationalV2,
    account_columns,
    operational_account,
)

PROVIDERS = frozenset({"UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP"})


class ChannelOrderOperationalV2(OrderAccountOperationalV2):
    channel: Literal["UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP"]


def list_channel_orders(
    session: Session,
    branch: str,
    provider: str,
    status: str | None,
    actor: str | None,
    legacy: Callable[[], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    try:
        if not actor:
            deny()
        assert actor is not None
        authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
        version = authority._begin()
        revision = authority.policy_revision(branch)
        ops.authorize_branch_scope(session, actor, "orders.read", branch)
        if provider not in PROVIDERS:
            raise ops.BusinessError("channel_query_invalid", "Unknown order channel")
        if revision is None:
            return legacy()
        query = (
            sa.select(*account_columns())
            .select_from(
                models.orders.outerjoin(
                    models.cash_shifts,
                    sa.and_(
                        models.orders.c.cash_shift_id == models.cash_shifts.c.id,
                        models.orders.c.branch_id == models.cash_shifts.c.branch_id,
                        models.orders.c.organization_id == models.cash_shifts.c.organization_id,
                    ),
                ).join(
                    models.channel_orders_meta,
                    sa.and_(
                        models.orders.c.id == models.channel_orders_meta.c.order_id,
                        models.channel_orders_meta.c.provider == provider,
                    ),
                )
            )
            .where(
                models.orders.c.organization_id == ops.ORGANIZATION_ID,
                models.orders.c.branch_id == branch,
                models.orders.c.channel == provider,
            )
        )
        if status is not None:
            query = query.where(models.orders.c.status == status)
        rows = session.execute(
            query.order_by(models.orders.c.created_at.desc(), models.orders.c.id.desc()).limit(100)
        ).mappings()
        result = [
            ChannelOrderOperationalV2.model_validate(
                {**operational_account(dict(row), revision), "channel": provider}
            ).model_dump(mode="json")
            for row in rows
        ]
        ops._audit(
            session,
            "channel.orders.read",
            "channel",
            provider,
            {"provider": provider, "policy_version": revision},
            branch_id=branch,
            actor_user_id=actor,
        )
        session.commit()
        authority._begin(expected_version=version)
        ops.authorize_branch_scope(session, actor, "orders.read", branch)
        if authority.policy_revision(branch) != revision:
            raise ops.BusinessError("cash_authorization_changed", "Refresh current authority")
        return result
    except Exception:
        session.rollback()
        raise
