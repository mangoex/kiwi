"""Explicit read dependencies; legacy permissions remain additional requirements."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

import sqlalchemy as sa
from fastapi import Depends, Request, Response
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.database import get_session
from restaurant_os.financial_authority import deny
from restaurant_os.financial_reads import require_financial_read


def financial_read_guard(
    *datasets: str,
    organization_scope: bool = False,
    active_only: bool = False,
    order_resource: bool = False,
    invoice_resource: bool = False,
) -> Callable[..., None]:
    def guard(
        request: Request,
        response: Response,
        session: Annotated[Session, Depends(get_session)],
    ) -> None:
        from restaurant_os.financial_access_api import _human_actor, _response

        response.headers["Cache-Control"] = "no-store"

        def check() -> None:
            actor = _human_actor(
                request.headers.get("X-Actor-User-Id"), request.headers.get("Authorization")
            )
            branch = None if organization_scope else request.query_params.get("branch_id")
            if order_resource or invoice_resource:
                table = models.orders if order_resource else models.cfdi_invoices
                key = "order_id" if order_resource else "invoice_id"
                branch = session.scalar(
                    sa.select(table.c.branch_id).where(
                        table.c.id == request.path_params[key],
                        table.c.organization_id == ops.ORGANIZATION_ID,
                    )
                )
                if branch is None and order_resource:
                    # The canonical order detail also resolves a public intent ID.
                    # Resolve only its scope here; pending and accepted intents retain
                    # the same financial gate, never a raw-body fallback.
                    branch = session.scalar(
                        sa.select(models.public_order_intents.c.branch_id).where(
                            models.public_order_intents.c.id == request.path_params[key],
                            models.public_order_intents.c.organization_id == ops.ORGANIZATION_ID,
                        )
                    )
                if branch is None:
                    # Keep the canonical not-found response for missing invoices;
                    # do not materialize any data or infer financial authority.
                    if invoice_resource:
                        return
                    deny()
            require_financial_read(
                session, actor, branch, datasets, active_only=active_only
            )

        _response(check)

    return guard
