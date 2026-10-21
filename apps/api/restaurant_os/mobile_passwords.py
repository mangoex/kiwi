"""Mobile credentials use local password hashing and a durable, private throttle."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from restaurant_os import mobile_customers as customers
from restaurant_os import models
from restaurant_os.auth import generate_password_salt, hash_password, verify_password
from restaurant_os.operations import _audit, normalize_mexican_phone


def require_password(password: str) -> None:
    if not 15 <= len(password) <= 128:
        raise customers.MobileError("mobile_password_policy", 422)


def throttle(session: Session, organization: str, peer: str, phone: str, secret: str) -> None:
    timestamp = customers.now()
    table = models.mobile_auth_attempts
    dialect = session.get_bind().dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise customers.MobileError("mobile_access_unavailable", 503)
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    allowed = True
    for kind, signal, seconds, limit in (
        ("organization", "", 60, 300), ("peer", peer, 600, 60), ("phone", phone, 600, 10),
    ):
        window = int(timestamp.timestamp()) // seconds
        bucket = hmac.new(secret.encode(),
                          f"{organization}|{kind}|{signal}|{window}".encode(),
                          hashlib.sha256).hexdigest()
        statement = insert(table).values(
            bucket_key=bucket, attempts=1,
            expires_at=datetime.fromtimestamp((window + 1) * seconds, timezone.utc),
        ).on_conflict_do_update(
            index_elements=[table.c.bucket_key], set_={"attempts": table.c.attempts + 1},
        ).returning(table.c.attempts)
        count = session.scalar(statement)
        if count is None or count > limit:
            allowed = False
            break  # A saturated global/peer bucket cannot create unbounded phone buckets.
    session.execute(table.delete().where(table.c.expires_at <= timestamp))
    session.commit()  # Invalid credentials never roll the counters back.
    if not allowed:
        raise customers.MobileError("mobile_rate_limited", 429)


def _credentials(session: Session, identity_id: str) -> Any:
    return session.execute(sa.select(models.mobile_customer_credentials).where(
        models.mobile_customer_credentials.c.identity_id == identity_id,
    )).mappings().first()


def _password_matches(password: str, credential: Any) -> bool:
    if not 1 <= len(password) <= 128:
        return False
    # Missing accounts perform the same KDF; neither response reveals account existence.
    salt = credential["password_salt"] if credential else "MDEyMzQ1Njc4OWFiY2RlZg"
    expected = credential["password_hash"] if credential else ""
    return verify_password(password, salt, expected)


def _store_password(session: Session, identity_id: str, password: str) -> None:
    require_password(password)
    salt = generate_password_salt()
    values = {"password_salt": salt, "password_hash": hash_password(password, salt),
              "updated_at": customers.now()}
    table = models.mobile_customer_credentials
    if _credentials(session, identity_id):
        session.execute(table.update().where(table.c.identity_id == identity_id).values(**values))
    else:
        session.execute(table.insert().values(identity_id=identity_id, **values))


def _issue(session: Session, identity: dict[str, Any], key: dict[str, Any],
           action: str, revoke: bool = False) -> tuple[dict[str, Any], str]:
    if revoke:
        session.execute(models.mobile_customer_sessions.update().where(
            models.mobile_customer_sessions.c.identity_id == identity["id"],
        ).values(revoked=True))
    token = secrets.token_urlsafe(32)
    session.execute(models.mobile_customer_sessions.insert().values(
        token_hash=customers.digest(token), identity_id=identity["id"],
        expires_at=customers.now() + timedelta(days=30), revoked=False,
    ))
    _audit(session, action, "mobile_customer_identity", str(identity["id"]), {},
           str(key["branch_id"]), str(key["organization_id"]), None)
    session.commit()
    return identity, token


def register(session: Session, key: dict[str, Any], phone: str,
             password: str) -> tuple[dict[str, Any], str]:
    require_password(password)
    phone = normalize_mexican_phone(phone)
    customers._organization_lock(session, str(key["organization_id"]))
    table = models.mobile_customer_identities
    if session.scalar(sa.select(table.c.id).where(
        table.c.organization_id == key["organization_id"], table.c.phone == phone,
    )):
        raise customers.MobileError("mobile_registration_unavailable")
    identity: dict[str, Any] = {"id": str(uuid4()), "organization_id": key["organization_id"],
                "phone": phone, "customer_id": None, "created_at": customers.now()}
    session.execute(table.insert().values(**identity))
    _store_password(session, identity["id"], password)
    return _issue(session, identity, key, "mobile.password_registered")


def login(session: Session, key: dict[str, Any], phone: str,
          password: str) -> tuple[dict[str, Any], str]:
    phone = normalize_mexican_phone(phone)
    customers._organization_lock(session, str(key["organization_id"]))
    table = models.mobile_customer_identities
    row = session.execute(sa.select(table).where(
        table.c.organization_id == key["organization_id"], table.c.phone == phone,
    )).mappings().first()
    credential = _credentials(session, str(row["id"])) if row else None
    valid = _password_matches(password, credential)
    active = row is not None and (row["customer_id"] is None or bool(session.scalar(
        sa.select(models.customers.c.id).where(
            models.customers.c.id == row["customer_id"],
            models.customers.c.organization_id == key["organization_id"],
            models.customers.c.status == "active",
        )
    )))
    if not valid or not active or row is None:
        raise customers.MobileError("mobile_credentials_invalid", 401)
    return _issue(session, dict(row), key, "mobile.password_login")


def change_password(session: Session, key: dict[str, Any], token: str,
                    current_password: str, new_password: str) -> tuple[dict[str, Any], str]:
    require_password(new_password)
    customers._organization_lock(session, str(key["organization_id"]))
    identity = customers.identity_for_session(session, token, str(key["organization_id"]))
    credential = _credentials(session, str(identity["id"]))
    if credential and not _password_matches(current_password, credential):
        raise customers.MobileError("mobile_credentials_invalid", 401)
    _store_password(session, str(identity["id"]), new_password)
    return _issue(session, identity, key, "mobile.password_changed", revoke=True)


def change_phone(session: Session, key: dict[str, Any], token: str,
                 current_password: str, phone: str) -> tuple[dict[str, Any], str]:
    phone = normalize_mexican_phone(phone)
    customers._organization_lock(session, str(key["organization_id"]))
    identity = customers.identity_for_session(session, token, str(key["organization_id"]))
    if not _password_matches(current_password, _credentials(session, str(identity["id"]))):
        raise customers.MobileError("mobile_credentials_invalid", 401)
    table = models.mobile_customer_identities
    if session.scalar(sa.select(table.c.id).where(
        table.c.organization_id == key["organization_id"], table.c.phone == phone,
        table.c.id != identity["id"],
    )) or any(cid != identity["customer_id"] for cid in customers._matching_customers(
        session, str(key["organization_id"]), phone,
    )):
        raise customers.MobileError("mobile_phone_in_use")
    if phone != identity["phone"]:
        session.execute(table.update().where(table.c.id == identity["id"]).values(phone=phone))
        if identity["customer_id"]:
            session.execute(models.customer_phones.update().where(
                models.customer_phones.c.customer_id == identity["customer_id"],
                models.customer_phones.c.normalized_number == identity["phone"],
            ).values(status="inactive", is_primary=False, updated_at=customers.now()))
            customers._insert_phone(session, str(identity["customer_id"]), phone, verified=False)
        identity = {**identity, "phone": phone}
    return _issue(session, identity, key, "mobile.phone_changed", revoke=True)
