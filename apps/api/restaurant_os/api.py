from __future__ import annotations

import os
import sys

# ruff: noqa: E501, E402
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Header, HTTPException

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
seed_import_error = None
try:
    from seed_menu import seed as run_seed_menu
except Exception as e:
    run_seed_menu = None
    seed_import_error = str(e)

seed_branches_error = None
try:
    from seed_branches import seed as run_seed_branches
except Exception as e:
    run_seed_branches = None
    seed_branches_error = str(e)

from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os.auth import create_session_token, verify_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.legacy_import import (
    complete_legacy_import_batch,
    create_legacy_import_batch,
    ingest_legacy_import_records,
    list_branch_legacy_import_batches,
    list_legacy_import_batches,
    list_legacy_import_records,
)
from restaurant_os.operations import (
    AuthorizationError,
    BusinessError,
    NotFoundError,
    add_customer_address,
    add_supplier_contact,
    advance_kds_task,
    amend_order,
    apply_ingredient_variation_assignments,
    approve_physical_count_session,
    archive_ingredient_variation_assignment,
    assign_user_role,
    authenticate_user,
    authorize_branch_scope,
    build_session_profile,
    bulk_order_comments,
    cancel_inventory_transfer,
    cancel_physical_count_session,
    cancel_purchase_document,
    capture_physical_count_line,
    close_cash_shift_with_cut,
    close_physical_count_session,
    confirm_production_batch,
    confirm_purchase_document,
    confirm_waste_record,
    create_branch,
    create_business_unit,
    create_customer,
    create_ingredient_variation,
    create_inventory_transfer,
    create_local_order,
    create_modifier_group,
    create_modifier_option,
    create_physical_count_session,
    create_product,
    create_production_batch,
    create_production_recipe,
    create_purchase_document,
    create_purchase_presentation,
    create_role,
    create_supplier,
    create_user,
    create_variation_note,
    create_waste_reason,
    create_waste_record,
    delete_branch,
    delete_product,
    delete_user,
    get_branch_context,
    get_cash_shift_summary,
    get_ingredient_variation,
    get_open_cash_shift,
    get_order_detail,
    get_sync_status,
    list_available_ingredient_extras,
    list_branch_admin_catalog_products,
    list_branch_ingredient_variations,
    list_branch_staff,
    list_branch_variation_notes,
    list_cash_movements,
    list_customers,
    list_customers_page,
    list_ingredient_variations,
    list_inventory_cost_states,
    list_inventory_transfers,
    list_kds_tasks,
    list_order_comments,
    list_payments,
    list_physical_count_sessions,
    list_print_jobs,
    list_product_modifiers,
    list_production_batches,
    list_purchase_documents,
    list_purchase_presentations,
    list_recent_orders,
    list_suppliers,
    list_sync_events,
    list_variation_notes,
    list_waste_reasons,
    list_waste_records,
    open_cash_shift,
    pay_order,
    preview_ingredient_variation_assignments,
    preview_order_comments_bulk,
    receive_inventory_transfer,
    receive_sync_command,
    record_inventory_opening_balance,
    repeat_order,
    replace_order_comment_products,
    require_permission,
    retry_print_job,
    reverse_waste_record,
    send_inventory_transfer,
    set_branch_ingredient_variation_option,
    set_branch_modifier_option,
    set_branch_product_availability,
    set_branch_variation_note,
    set_supplier_branch_terms,
    submit_physical_count_session,
    update_branch,
    update_customer,
    update_customer_address,
    update_ingredient_variation,
    update_order_comment,
    update_product,
    update_purchase_presentation_price,
    update_user,
    update_variation_note,
    update_waste_reason,
    upsert_customer_tax_profile,
)
from restaurant_os.operations import (
    cancel_order as cancel_order_operation,
)
from restaurant_os.platform_data import (
    bootstrap_status,
    get_catalog_cleanup_status,
    get_dashboard_overview,
    list_active_recipes,
    list_branches,
    list_business_units,
    list_catalog_products,
    list_inventory_kardex,
    list_inventory_stock,
    list_organizations,
    list_roles,
    list_users,
)

router = APIRouter(prefix="/api/v1", tags=["platform-api"])


