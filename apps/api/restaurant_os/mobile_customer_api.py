"""Same-origin mobile self-service boundary, separate from employee APIs."""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Annotated, Any, TypeVar

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os import mobile_customers as service
from restaurant_os import mobile_passwords as passwords
from restaurant_os.api import (
    PublicOrderIntentLine,
    _business_response,
    _create_public_order_intent_with_runtime,
    _resolve_active_public_order_key,
)
from restaurant_os.cashier_projection import project_cashier_contact
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.operations import (
    _recover_public_order_command,
    get_public_catalog,
    mobile_order_request_hash,
    normalize_mexican_phone,
)
from restaurant_os.phone_verification import PhoneVerifier, VerificationUnavailable

router = APIRouter(prefix="/api/v1/mobile/branches/{public_key}")
SessionDep = Annotated[Session, Depends(get_session)]
T = TypeVar("T")


class StrictPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class AccessStart(StrictPayload):
    phone: str = Field(min_length=10, max_length=32)


class AccessVerify(StrictPayload):
    challenge: str = Field(min_length=40, max_length=64)
    code: str = Field(pattern=r"^[0-9]{4,10}$")


class PasswordLogin(AccessStart):
    password: str = Field(min_length=1, max_length=128, repr=False)


class PasswordRegister(AccessStart):
    password: str = Field(min_length=15, max_length=128, repr=False)


class PasswordChange(StrictPayload):
    current_password: str = Field(default="", max_length=128, repr=False)
    new_password: str = Field(min_length=15, max_length=128, repr=False)


class PasswordPhoneChange(AccessStart):
    current_password: str = Field(min_length=1, max_length=128, repr=False)


class Address(StrictPayload):
    id: str | None = Field(default=None, min_length=1, max_length=36)
    creation_key: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{16,64}$")
    alias: str = Field(min_length=1, max_length=60)
    street: str = Field(min_length=1, max_length=180)
    exterior_number: str = Field(min_length=1, max_length=32)
    interior_number: str | None = Field(default=None, max_length=32)
    neighborhood: str = Field(min_length=1, max_length=120)
    postal_code: str = Field(pattern=r"^[0-9]{5}$")
    city: str = Field(min_length=1, max_length=100)
    municipality: str = Field(min_length=1, max_length=100)
    state: str = Field(min_length=1, max_length=100)
    references: str | None = Field(default=None, max_length=600)
    is_default: bool = True


class ProfileUpdate(StrictPayload):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    birthday_day: int | None = Field(default=None, ge=1, le=31)
    birthday_month: int | None = Field(default=None, ge=1, le=12)
    birthday_year: int | None = Field(default=None, ge=1900, le=9999)
    email: str | None = Field(default=None, max_length=180)
    address: Address | None = None

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str | None) -> str | None:
        if value is None or not value.strip():
            return None
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()):
            raise ValueError("Invalid email")
        return value.strip().lower()


class MobileOrder(StrictPayload):
    order_type: str = Field(pattern=r"^(takeout|delivery|dine-in)$")
    lines: list[PublicOrderIntentLine] = Field(min_length=1, max_length=50)
    address_id: str | None = Field(default=None, min_length=1, max_length=36)
    order_notes: str | None = Field(default=None, max_length=500)


def _run(session: Session, operation: Callable[[], T]) -> T:
    def private_operation() -> T:
        try:
            return operation()
        except SQLAlchemyError:
            session.rollback()
            raise HTTPException(
                503, detail={"code": "mobile_storage_unavailable", "message": "Intenta más tarde"}
            ) from None

    try:
        return _business_response(private_operation)
    except service.MobileError as exc:
        session.rollback()
        raise HTTPException(
            exc.status, detail={"code": exc.code, "message": "No se pudo completar la solicitud"}
        ) from None
    except VerificationUnavailable:
        session.rollback()
        raise HTTPException(
            503,
            detail={
                "code": "mobile_verification_unavailable",
                "message": "La verificación no está disponible",
            },
        ) from None


