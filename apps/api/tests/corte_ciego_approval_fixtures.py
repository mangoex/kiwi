"""Synthetic approved inputs for receipt regressions; real authority and consumption run."""

from datetime import timedelta
from typing import Any

import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.order_exception_schema import CAPABILITY
from restaurant_os.order_exceptions import digest
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID


def approved(
    factory: Any,
    order: str,
    action: str,
    version: int,
    reason: str,
    command: dict[str, Any],
    *,
    actor_user_id: str = ADMIN_USER_ID,
) -> str:
    with factory() as session:
        grant_permission(session, ADMIN_ROLE_ID, CAPABILITY)
        branch = session.scalar(
            sa.select(models.orders.c.branch_id).where(models.orders.c.id == order)
        )
        auth_version = session.scalar(
            sa.select(models.users.c.authorization_version).where(
                models.users.c.id == ADMIN_USER_ID
            )
        )
        now, identifier = ops._now(), ops._id()
        session.execute(
            models.order_exception_authorizations.insert().values(
                id=identifier,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=branch,
                order_id=order,
                actor_user_id=actor_user_id,
                supervisor_user_id=ADMIN_USER_ID,
                supervisor_version=auth_version,
                action=action,
                expected_version=version,
                request_hash=digest(action, version, reason, command),
                reason=reason,
                authorized_at=now,
                expires_at=now + timedelta(minutes=2),
            )
        )
        session.commit()
        return identifier
