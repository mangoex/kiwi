"""Explicit route dependency: mixed v1 contracts cannot serve activated branches."""

from __future__ import annotations

from typing import Annotated, Any

import sqlalchemy as sa
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.cash_views import active_revision
from restaurant_os.database import get_session
from restaurant_os.financial_authority import governance_lock


async def cash_legacy_guard(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
) -> None:
    # Lazy import avoids api -> dependency -> api initialization cycles.
    from restaurant_os.financial_access_api import _human_actor, _response

    body: Any = {}
    if request.method == "POST":
        try:
            body = await request.json()
        except ValueError:
            body = {}
    response.headers["Cache-Control"] = "no-store"

    def check() -> None:
        governance_lock(session, ops.ORGANIZATION_ID, write=request.method == "POST")
        actor = _human_actor(
            request.headers.get("X-Actor-User-Id"), request.headers.get("Authorization")
        )
        if (
            session.scalar(
                sa.select(models.users.c.id).where(
                    models.users.c.id == actor,
                    models.users.c.organization_id == ops.ORGANIZATION_ID,
                    models.users.c.status == "active",
                )
            )
            is None
        ):
            raise ops.AuthorizationError("actor_not_authorized", "Actor is not authorized")
        params = request.path_params
        table: sa.Table | None = None
        resource = params.get("cash_shift_id") or params.get("cash_cut_id")
        if "cash_shift_id" in params:
            table = models.cash_shifts
        elif "cash_cut_id" in params:
            table = models.user_cash_cuts
        elif "request_id" in params:
            table = models.user_cash_cuts
            resource = session.scalar(
                sa.select(models.user_cash_cut_reopen_requests.c.cash_cut_id).where(
                    models.user_cash_cut_reopen_requests.c.id == params["request_id"],
                    models.user_cash_cut_reopen_requests.c.organization_id == ops.ORGANIZATION_ID,
                )
            )
        if table is not None:
            branches = list(
                session.scalars(
                    sa.select(table.c.branch_id).where(
                        table.c.id == resource,
                        table.c.organization_id == ops.ORGANIZATION_ID,
                    )
                )
            )
        else:
            branch = request.query_params.get("branch_id")
            if isinstance(body, dict):
                branch = body.get("branch_id") or branch
                # Create scope is derived from the shift, not the client branch claim.
                if body.get("cash_shift_id"):
                    branch = session.scalar(
                        sa.select(models.cash_shifts.c.branch_id).where(
                            models.cash_shifts.c.id == body["cash_shift_id"],
                            models.cash_shifts.c.organization_id == ops.ORGANIZATION_ID,
                        )
                    )
            branches = (
                [branch]
                if branch
                else list(
                    session.scalars(
                        sa.select(models.branches.c.id).where(
                            models.branches.c.organization_id == ops.ORGANIZATION_ID
                        )
                    )
                )
            )
        if any(active_revision(session, str(branch)) is not None for branch in branches):
            raise ops.BusinessError("cash_contract_upgrade_required", "Use the version 2 contract")

    # SQL lock waits must leave the event loop free to close sibling transactions.
    await run_in_threadpool(_response, check)