SessionDep = Annotated[Session, Depends(get_session)]
ActorUserDep = Annotated[Optional[str], Header(alias="X-Actor-User-Id")]
AuthorizationDep = Annotated[Optional[str], Header(alias="Authorization")]
IdempotencyKeyDep = Annotated[Optional[str], Header(alias="Idempotency-Key")]


def _actor_from_request(actor_user_id: str | None, authorization: str | None) -> str | None:
    if actor_user_id:
        return actor_user_id
    if not authorization or not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    payload = verify_session_token(token, get_settings().secret_key)
    return str(payload.get("sub")) if payload and payload.get("sub") else None


def _required_actor_from_request(actor_user_id: str | None, authorization: str | None) -> str:
    actor_id = _actor_from_request(actor_user_id, authorization)
    if not actor_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "actor_required", "message": "Actor authentication is required"},
        )
    return actor_id


@router.get("/platform/bootstrap-status")
def get_bootstrap_status(session: SessionDep) -> dict[str, Any]:
    return _database_response(lambda: bootstrap_status(session))

@router.get("/dashboard/overview")
def get_dashboard_overview_endpoint(
    session: SessionDep,
    branch_id: str | None = None,
    month: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "dashboard.read", branch_id)
        return get_dashboard_overview(session, authorized_branch_id, month)

    return _business_response(operation)


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


@router.get("/auth/session")
def get_authenticated_session_endpoint(
    session: SessionDep,
    branch_id: str | None = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        if not authorization or not authorization.startswith("Bearer "):
            raise HTTPException(
                status_code=401,
                detail={"code": "token_required", "message": "Authorization Bearer token is required"},
            )
        token = authorization.removeprefix("Bearer ").strip()
        payload = verify_session_token(token, get_settings().secret_key)
        if not payload or not payload.get("sub"):
            raise HTTPException(
                status_code=401,
                detail={"code": "token_invalid", "message": "Token is invalid or expired"},
            )
        actor_id = str(payload["sub"])
        return build_session_profile(session, actor_id, branch_id)

    try:
        return _database_response(operation)
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=403, detail={"code": exc.code, "message": exc.message}
        ) from exc
    except BusinessError as exc:
        raise HTTPException(
            status_code=409, detail={"code": exc.code, "message": exc.message}
        ) from exc


@router.get("/organizations")
def get_organizations(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "admin.manage")
        return list_organizations(session)

    return _business_response(operation)


