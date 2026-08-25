from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any, Optional, TypeVar
from uuid import UUID

# ruff: noqa: E501, E402, I001
from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os import models
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
from restaurant_os.recipe_ai import (
    calculate_theoretical_recipe_cost,
    match_ingredient_to_catalog,
    normalize_culinary_quantity,
    parse_recipe_text,
)
from restaurant_os.operational_guard import OperationalRouteGuard
from restaurant_os.operations import (
    BRANCH_ID,
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    NotFoundError,
    OperationalCloseResponse,
    ReportingProjectionService,
    UserCashCutService,
    accept_pending_order,
    acknowledge_print_attempt,
    add_customer_address,
    add_supplier_contact,
    advance_kds_task,
    amend_order,
    apply_ingredient_variation_assignments,
    apply_order_reopen_request,
    approve_physical_count_session,
    archive_cash_concept,
    archive_ingredient_variation_assignment,
    assign_product_category_option,
    assign_user_role,
    authenticate_user,
    authorize_branch_scope,
    authorize_cash_movement_scope,
    authorize_order_adjustment,
    authorize_supervisor_step_up,
    build_session_profile,
    bulk_order_comments,
    cancel_inventory_transfer,
    cancel_physical_count_session,
    cancel_purchase_document,
    capture_physical_count_line,
    category_option_coverage,
    claim_print_attempt,
    close_cash_shift_operationally,
    close_cash_shift_operationally_for_register,
    close_physical_count_session,
    compensate_cash_movement,
    confirm_production_batch,
    confirm_purchase_document,
    confirm_waste_record,
    fail_print_attempt,
    fulfill_order,
    create_branch,
    create_business_unit,
    create_cash_concept,
    create_cash_concept_version,
    create_cash_movement,
    create_customer,
    create_driver,
    create_ingredient_variation,
    create_inventory_transfer,
    create_local_order,
    create_modifier_group,
    create_modifier_option,
    create_order_reopen_request,
    create_physical_count_session,
    create_product,
    create_production_batch,
    create_production_recipe,
    create_public_online_order,
    create_purchase_document,
    create_purchase_presentation,
    create_role,
    create_supplier,
    create_user,
    create_variation_note,
    create_waste_reason,
    create_waste_record,
    deactivate_driver,
    decide_order_reopen_request,
    delete_branch,
    delete_product,
    delete_user,
    get_branch_context,
    get_cash_shift_summary,
    get_ingredient_variation,
    get_open_cash_shift,
    get_order_detail,
    get_public_catalog,
    get_sync_status,
    list_attendance_checks,
    list_available_delivery_drivers,
    list_available_ingredient_extras,
    list_branch_admin_catalog_products,
    list_branch_ingredient_variations,
    list_branch_staff,
    list_branch_variation_notes,
    list_cash_concepts,
    list_cash_movement_ledger,
    list_cash_movements,
    list_customers,
    list_customers_page,
    list_driver_deliveries,
    list_drivers,
    list_effective_cash_concepts,
    list_ingredient_variations,
    list_inventory_cost_states,
    list_inventory_transfers,
    list_kds_tasks,
    list_order_accounts,
    list_order_comments,
    list_order_reopen_requests,
    list_payments,
    list_physical_count_sessions,
    list_print_jobs,
    list_queued_print_attempts,
    list_product_modifiers,
    list_production_batches,
    list_public_branches,
    list_purchase_documents,
    list_purchase_presentations,
    list_recent_orders,
    list_suppliers,
    list_sync_events,
    list_variation_notes,
    list_waste_reasons,
    list_waste_records,
    open_cash_shift_idempotently,
    pay_order,
    preview_ingredient_variation_assignments,
    preview_order_comments_bulk,
    quote_local_order,
    receive_inventory_transfer,
    receive_sync_command,
    recover_expired_print_claim,
    record_attendance_check,
    record_inventory_opening_balance,
    record_pco004_metric,
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
    update_driver,
    update_ingredient_variation,
    update_order_comment,
    update_product,
    update_purchase_presentation_price,
    update_supplier,
    delete_supplier,
    update_user,
    update_variation_note,
    update_waste_reason,
    upsert_category_option_group,
    upsert_category_option_value,
    upsert_customer_tax_profile,
)
from restaurant_os.operations import (
    cancel_order as cancel_order_operation,
)
from restaurant_os.operations import (
    get_category_option_group_coverage as get_category_option_group_coverage_operation,
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
operational_route_guard = OperationalRouteGuard()


SessionDep = Annotated[Session, Depends(get_session)]
ActorUserDep = Annotated[Optional[str], Header(alias="X-Actor-User-Id")]
AuthorizationDep = Annotated[Optional[str], Header(alias="Authorization")]
IdempotencyKeyDep = Annotated[Optional[str], Header(alias="Idempotency-Key")]
DeviceTokenDep = Annotated[Optional[str], Header(alias="X-Device-Token")]


class RecipeComponentRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    item_id: UUID
    unit_id: UUID
    net_quantity: Decimal = Field(gt=Decimal("0"))
    waste_rate: Decimal = Field(default=Decimal("0"), ge=Decimal("0"), lt=Decimal("1"))


class RecipeVersionRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    branch_id: UUID | None = None
    expected_active_recipe_id: UUID | None = None
    yield_quantity: Decimal = Field(default=Decimal("1"), gt=Decimal("0"))
    yield_unit_id: UUID | None = None
    components: list[RecipeComponentRequest] = Field(min_length=1)

    @field_validator("branch_id", "expected_active_recipe_id", "yield_unit_id", mode="before")
    @classmethod
    def empty_str_to_none(cls, v: Any) -> Any:
        if v == "" or v is False:
            return None
        return v


class PrintFailureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    error_code: str = Field(pattern=r"^[A-Z0-9_]{1,64}$")


ResponseT = TypeVar("ResponseT")


def _actor_from_request(actor_user_id: str | None, authorization: str | None) -> str | None:
    settings = get_settings()
    if authorization and authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ").strip()
        payload = verify_session_token(token, settings.secret_key)
        if payload and payload.get("sub"):
            return str(payload["sub"])
    if (
        actor_user_id
        and settings.environment != "production"
        and os.getenv("PYTEST_CURRENT_TEST")
    ):
        return actor_user_id
    return None


def _required_actor_from_request(actor_user_id: str | None, authorization: str | None) -> str:
    actor_id = _actor_from_request(actor_user_id, authorization)
    if not actor_id:
        raise HTTPException(
            status_code=401,
            detail={"code": "actor_required", "message": "Actor authentication is required"},
        )
    return actor_id


@router.get("/platform/bootstrap-status")
def get_bootstrap_status(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "admin.manage")
        return bootstrap_status(session)

    return _business_response(operation)

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


@router.post("/auth/supervisor-authorize")
def supervisor_authorize_endpoint(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    pin_or_code = str(payload.get("supervisor_pin") or payload.get("pin") or payload.get("code") or "").strip()
    branch_id = str(payload.get("branch_id") or "").strip()
    permission_code = str(payload.get("permission_code") or "orders.discount.authorize").strip()

    def operation() -> dict[str, Any]:
        return authorize_supervisor_step_up(
            session=session,
            supervisor_code_or_password=pin_or_code,
            branch_id=branch_id,
            permission_code=permission_code,
        )

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
    return _business_response(
        lambda: create_branch(
            session,
            name=name,
            code=code,
            actor_user_id=actor_id,
            business_unit_id=business_unit_id,
            street=payload.get("street"),
            exterior_number=payload.get("exterior_number"),
            interior_number=payload.get("interior_number"),
            neighborhood=payload.get("neighborhood"),
            postal_code=payload.get("postal_code"),
            city=payload.get("city"),
            state=payload.get("state"),
            cross_streets=payload.get("cross_streets"),
            latitude=payload.get("latitude"),
            longitude=payload.get("longitude"),
            phone=payload.get("phone"),
        )
    )


@router.get("/drivers")
def get_drivers(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_drivers(session, actor_id))


@router.get("/delivery/drivers/available")
def get_available_delivery_drivers(
    branch_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_available_delivery_drivers(session, branch_id, actor_id)
    )


@router.get("/drivers/{driver_id}/deliveries")
def get_driver_deliveries(
    driver_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_driver_deliveries(session, driver_id, actor_id))


@router.post("/drivers")
def post_driver(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_driver(
            session,
            str(payload.get("branch_id", "")),
            payload,
            actor_id,
        )
    )


@router.put("/drivers/{driver_id}")
def put_driver(
    driver_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: update_driver(
            session,
            driver_id,
            str(payload.get("branch_id", "")),
            payload,
            actor_id,
        )
    )


@router.delete("/drivers/{driver_id}")
def delete_driver_endpoint(
    driver_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: deactivate_driver(session, driver_id, actor_id))


@router.get("/roles")
def get_roles(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
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
    employee_code = payload.get("employee_code")
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
            employee_code,
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
        if branch_id:
            authorized_branch = authorize_branch_scope(session, actor_id, "pos.operate", branch_id)
            return list_catalog_products(session, authorized_branch)
        return list_catalog_products(session)

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


@router.post("/catalog/load-real-excels")
def post_load_real_excels_endpoint(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "catalog.manage")
        from .real_catalog_loader import load_real_catalog_from_excels
        candidates = [
            "/app/apps/api",
            "/app",
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")),
            os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")),
            ".",
        ]
        excel_dir = next((p for p in candidates if os.path.exists(os.path.join(p, "INSUMOS.XLS"))), ".")
        summary = load_real_catalog_from_excels(session, excel_dir=excel_dir, import_customers=True, max_customers=5000)
        return {"status": "ok", "summary": summary}

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


@router.get("/cash/shifts/current")
def get_current_cash_shift(
    session: SessionDep,
    branch_id: str | None = None,
    register_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        if not register_id or not register_id.strip():
            raise BusinessError("cash_shift_current_payload_invalid", "register_id is required")
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.read", branch_id)
        if not authorized_branch_id:
            raise BusinessError("cash_shift_current_payload_invalid", "branch_id is required")
        shift = get_open_cash_shift(session, register_code=register_id, branch_id=authorized_branch_id)
        closure = None
        if not shift:
            last_shift = session.execute(sa.select(models.cash_shifts).where(
                models.cash_shifts.c.branch_id == authorized_branch_id,
                models.cash_shifts.c.register_code == register_id,
            ).order_by(models.cash_shifts.c.opened_at.desc()).limit(1)).mappings().first()
            if last_shift:
                closure = session.execute(sa.select(models.cash_shift_closures).where(
                    models.cash_shift_closures.c.cash_shift_id == last_shift["id"]
                )).mappings().first()
        return _serialize_pco_response({
            "cash_shift": shift,
            "closure": dict(closure) if closure else None,
        })

    return _business_response(operation)


@router.get("/cash-shifts/current")
def get_current_cash_shift_legacy(
    session: SessionDep,
    branch_id: str | None = None,
    register_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        if not register_id or not register_id.strip():
            raise BusinessError("cash_shift_current_payload_invalid", "register_id is required")
        scoped_branch = authorize_cash_movement_scope(session, actor_id, branch_id)
        if not scoped_branch:
            raise BusinessError("cash_shift_current_payload_invalid", "branch_id is required")
        return _serialize_pco_response(
            {"cash_shift": get_open_cash_shift(session, register_id, scoped_branch), "closure": None}
        )
    return _business_response(operation)


@router.post("/cash/shifts/open", operation_id="open_current_cash_shift_v1_post")
@router.post("/cash-shifts/open", operation_id="open_current_cash_shift_alias_post")
def open_current_cash_shift(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    if set(payload) != {"branch_id", "register_id", "opening_cash_cents"}:
        record_pco004_metric("cash_shift_open_total", result="error", error_code="cash_shift_open_payload_invalid")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_open_payload_invalid", "Open requires exactly branch_id, register_id and opening_cash_cents"
        )))
    opening_cash_cents = payload.get("opening_cash_cents")
    branch_id = payload.get("branch_id")
    register_id = payload.get("register_id")
    if not isinstance(opening_cash_cents, int) or isinstance(opening_cash_cents, bool) or opening_cash_cents < 0:
        record_pco004_metric("cash_shift_open_total", result="error", branch_id=branch_id if isinstance(branch_id, str) else None, error_code="cash_shift_open_payload_invalid")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_open_payload_invalid", "opening_cash_cents must be a non-negative integer"
        )))
    if not isinstance(branch_id, str) or not branch_id.strip() or not isinstance(register_id, str) or not register_id.strip():
        record_pco004_metric("cash_shift_open_total", result="error", branch_id=branch_id if isinstance(branch_id, str) else None, error_code="cash_shift_open_payload_invalid")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_open_payload_invalid", "branch_id and register_id are required"
        )))
    if not idempotency_key:
        record_pco004_metric("cash_shift_open_total", result="error", branch_id=branch_id, error_code="idempotency_key_required")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "idempotency_key_required", "Idempotency-Key is required"
        )))
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.open", branch_id)
        if not authorized_branch_id:
            raise BusinessError("cash_shift_open_payload_invalid", "An explicit branch is required")
        return _serialize_pco_response(
            open_cash_shift_idempotently(
                session, authorized_branch_id, register_id, opening_cash_cents, idempotency_key, actor_id,
            )
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
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    raw_payload = payload or {}
    forbidden = {"counted_cash_cents", "expected_cash_cents", "difference_cents"}.intersection(raw_payload)
    if forbidden:
        record_pco004_metric("cash_shift_operational_close_total", result="error", branch_id=raw_payload.get("branch_id") if isinstance(raw_payload.get("branch_id"), str) else None, error_code="cash_shift_counted_cash_forbidden")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_counted_cash_forbidden", "Counted cash is not accepted for operational close"
        )))
    if set(raw_payload) != {"branch_id", "register_id"}:
        record_pco004_metric("cash_shift_operational_close_total", result="error", branch_id=raw_payload.get("branch_id") if isinstance(raw_payload.get("branch_id"), str) else None, error_code="cash_shift_close_payload_invalid")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_close_payload_invalid", "Legacy close accepts only branch_id and register_id"
        )))
    branch_id = raw_payload.get("branch_id")
    register_id = raw_payload.get("register_id")
    if not isinstance(branch_id, str) or not branch_id.strip() or not isinstance(register_id, str) or not register_id.strip():
        record_pco004_metric("cash_shift_operational_close_total", result="error", branch_id=branch_id if isinstance(branch_id, str) else None, error_code="cash_shift_close_payload_invalid")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_close_payload_invalid", "branch_id and register_id are required"
        )))
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorized_branch_id = authorize_branch_scope(session, actor_id, "cash.shift.close", branch_id)
        return _serialize_operational_close_response(
            close_cash_shift_operationally_for_register(
                session, str(authorized_branch_id), str(register_id), idempotency_key or "", actor_id
            )
        )

    return _business_response(operation)


