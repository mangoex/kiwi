from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Request

from restaurant_os import delivery_fee, models
from restaurant_os.api import (
    ActorUserDep,
    AuthorizationDep,
    SessionDep,
    _business_response,
    _required_actor_from_request,
)
from restaurant_os.operations import ORGANIZATION_ID

router = APIRouter(prefix="/api/v1", tags=["Delivery services"])


@router.get("/reports/delivery-fees")
def delivery_report(
    branch_id: str,
    start: datetime,
    end: datetime,
    session: SessionDep,
    limit: int = 50,
    offset: int = 0,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    from restaurant_os.delivery_fee_report import report

    actor = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: report(session, actor, branch_id, start, end, limit, offset))


@router.get("/delivery-scopes")
def delivery_scopes(
    session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None
) -> list[dict[str, Any]]:
    actor = _required_actor_from_request(actor_user_id, authorization)

    def read() -> list[dict[str, Any]]:
        delivery_fee.require_catalog_manager(session, actor)
        return [
            dict(row)
            for row in session.execute(
                sa.select(models.branches.c.id, models.branches.c.name, models.branches.c.status)
                .where(
                    models.branches.c.organization_id == ORGANIZATION_ID,
                    models.branches.c.status == "active",
                )
                .order_by(models.branches.c.name)
            ).mappings()
        ]

    return _business_response(read)


@router.get("/delivery-tariffs")
def list_tariffs(
    session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None
) -> dict[str, Any]:
    actor = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delivery_fee.catalog(session, actor))


@router.post("/delivery-tariffs")
def create_tariff(
    payload: dict[str, Any],
    request: Request,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: delivery_fee.save_tariff(
            session, actor, request.headers.get("Idempotency-Key", ""), payload
        )
    )


@router.post("/delivery-tariffs/{tariff_id}/revisions")
def revise_tariff(
    tariff_id: str,
    payload: dict[str, Any],
    request: Request,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: delivery_fee.save_tariff(
            session, actor, request.headers.get("Idempotency-Key", ""), payload, tariff_id
        )
    )


@router.get("/delivery-policies")
def get_policy(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _required_actor_from_request(actor_user_id, authorization)

    def read() -> dict[str, Any]:
        delivery_fee.require_catalog_manager(session, actor)
        if branch_id is not None:
            delivery_fee._branch(session, branch_id)
        return {"policy": delivery_fee.current_policy(session, branch_id or "*")}

    return _business_response(read)


@router.post("/delivery-policies")
def publish_policy(
    payload: dict[str, Any],
    request: Request,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: delivery_fee.save_policy(
            session, actor, request.headers.get("Idempotency-Key", ""), payload
        )
    )


@router.get("/delivery-options")
def delivery_options(
    branch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delivery_fee.options(session, branch_id, actor))