@router.get("/branches")
def get_branches(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorize_branch_scope(session, actor_id, "catalog.manage", branch_id)
        return list_branches(session)

    return _business_response(operation)


@router.get("/business-units")
def get_business_units(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "catalog.manage")
        return list_business_units(session)

    return _business_response(operation)


@router.post("/business-units")
def post_business_unit(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_business_unit(
        session,
        str(payload.get("name", "")),
        str(payload.get("code", "")),
        str(payload.get("unit_type", "restaurant")),
        str(payload.get("legal_entity_id", "")),
        actor_id,
    ))


@router.post("/branches")
def post_branch(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    code = str(payload.get("code", ""))
    business_unit_id = str(payload.get("business_unit_id", "")) or None
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_branch(session, name, code, actor_id, business_unit_id))


@router.get("/roles")
def get_roles(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "admin.manage")
        return list_roles(session)

    return _business_response(operation)


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
def get_users(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "admin.manage")
        return list_users(session)

    return _business_response(operation)


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
    role_id = payload.get("role_id")
    branch_id = payload.get("branch_id")
    actor_id = _actor_from_request(actor_user_id, authorization)
    normalized_password = str(password) if password else None
    return _business_response(
        lambda: create_user(
            session,
            email,
            display_name,
            actor_id,
            normalized_password,
            role_id,
            branch_id,
        )
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
def get_catalog_products(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "pos.operate", branch_id)
        return list_catalog_products(session, authorized_branch)

    return _business_response(operation)


@router.get("/catalog/cleanup-status")
def get_catalog_cleanup_status_endpoint(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "catalog.manage")
        return get_catalog_cleanup_status(session)

    return _business_response(operation)


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
    image_url = payload.get("image_url") if "image_url" in payload else None
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_product(session, name, sku, category_name, station, price_cents, image_url, actor_id)
    )


@router.get("/inventory/stock")
def get_inventory_stock(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(
            session, actor_id, "inventory.read", branch_id
        )
        return list_inventory_stock(session, authorized_branch)

    return _business_response(operation)


@router.get("/inventory/kardex")
def get_inventory_kardex(
    session: SessionDep,
    item_id: str | None = None,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(
            session, actor_id, "inventory.read", branch_id
        )
        return list_inventory_kardex(session, item_id, authorized_branch)

    return _business_response(operation)


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
def get_recipes(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "production.manage")
        return list_active_recipes(session)

    return _business_response(operation)


@router.get("/cash-shifts/current")
def get_current_cash_shift(
    session: SessionDep,
    branch_id: str | None = None,
    register_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.read", branch_id)
        return {
            "cash_shift": get_open_cash_shift(
                session,
                register_code=register_id or "CAJA-01",
                branch_id=authorized_branch_id,
            )
        }

    return _business_response(operation)


@router.post("/cash-shifts/open")
def open_current_cash_shift(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    opening_cash_cents = int(payload.get("opening_cash_cents", 0))
    branch_id = payload.get("branch_id")
    register_id = payload.get("register_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.open", branch_id)
        return open_cash_shift(
            session,
            opening_cash_cents,
            register_code=register_id or "CAJA-01",
            branch_id=authorized_branch_id,
            actor_user_id=actor_id,
        )

    return _business_response(operation)


@router.get("/cash-shifts/summary")
def get_current_cash_shift_summary(
    session: SessionDep,
    branch_id: str | None = None,
    register_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.read", branch_id)
        return get_cash_shift_summary(
            session,
            register_code=register_id or "CAJA-01",
            branch_id=authorized_branch_id,
        )

    return _business_response(operation)


@router.post("/cash-shifts/close")
def close_current_cash_shift(
    session: SessionDep,
    payload: dict[str, Any] | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    counted_cash_cents = int((payload or {}).get("counted_cash_cents", 0))
    branch_id = (payload or {}).get("branch_id")
    register_id = (payload or {}).get("register_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.close", branch_id)
        return close_cash_shift_with_cut(
            session,
            counted_cash_cents,
            register_code=register_id or "CAJA-01",
            branch_id=authorized_branch_id,
            actor_user_id=actor_id,
        )

    return _business_response(operation)


@router.get("/orders")
def get_recent_orders(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "orders.read", branch_id)
        return list_recent_orders(session, authorized_branch_id)

    return _business_response(operation)


@router.post("/orders")
def create_order(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    lines = payload.get("lines", [])
    owner_name = payload.get("owner_name")
    order_type = str(payload.get("order_type", "dine-in"))
    branch_id = payload.get("branch_id")
    register_id = payload.get("register_id")
    customer_id = payload.get("customer_id")
    delivery_address_id = payload.get("delivery_address_id")
    payment_method_intent = payload.get("payment_method_intent")
    def operation() -> dict[str, Any]:
        if "ingredient_extras" in payload or "comment_preset_ids" in payload:
            raise BusinessError(
                "order_line_modifiers_required",
                "Comments and ingredient extras must belong to a specific order line",
            )
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "orders.create", branch_id)
        return create_local_order(
            session,
            lines,
            owner_name,
            order_type,
            authorized_branch_id,
            register_id,
            actor_id,
            customer_id,
            delivery_address_id,
            payment_method_intent,
        )

    return _business_response(operation)


@router.get("/orders/{order_id}")
def get_order_detail_endpoint(
    order_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_order_detail(session, order_id, actor_id))


@router.post("/orders/{order_id}/amendments")
def amend_order_endpoint(
    order_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: amend_order(
            session,
            order_id,
            list(payload.get("lines", [])),
            int(payload.get("expected_version", 0)),
            idempotency_key or "",
            actor_id,
        )
    )


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
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    amount_cents = int(payload.get("amount_cents", 0))
    method = str(payload.get("method", "cash"))
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        return pay_order(session, order_id, amount_cents, method, actor_id)

    return _business_response(operation)


@router.post("/orders/{order_id}/repeat")
def repeat_order_endpoint(
    order_id: str,
    payload: dict[str, Any] | None,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    register_id = str((payload or {}).get("register_id", "CAJA-01"))
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: repeat_order(session, order_id, register_id, actor_id))


@router.get("/payments")
def get_payments(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "payments.read", branch_id)
        return list_payments(session, authorized_branch_id)

    return _business_response(operation)


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


@router.post("/seed_menu")
def seed_menu_endpoint() -> dict[str, Any]:
    if not run_seed_menu:
        return {"status": "error", "message": f"Seed menu script not found or failed to load. Error: {seed_import_error}"}
    try:
        run_seed_menu()
        return {"status": "ok", "message": "Menu seeded successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@router.post("/seed_branches")
def seed_branches_endpoint() -> dict[str, Any]:
    if not run_seed_branches:
        return {"status": "error", "message": f"Seed branches script not found or failed to load. Error: {seed_branches_error}"}
    try:
        run_seed_branches()
        return {"status": "ok", "message": "Branches seeded successfully"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


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
    role_id = payload.get("role_id")
    password = payload.get("password")
    branch_id = payload.get("branch_id")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_user(
            session,
            user_id,
            email,
            display_name,
            actor_id,
            role_id,
            password,
            branch_id,
        )
    )


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
    image_url = payload.get("image_url") if "image_url" in payload else None
    category_name = payload.get("category_name")
    station = payload.get("station")
    status = payload.get("status")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_product(
            session,
            product_id,
            name,
            sku,
            price_cents,
            image_url,
            category_name,
            station,
            status,
            actor_id,
        )
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
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Database error: {traceback.format_exc()}")
        raise HTTPException(status_code=503, detail=f"database_unavailable: {repr(exc)}") from exc



def _business_response(operation):
    try:
        return _database_response(operation)
    except AuthorizationError as exc:
        raise HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except NotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except BusinessError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

from restaurant_os.operations import (
    create_warehouse,
    delete_role,
    update_role,
    update_role_permissions,
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
def get_permissions(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "admin.manage")
        return list_permissions(session)

    return _business_response(operation)

@router.get("/roles/{role_id}/permissions")
def get_role_permissions(
    role_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[str]:
    def operation() -> list[str]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "admin.manage")
        return list_role_permissions(session, role_id)

    return _business_response(operation)

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
def get_warehouses(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorize_branch_scope(session, actor_id, "catalog.manage", branch_id)
        return list_warehouses(session)

    return _business_response(operation)

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


from restaurant_os.operations import (
    create_inventory_item,
    create_inventory_unit,
    update_inventory_item,
    update_inventory_unit,
)
from restaurant_os.platform_data import (
    list_inventory_items,
    list_inventory_units,
)


@router.get("/inventory/units")
def get_inventory_units(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
        return list_inventory_units(session)

    return _business_response(operation)

@router.post("/inventory/units")
def post_inventory_unit(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    code = str(payload.get("code", ""))
    name = str(payload.get("name", ""))
    precision_scale = int(payload.get("precision_scale", 0))
    dimension = str(payload.get("dimension", "discrete"))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_inventory_unit(session, code, name, precision_scale, dimension, actor_id))

@router.put("/inventory/units/{unit_id}")
def put_inventory_unit(
    unit_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    precision_scale = payload.get("precision_scale")
    if precision_scale is not None:
        precision_scale = int(precision_scale)
    dimension = payload.get("dimension")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_inventory_unit(session, unit_id, name, precision_scale, dimension, actor_id))


@router.get("/inventory/items")
def get_inventory_items(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
        return list_inventory_items(session, authorized_branch)

    return _business_response(operation)

@router.post("/inventory/items")
def post_inventory_item(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    sku = str(payload.get("sku", ""))
    base_unit_id = str(payload.get("base_unit_id", ""))
    item_type = str(payload.get("item_type", "ingredient"))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_inventory_item(session, name, sku, base_unit_id, item_type, actor_id))

@router.put("/inventory/items/{item_id}")
def put_inventory_item(
    item_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    base_unit_id = payload.get("base_unit_id")
    item_type = payload.get("item_type")
    status = payload.get("status")
    category_name = payload.get("category_name")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_inventory_item(
            session,
            item_id,
            name,
            base_unit_id,
            item_type,
            status,
            category_name,
            actor_id,
        )
    )


from restaurant_os.operations import (
    create_category,
    update_category,
    update_product_recipe,
)
from restaurant_os.platform_data import (
    get_product_recipe,
    list_categories,
)


@router.get("/categories")
def get_categories(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorize_branch_scope(session, actor_id, "pos.operate", branch_id)
        return list_categories(session)

    return _business_response(operation)

@router.post("/categories")
def post_category(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = str(payload.get("name", ""))
    display_order = int(payload.get("display_order", 0))
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_category(session, name, display_order, actor_id))

@router.put("/categories/{category_id}")
def put_category(
    category_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    name = payload.get("name")
    display_order = payload.get("display_order")
    if display_order is not None:
        display_order = int(display_order)
    status = payload.get("status")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_category(session, category_id, name, display_order, status, actor_id))


@router.get("/products/{product_id}/recipe")
def get_recipe(product_id: str, session: SessionDep) -> dict[str, Any]:
    recipe = _database_response(lambda: get_product_recipe(session, product_id))
    if not recipe:
        return {"components": []} # Return empty template if not found
    return recipe

@router.put("/products/{product_id}/recipe")
def put_recipe(
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    components = payload.get("components", [])
    yield_quantity = payload.get("yield_quantity", 1)
    yield_unit_id = payload.get("yield_unit_id", "")
    branch_id = payload.get("branch_id")
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_product_recipe(
            session,
            product_id,
            components,
            yield_quantity,
            yield_unit_id,
            branch_id,
            actor_id,
        )
    )


@router.get("/products/{product_id}/modifiers")
def get_product_modifiers(
    product_id: str,
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "pos.operate", branch_id)
        return list_product_modifiers(session, product_id, authorized_branch)

    return _business_response(operation)


@router.post("/products/{product_id}/modifier-groups")
def post_modifier_group(
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_modifier_group(session, product_id, payload, actor_id))


@router.get("/catalog/variation-notes")
def get_variation_notes(
    product_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_variation_notes(session, product_id, actor_id))


@router.post("/products/{product_id}/variation-notes")
def post_variation_note(
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_variation_note(session, product_id, payload, actor_id))


@router.put("/variation-notes/{option_id}")
def put_variation_note(
    option_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_variation_note(session, option_id, payload, actor_id))


@router.get("/catalog/order-comments")
def get_order_comments(
    session: SessionDep,
    status: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_order_comments(session, status, actor_id))


@router.post("/catalog/order-comments/bulk/preview")
def post_order_comments_bulk_preview(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: preview_order_comments_bulk(session, payload, actor_id))


@router.post("/catalog/order-comments/bulk")
def post_order_comments_bulk(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: bulk_order_comments(session, payload, actor_id))


@router.put("/catalog/order-comments/{comment_id}")
def put_order_comment(
    comment_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_order_comment(session, comment_id, payload, actor_id))


@router.put("/catalog/order-comments/{comment_id}/products")
def put_order_comment_products(
    comment_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: replace_order_comment_products(session, comment_id, payload, actor_id)
    )


@router.get("/catalog/ingredient-extras/available")
def get_available_ingredient_extras(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_available_ingredient_extras(session, actor_id, branch_id)
    )


@router.get("/catalog/ingredient-variations")
def get_ingredient_variations(
    session: SessionDep,
    search: str = "",
    status: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_ingredient_variations(session, search, status, actor_id))


@router.post("/catalog/ingredient-variations")
def post_ingredient_variation(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_ingredient_variation(session, payload, actor_id))


@router.get("/catalog/ingredient-variations/{variation_id}")
def get_ingredient_variation_endpoint(
    variation_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_ingredient_variation(session, variation_id, actor_id))


@router.put("/catalog/ingredient-variations/{variation_id}")
def put_ingredient_variation(
    variation_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_ingredient_variation(session, variation_id, payload, actor_id)
    )


@router.post("/catalog/ingredient-variations/{variation_id}/assignments/preview")
def post_ingredient_variation_assignment_preview(
    variation_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: preview_ingredient_variation_assignments(session, variation_id, payload, actor_id)
    )


@router.put("/catalog/ingredient-variations/{variation_id}/assignments")
def put_ingredient_variation_assignments(
    variation_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: apply_ingredient_variation_assignments(
            session, variation_id, payload, idempotency_key or "", actor_id
        )
    )


@router.put("/catalog/ingredient-variations/{variation_id}/assignments/{product_id}")
def put_ingredient_variation_assignment(
    variation_id: str,
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: apply_ingredient_variation_assignments(
            session,
            variation_id,
            {**payload, "product_ids": [product_id], "category_ids": []},
            idempotency_key or "",
            actor_id,
            assignment_update=True,
        )
    )


@router.delete("/catalog/ingredient-variations/{variation_id}/assignments/{product_id}")
def delete_ingredient_variation_assignment(
    variation_id: str,
    product_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: archive_ingredient_variation_assignment(session, variation_id, product_id, actor_id)
    )


@router.post("/modifier-groups/{group_id}/options")
def post_modifier_option(
    group_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_modifier_option(session, group_id, payload, actor_id))


@router.put("/modifier-options/{option_id}/branches/{branch_id}")
def put_branch_modifier_option(
    option_id: str,
    branch_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: set_branch_modifier_option(session, option_id, branch_id, payload, actor_id))


@router.post("/production-recipes")
def post_production_recipe(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_production_recipe(
            session,
            str(payload.get("output_item_id", "")),
            list(payload.get("components", [])),
            payload.get("yield_quantity", 1),
            str(payload.get("yield_unit_id", "")),
            payload.get("branch_id"),
            actor_id,
        )
    )


@router.get("/production-batches")
def get_production_batches(
    branch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "production.manage", branch_id)
        return list_production_batches(session, authorized_branch)

    return _business_response(operation)


@router.post("/production-batches")
def post_production_batch(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_production_batch(session, payload, actor_id))


@router.post("/production-batches/{batch_id}/confirm")
def post_confirm_production_batch(
    batch_id: str,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: confirm_production_batch(session, batch_id, idempotency_key or "", actor_id)
    )



@router.get("/customers")
def get_customers(
    session: SessionDep,
    phone: str | None = None,
    branch_id: str | None = None,
    q: str | None = None,
    limit: int | None = None,
    offset: int = 0,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> Any:
    def operation() -> Any:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "orders.read", branch_id)
        if limit is not None or q is not None:
            return list_customers_page(
                session, authorized_branch, q, phone, limit or 50, offset
            )
        return list_customers(session, phone, authorized_branch)
    return _business_response(operation)


@router.post("/customers")
def post_customer(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    branch_id = payload.get("branch_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "orders.create", branch_id)
        return create_customer(
            session,
            str(payload.get("name", "")),
            payload.get("email"),
            list(payload.get("phones", [])),
            authorized_branch,
            actor_id,
        )
    return _business_response(operation)


@router.post("/customers/{customer_id}/addresses")
def post_customer_address(
    customer_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    branch_id = payload.get("branch_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "orders.create", branch_id)
        return add_customer_address(session, customer_id, payload, authorized_branch, actor_id)
    return _business_response(operation)


@router.put("/customers/{customer_id}")
def put_customer(
    customer_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    branch_id = payload.get("branch_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "orders.create", branch_id)
        return update_customer(session, customer_id, payload, authorized_branch, actor_id)
    return _business_response(operation)


@router.put("/customers/{customer_id}/addresses/{address_id}")
def put_customer_address(
    customer_id: str,
    address_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    branch_id = payload.get("branch_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "orders.create", branch_id)
        return update_customer_address(
            session, customer_id, address_id, payload, authorized_branch, actor_id
        )
    return _business_response(operation)


@router.put("/customers/{customer_id}/tax-profile")
def put_customer_tax_profile(
    customer_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    branch_id = payload.get("branch_id")
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch = authorize_branch_scope(session, actor_id, "orders.create", branch_id)
        return upsert_customer_tax_profile(session, customer_id, payload, authorized_branch, actor_id)
    return _business_response(operation)


@router.get("/suppliers")
def get_suppliers(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorize_branch_scope(session, actor_id, "purchases.read", branch_id)
    return _database_response(lambda: list_suppliers(session))


@router.post("/suppliers")
def post_supplier(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_supplier(session, payload, actor_id))


@router.post("/suppliers/{supplier_id}/contacts")
def post_supplier_contact(
    supplier_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: add_supplier_contact(session, supplier_id, payload, actor_id))


@router.put("/suppliers/{supplier_id}/branches/{branch_id}")
def put_supplier_branch_terms(
    supplier_id: str, branch_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: set_supplier_branch_terms(
        session, supplier_id, branch_id, payload, actor_id
    ))


@router.get("/purchase-presentations")
def get_purchase_presentations(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorize_branch_scope(session, actor_id, "purchases.read", branch_id)
    return _database_response(lambda: list_purchase_presentations(session))


@router.post("/purchase-presentations")
def post_purchase_presentation(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_purchase_presentation(session, payload, actor_id))


@router.put("/purchase-presentations/{presentation_id}/price")
def put_purchase_presentation_price(
    presentation_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_purchase_presentation_price(
        session, presentation_id, payload.get("net_price"), actor_id
    ))


@router.get("/purchases")
def get_purchases(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(session, actor_id, "purchases.read", branch_id)
    return _database_response(lambda: list_purchase_documents(session, authorized_branch))


@router.post("/purchases")
def post_purchase(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_purchase_document(session, payload, actor_id))


@router.post("/purchases/{purchase_id}/confirm")
def confirm_purchase_endpoint(
    purchase_id: str, payload: dict[str, Any] | None, session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
    idempotency_key_header: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    idempotency_key = idempotency_key_header or str((payload or {}).get("idempotency_key", ""))
    return _business_response(lambda: confirm_purchase_document(
        session, purchase_id, idempotency_key, actor_id
    ))


@router.post("/purchases/{purchase_id}/cancel")
def cancel_purchase_endpoint(
    purchase_id: str, payload: dict[str, Any] | None, session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    reason = str((payload or {}).get("reason", ""))
    return _business_response(lambda: cancel_purchase_document(session, purchase_id, reason, actor_id))


@router.get("/cash-movements")
def get_cash_movements(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(session, actor_id, "cash.shift.read", branch_id)
    return _database_response(lambda: list_cash_movements(session, authorized_branch))


@router.get("/inventory/costs")
def get_inventory_costs(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
    return _database_response(lambda: list_inventory_cost_states(session, authorized_branch))


@router.get("/inventory/waste-reasons")
def get_waste_reasons(session: SessionDep) -> list[dict[str, Any]]:
    return _database_response(lambda: list_waste_reasons(session))


@router.post("/inventory/waste-reasons")
def post_waste_reason(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_waste_reason(session, payload, actor_id))


@router.put("/inventory/waste-reasons/{reason_id}")
def put_waste_reason(
    reason_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_waste_reason(session, reason_id, payload, actor_id))


@router.get("/inventory/wastes")
def get_waste_records_endpoint(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
    return _database_response(lambda: list_waste_records(session, authorized_branch))


@router.post("/inventory/wastes")
def post_waste_record_endpoint(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_waste_record(session, payload, actor_id))


@router.post("/inventory/wastes/{waste_id}/confirm")
def confirm_waste_record_endpoint(
    waste_id: str, session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: confirm_waste_record(
        session, waste_id, idempotency_key or "", actor_id
    ))


@router.post("/inventory/wastes/{waste_id}/reverse")
def reverse_waste_record_endpoint(
    waste_id: str, payload: dict[str, Any], session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: reverse_waste_record(
        session, waste_id, str(payload.get("reason", "")), idempotency_key or "", actor_id
    ))


@router.get("/inventory/transfers")
def get_inventory_transfers_endpoint(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
    return _database_response(lambda: list_inventory_transfers(session, authorized_branch))


@router.post("/inventory/transfers")
def post_inventory_transfer_endpoint(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_inventory_transfer(session, payload, actor_id))


@router.post("/inventory/transfers/{transfer_id}/send")
def send_inventory_transfer_endpoint(
    transfer_id: str, session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: send_inventory_transfer(
        session, transfer_id, idempotency_key or "", actor_id
    ))


@router.post("/inventory/transfers/{transfer_id}/receive")
def receive_inventory_transfer_endpoint(
    transfer_id: str, payload: dict[str, Any], session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: receive_inventory_transfer(
        session, transfer_id, list(payload.get("lines", [])), idempotency_key or "", actor_id
    ))


@router.post("/inventory/transfers/{transfer_id}/cancel")
def cancel_inventory_transfer_endpoint(
    transfer_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: cancel_inventory_transfer(
        session, transfer_id, str(payload.get("reason", "")), actor_id
    ))


@router.get("/inventory/physical-counts")
def get_physical_counts_endpoint(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(session, actor_id, "inventory.count", branch_id)
    return _database_response(lambda: list_physical_count_sessions(session, authorized_branch))


@router.post("/inventory/physical-counts")
def post_physical_count_endpoint(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_physical_count_session(session, payload, actor_id))


@router.put("/inventory/physical-counts/{count_id}/lines/{line_id}")
def put_physical_count_line_endpoint(
    count_id: str, line_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: capture_physical_count_line(
        session, count_id, line_id, payload.get("counted_quantity", 0), payload.get("notes"), actor_id
    ))


@router.post("/inventory/physical-counts/{count_id}/submit")
def submit_physical_count_endpoint(
    count_id: str, session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: submit_physical_count_session(session, count_id, actor_id))


@router.post("/inventory/physical-counts/{count_id}/approve")
def approve_physical_count_endpoint(
    count_id: str, session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: approve_physical_count_session(
        session, count_id, idempotency_key or "", actor_id
    ))


@router.post("/inventory/physical-counts/{count_id}/close")
def close_physical_count_endpoint(
    count_id: str, session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: close_physical_count_session(session, count_id, actor_id))


@router.post("/inventory/physical-counts/{count_id}/cancel")
def cancel_physical_count_endpoint(
    count_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: cancel_physical_count_session(
        session, count_id, str(payload.get("reason", "")), actor_id
    ))


# ---------------------------------------------------------------------------
# Branch administration (BA-001)
# ---------------------------------------------------------------------------


@router.get("/branch-administration/context")
def get_branch_admin_context(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_branch_context(session, actor_id, branch_id))


@router.get("/branch-administration/staff")
def get_branch_admin_staff(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_branch_staff(session, actor_id, branch_id))


@router.get("/branch-administration/catalog/products")
def get_branch_admin_catalog_products(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_branch_admin_catalog_products(session, actor_id, branch_id)
    )


@router.get("/branch-administration/catalog/variation-notes")
def get_branch_admin_variation_notes(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_branch_variation_notes(session, actor_id, branch_id))


@router.get("/branch-administration/imports")
def get_branch_admin_imports(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_branch_legacy_import_batches(session, actor_id, branch_id)
    )


@router.put("/branch-administration/catalog/products/{product_id}/availability")
def put_branch_admin_availability(
    product_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    action = str(payload.get("action", ""))
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: set_branch_product_availability(session, actor_id, product_id, action, branch_id)
    )


@router.put("/branch-administration/catalog/variation-notes/{option_id}")
def put_branch_admin_variation_note(
    option_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: set_branch_variation_note(
        session, actor_id, option_id, str(payload.get("action", "")), branch_id
    ))


@router.get("/branch-administration/catalog/ingredient-variations")
def get_branch_admin_ingredient_variations(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_branch_ingredient_variations(session, actor_id, branch_id)
    )


@router.put("/branch-administration/catalog/ingredient-variations/{option_id}")
def put_branch_admin_ingredient_variation(
    option_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: set_branch_ingredient_variation_option(
            session, actor_id, option_id, str(payload.get("action", "")), branch_id
        )
    )


# ---------------------------------------------------------------------------
# Legacy branch catalog imports (DATA-001)
# ---------------------------------------------------------------------------


@router.post("/legacy-imports")
def post_legacy_import_batch(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_legacy_import_batch(
            session,
            actor_id,
            str(payload.get("branch_id", "")),
            str(payload.get("source_system", "")),
            str(payload.get("manifest_checksum", "")),
            dict(payload.get("manifest") or {}),
        )
    )


@router.get("/legacy-imports")
def get_legacy_import_batches(
    branch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_legacy_import_batches(session, actor_id, branch_id)
    )


@router.post("/legacy-imports/{batch_id}/records")
def post_legacy_import_records(
    batch_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: ingest_legacy_import_records(
            session, actor_id, batch_id, list(payload.get("records") or [])
        )
    )


@router.get("/legacy-imports/{batch_id}/records")
def get_legacy_import_records(
    batch_id: str,
    session: SessionDep,
    status: str | None = None,
    entity_type: str | None = None,
    limit: int = 100,
    offset: int = 0,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_legacy_import_records(
            session, actor_id, batch_id, status, limit, offset, entity_type
        )
    )


@router.post("/legacy-imports/{batch_id}/complete")
def post_complete_legacy_import(
    batch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: complete_legacy_import_batch(session, actor_id, batch_id)
    )