@router.post("/cash/shifts/{cash_shift_id}/close-operationally")
def close_cash_shift_operational_endpoint(
    cash_shift_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    if payload != {}:
        record_pco004_metric("cash_shift_operational_close_total", result="error", error_code="cash_shift_close_payload_invalid")
        return _business_response(lambda: (_ for _ in ()).throw(BusinessError(
            "cash_shift_close_payload_invalid", "Operational close requires an empty object"
        )))
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: _serialize_operational_close_response(close_cash_shift_operationally(
        session, cash_shift_id, idempotency_key or "", actor_id
    )))


@router.get("/cash/shifts")
def list_cash_shifts_endpoint(
    branch_id: str,
    session: SessionDep,
    register_id: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        if not 1 <= limit <= 100:
            raise BusinessError("cash_shift_list_invalid", "limit must be between 1 and 100")
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        scoped_branch = authorize_branch_scope(session, actor_id, "cash.shift.read", branch_id)
        query = sa.select(models.cash_shifts).where(
            models.cash_shifts.c.organization_id == ORGANIZATION_ID,
            models.cash_shifts.c.branch_id == scoped_branch,
        )
        if register_id:
            query = query.where(models.cash_shifts.c.register_code == register_id)
        if cursor:
            cursor_at, cursor_id = _decode_cash_shift_cursor(cursor)
            query = query.where(
                sa.or_(
                    models.cash_shifts.c.opened_at < cursor_at,
                    sa.and_(
                        models.cash_shifts.c.opened_at == cursor_at,
                        models.cash_shifts.c.id < cursor_id,
                    ),
                )
            )
        rows = [
            dict(row)
            for row in session.execute(
                query.order_by(models.cash_shifts.c.opened_at.desc(), models.cash_shifts.c.id.desc()).limit(limit + 1)
            ).mappings()
        ]
        next_cursor = None
        if len(rows) > limit:
            last = rows[limit - 1]
            next_cursor = f"{_serialize_api_value(last['opened_at'])}|{last['id']}"
        return _serialize_pco_response({"items": rows[:limit], "next_cursor": next_cursor})
    return _business_response(operation)


@router.get("/cash/shifts/{cash_shift_id}")
def get_cash_shift_endpoint(
    cash_shift_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        shift = session.execute(sa.select(models.cash_shifts).where(
            models.cash_shifts.c.id == cash_shift_id,
            models.cash_shifts.c.organization_id == ORGANIZATION_ID,
        )).mappings().first()
        if not shift:
            raise NotFoundError("cash_shift_not_found", "Cash shift was not found")
        authorize_branch_scope(session, actor_id, "cash.shift.read", str(shift["branch_id"]))
        closure = session.execute(sa.select(models.cash_shift_closures).where(
            models.cash_shift_closures.c.cash_shift_id == cash_shift_id
        )).mappings().first()
        return _serialize_pco_response(
            {"cash_shift": dict(shift), "closure": dict(closure) if closure else None}
        )
    return _business_response(operation)


@router.post("/cash/user-cuts")
def create_user_cash_cut_endpoint(payload: dict[str, Any], session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    return _business_response(lambda: _serialize_pco_response(UserCashCutService(session).create(payload, idempotency_key or "", _required_actor_from_request(actor_user_id, authorization))))


@router.get("/cash/user-cuts")
def list_user_cash_cuts_endpoint(
    session: SessionDep,
    branch_id: str,
    register_id: str | None = None,
    cashier_user_id: str | None = None,
    cash_shift_id: str | None = None,
    status: str | None = None,
    from_utc: str | None = None,
    to_utc: str | None = None,
    limit: int = 50,
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    filters = {"branch_id": branch_id, "limit": limit}
    for key, value in {"register_id": register_id, "cashier_user_id": cashier_user_id, "cash_shift_id": cash_shift_id, "status": status, "from_utc": from_utc, "to_utc": to_utc, "cursor": cursor}.items():
        if value is not None:
            filters[key] = value
    return _business_response(lambda: _serialize_pco_response(UserCashCutService(session).list(filters, _required_actor_from_request(actor_user_id, authorization))))


@router.get("/cash/user-cuts/{cash_cut_id}")
def get_user_cash_cut_endpoint(cash_cut_id: str, session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None) -> dict[str, Any]:
    return _business_response(lambda: _serialize_pco_response(UserCashCutService(session).detail(cash_cut_id, _required_actor_from_request(actor_user_id, authorization))))


@router.post("/cash/user-cuts/{cash_cut_id}/counted-cash")
def count_user_cash_cut_endpoint(cash_cut_id: str, payload: dict[str, Any], session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    return _business_response(lambda: _serialize_pco_response(UserCashCutService(session).counted_cash(cash_cut_id, payload, idempotency_key or "", _required_actor_from_request(actor_user_id, authorization))))


@router.post("/cash/user-cuts/{cash_cut_id}/finalize")
def finalize_user_cash_cut_endpoint(cash_cut_id: str, payload: dict[str, Any], session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    return _business_response(lambda: _serialize_pco_response(UserCashCutService(session).finalize(cash_cut_id, payload, idempotency_key or "", _required_actor_from_request(actor_user_id, authorization))))


@router.post("/cash/user-cuts/{cash_cut_id}/reopen-requests")
def request_user_cash_cut_reopen_endpoint(cash_cut_id: str, payload: dict[str, Any], session: SessionDep, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    return _business_response(lambda: _serialize_pco_response(UserCashCutService(session).request_reopen(cash_cut_id, payload, idempotency_key or "", _required_actor_from_request(actor_user_id, authorization))))


@router.post("/cash/user-cuts/reopen-requests/{request_id}/approve")
def approve_user_cash_cut_reopen_endpoint(request_id: str, session: SessionDep, payload: dict[str, Any] | None = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        if payload not in (None, {}):
            raise BusinessError("cash_cut_scope_invalid", "Reopen decision body must be empty")
        return _serialize_pco_response(UserCashCutService(session).decide_reopen(request_id, "APPROVED", idempotency_key or "", _required_actor_from_request(actor_user_id, authorization)))

    return _business_response(operation)


@router.post("/cash/user-cuts/reopen-requests/{request_id}/reject")
def reject_user_cash_cut_reopen_endpoint(request_id: str, session: SessionDep, payload: dict[str, Any] | None = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        if payload not in (None, {}):
            raise BusinessError("cash_cut_scope_invalid", "Reopen decision body must be empty")
        return _serialize_pco_response(
            UserCashCutService(session).decide_reopen(
                request_id,
                "REJECTED",
                idempotency_key or "",
                _required_actor_from_request(actor_user_id, authorization),
            )
        )

    return _business_response(operation)


@router.post("/cash/user-cuts/reopen-requests/{request_id}/compensate")
def compensate_user_cash_cut_reopen_endpoint(request_id: str, session: SessionDep, payload: dict[str, Any] | None = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None, idempotency_key: IdempotencyKeyDep = None) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        if payload not in (None, {}):
            raise BusinessError("cash_cut_scope_invalid", "Reopen compensation body must be empty")
        return _serialize_pco_response(
            UserCashCutService(session).compensate_reopen(
                request_id,
                idempotency_key or "",
                _required_actor_from_request(actor_user_id, authorization),
            )
        )

    return _business_response(operation)


@router.get("/reports/sales-monitor")
def sales_monitor_endpoint(
    from_utc: datetime, to_utc: datetime, session: SessionDep, branch_id: str | None = None,
    register_id: str | None = None, cash_shift_id: str | None = None, family_id: str | None = None,
    service_type: str | None = None, actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: _serialize_api_value(ReportingProjectionService(session, actor_id).summary({
        "from_utc": from_utc, "to_utc": to_utc, "branch_id": branch_id, "register_id": register_id,
        "cash_shift_id": cash_shift_id, "family_id": family_id, "service_type": service_type,
    })))


@router.get("/reports/sales-monitor/drill-down")
def sales_monitor_drill_down_endpoint(
    from_utc: datetime, to_utc: datetime, metric: str, session: SessionDep, branch_id: str | None = None,
    register_id: str | None = None, cash_shift_id: str | None = None, family_id: str | None = None,
    service_type: str | None = None, limit: int = 50, cursor: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: _serialize_api_value(ReportingProjectionService(session, actor_id).drill_down({
        "from_utc": from_utc, "to_utc": to_utc, "branch_id": branch_id, "register_id": register_id,
        "cash_shift_id": cash_shift_id, "family_id": family_id, "service_type": service_type,
        "metric": metric, "limit": limit, "cursor": cursor,
    })))


@router.get("/reports/ingredient-sales")
def ingredient_sales_report_endpoint(
    from_utc: datetime, to_utc: datetime, session: SessionDep, branch_id: str | None = None,
    limit: int = 50, cursor: str | None = None, actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: _serialize_api_value(ReportingProjectionService(session, actor_id).ingredient_sales({
        "from_utc": from_utc, "to_utc": to_utc, "branch_id": branch_id, "limit": limit, "cursor": cursor,
    })))


@router.get("/reports/expenses")
def expenses_report_endpoint(
    from_utc: datetime, to_utc: datetime, session: SessionDep, branch_id: str | None = None,
    limit: int = 50, cursor: str | None = None, actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: _serialize_api_value(ReportingProjectionService(session, actor_id).expenses({
        "from_utc": from_utc, "to_utc": to_utc, "branch_id": branch_id, "limit": limit, "cursor": cursor,
    })))


class ReconciliationAuditRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    branch_id: str
    date: str
    reviewed: bool
    notes: str | None = None


@router.get("/reports/branch-reconciliation/daily")
def branch_reconciliation_daily_endpoint(
    branch_id: str,
    date: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_branch_daily_reconciliation(session, branch_id, date, actor_id))


@router.get("/reports/branch-reconciliation/consolidated")
def branch_reconciliation_consolidated_endpoint(
    date_from: str,
    date_to: str,
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    from restaurant_os.reconciliation_reports import get_multi_branch_consolidated_report
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_multi_branch_consolidated_report(session, date_from, date_to, branch_id, actor_id))


@router.post("/reports/branch-reconciliation/audit")
def branch_reconciliation_audit_endpoint(
    payload: ReconciliationAuditRequest,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    from restaurant_os.reconciliation_reports import update_reconciliation_audit_status
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_reconciliation_audit_status(
        session, payload.branch_id, payload.date, payload.reviewed, payload.notes, actor_id
    ))


@router.get("/reports/branch-reconciliation/export")
def branch_reconciliation_export_endpoint(
    branch_id: str,
    month: int,
    year: int,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> Response:
    from restaurant_os.reconciliation_reports import export_reconciliation_workbook
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    excel_stream = _business_response(
        lambda: export_reconciliation_workbook(session, branch_id, month, year, actor_id)
    )
    return Response(
        content=excel_stream.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Corte_Kiwi_{branch_id}_{year}_{month:02d}.xlsx"'},
    )



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


@router.get("/orders/accounts")
def get_order_accounts(
    session: SessionDep, branch_id: str | None = None, from_utc: str | None = None,
    to_utc: str | None = None, cash_shift_id: str | None = None,
    register_code: str | None = None, service_type: str | None = None,
    q: str | None = None, limit: int = 50, cursor: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_order_accounts(session, {"branch_id": branch_id, "from_utc": from_utc, "to_utc": to_utc, "cash_shift_id": cash_shift_id, "register_code": register_code, "service_type": service_type, "q": q, "limit": limit, "cursor": cursor}, actor_id))


@router.post("/orders/{order_id}/reopen-requests")
def create_order_reopen_request_endpoint(order_id: str, payload: dict[str, Any], session: SessionDep, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_order_reopen_request(session, order_id, payload, idempotency_key, actor_id))


@router.get("/orders/reopen-requests")
def get_order_reopen_requests(session: SessionDep, branch_id: str | None = None, status: str | None = None, limit: int = 50, cursor: str | None = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_order_reopen_requests(session, {"branch_id": branch_id, "status": status, "limit": limit, "cursor": cursor}, actor_id))


@router.post("/orders/reopen-requests/{request_id}/approve")
def approve_order_reopen_request_endpoint(request_id: str, payload: dict[str, Any], session: SessionDep, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: decide_order_reopen_request(session, request_id, "APPROVED", payload, idempotency_key, actor_id))


@router.post("/orders/reopen-requests/{request_id}/reject")
def reject_order_reopen_request_endpoint(request_id: str, payload: dict[str, Any], session: SessionDep, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: decide_order_reopen_request(session, request_id, "REJECTED", payload, idempotency_key, actor_id))


@router.post("/orders/reopen-requests/{request_id}/apply")
def apply_order_reopen_request_endpoint(request_id: str, payload: dict[str, Any], session: SessionDep, idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None, actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: apply_order_reopen_request(session, request_id, payload, idempotency_key, actor_id))


@router.post("/orders/quote")
def quote_order(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        branch_id = authorize_branch_scope(
            session,
            actor_id,
            "orders.create",
            str(payload.get("branch_id") or "") or None,
        )
        if not branch_id:
            raise BusinessError("branch_scope_required", "A branch scope is required")
        return quote_local_order(
            session,
            list(payload.get("lines", [])),
            branch_id,
            actor_id,
            str(payload.get("adjustment_authorization_id") or "").strip() or None,
        )

    return _business_response(operation)


@router.post("/orders/adjustments/authorize")
def authorize_order_adjustment_endpoint(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        branch_id = authorize_branch_scope(
            session,
            actor_id,
            "orders.create",
            str(payload.get("branch_id") or "") or None,
        )
        if not branch_id:
            raise BusinessError("branch_scope_required", "A branch scope is required")
        adjustment = payload.get("adjustment")
        if not isinstance(adjustment, dict):
            raise BusinessError(
                "invalid_order_adjustment", "Adjustment details are required"
            )
        return authorize_order_adjustment(
            session=session,
            lines=list(payload.get("lines", [])),
            branch_id=branch_id,
            actor_user_id=actor_id,
            supervisor_code_or_password=str(payload.get("supervisor_pin") or ""),
            adjustment_type=str(adjustment.get("type") or ""),
            adjustment_value=adjustment.get("value"),
            reason=str(adjustment.get("reason") or ""),
        )

    return _business_response(operation)


@router.post("/orders/{order_id}/fulfillment/{command}")
def fulfill_order_endpoint(
    order_id: str,
    command: str,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: fulfill_order(session, order_id, command, idempotency_key, actor_id)
    )


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
    driver_id = payload.get("driver_id")
    adjustment_authorization_id = (
        str(payload.get("adjustment_authorization_id") or "").strip() or None
    )
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
            driver_id,
            adjustment_authorization_id,
        )

    return _business_response(operation)


@router.get("/public/branches")
def public_branches_endpoint(
    session: SessionDep,
    lat: float | None = None,
    lng: float | None = None,
) -> list[dict[str, Any]]:
    return _business_response(lambda: list_public_branches(session, customer_lat=lat, customer_lng=lng))


@router.get("/public/catalog")
def public_catalog_endpoint(session: SessionDep) -> dict[str, Any]:
    return _business_response(lambda: get_public_catalog(session))


@router.post("/public/orders")
def public_create_order(payload: dict[str, Any], session: SessionDep) -> dict[str, Any]:
    lines = payload.get("lines", [])
    owner_name = payload.get("owner_name")
    customer_phone = payload.get("customer_phone")
    order_type = str(payload.get("order_type", "takeout"))
    delivery_address = payload.get("delivery_address")
    payment_method_intent = payload.get("payment_method_intent")
    order_notes = payload.get("order_notes")
    branch_id = payload.get("branch_id")
    customer_lat = payload.get("customer_lat")
    customer_lng = payload.get("customer_lng")

    return _business_response(
        lambda: create_public_online_order(
            session,
            lines=lines,
            owner_name=owner_name,
            customer_phone=customer_phone,
            order_type=order_type,
            delivery_address=delivery_address,
            payment_method_intent=payment_method_intent,
            order_notes=order_notes,
            branch_id=branch_id,
            customer_lat=float(customer_lat) if customer_lat is not None else None,
            customer_lng=float(customer_lng) if customer_lng is not None else None,
        )
    )


@router.get("/orders/{order_id}")
def get_order_detail_endpoint(
    order_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_order_detail(session, order_id, actor_id))


@router.post("/orders/{order_id}/accept")
def accept_order_endpoint(
    order_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: accept_pending_order(session, order_id, actor_id))


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
    register_id = str(payload.get("register_id", "")).strip()
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        return pay_order(session, order_id, amount_cents, method, actor_id, register_id)

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
def get_kds_tasks(
    session: SessionDep,
    authorization: AuthorizationDep = None,
    device_token: DeviceTokenDep = None,
) -> list[dict[str, Any]]:
    if device_token:
        actor = operational_route_guard.require_device_for_capability(
            session, device_token, "kds.operate"
        )
    else:
        actor = operational_route_guard.require_human(
            session, authorization, "kds.tasks.operate", BRANCH_ID
        )
    return _database_response(lambda: list_kds_tasks(session, actor.branch_id or ""))


@router.post("/kds/tasks/{task_id}/transition")
def transition_kds_task(
    task_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
    device_token: DeviceTokenDep = None,
) -> dict[str, Any]:
    status = str(payload.get("status", ""))
    if device_token:
        actor = operational_route_guard.require_device_for_capability(
            session, device_token, "kds.operate"
        )
        actor_user_id, actor_device_id = None, actor.user_id
    else:
        actor = operational_route_guard.require_human(
            session, authorization, "kds.tasks.operate", BRANCH_ID
        )
        actor_user_id, actor_device_id = actor.user_id, None
    return _business_response(
        lambda: advance_kds_task(
            session,
            task_id,
            status,
            actor.branch_id or "",
            actor_user_id=actor_user_id,
            actor_device_id=actor_device_id,
        )
    )


@router.get("/print-jobs")
def get_print_jobs(
    session: SessionDep, authorization: AuthorizationDep = None
) -> list[dict[str, Any]]:
    operational_route_guard.require_human(
        session, authorization, "print.jobs.read", BRANCH_ID
    )
    return _database_response(lambda: list_print_jobs(session, BRANCH_ID))


@router.post("/print-jobs/{job_id}/retry")
def retry_print_job_endpoint(
    job_id: str,
    session: SessionDep,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor = operational_route_guard.require_human(
        session, authorization, "print.jobs.retry", BRANCH_ID
    )
    return _business_response(
        lambda: retry_print_job(
            session, job_id, idempotency_key or "", BRANCH_ID, actor_user_id=actor.user_id
        )
    )


@router.get("/print-attempts/pull")
def pull_print_attempts(
    session: SessionDep, device_token: DeviceTokenDep = None
) -> list[dict[str, Any]]:
    actor = operational_route_guard.require_device_for_capability(
        session, device_token, "print.agent"
    )
    return _database_response(
        lambda: list_queued_print_attempts(session, actor.organization_id, actor.branch_id or "")
    )


@router.post("/print-attempts/{attempt_id}/claim")
def claim_print_attempt_endpoint(
    attempt_id: str, session: SessionDep, device_token: DeviceTokenDep = None
) -> dict[str, Any]:
    attempt = session.execute(
        models.print_attempts.select().where(models.print_attempts.c.id == attempt_id)
    ).mappings().first()
    if not attempt:
        operational_route_guard.deny(session, "device_scope_denied", "print.agent", BRANCH_ID)
    actor = operational_route_guard.require_device(
        session, device_token, "print.agent", attempt["organization_id"], attempt["branch_id"]
    )
    return _business_response(lambda: claim_print_attempt(session, attempt_id, actor.user_id))


@router.post("/print-attempts/{attempt_id}/ack")
def acknowledge_print_attempt_endpoint(
    attempt_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    device_token: DeviceTokenDep = None,
) -> dict[str, Any]:
    attempt = session.execute(
        models.print_attempts.select().where(models.print_attempts.c.id == attempt_id)
    ).mappings().first()
    if not attempt:
        operational_route_guard.deny(session, "device_scope_denied", "print.agent", BRANCH_ID)
    actor = operational_route_guard.require_device(
        session, device_token, "print.agent", attempt["organization_id"], attempt["branch_id"]
    )
    return _business_response(
        lambda: acknowledge_print_attempt(
            session, attempt_id, actor.user_id, str(payload.get("acknowledgement", ""))
        )
    )


@router.post("/print-attempts/{attempt_id}/fail")
def fail_print_attempt_endpoint(
    attempt_id: str,
    payload: PrintFailureRequest,
    session: SessionDep,
    device_token: DeviceTokenDep = None,
) -> dict[str, Any]:
    attempt = session.execute(
        models.print_attempts.select().where(models.print_attempts.c.id == attempt_id)
    ).mappings().first()
    if not attempt:
        operational_route_guard.deny(session, "device_scope_denied", "print.agent", BRANCH_ID)
    actor = operational_route_guard.require_device(
        session, device_token, "print.agent", attempt["organization_id"], attempt["branch_id"]
    )
    return _business_response(
        lambda: fail_print_attempt(session, attempt_id, actor.user_id, payload.error_code)
    )


@router.post("/print-attempts/{attempt_id}/recover-expired-claim")
def recover_expired_print_claim_endpoint(
    attempt_id: str, session: SessionDep, device_token: DeviceTokenDep = None
) -> dict[str, Any]:
    actor = operational_route_guard.require_device_for_capability(
        session, device_token, "print.agent"
    )

    def operation() -> dict[str, Any]:
        try:
            return recover_expired_print_claim(
                session,
                attempt_id,
                actor.organization_id,
                actor.branch_id or "",
            )
        except BusinessError as exc:
            if exc.code == "device_scope_denied":
                operational_route_guard.deny(
                    session,
                    exc.code,
                    "print.agent",
                    actor.branch_id,
                    device_id=actor.user_id,
                    organization_id=actor.organization_id,
                )
            raise

    return _business_response(operation)


@router.post("/sync/commands")
def sync_command(
    payload: dict[str, Any], session: SessionDep, device_token: DeviceTokenDep = None
) -> dict[str, Any]:
    actor = operational_route_guard.require_device_for_capability(
        session, device_token, "gateway.sync"
    )
    if (
        payload.get("organization_id") != actor.organization_id
        or payload.get("branch_id") != actor.branch_id
        or payload.get("source_device_id") != actor.user_id
    ):
        operational_route_guard.deny(
            session,
            "device_scope_denied",
            "gateway.sync",
            actor.branch_id,
            device_id=actor.user_id,
            organization_id=actor.organization_id,
        )
    return _business_response(
        lambda: receive_sync_command(
            session,
            payload,
            actor.organization_id,
            actor.branch_id or "",
            actor.user_id,
        )
    )


@router.get("/sync/events")
def get_sync_events(
    session: SessionDep,
    after_checkpoint: int = 0,
    authorization: AuthorizationDep = None,
    device_token: DeviceTokenDep = None,
) -> list[dict[str, Any]]:
    if device_token:
        actor = operational_route_guard.require_device_for_capability(
            session, device_token, "gateway.sync"
        )
    else:
        actor = operational_route_guard.require_human(
            session, authorization, "orders.create", BRANCH_ID
        )
    return _database_response(
        lambda: list_sync_events(
            session,
            actor.organization_id,
            actor.branch_id or "",
            after_checkpoint,
        )
    )


@router.get("/sync/status")
def sync_status(
    session: SessionDep, authorization: AuthorizationDep = None
) -> dict[str, Any]:
    operational_route_guard.require_human(session, authorization, "orders.create", BRANCH_ID)
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
    employee_code = payload.get("employee_code") if "employee_code" in payload else None
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
            employee_code,
        )
    )


@router.post("/attendance/checks")
def post_attendance_check(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: record_attendance_check(
            session,
            str(payload.get("employee_code", "")),
            str(payload.get("branch_id", "")),
            actor_id,
        )
    )


@router.get("/attendance/checks")
def get_attendance_checks(
    session: SessionDep,
    employee_code: str | None = None,
    day: str | None = None,
    month: str | None = None,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_attendance_checks(
            session,
            actor_id,
            employee_code=employee_code,
            day=day,
            month=month,
            branch_id=branch_id,
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
    return _business_response(
        lambda: update_branch(
            session,
            branch_id,
            name=name,
            code=code,
            actor_user_id=actor_id,
            extra_payload=payload,
        )
    )


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


def _database_response(operation: Callable[[], ResponseT]) -> ResponseT:
    try:
        return operation()
    except SQLAlchemyError as exc:
        import logging
        import traceback
        logger = logging.getLogger(__name__)
        logger.error(f"Database error: {traceback.format_exc()}")
        raise HTTPException(status_code=503, detail=f"database_unavailable: {repr(exc)}") from exc


def _serialize_api_value(value: Any) -> Any:
    """Render timestamps at the HTTP boundary as canonical RFC3339 UTC strings."""
    if isinstance(value, datetime):
        utc_value = value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
        return utc_value.isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {key: _serialize_api_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_api_value(item) for item in value]
    return value


def _serialize_pco_response(response: dict[str, Any]) -> dict[str, Any]:
    serialized = _serialize_api_value(response)
    if not isinstance(serialized, dict):
        raise BusinessError("pco004_response_invalid", "PCO-004 response must be an object")
    return serialized


def _serialize_operational_close_response(
    response: OperationalCloseResponse,
) -> dict[str, Any]:
    serialized_shift = _serialize_api_value(response["cash_shift"])
    serialized_closure = _serialize_api_value(response["closure"])
    if not isinstance(serialized_shift, dict) or not isinstance(serialized_closure, dict):
        raise BusinessError(
            "cash_shift_response_invalid",
            "Operational close response must contain cash shift and closure objects",
        )
    return {"cash_shift": serialized_shift, "closure": serialized_closure}


def _decode_cash_shift_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw_timestamp, cash_shift_id = cursor.rsplit("|", 1)
        timestamp = datetime.fromisoformat(raw_timestamp.replace("Z", "+00:00"))
        UUID(cash_shift_id)
    except ValueError as exc:
        raise BusinessError("cash_shift_cursor_invalid", "cursor is invalid") from exc
    if timestamp.tzinfo is None:
        raise BusinessError("cash_shift_cursor_invalid", "cursor is invalid")
    return timestamp.astimezone(timezone.utc), cash_shift_id



def _business_response(operation: Callable[[], ResponseT]) -> ResponseT:
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
    get_effective_product_recipe,
    get_recipes_workspace,
    update_category,
    update_product_recipe_versioned,
)
from restaurant_os.platform_data import (
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
        if branch_id:
            authorized_branch = authorize_branch_scope(session, actor_id, "pos.operate", branch_id)
            return list_categories(session, authorized_branch)
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


@router.get("/categories/{category_id}/selection-group")
def get_category_selection_group(
    category_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: category_option_coverage(session, category_id, actor_id))


@router.post("/categories/{category_id}/selection-group")
def post_category_selection_group(
    category_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: upsert_category_option_group(session, category_id, payload, actor_id))


@router.get("/catalog/category-option-groups/{group_id}/coverage")
def get_category_option_group_coverage(
    group_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: get_category_option_group_coverage_operation(session, group_id, actor_id)
    )


@router.post("/catalog/category-option-groups/{group_id}/values")
def post_category_option_value(
    group_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: upsert_category_option_value(session, group_id, payload, actor_user_id=actor_id))


@router.put("/catalog/category-option-groups/{group_id}/values/{value_id}")
def put_category_option_value(
    group_id: str, value_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: upsert_category_option_value(session, group_id, payload, value_id, actor_id))


@router.put("/catalog/category-option-groups/{group_id}/assignments/{product_id}")
def put_product_category_option_assignment(
    group_id: str, product_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: assign_product_category_option(session, group_id, product_id, str(payload.get("option_value_id", "")), actor_id))


@router.get("/products/{product_id}/recipe")
def get_recipe(
    product_id: str, session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    recipe = _business_response(lambda: get_effective_product_recipe(session, product_id, branch_id, actor_id))
    return recipe or {"components": []}


@router.get("/recipes/workspace")
def get_recipes_workspace_route(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: get_recipes_workspace(session, actor_id, branch_id))


class RecipeAiParseRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")
    raw_text: str = Field(..., min_length=5)
    product_id: str | None = None
    sale_price: Decimal | None = None
    yield_portions: Decimal | None = Field(default=Decimal("1"))


@router.post("/recipes/ai-parse")
def post_recipe_ai_parse(
    payload: RecipeAiParseRequest,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    def operation() -> dict[str, Any]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        require_permission(session, actor_id, "catalog.manage")

        # 1. Fetch available supplies with base units and costs
        items_query = sa.select(
            models.inventory_items.c.id,
            models.inventory_items.c.name,
            models.inventory_items.c.sku,
            models.inventory_units.c.code.label("unit"),
            sa.func.coalesce(models.purchase_presentations.c.cost_per_base_unit, 0).label("cost"),
        ).select_from(
            models.inventory_items.join(
                models.inventory_units,
                models.inventory_items.c.base_unit_id == models.inventory_units.c.id,
            ).outerjoin(
                models.purchase_presentations,
                sa.and_(
                    models.purchase_presentations.c.item_id == models.inventory_items.c.id,
                    models.purchase_presentations.c.is_preferred.is_(True),
                ),
            )
        ).where(
            models.inventory_items.c.organization_id == ORGANIZATION_ID,
            models.inventory_items.c.status == "active",
        )
        catalog_supplies = [dict(row) for row in session.execute(items_query).mappings().all()]

        # 2. If product_id given, lookup product sale price if not explicitly provided
        sale_price = payload.sale_price or Decimal("0")
        product_name = ""
        if payload.product_id:
            prod_row = session.execute(
                sa.select(
                    models.products.c.name,
                    models.price_versions.c.price_cents,
                ).select_from(
                    models.products.outerjoin(
                        models.price_versions,
                        sa.and_(
                            models.price_versions.c.product_id == models.products.c.id,
                            models.price_versions.c.valid_to.is_(None),
                        ),
                    )
                ).where(
                    models.products.c.id == payload.product_id,
                    models.products.c.organization_id == ORGANIZATION_ID,
                )
            ).mappings().first()
            if prod_row:
                product_name = prod_row["name"]
                if sale_price == 0 and prod_row["price_cents"]:
                    sale_price = Decimal(prod_row["price_cents"]) / Decimal("100")

        # 3. Parse free-form recipe text
        parsed = parse_recipe_text(payload.raw_text)

        # 4. Semantic match and unit normalization for each ingredient
        matched_ingredients = []
        for ing in parsed["ingredients"]:
            match = match_ingredient_to_catalog(ing["raw_name"], catalog_supplies)
            if match:
                target_base_unit = match["base_unit"]
                normalized_qty = normalize_culinary_quantity(
                    quantity=ing["quantity"],
                    unit=ing["unit"],
                    target_base_unit=target_base_unit,
                    density_hint=ing["raw_name"],
                )
                unit_cost = match["unit_cost"]
                matched_ingredients.append({
                    "raw_name": ing["raw_name"],
                    "quantity": ing["quantity"],
                    "unit": ing["unit"],
                    "matched_item_id": match["matched_item_id"],
                    "matched_item_name": match["matched_item_name"],
                    "base_unit": target_base_unit,
                    "normalized_quantity": normalized_qty,
                    "unit_cost": unit_cost,
                    "confidence_score": match["confidence_score"],
                    "status": "matched",
                })
            else:
                matched_ingredients.append({
                    "raw_name": ing["raw_name"],
                    "quantity": ing["quantity"],
                    "unit": ing["unit"],
                    "matched_item_id": None,
                    "matched_item_name": None,
                    "base_unit": "KILO" if "g" in ing["unit"] or "kg" in ing["unit"] else ("LITRO" if "l" in ing["unit"] or "taza" in ing["unit"] or "cda" in ing["unit"] else "PIEZA"),
                    "normalized_quantity": ing["quantity"],
                    "unit_cost": Decimal("0.00"),
                    "confidence_score": 0.0,
                    "status": "unmatched",
                })

        # 5. Calculate theoretical cost and margins
        cost_analysis = calculate_theoretical_recipe_cost(
            ingredients=matched_ingredients,
            yield_portions=payload.yield_portions or Decimal("1"),
            sale_price=sale_price,
        )

        return {
            "title": product_name or parsed["title"],
            "product_id": payload.product_id,
            "steps": parsed["steps"],
            **cost_analysis,
        }

    return _business_response(operation)


@router.put("/products/{product_id}/recipe")
def put_recipe(
    product_id: UUID,
    payload: RecipeVersionRequest,
    session: SessionDep,
    idempotency_key: IdempotencyKeyDep = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    if not idempotency_key:
        raise HTTPException(status_code=409, detail={
            "code": "idempotency_key_required", "message": "Idempotency-Key is required",
        })
    body = payload.model_dump(mode="json")
    branch_id = body.pop("branch_id")
    expected_active_recipe_id = body.pop("expected_active_recipe_id")
    return _business_response(lambda: update_product_recipe_versioned(
        session, str(product_id), body, branch_id, expected_active_recipe_id, idempotency_key, actor_id,
    ))


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
        authorized_branch = authorize_branch_scope(
            session, actor_id, "production.manage", branch_id
        )
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
        authorized_branch = authorize_branch_scope(
            session, actor_id, "orders.create", branch_id
        )
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
        authorized_branch = authorize_branch_scope(
            session, actor_id, "orders.create", branch_id
        )
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
        authorized_branch = authorize_branch_scope(
            session, actor_id, "orders.create", branch_id
        )
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
        authorized_branch = authorize_branch_scope(
            session, actor_id, "orders.create", branch_id
        )
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
        authorized_branch = authorize_branch_scope(
            session, actor_id, "orders.create", branch_id
        )
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


@router.put("/suppliers/{supplier_id}")
def put_supplier(
    supplier_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_supplier(session, supplier_id, payload, actor_id))


@router.delete("/suppliers/{supplier_id}")
def delete_supplier_route(
    supplier_id: str, session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: delete_supplier(session, supplier_id, actor_id))


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
    return _database_response(lambda: list_purchase_presentations(session))


@router.post("/purchase-presentations")
def post_purchase_presentation(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_purchase_presentation(session, payload, actor_id))


@router.put("/purchase-presentations/{presentation_id}")
def put_purchase_presentation(
    presentation_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_purchase_presentation(
        session, presentation_id, payload, actor_id
    ))


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
    authorized_branch = authorize_branch_scope(
        session, actor_id, "purchases.read", branch_id
    )
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
    register_id = str((payload or {}).get("register_id", ""))
    return _business_response(lambda: confirm_purchase_document(
        session, purchase_id, idempotency_key, register_id, actor_id
    ))


@router.post("/purchases/{purchase_id}/cancel")
def cancel_purchase_endpoint(
    purchase_id: str, payload: dict[str, Any] | None, session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _actor_from_request(actor_user_id, authorization)
    reason = str((payload or {}).get("reason", ""))
    return _business_response(lambda: cancel_purchase_document(session, purchase_id, reason, actor_id))


@router.get("/cash/concepts/effective")
def get_effective_cash_concepts(
    session: SessionDep,
    movement_type: str,
    effective_at: datetime | None = None,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_effective_cash_concepts(
            session,
            movement_type,
            effective_at or datetime.now(timezone.utc),
            actor_id,
            branch_id,
        )
    )


@router.get("/cash/concepts")
def get_cash_concepts(
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: list_cash_concepts(session, actor_id))


@router.post("/cash/concepts")
def post_cash_concept(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_cash_concept(
            session, payload, idempotency_key or "", actor_id
        )
    )


@router.put("/cash/concepts/{concept_id}/versions")
def put_cash_concept_version(
    concept_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_cash_concept_version(
            session, concept_id, payload, idempotency_key or "", actor_id
        )
    )


@router.post("/cash/concepts/{concept_id}/archive")
def post_cash_concept_archive(
    concept_id: str,
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: archive_cash_concept(
            session, concept_id, idempotency_key or "", actor_id
        )
    )


@router.post("/cash/movements")
def post_cash_movement(
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: create_cash_movement(session, payload, idempotency_key or "", actor_id)
    )


@router.post("/cash/movements/{movement_id}/compensations")
def post_cash_movement_compensation(
    movement_id: str,
    payload: dict[str, Any],
    session: SessionDep,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
    idempotency_key: IdempotencyKeyDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: compensate_cash_movement(
            session, movement_id, payload, idempotency_key or "", actor_id
        )
    )


@router.get("/cash/movements")
def get_cash_movement_ledger(
    branch_id: str,
    session: SessionDep,
    register_id: str | None = None,
    cash_shift_id: str | None = None,
    movement_type: str | None = None,
    from_utc: datetime | None = None,
    to_utc: datetime | None = None,
    limit: int = 50,
    cursor: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(
        lambda: list_cash_movement_ledger(
            session, actor_id, branch_id, register_id, cash_shift_id, movement_type,
            from_utc, to_utc, limit, cursor
        )
    )


@router.get("/cash-movements")
def get_cash_movements(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(
        session, actor_id, "cash.shift.read", branch_id
    )
    return _database_response(lambda: list_cash_movements(session, authorized_branch))


@router.get("/inventory/costs")
def get_inventory_costs(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(
        session, actor_id, "inventory.read", branch_id
    )
    return _database_response(lambda: list_inventory_cost_states(session, authorized_branch))


@router.get("/inventory/waste-reasons")
def get_waste_reasons(
    session: SessionDep,
    branch_id: str | None = None,
    actor_user_id: ActorUserDep = None,
    authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    def operation() -> list[dict[str, Any]]:
        actor_id = _required_actor_from_request(actor_user_id, authorization)
        authorize_branch_scope(session, actor_id, "inventory.read", branch_id)
        return list_waste_reasons(session)

    return _business_response(operation)


@router.post("/inventory/waste-reasons")
def post_waste_reason(
    payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: create_waste_reason(session, payload, actor_id))


@router.put("/inventory/waste-reasons/{reason_id}")
def put_waste_reason(
    reason_id: str, payload: dict[str, Any], session: SessionDep,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    return _business_response(lambda: update_waste_reason(session, reason_id, payload, actor_id))


@router.get("/inventory/wastes")
def get_waste_records_endpoint(
    session: SessionDep, branch_id: str | None = None,
    actor_user_id: ActorUserDep = None, authorization: AuthorizationDep = None,
) -> list[dict[str, Any]]:
    actor_id = _required_actor_from_request(actor_user_id, authorization)
    authorized_branch = authorize_branch_scope(
        session, actor_id, "inventory.read", branch_id
    )
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
    authorized_branch = authorize_branch_scope(
        session, actor_id, "inventory.read", branch_id
    )
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
    authorized_branch = authorize_branch_scope(
        session, actor_id, "inventory.count", branch_id
    )
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
