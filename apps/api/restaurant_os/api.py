from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os.database import get_session
from restaurant_os.operations import (
    BusinessError,
    advance_kds_task,
    assign_user_role,
    close_cash_shift_with_cut,
    create_branch,
    create_local_order,
    create_product,
    create_role,
    create_user,
    get_cash_shift_summary,
    get_open_cash_shift,
    get_sync_status,
    list_kds_tasks,
    list_payments,
    list_print_jobs,
    list_recent_orders,
    list_sync_events,
    open_cash_shift,
    pay_order,
    receive_sync_command,
    retry_print_job,
)
from restaurant_os.platform_data import (
    bootstrap_status,
    list_branches,
    list_catalog_products,
    list_organizations,
    list_roles,
    list_users,
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


@router.post("/branches")
def post_branch(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    code = str(payload.get("code", ""))
    return _business_response(lambda: create_branch(session, name, code))


@router.get("/roles")
def get_roles(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_roles(session))


@router.post("/roles")
def post_role(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    scope = str(payload.get("scope", "branch"))
    return _business_response(lambda: create_role(session, name, scope))


@router.get("/users")
def get_users(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_users(session))


@router.post("/users")
def post_user(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    email = str(payload.get("email", ""))
    display_name = str(payload.get("display_name", ""))
    return _business_response(lambda: create_user(session, email, display_name))


@router.post("/users/{user_id}/roles")
def post_user_role(
    user_id: str,
    payload: dict[str, Any],
    session: SessionDep,
) -> dict[str, Any]:
    role_id = str(payload.get("role_id", ""))
    branch_id = payload.get("branch_id")
    return _business_response(lambda: assign_user_role(session, user_id, role_id, branch_id))


@router.get("/catalog/products")
def get_catalog_products(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_catalog_products(session))


@router.post("/catalog/products")
def post_catalog_product(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    sku = str(payload.get("sku", ""))
    category_name = str(payload.get("category_name", ""))
    station = str(payload.get("station", "kitchen"))
    price_cents = int(payload.get("price_cents", 0))
    return _business_response(
        lambda: create_product(session, name, sku, category_name, station, price_cents)
    )


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


@router.post("/sync/commands")
def sync_command(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    return _business_response(lambda: receive_sync_command(session, payload))


@router.get("/sync/events")
def get_sync_events(session: SessionDep, after_checkpoint: int = 0) -> list[dict[str, Any]]:
    return _database_response(lambda: list_sync_events(session, after_checkpoint))


@router.get("/sync/status")
def sync_status(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: get_sync_status(session))


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
