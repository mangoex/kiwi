from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os.database import get_session
from restaurant_os.operations import (
    BusinessError,
    advance_kds_task,
    close_cash_shift_with_cut,
    create_local_order,
    get_cash_shift_summary,
    get_open_cash_shift,
    list_kds_tasks,
    list_payments,
    list_print_jobs,
    list_recent_orders,
    open_cash_shift,
    pay_order,
    retry_print_job,
)
from restaurant_os.platform_data import (
    bootstrap_status,
    list_branches,
    list_catalog_products,
    list_organizations,
)

router = APIRouter(prefix="/api/v1", tags=["platform-api"])


SessionDep = Annotated[Session, Depends(get_session)]


@router.get("/platform/bootstrap-status")
def get_bootstrap_status(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: bootstrap_status(session))


@router.get("/organizations")
def get_organizations(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_organizations(session))


@router.get("/branches")
def get_branches(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_branches(session))


@router.get("/catalog/products")
def get_catalog_products(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_catalog_products(session))


@router.get("/cash-shifts/current")
def get_current_cash_shift(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: {"cash_shift": get_open_cash_shift(session)})


@router.post("/cash-shifts/open")
def open_current_cash_shift(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    opening_cash_cents = int(payload.get("opening_cash_cents", 0))
    return _business_response(lambda: open_cash_shift(session, opening_cash_cents))


@router.get("/cash-shifts/summary")
def get_current_cash_shift_summary(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: get_cash_shift_summary(session))


@router.post("/cash-shifts/close")
def close_current_cash_shift(
    session: SessionDep,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counted_cash_cents = int((payload or {}).get("counted_cash_cents", 0))
    return _business_response(lambda: close_cash_shift_with_cut(session, counted_cash_cents))


@router.get("/orders")
def get_recent_orders(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_recent_orders(session))


@router.post("/orders")
def create_order(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    product_id = str(payload.get("product_id", ""))
    quantity = int(payload.get("quantity", 1))
    return _business_response(lambda: create_local_order(session, product_id, quantity))


@router.post("/orders/{order_id}/payments")
def create_order_payment(
    order_id: str,
    payload: dict[str, Any],
    session: SessionDep,
) -> dict[str, Any]:
    amount_cents = int(payload.get("amount_cents", 0))
    method = str(payload.get("method", "cash"))
    return _business_response(lambda: pay_order(session, order_id, amount_cents, method))


@router.get("/payments")
def get_payments(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_payments(session))


@router.get("/kds/tasks")
def get_kds_tasks(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_kds_tasks(session))


@router.post("/kds/tasks/{task_id}/transition")
def transition_kds_task(
    task_id: str,
    payload: dict[str, Any],
    session: SessionDep,
) -> dict[str, Any]:
    status = str(payload.get("status", ""))
    return _business_response(lambda: advance_kds_task(session, task_id, status))


@router.get("/print-jobs")
def get_print_jobs(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_print_jobs(session))


@router.post("/print-jobs/{job_id}/retry")
def retry_print_job_endpoint(job_id: str, session: SessionDep) -> dict[str, Any]:
    return _business_response(lambda: retry_print_job(session, job_id))


def _database_response(operation):
    try:
        return operation()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc


def _business_response(operation):
    try:
        return _database_response(operation)
    except BusinessError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