def _key(request: Request, session: Session, public_key: str) -> dict[str, Any]:
    if request.method != "GET" and request.headers.get("x-mobile-request") != "1":
        raise service.MobileError("mobile_same_origin_required", 403)
    if not getattr(request.app.state, "mobile_customer_access_enabled", False):
        raise service.MobileError("mobile_access_unavailable", 503)
    key = _resolve_active_public_order_key(session, public_key)
    if not key:
        raise service.MobileError("mobile_branch_not_found", 404)
    return key


def _identity(request: Request, session: Session, key: dict[str, Any]) -> dict[str, Any]:
    return service.identity_for_session(
        session, request.cookies.get(service.COOKIE, ""), str(key["organization_id"])
    )


def _verifier(request: Request) -> PhoneVerifier:
    verifier: PhoneVerifier | None = getattr(request.app.state, "mobile_phone_verifier", None)
    if verifier is None:
        raise VerificationUnavailable()
    return verifier


def _limit(request: Request, key: dict[str, Any], phone: str = "") -> None:
    limiter = getattr(request.app.state, "mobile_customer_rate_limiter", None)
    if limiter is None:
        raise service.MobileError("mobile_access_unavailable", 503)
    peer = request.client.host if request.client else "unknown"
    try:
        allowed = limiter.allow("mobile:" + str(key["organization_id"]), peer)
        if allowed and phone:
            allowed = limiter.allow("mobile-phone:" + str(key["organization_id"]), phone)
    except Exception:
        raise service.MobileError("mobile_access_unavailable", 503) from None
    if not allowed:
        raise service.MobileError("mobile_rate_limited", 429)


def _password_limit(request: Request, session: Session, key: dict[str, Any], phone: str) -> None:
    passwords.throttle(
        session, str(key["organization_id"]),
        request.client.host if request.client else "unknown", phone, get_settings().secret_key,
    )


def _password_response(
    session: Session, response: Response, result: tuple[dict[str, Any], str],
) -> Any:
    identity, token = result
    response.set_cookie(
        service.COOKIE, token, max_age=30 * 86400, httponly=True,
        secure=get_settings().environment == "production", samesite="strict",
        path="/api/v1/mobile",
    )
    return service.read_profile(session, identity)


