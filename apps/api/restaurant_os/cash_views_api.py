"""Version 2 cash reads, receipts, and CORTE-CIEGO-001 Phases 2-6 endpoints."""

from __future__ import annotations

from typing import Any

import sqlalchemy as sa
from fastapi import APIRouter, Query, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.api import ActorUserDep, AuthorizationDep, SessionDep
from restaurant_os.blind_cash_phase2 import (
    configure_denominations,
    confirm_declaration,
    denomination_catalog_ready,
    finalize_blind_cut,
    get_financial_reconciliation_detail,
    list_denominations,
    record_custody_delivery,
    report_cut_error,
    save_declaration_draft,
)
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
from restaurant_os.operational_controls import (
    authorize_and_reprint_ticket,
    evaluate_consumption_variance_alerts,
    evaluate_delayed_orders,
    evaluate_expiring_lots,
    evaluate_high_waste_alerts,
    open_cash_drawer_no_sale,
)
from restaurant_os.owner_alerts import (
    acknowledge_owner_alert,
    configure_alert_recipient,
    list_owner_alerts,
    retry_pending_alerts,
)
from restaurant_os.product_margins import evaluate_product_margins
from restaurant_os.suggested_purchases import list_suggested_purchases

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

        # Phase 2 denomination capture & blind finalization pathways
        if action == "count" and "denominations" in payload:
            return confirm_declaration(session, user, str(cut_id), payload, key)
        if action == "finalize":
            return finalize_blind_cut(session, user, str(cut_id), payload, key)

        stored = session.scalar(
            sa.select(models.user_cash_cut_commands.c.id).where(
                models.user_cash_cut_commands.c.organization_id == ops.ORGANIZATION_ID,
                models.user_cash_cut_commands.c.actor_user_id == user,
                models.user_cash_cut_commands.c.idempotency_key == key,
            )
        )
        if stored is None:
            if action == "create" and denomination_catalog_ready(session, ops.ORGANIZATION_ID):
                views.authority.require_capability("cash.user_cut.capture", str(meta["branch_id"]))
                return ops.UserCashCutService(session).create(payload, key, user)
            views.authority.require_capability(
                "cash.user_cut.finalize" if action == "finalize" else "cash.user_cut.capture",
                str(meta["branch_id"]),
            )
            if (
                action == "count"
                and ("counted_cash_cents" in payload or "total_cents" in payload)
                and denomination_catalog_ready(session, ops.ORGANIZATION_ID)
            ):
                raise ops.BusinessError(
                    "client_total_forbidden",
                    "Client-calculated totals are not accepted; "
                    "submit denomination piece counts only",
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


# --- Phase 2: Denominations, Drafts, Custody Delivery, Error Reports, Reconciliation ---


@router.get("/cash/denominations")
def get_denominations(
    branch_id: str,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: {"items": list_denominations(session, user, branch_id)})


@router.put("/cash/denominations")
def put_denominations(
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: {"items": configure_denominations(session, user, payload)})


@router.put("/cash/user-cuts/{cut_id}/declaration-draft")
def put_declaration_draft(
    cut_id: str,
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: save_declaration_draft(session, user, cut_id, payload))


@router.post("/cash/user-cuts/{cut_id}/custody-delivery")
def post_custody_delivery(
    cut_id: str,
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: record_custody_delivery(session, user, cut_id, payload))


@router.post("/cash/user-cuts/{cut_id}/error-reports")
def post_cut_error_report(
    cut_id: str,
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: report_cut_error(session, user, cut_id, payload))


@router.get("/financial/cash/user-cuts/{cut_id}/reconciliation")
def get_cut_reconciliation(
    cut_id: str,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: get_financial_reconciliation_detail(session, user, cut_id))


# --- Phase 3: Owner Alerts, Delegate Recipients, Retry ---


@router.get("/financial/owner-alerts")
def get_owner_alerts(
    branch_id: str,
    response: Response,
    session: SessionDep,
    alert_type: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: {
            "items": list_owner_alerts(session, user, branch_id=branch_id, alert_type=alert_type)
        }
    )


@router.post("/financial/owner-alerts/recipients")
def post_owner_alert_recipient(
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: configure_alert_recipient(
            session,
            user,
            branch_id=str(payload.get("branch_id", "")),
            user_id=str(payload.get("user_id", "")),
            alert_type=str(payload.get("alert_type", "")),
            channel=str(payload.get("channel", "in_app")),
            is_active=bool(payload.get("is_active", True)),
        )
    )


@router.post("/financial/owner-alerts/retry")
def post_owner_alerts_retry(
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    branch_id = payload.get("branch_id")
    return _response(
        lambda: retry_pending_alerts(session, user, branch_id=str(branch_id) if branch_id else None)
    )


@router.post("/financial/owner-alerts/{alert_id}/acknowledge")
def post_acknowledge_owner_alert(
    alert_id: str,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: acknowledge_owner_alert(session, user, alert_id))


# --- Phase 4: Suggested Purchases ---


@router.get("/inventory/suggested-purchases")
def get_suggested_purchases(
    branch_id: str,
    response: Response,
    session: SessionDep,
    include_all_below_max: bool = False,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: list_suggested_purchases(
            session,
            user,
            branch_id,
            include_all_below_max=include_all_below_max,
        )
    )


# --- Phase 5: Product Margins ---


@router.get("/financial/products/margins")
def get_product_margins(
    branch_id: str,
    response: Response,
    session: SessionDep,
    product_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: evaluate_product_margins(
            session,
            user,
            branch_id,
            product_id=product_id,
        )
    )


# --- Phase 6: Operational Controls (Ticket Reprint, No-Sale Drawer Open, Alert Evaluations) ---


@router.post("/orders/{order_id}/reprint-ticket")
def post_reprint_ticket(
    order_id: str,
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: authorize_and_reprint_ticket(session, user, order_id, payload))


@router.post("/cash/shifts/{shift_id}/open-drawer-no-sale")
def post_open_drawer_no_sale(
    shift_id: str,
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: open_cash_drawer_no_sale(session, user, shift_id, payload))


@router.post("/operational-controls/evaluate")
def post_evaluate_operational_controls(
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor(response, actor_user_id, authorization)
    branch_id = str(payload.get("branch_id", ""))
    lots = payload.get("lots")
    delay_minutes = int(payload.get("delay_threshold_minutes", 25))

    def run_eval() -> dict[str, Any]:
        waste_alerts = evaluate_high_waste_alerts(session, branch_id)
        variance_alerts = evaluate_consumption_variance_alerts(session, branch_id)
        fefo_result = evaluate_expiring_lots(
            session, branch_id, lots=lots if isinstance(lots, list) else None
        )
        delayed_alerts = evaluate_delayed_orders(
            session, branch_id, threshold_minutes=delay_minutes
        )
        return {
            "branch_id": branch_id,
            "high_waste_alerts": waste_alerts,
            "consumption_variance_alerts": variance_alerts,
            "fefo_lots": fefo_result["fefo_lots"],
            "expiring_lot_alerts": fefo_result["alerts"],
            "delayed_order_alerts": delayed_alerts,
        }

    return _response(run_eval)
