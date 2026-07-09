from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os.auth import create_session_token, verify_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.operations import (
    AuthorizationError,
    BusinessError,
    advance_kds_task,
    assign_user_role,
    authenticate_user,
    close_cash_shift_with_cut,
    create_branch,
    create_local_order,
    create_product,
    create_role,
    create_user,
    delete_branch,
    delete_product,
    delete_user,
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
    record_inventory_opening_balance,
    retry_print_job,
    update_branch,
    update_product,
    update_user,
)
from restaurant_os.operations import (
    cancel_order as cancel_order_operation,
)
from restaurant_os.platform_data import (
    bootstrap_status,
    list_active_recipes,
    list_branches,
    list_catalog_products,
    list_inventory_kardex,
    list_inventory_stock,
    list_organizations,
    list_roles,
    list_users,
)

router = APIRouter(prefix="/api/v1", tags=["platform-api"])


SessionDep = Annotated[Session, Depends(get_session)]
ActorUserDep = Annotated[str | None, Header(alias="X-Actor-User-Id")]
AuthorizationDep = Annotated[str | None, Header(alias="Authorization")]


def _actor_from_request(actor_user_id: str | None, authorization: str | None) -> str | None:
    if actor_user_id:
        return actor_user_id
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_session_token(token, get_settings().secret_key)
    return str(payload.get("sub")) if payload and payload.get("sub") else None


@router.get("/platform/bootstrap-status")
def get_bootstrap_status(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: bootstrap_status(session))


@router.post("/auth/login")
def login(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    email = str(payload.get("email", ""))
    password = str(payload.get("password", ""))

    def operation() -> dict[str, Any]:
        user = authenticate_user(session, email, password)
        token = create_session_token(
            {"sub": user["id"], "email": user["email"]},
            get_settings().secret_key,
        )
        return {"token": token, "user": user}

    return _business_response(operation)


@router.get("/organizations")
def get_organizations(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_organizations(session))


@router.get("/branches")
def get_branches(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_branches(session))


@router.post("/branches")
def post_branch(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    code = str(payload.get("code", ""))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_branch(session, name, code, actor_id))


@router.get("/roles")
def get_roles(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_roles(session))


@router.post("/roles")
def post_role(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    scope = str(payload.get("scope", "branch"))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_role(session, name, scope, actor_id))


@router.get("/users")
def get_users(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_users(session))


@router.post("/users")
def post_user(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    email = str(payload.get("email", ""))
    display_name = str(payload.get("display_name", ""))
    password = payload.get("password")
    actor_id = _actor_from_request(actor_user_id, authorization)
    normalized_password = str(password) if password else None
    return _business_response(
        lambda: create_user(session, email, display_name, actor_id, normalized_password)
    )


@router.post("/users/{user_id}/roles")
def post_user_role(
    user_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    role_id = str(payload.get("role_id", ""))
    branch_id = payload.get("branch_id")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: assign_user_role(session, user_id, role_id, branch_id, actor_id)
    )


@router.get("/catalog/products")
def get_catalog_products(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_catalog_products(session))


@router.post("/catalog/products")
def post_catalog_product(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    sku = str(payload.get("sku", ""))
    category_name = str(payload.get("category_name", ""))
    station = str(payload.get("station", "kitchen"))
    price_cents = int(payload.get("price_cents", 0))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_product(session, name, sku, category_name, station, price_cents, actor_id)
    )


@router.get("/inventory/stock")
def get_inventory_stock(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_inventory_stock(session))


@router.get("/inventory/kardex")
def get_inventory_kardex(
    session: SessionDep,
    item_id: str | None = None,
) -> list[dict[str, Any]]:
    return _database_response(lambda: list_inventory_kardex(session, item_id))


@router.post("/inventory/opening-balances")
def post_inventory_opening_balance(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    item_id = str(payload.get("item_id", ""))
    quantity_base_units = int(payload.get("quantity_base_units", 0))
    reason = str(payload.get("reason", "Saldo inicial"))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: record_inventory_opening_balance(
            session,
            item_id,
            quantity_base_units,
            reason,
            actor_id,
        )
    )


@router.get("/recipes")
def get_recipes(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_active_recipes(session))


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


@router.post("/orders/{order_id}/cancel")
def cancel_order_endpoint(
    order_id: str,
    payload: dict[str, Any] | None,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    reason = str((payload or {}).get("reason", "Cancelacion solicitada en POS"))
    classification = (payload or {}).get("classification")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: cancel_order_operation(session, order_id, reason, classification, actor_id)
    )


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


@router.put("/users/{user_id}")
def put_user(
    user_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    email = payload.get("email")
    display_name = payload.get("display_name")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_user(session, user_id, email, display_name, actor_id))


@router.delete("/users/{user_id}")
def delete_user_endpoint(
    user_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delete_user(session, user_id, actor_id))


@router.put("/branches/{branch_id}")
def put_branch(
    branch_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    code = payload.get("code")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_branch(session, branch_id, name, code, actor_id))


@router.delete("/branches/{branch_id}")
def delete_branch_endpoint(
    branch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delete_branch(session, branch_id, actor_id))


@router.put("/catalog/products/{product_id}")
def put_catalog_product(
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    sku = payload.get("sku")
    price_cents = payload.get("price_cents")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_product(session, product_id, name, sku, price_cents, actor_id)
    )


@router.delete("/catalog/products/{product_id}")
def delete_catalog_product_endpoint(
    product_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delete_product(session, product_id, actor_id))


def _database_response(operation):
    try:
        return operation()
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="database_unavailable") from exc


def _business_response(operation):
    try:
        return _database_response(operation)
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except BusinessError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

from restaurant_os.operations import (
    update_role,
    delete_role,
    update_role_permissions,
    create_warehouse,
    update_warehouse,
)
from restaurant_os.platform_data import (
    list_permissions,
    list_role_permissions,
    list_warehouses,
)

@router.put("/roles/{role_id}")
def put_role(
    role_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    scope = payload.get("scope")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_role(session, role_id, name, scope, actor_id))

@router.delete("/roles/{role_id}")
def delete_role_endpoint(
    role_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delete_role(session, role_id, actor_id))

@router.get("/permissions")
def get_permissions(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_permissions(session))

@router.get("/roles/{role_id}/permissions")
def get_role_permissions(role_id: str, session: SessionDep) -> list[str]:
    return _database_response(lambda: list_role_permissions(session, role_id))

@router.put("/roles/{role_id}/permissions")
def put_role_permissions(
    role_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    permission_ids = payload.get("permission_ids", [])
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_role_permissions(session, role_id, permission_ids, actor_id))

@router.get("/warehouses")
def get_warehouses(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_warehouses(session))

@router.post("/warehouses")
def post_warehouse(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    branch_id = str(payload.get("branch_id", ""))
    name = str(payload.get("name", ""))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_warehouse(session, branch_id, name, actor_id))

@router.put("/warehouses/{warehouse_id}")
def put_warehouse(
    warehouse_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    status = payload.get("status")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_warehouse(session, warehouse_id, name, status, actor_id))