@router.post("/access/register")
def register(
    public_key: str, payload: PasswordRegister, request: Request,
    response: Response, session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        phone = normalize_mexican_phone(payload.phone)
        _password_limit(request, session, key, phone)
        return _password_response(session, response,
                                  passwords.register(session, key, phone, payload.password))
    return _run(session, operation)


@router.post("/access/login")
def login(
    public_key: str, payload: PasswordLogin, request: Request,
    response: Response, session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        phone = normalize_mexican_phone(payload.phone)
        _password_limit(request, session, key, phone)
        return _password_response(session, response,
                                  passwords.login(session, key, phone, payload.password))
    return _run(session, operation)


@router.put("/profile/password")
def change_password(
    public_key: str, payload: PasswordChange, request: Request,
    response: Response, session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        identity = _identity(request, session, key)
        _password_limit(request, session, key, str(identity["phone"]))
        return _password_response(session, response, passwords.change_password(
            session, key, request.cookies.get(service.COOKIE, ""),
            payload.current_password, payload.new_password,
        ))
    return _run(session, operation)


@router.put("/profile/phone")
def change_phone(
    public_key: str, payload: PasswordPhoneChange, request: Request,
    response: Response, session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        identity = _identity(request, session, key)
        _password_limit(request, session, key, str(identity["phone"]))
        return _password_response(session, response, passwords.change_phone(
            session, key, request.cookies.get(service.COOKIE, ""),
            payload.current_password, payload.phone,
        ))
    return _run(session, operation)


@router.post("/access/start")
def start(public_key: str, payload: AccessStart, request: Request, session: SessionDep) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        phone = normalize_mexican_phone(payload.phone)
        _limit(request, key, phone)
        return service.start_access(session, key, phone, _verifier(request))

    return _run(session, operation)


@router.post("/profile/phone/start")
def start_phone_change(
    public_key: str,
    payload: AccessStart,
    request: Request,
    session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        identity = _identity(request, session, key)
        phone = normalize_mexican_phone(payload.phone)
        _limit(request, key, phone)
        return service.start_access(session, key, phone, _verifier(request), identity)

    return _run(session, operation)


@router.post("/access/verify")
def verify(
    public_key: str,
    payload: AccessVerify,
    request: Request,
    response: Response,
    session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        _limit(request, key)
        token = request.cookies.get(service.COOKIE)
        current = None
        if token:
            try:
                current = service.identity_for_session(session, token, str(key["organization_id"]))
            except service.MobileError:
                pass  # An expired cookie must not prevent a fresh login.
        identity, session_token = service.verify_access(
            session,
            key,
            payload.challenge,
            payload.code,
            _verifier(request),
            current,
        )
        response.set_cookie(
            service.COOKIE,
            session_token,
            max_age=30 * 86400,
            httponly=True,
            secure=get_settings().environment == "production",
            samesite="strict",
            path="/api/v1/mobile",
        )
        return service.read_profile(session, identity)

    return _run(session, operation)


@router.get("/profile")
def profile(public_key: str, request: Request, session: SessionDep) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        return service.read_profile(session, _identity(request, session, key))

    return _run(session, operation)


@router.put("/profile")
def update_profile(
    public_key: str,
    payload: ProfileUpdate,
    request: Request,
    session: SessionDep,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        return service.save_profile(
            session, _identity(request, session, key), key, payload.model_dump(exclude_unset=True)
        )

    return _run(session, operation)


@router.post("/logout")
def logout(public_key: str, request: Request, response: Response, session: SessionDep) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        identity = _identity(request, session, key)
        service.logout(session, request.cookies.get(service.COOKIE, ""), identity, key)
        response.delete_cookie(service.COOKIE, path="/api/v1/mobile")
        return {"ok": True}

    return _run(session, operation)


def _complete_profile(session: Session, identity: dict[str, Any]) -> dict[str, Any]:
    result = service.read_profile(session, identity)
    if not result["complete"]:
        raise service.MobileError("mobile_profile_incomplete")
    return result


@router.get("/catalog")
def catalog(public_key: str, request: Request, session: SessionDep) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        _complete_profile(session, _identity(request, session, key))
        return get_public_catalog(session, branch_id=str(key["branch_id"]))

    return _run(session, operation)


@router.post("/order-intents")
def order(
    public_key: str,
    payload: MobileOrder,
    request: Request,
    response: Response,
    session: SessionDep,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> Any:
    def operation() -> Any:
        key = _key(request, session, public_key)
        identity = _identity(request, session, key)
        if identity["customer_id"]:
            recovered = _recover_public_order_command(
                session,
                str(key["organization_id"]),
                "create",
                idempotency_key or "",
                mobile_order_request_hash(
                    str(key["branch_id"]), str(identity["customer_id"]), payload.model_dump()
                ),
            )
            if recovered:
                response.status_code = 200
                return recovered[0]
        profile = _complete_profile(session, identity)
        address = None
        if payload.order_type == "delivery":
            address = next((a for a in profile["addresses"] if a["id"] == payload.address_id), None)
            if not profile["email"] or not address:
                raise service.MobileError("mobile_delivery_profile_required")
            address = {
                **address,
                "address_text": project_cashier_contact(
                    None,
                    address,
                )["delivery_address"],
            }
        return _create_public_order_intent_with_runtime(
            session,
            public_key,
            {
                "customer_name": profile["name"],
                "customer_phone": identity["phone"],
                "order_type": payload.order_type,
                "lines": [line.model_dump() for line in payload.lines],
                "order_notes": payload.order_notes,
                "delivery_address": address,
            },
            idempotency_key or "",
            response,
            request,
            customer_id=str(profile["id"]),
            mobile_request=payload.model_dump(),
        )

    return _run(session, operation)
