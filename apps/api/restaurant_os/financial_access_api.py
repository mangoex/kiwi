"""Owner-governed delegation metadata only; no financial DTOs or cash commands."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypeVar
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request, Response
from sqlalchemy.exc import SQLAlchemyError

from restaurant_os.api import (
    ActorUserDep,
    AuthorizationDep,
    SessionDep,
    _business_response,
    _required_actor_from_request,
)
from restaurant_os.auth import verify_session_token
from restaurant_os.blind_cash_transition import TransitionInput, preflight
from restaurant_os.config import get_settings
from restaurant_os.financial_access import FinancialAccessService, GrantInput, RevokeInput
from restaurant_os.operations import ORGANIZATION_ID

router = APIRouter(prefix="/api/v2/financial-access", tags=["Financial authority"])


@router.post("/branches/{branch_id}/preflight")
def transition_preflight(
    branch_id: str,
    payload: TransitionInput,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _human_actor(actor_user_id, authorization)
    response.headers["Cache-Control"] = "no-store"
    return _response(lambda: preflight(session, actor, branch_id, payload))


ResultT = TypeVar("ResultT")


def _human_actor(actor_user_id: str | None, authorization: str | None) -> str:
    if authorization and authorization.startswith("Bearer "):
        payload = verify_session_token(authorization[7:].strip(), get_settings().secret_key)
        # Current human sessions have no typ; service audiences cannot cross this boundary.
        if payload and payload.get("typ") is not None:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "financial_access_denied",
                    "message": "Human authority is required",
                },
            )
    return _required_actor_from_request(actor_user_id, authorization)


def _response(operation: Callable[[], ResultT]) -> ResultT:
    def guarded() -> ResultT:
        try:
            return operation()
        except SQLAlchemyError:
            # Never pass SQL/parameters to the legacy database response/log wrapper.
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "financial_access_unavailable",
                    "message": "Retry this command later",
                },
            ) from None

    return _business_response(guarded)


@router.post("/grants")
def issue_grant(
    payload: GrantInput,
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _human_actor(actor_user_id, authorization)
    response.headers["Cache-Control"] = "no-store"
    return _response(
        lambda: FinancialAccessService(session, ORGANIZATION_ID).issue(
            actor,
            request.headers.get("Idempotency-Key", ""),
            payload.model_dump(mode="json"),
        )
    )


@router.post("/grants/{grant_id}/revoke")
def revoke_grant(
    grant_id: UUID,
    payload: RevokeInput,
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _human_actor(actor_user_id, authorization)
    response.headers["Cache-Control"] = "no-store"
    return _response(
        lambda: FinancialAccessService(session, ORGANIZATION_ID).revoke(
            actor,
            str(grant_id),
            request.headers.get("Idempotency-Key", ""),
            payload.model_dump(mode="json"),
        )
    )


@router.get("/grants")
def list_grants(
    response: Response,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor = _human_actor(actor_user_id, authorization)
    response.headers["Cache-Control"] = "no-store"
    return _response(
        lambda: {
            "grants": FinancialAccessService(
                session,
                ORGANIZATION_ID,
            ).list_grants(actor, limit=limit, offset=offset)
        }
    )
