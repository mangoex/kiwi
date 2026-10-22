"""Version 2 cash reads and receipts; phase-2 capture is deliberately not activated."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.api import ActorUserDep, AuthorizationDep, SessionDep
from restaurant_os.cash_command_views import shift_command
from restaurant_os.cash_financial_schemas import (
    CashShiftFinancialV2,
    CashShiftSummaryFinancialV2,
    UserCashCutFinancialV2,
)
from restaurant_os.cash_views import (
    CashCommandReceiptV2,
    CashPageV2,
    CashShiftOperationalV2,
    CashViews,
    CurrentShiftV2,
    OwnDeclarationV2,
    UserCashCutOperationalV2,
)
from restaurant_os.financial_access_api import _human_actor, _response
from restaurant_os.financial_authority import governance_lock

router = APIRouter(prefix="/api/v2", tags=["Cash projections"])


class OpenInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    branch_id: str = Field(min_length=1)
    register_id: str = Field(min_length=1, max_length=32)
    opening_cash_cents: int = Field(ge=0)


def actor(response: Response, user: str | None, authorization: str | None) -> str:
    response.headers["Cache-Control"] = "no-store"
    return _human_actor(user, authorization)


@router.get(
    "/cash/shifts/current", response_model=CurrentShiftV2, response_model_exclude_unset=True
)
def current_shift(
    branch_id: str,
    register_id: str,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: CashViews(session, user).current_shift(branch_id, register_id))


@router.get(
    "/cash/shifts",
    response_model=CashPageV2[CashShiftOperationalV2],
    response_model_exclude_unset=True,
)
@router.get(
    "/financial/cash/shifts",
    response_model=CashPageV2[CashShiftFinancialV2],
    response_model_exclude_unset=True,
)
@router.get(
    "/cash/user-cuts",
    response_model=CashPageV2[UserCashCutOperationalV2],
    response_model_exclude_unset=True,
)
@router.get(
    "/financial/cash/user-cuts",
    response_model=CashPageV2[UserCashCutFinancialV2],
    response_model_exclude_unset=True,
)
def cash_list(
    request: Request,
    response: Response,
    session: SessionDep,
    branch_id: str | None = None,
    register_id: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    kind = "shift" if request.url.path.endswith("shifts") else "cut"
    return _response(
        lambda: CashViews(session, user).list_resources(
            kind,
            branch_id,
            financial="/financial/" in request.url.path,
            limit=limit,
            cursor=cursor,
            register_id=register_id,
        )
    )


@router.get(
    "/cash/shifts/{resource_id}",
    response_model=CashShiftOperationalV2,
    response_model_exclude_unset=True,
)
@router.get(
    "/financial/cash/shifts/{resource_id}",
    response_model=CashShiftFinancialV2,
    response_model_exclude_unset=True,
)
@router.get(
    "/financial/cash/shifts/{resource_id}/summary",
    response_model=CashShiftSummaryFinancialV2,
    response_model_exclude_unset=True,
)
@router.get(
    "/cash/user-cuts/{resource_id}",
    response_model=UserCashCutOperationalV2,
    response_model_exclude_unset=True,
)
@router.get(
    "/financial/cash/user-cuts/{resource_id}",
    response_model=UserCashCutFinancialV2,
    response_model_exclude_unset=True,
)
def cash_detail(
    resource_id: str,
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    kind = "shift" if "/shifts/" in request.url.path else "cut"

    def read() -> dict[str, Any]:
        detail = CashViews(session, user).detail(
            kind,
            resource_id,
            financial="/financial/" in request.url.path,
        )
        if request.url.path.endswith("/summary"):
            return CashShiftSummaryFinancialV2.model_validate(
                {
                    "resource_id": resource_id,
                    **{
                        key: detail[key]
                        for key in (
                            "projection",
                            "schema_version",
                            "policy_version",
                            "closure",
                            "current_summary",
                        )
                    },
                }
            ).model_dump(mode="json", exclude_unset=True)
        return detail

    return _response(read)


@router.get(
    "/cash/user-cuts/{cut_id}/own-declaration",
    response_model=OwnDeclarationV2,
    response_model_exclude_unset=True,
)
def own_declaration(
    cut_id: str,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: CashViews(session, user).declaration(cut_id))


@router.post("/cash/shifts/open", response_model=CashCommandReceiptV2)
def open_shift(
    payload: OpenInput,
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: shift_command(
            session,
            user,
            "open",
            None,
            payload.model_dump(),
            request.headers.get("Idempotency-Key", ""),
            intent=request.headers.get("X-Operational-Intent"),
            context=request.headers.get("X-Branch-Context"),
        )
    )


@router.post("/cash/shifts/{shift_id}/close-operationally", response_model=CashCommandReceiptV2)
def close_shift(
    shift_id: str,
    payload: dict[str, Any],
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)

    def execute() -> dict[str, Any]:
        if payload:
            raise ops.BusinessError("cash_shift_close_payload_invalid", "Use an empty object")
        return shift_command(
            session,
            user,
            "close",
            shift_id,
            {},
            request.headers.get("Idempotency-Key", ""),
            intent=request.headers.get("X-Operational-Intent"),
            context=request.headers.get("X-Branch-Context"),
        )

    return _response(execute)


@router.post("/cash/user-cuts", response_model=CashCommandReceiptV2)
@router.post("/cash/user-cuts/{cut_id}/counted-cash", response_model=CashCommandReceiptV2)
@router.post("/cash/user-cuts/{cut_id}/finalize", response_model=CashCommandReceiptV2)
def cut_capture_gate(
    payload: dict[str, Any],
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    cut_id: str | None = request.path_params.get("cut_id")
    user = actor(response, actor_user_id, authorization)

    def execute() -> dict[str, Any]:
        governance_lock(session, ops.ORGANIZATION_ID, write=True)
        views = CashViews(session, user)
        meta = (
            views.metadata("cut", cut_id)
            if cut_id
            else views.metadata("shift", str(payload.get("cash_shift_id", "")))
        )
        views.revision(str(meta["branch_id"]))
        action = (
            "create"
            if not cut_id
            else "count"
            if request.url.path.endswith("counted-cash")
            else "finalize"
        )
        key = request.headers.get("Idempotency-Key", "")
        stored = session.scalar(
            sa.select(models.user_cash_cut_commands.c.id).where(
                models.user_cash_cut_commands.c.organization_id == ops.ORGANIZATION_ID,
                models.user_cash_cut_commands.c.actor_user_id == user,
                models.user_cash_cut_commands.c.idempotency_key == key,
            )
        )
        if stored is None:
            views.authority.require_capability(
                "cash.user_cut.finalize" if action == "finalize" else "cash.user_cut.capture",
                str(meta["branch_id"]),
            )
            raise ops.BusinessError("cash_capture_not_ready", "Phase 2 capture is not active")
        service = ops.UserCashCutService(session)
        if action == "create":
            return service.create(payload, key, user)
        if action == "count":
            return service.counted_cash(str(cut_id), payload, key, user)
        return service.finalize(str(cut_id), payload, key, user)

    return _response(execute)


@router.post("/cash/user-cuts/{cut_id}/reopen-requests", response_model=CashCommandReceiptV2)
def request_correction(
    cut_id: str,
    payload: dict[str, Any],
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)

    def execute() -> dict[str, Any]:
        views = CashViews(session, user)
        governance_lock(session, ops.ORGANIZATION_ID, write=True)
        views.revision(str(views.metadata("cut", cut_id)["branch_id"]))
        return ops.UserCashCutService(session).request_reopen(
            cut_id,
            payload,
            request.headers.get("Idempotency-Key", ""),
            user,
        )

    return _response(execute)


@router.post(
    "/cash/user-cuts/reopen-requests/{request_id}/{action}", response_model=CashCommandReceiptV2
)
def decide_correction(
    request_id: str,
    action: str,
    payload: dict[str, Any],
    request: Request,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)

    def execute() -> dict[str, Any]:
        if payload or action not in {"approve", "reject", "compensate"}:
            raise ops.BusinessError("cash_cut_scope_invalid", "Correction action is invalid")
        governance_lock(session, ops.ORGANIZATION_ID, write=True)
        views = CashViews(session, user)
        cut_id = session.scalar(
            sa.select(models.user_cash_cut_reopen_requests.c.cash_cut_id).where(
                models.user_cash_cut_reopen_requests.c.organization_id == ops.ORGANIZATION_ID,
                models.user_cash_cut_reopen_requests.c.id == request_id,
            )
        )
        views.revision(str(views.metadata("cut", str(cut_id))["branch_id"]))
        service = ops.UserCashCutService(session)
        key = request.headers.get("Idempotency-Key", "")
        if action == "compensate":
            return service.compensate_reopen(request_id, key, user)
        return service.decide_reopen(
            request_id,
            "APPROVED" if action == "approve" else "REJECTED",
            key,
            user,
        )

    return _response(execute)
