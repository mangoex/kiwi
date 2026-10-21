"""Verified customer identities. No employee authority or provider-specific domain logic."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, cast
from uuid import NAMESPACE_URL, uuid4, uuid5

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.customer_profile import birthday_values
from restaurant_os.operations import _audit, normalize_mexican_phone
from restaurant_os.phone_verification import PhoneVerifier

COOKIE = "kiwi_mobile_session"


class MobileError(Exception):
    def __init__(self, code: str, status: int = 409) -> None:
        self.code, self.status = code, status
        super().__init__(code)


def now() -> datetime:
    return datetime.now(timezone.utc)


def digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _organization_lock(session: Session, organization_id: str) -> None:
    session.execute(
        sa.select(models.organizations.c.id)
        .where(models.organizations.c.id == organization_id)
        .with_for_update()
    ).scalar_one()


def identity_for_session(session: Session, token: str, organization_id: str) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(models.mobile_customer_identities)
            .join(
                models.mobile_customer_sessions,
                models.mobile_customer_sessions.c.identity_id
                == models.mobile_customer_identities.c.id,
            )
            .where(
                models.mobile_customer_sessions.c.token_hash == digest(token),
                models.mobile_customer_sessions.c.expires_at > now(),
                models.mobile_customer_sessions.c.revoked.is_(False),
                models.mobile_customer_identities.c.organization_id == organization_id,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        raise MobileError("mobile_session_required", 401)
    if row["customer_id"] and not session.scalar(
        sa.select(models.customers.c.id).where(
            models.customers.c.id == row["customer_id"],
            models.customers.c.organization_id == organization_id,
            models.customers.c.status == "active",
        )
    ):
        raise MobileError("mobile_session_required", 401)
    return dict(row)


def start_access(
    session: Session,
    key: dict[str, Any],
    phone: str,
    verifier: PhoneVerifier,
    identity: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized = normalize_mexican_phone(phone)
    verification_id = verifier.start(normalized)
    token = secrets.token_urlsafe(32)
    session.execute(
        models.mobile_access_challenges.insert().values(
            token_hash=digest(token),
            organization_id=key["organization_id"],
            branch_id=key["branch_id"],
            phone=normalized,
            verification_id=verification_id,
            identity_id=identity["id"] if identity else None,
            attempts=0,
            consumed=False,
            expires_at=now() + timedelta(minutes=10),
        )
    )
    session.commit()
    return {"challenge": token, "expires_in": 600}


def _matching_customers(session: Session, organization_id: str, phone: str) -> list[str]:
    return list(
        session.scalars(
            sa.select(models.customers.c.id)
            .join(
                models.customer_phones,
                models.customer_phones.c.customer_id == models.customers.c.id,
            )
            .where(
                models.customers.c.organization_id == organization_id,
                models.customers.c.status == "active",
                models.customer_phones.c.normalized_number == phone,
                models.customer_phones.c.status == "active",
            )
            .distinct()
        )
    )


def verify_access(
    session: Session,
    key: dict[str, Any],
    token: str,
    code: str,
    verifier: PhoneVerifier,
    current_identity: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], str]:
    challenges = models.mobile_access_challenges
    criteria = (
        challenges.c.token_hash == digest(token),
        challenges.c.organization_id == key["organization_id"],
        challenges.c.branch_id == key["branch_id"],
        challenges.c.expires_at > now(),
        challenges.c.consumed.is_(False),
        challenges.c.attempts < 5,
    )
    challenge = session.execute(sa.select(challenges).where(*criteria)).mappings().first()
    if not challenge:
        raise MobileError("mobile_code_invalid", 401)
    if challenge["identity_id"] and (
        not current_identity or current_identity["id"] != challenge["identity_id"]
    ):
        raise MobileError("mobile_session_required", 401)
    reserved = cast(
        Any,
        session.execute(
            challenges.update().where(*criteria).values(attempts=challenges.c.attempts + 1)
        ),
    )
    session.commit()  # Attempts survive invalid codes, network errors, and concurrent requests.
    if reserved.rowcount != 1 or not verifier.check(str(challenge["verification_id"]), code):
        raise MobileError("mobile_code_invalid", 401)
    _organization_lock(session, str(key["organization_id"]))
    consumed = cast(
        Any,
        session.execute(
            challenges.update()
            .where(
                challenges.c.token_hash == digest(token),
                challenges.c.consumed.is_(False),
                challenges.c.expires_at > now(),
            )
            .values(consumed=True)
        ),
    )
    if consumed.rowcount != 1:
        raise MobileError("mobile_code_invalid", 401)
    identities = models.mobile_customer_identities
    existing = (
        session.execute(
            sa.select(identities).where(
                identities.c.organization_id == key["organization_id"],
                identities.c.phone == challenge["phone"],
            )
        )
        .mappings()
        .first()
    )
    matches = _matching_customers(session, str(key["organization_id"]), str(challenge["phone"]))
    password_identity = current_identity if challenge["identity_id"] else existing
    if password_identity and session.scalar(
        sa.select(models.mobile_customer_credentials.c.identity_id).where(
            models.mobile_customer_credentials.c.identity_id == password_identity["id"],
        )
    ):
        session.commit()  # Legacy challenges cannot bypass the password authority.
        raise MobileError("mobile_password_required")
    if challenge["identity_id"]:
        assert current_identity is not None
        fresh = (
            session.execute(
                sa.select(identities)
                .where(
                    identities.c.id == current_identity["id"],
                )
                .with_for_update()
            )
            .mappings()
            .one()
        )
        if fresh["phone"] != current_identity["phone"]:
            session.commit()
            raise MobileError("mobile_identity_changed")
        current_identity = dict(fresh)
        if (existing and existing["id"] != current_identity["id"]) or any(
            cid != current_identity["customer_id"] for cid in matches
        ):
            session.commit()  # An approved challenge may not be reused after a collision.
            raise MobileError("mobile_phone_in_use")
        session.execute(
            identities.update()
            .where(identities.c.id == current_identity["id"])
            .values(phone=challenge["phone"])
        )
        customer_id = current_identity["customer_id"]
        if customer_id:
            session.execute(
                models.customer_phones.update()
                .where(
                    models.customer_phones.c.customer_id == customer_id,
                    models.customer_phones.c.normalized_number == current_identity["phone"],
                )
                .values(status="inactive", is_primary=False, updated_at=now())
            )
            _insert_phone(session, str(customer_id), str(challenge["phone"]))
        session.execute(
            models.mobile_customer_sessions.update()
            .where(
                models.mobile_customer_sessions.c.identity_id == current_identity["id"],
            )
            .values(revoked=True)
        )
        identity = {**current_identity, "phone": challenge["phone"]}
        action = "mobile.phone_changed"
    elif existing:
        identity = dict(existing)
        action = "mobile.access_verified"
    else:
        if len(matches) > 1:
            session.commit()
            raise MobileError("mobile_customer_ambiguous")
        if matches and session.scalar(
            sa.select(identities.c.id).where(
                identities.c.customer_id == matches[0],
            )
        ):
            session.commit()
            raise MobileError("mobile_customer_ambiguous")
        identity = {
            "id": str(uuid4()),
            "organization_id": key["organization_id"],
            "phone": challenge["phone"],
            "customer_id": matches[0] if matches else None,
            "created_at": now(),
        }
        session.execute(identities.insert().values(**identity))
        action = "mobile.access_verified"
    session_token = secrets.token_urlsafe(32)
    session.execute(
        models.mobile_customer_sessions.insert().values(
            token_hash=digest(session_token),
            identity_id=identity["id"],
            expires_at=now() + timedelta(days=30),
            revoked=False,
        )
    )
    _audit(
        session,
        action,
        "mobile_customer_identity",
        str(identity["id"]),
        {},
        str(key["branch_id"]),
        str(key["organization_id"]),
        None,
    )
    session.commit()
    return identity, session_token


def _insert_phone(session: Session, customer_id: str, phone: str, verified: bool = True) -> None:
    session.execute(
        models.customer_phones.update()
        .where(
            models.customer_phones.c.customer_id == customer_id,
        )
        .values(is_primary=False, updated_at=now())
    )
    session.execute(
        models.customer_phones.insert().values(
            id=str(uuid4()),
            customer_id=customer_id,
            captured_number=phone,
            normalized_number=phone,
            phone_type="mobile",
            is_primary=True,
            whatsapp_enabled=False,
            is_verified=verified,
            status="active",
            created_at=now(),
            updated_at=now(),
        )
    )


def read_profile(session: Session, identity: dict[str, Any]) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(models.customers).where(
                models.customers.c.id == identity["customer_id"],
                models.customers.c.organization_id == identity["organization_id"],
                models.customers.c.status == "active",
            )
        )
        .mappings()
        .first()
        if identity["customer_id"]
        else None
    )
    result = {
        field: row[field] if row else None
        for field in (
            "id",
            "name",
            "email",
            "birthday_day",
            "birthday_month",
            "birthday_year",
        )
    }
    result["has_password"] = bool(session.scalar(
        sa.select(models.mobile_customer_credentials.c.identity_id).where(
            models.mobile_customer_credentials.c.identity_id == identity["id"],
        )
    ))
    result["phone"] = identity["phone"]
    result["complete"] = bool(row and row["name"] and row["birthday_day"] and row["birthday_month"])
    address_fields = (
        "id",
        "alias",
        "street",
        "exterior_number",
        "interior_number",
        "neighborhood",
        "postal_code",
        "city",
        "municipality",
        "state",
        "references",
        "is_default",
    )
    result["addresses"] = (
        [
            dict(address)
            for address in session.execute(
                sa.select(
                    *(models.customer_addresses.c[field] for field in address_fields),
                )
                .where(
                    models.customer_addresses.c.customer_id == identity["customer_id"],
                    models.customer_addresses.c.status == "active",
                )
                .order_by(
                    models.customer_addresses.c.is_default.desc(),
                    models.customer_addresses.c.id,
                )
            ).mappings()
        ]
        if identity["customer_id"]
        else []
    )
    return result


def save_profile(
    session: Session,
    identity: dict[str, Any],
    key: dict[str, Any],
    payload: dict[str, Any],
) -> dict[str, Any]:
    _organization_lock(session, str(identity["organization_id"]))
    # Serialize profile creation and default-address changes, including simultaneous browser tabs.
    locked = (
        session.execute(
            sa.select(models.mobile_customer_identities)
            .where(
                models.mobile_customer_identities.c.id == identity["id"],
            )
            .with_for_update()
        )
        .mappings()
        .one()
    )
    identity = dict(locked)
    password_account = bool(session.scalar(
        sa.select(models.mobile_customer_credentials.c.identity_id).where(
            models.mobile_customer_credentials.c.identity_id == identity["id"],
        )
    ))
    if not identity["customer_id"] and not password_account:
        matches = _matching_customers(
            session, str(identity["organization_id"]), str(identity["phone"])
        )
        if len(matches) > 1:
            raise MobileError("mobile_customer_ambiguous")
        if matches:
            owned = session.scalar(
                sa.select(models.mobile_customer_identities.c.id).where(
                    models.mobile_customer_identities.c.customer_id == matches[0],
                )
            )
            if owned and owned != identity["id"]:
                raise MobileError("mobile_customer_ambiguous")
            identity["customer_id"] = matches[0]
            session.execute(
                models.mobile_customer_identities.update()
                .where(
                    models.mobile_customer_identities.c.id == identity["id"],
                )
                .values(customer_id=matches[0])
            )
    profile = read_profile(session, identity)
    updated = {**profile, **payload}
    try:
        birthday = birthday_values(updated)
    except ValueError as exc:
        raise MobileError("invalid_birthday", 422) from exc
    name = str(updated.get("name") or "").strip()
    if not name or not birthday["birthday_day"]:
        raise MobileError("mobile_profile_incomplete", 422)
    values = {
        "name": name,
        "email": (str(updated.get("email") or "").strip().lower() or None),
        **birthday,
        "updated_at": now(),
    }
    if not identity["customer_id"]:
        customer_id = str(uuid4())
        session.execute(
            models.customers.insert().values(
                id=customer_id,
                organization_id=identity["organization_id"],
                origin_branch_id=key["branch_id"],
                customer_type="person",
                status="active",
                created_at=now(),
                **values,
            )
        )
        _insert_phone(session, customer_id, str(identity["phone"]), verified=not password_account)
        session.execute(
            models.mobile_customer_identities.update()
            .where(
                models.mobile_customer_identities.c.id == identity["id"],
            )
            .values(customer_id=customer_id)
        )
        identity["customer_id"] = customer_id
    else:
        session.execute(
            sa.select(models.customers.c.id)
            .where(
                models.customers.c.id == identity["customer_id"],
            )
            .with_for_update()
        ).scalar_one()
        session.execute(
            models.customers.update()
            .where(
                models.customers.c.id == identity["customer_id"],
                models.customers.c.organization_id == identity["organization_id"],
            )
            .values(**values)
        )
    address = payload.get("address")
    saved_address_id = None
    if address is not None:
        saved_address_id = _save_address(session, str(identity["customer_id"]), dict(address))
    _audit(
        session,
        "mobile.profile_updated",
        "customer",
        str(identity["customer_id"]),
        {"fields": sorted(payload)},
        str(key["branch_id"]),
        str(key["organization_id"]),
        None,
    )
    session.commit()
    return {**read_profile(session, identity), "saved_address_id": saved_address_id}


def _save_address(session: Session, customer_id: str, address: dict[str, Any]) -> str:
    address_id = address.pop("id", None)
    creation_key = address.pop("creation_key", None)
    if not address_id and not creation_key:
        raise MobileError("mobile_address_creation_key_required", 422)
    candidate_id = address_id or str(
        uuid5(
            NAMESPACE_URL,
            f"mobile-address:{customer_id}:{creation_key}",
        )
    )
    exists = session.scalar(
        sa.select(models.customer_addresses.c.id).where(
            models.customer_addresses.c.id == candidate_id,
            models.customer_addresses.c.customer_id == customer_id,
            models.customer_addresses.c.status == "active",
        )
    )
    if address_id and not session.scalar(
        sa.select(models.customer_addresses.c.id).where(
            models.customer_addresses.c.id == address_id,
            models.customer_addresses.c.customer_id == customer_id,
            models.customer_addresses.c.status == "active",
        )
    ):
        raise MobileError("mobile_address_not_found", 404)
    values = {
        key: value.strip() if isinstance(value, str) else value for key, value in address.items()
    }
    if any(
        not values.get(field)
        for field in (
            "alias",
            "street",
            "exterior_number",
            "neighborhood",
            "postal_code",
            "city",
            "municipality",
            "state",
        )
    ):
        raise MobileError("invalid_customer_address", 422)
    if values.get("is_default", True):
        session.execute(
            models.customer_addresses.update()
            .where(
                models.customer_addresses.c.customer_id == customer_id,
            )
            .values(is_default=False, updated_at=now())
        )
    if address_id or exists:
        session.execute(
            models.customer_addresses.update()
            .where(
                models.customer_addresses.c.id == candidate_id,
                models.customer_addresses.c.customer_id == customer_id,
            )
            .values(**values, updated_at=now())
        )
    else:
        session.execute(
            models.customer_addresses.insert().values(
                id=candidate_id,
                customer_id=customer_id,
                **values,
                country="MX",
                status="active",
                created_at=now(),
                updated_at=now(),
            )
        )
    return str(candidate_id)


def logout(session: Session, token: str, identity: dict[str, Any], key: dict[str, Any]) -> None:
    session.execute(
        models.mobile_customer_sessions.update()
        .where(
            models.mobile_customer_sessions.c.token_hash == digest(token),
        )
        .values(revoked=True)
    )
    _audit(
        session,
        "mobile.logout",
        "mobile_customer_identity",
        str(identity["id"]),
        {},
        str(key["branch_id"]),
        str(key["organization_id"]),
        None,
    )
    session.commit()
