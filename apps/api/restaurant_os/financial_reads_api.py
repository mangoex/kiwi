"""Read-only financial and operational contracts for activated branches."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Query, Response
from pydantic import ValidationError

from restaurant_os import operations as ops
from restaurant_os.api import ActorUserDep, AuthorizationDep, SessionDep
from restaurant_os.cash_views import CashPageV2
from restaurant_os.cash_views_api import actor
from restaurant_os.customer_operational_views import CustomerOperationalPageV2
from restaurant_os.expense_views import ExpenseOperationalPageV2
from restaurant_os.financial_access_api import _response
from restaurant_os.financial_lists import MovementFinancialV2, PaymentFinancialV2, financial_page
from restaurant_os.operational_reports import OperationalReportV2, Period, operational_report
from restaurant_os.order_detail_views import OrderDetailV2
from restaurant_os.order_exceptions import ExceptionReceipt, ExceptionRequest
from restaurant_os.order_exceptions import issue as issue_order_exception
from restaurant_os.order_exceptions import receipt as order_exception_receipt
from restaurant_os.order_operational_views import OrderAccountOperationalV2
from restaurant_os.purchase_receiving import ReceivingPage

router = APIRouter(prefix="/api/v2", tags=["Scoped reporting"])


@router.get(
    "/orders/{order_id}/exception-authorizations/{authorization_id}/receipt",
    response_model=ExceptionReceipt,
)
def read_order_exception_receipt(
    order_id: str,
    authorization_id: str,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: order_exception_receipt(session, user, order_id, authorization_id))


@router.post("/orders/{order_id}/exception-authorizations")
def authorize_order_exception(
    order_id: str,
    payload: dict[str, Any],
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)

    def operation() -> dict[str, Any]:
        try:
            request = ExceptionRequest.model_validate(payload)
        except ValidationError:
            raise ops.BusinessError(
                "order_exception_invalid", "Invalid authorization request"
            ) from None
        return issue_order_exception(session, user, order_id, request)

    return _response(operation)


@router.get("/purchases/receiving", response_model=ReceivingPage)
def operational_receiving(
    branch_id: str,
    response: Response,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = Query(25, ge=1, le=50),
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    from restaurant_os.purchase_receiving import receiving_page

    user = actor(response, actor_user_id, authorization)
    return _response(lambda: receiving_page(session, user, branch_id, cursor, limit))


@router.get("/expenses", response_model=ExpenseOperationalPageV2)
def operational_expenses(
    branch_id: str,
    response: Response,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    status: str | None = None,
    concept_id: str | None = None,
    payment_method: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    from restaurant_os import expenses

    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: expenses.documents(
            session,
            user,
            branch_id,
            cursor,
            limit,
            status,
            concept_id,
            payment_method,
            operational=True,
        )
    )


@router.get("/customers", response_model=CustomerOperationalPageV2)
def operational_customers(
    branch_id: str,
    response: Response,
    session: SessionDep,
    q: str | None = None,
    phone: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: ops.list_customers_page(
            session,
            branch_id,
            q,
            phone,
            limit,
            offset,
            actor_id=user,
            operational=True,
        )
    )


@router.get("/orders/accounts", response_model=CashPageV2[OrderAccountOperationalV2])
def operational_accounts(
    branch_id: str,
    response: Response,
    session: SessionDep,
    from_utc: datetime | None = None,
    to_utc: datetime | None = None,
    cash_shift_id: str | None = None,
    register_code: str | None = None,
    service_type: str | None = None,
    driver_id: str | None = None,
    q: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: ops.list_order_accounts(
            session,
            {
                "branch_id": branch_id,
                "from_utc": from_utc,
                "to_utc": to_utc,
                "cash_shift_id": cash_shift_id,
                "register_code": register_code,
                "service_type": service_type,
                "driver_id": driver_id,
                "q": q,
                "limit": limit,
                "cursor": cursor,
            },
            user,
            operational=True,
        )
    )


@router.get("/reports/operations", response_model=OperationalReportV2)
def report_operations(
    branch_id: str,
    period: Period,
    anchor_date: date,
    response: Response,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> OperationalReportV2:
    user = actor(response, actor_user_id, authorization)
    return _response(lambda: operational_report(session, user, branch_id, period, anchor_date))


@router.get("/financial/payments", response_model=CashPageV2[PaymentFinancialV2])
def financial_payments(
    response: Response,
    session: SessionDep,
    branch_id: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: financial_page(
            session,
            user,
            branch_id,
            "payments",
            limit=limit,
            cursor=cursor,
        )
    )


@router.get("/financial/cash/movements", response_model=CashPageV2[MovementFinancialV2])
def financial_movements(
    response: Response,
    session: SessionDep,
    branch_id: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)
    return _response(
        lambda: financial_page(
            session,
            user,
            branch_id,
            "movements",
            limit=limit,
            cursor=cursor,
        )
    )


@router.get("/orders/{order_id}", response_model=OrderDetailV2)
def attended_order(
    order_id: str,
    response: Response,
    session: SessionDep,
    expected_version: int = Query(..., ge=1),
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    user = actor(response, actor_user_id, authorization)

    def operation() -> dict[str, Any]:
        result = ops.get_order_detail(
            session,
            order_id,
            user,
            expected_version=expected_version,
            projection_v2=True,
        )
        # Projection is fully materialized under authority/resource locks. Only the
        # read audit is committed here; commands retain their own transaction boundary.
        session.commit()
        return result

    return _response(operation)
