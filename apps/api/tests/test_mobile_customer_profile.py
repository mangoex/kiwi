"""CRM-MOBILE-001: real HTTP/DB contracts with a deterministic verification port."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest
import sqlalchemy as sa
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)
from test_public_order_intents import PUBLIC_KEY, _enable_public_order_capture, _payload

BASE = f"/api/v1/mobile/branches/{PUBLIC_KEY}"
HEADERS = {"X-Mobile-Request": "1"}
PROFILE = {"name": "Ana Prueba", "birthday_day": 29, "birthday_month": 2}


class Verifier:
    def start(self, phone: str) -> str:
        return "VE" + "a" * 32

    def check(self, verification_id: str, code: str) -> bool:
        return code == "123456"


def client_with_mobile() -> Any:
    client = _client_with_seeded_database()
    _enable_public_order_capture(client)
    client.app.state.mobile_customer_access_enabled = True
    client.app.state.mobile_phone_verifier = Verifier()
    client.app.state.mobile_customer_rate_limiter = client.app.state.public_order_rate_limiter
    return client


def login(client: Any, phone: str = "6691234567") -> Any:
    start = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": phone})
    assert start.status_code == 200, start.text
    result = client.post(
        BASE + "/access/verify",
        headers=HEADERS,
        json={"challenge": start.json()["challenge"], "code": "123456"},
    )
    assert result.status_code == 200, result.text
    return result


def complete_profile(client: Any) -> Any:
    login(client)
    response = client.put(BASE + "/profile", headers=HEADERS, json=PROFILE)
    assert response.status_code == 200, response.text
    return response.json()


def test_mobile_requires_verified_session_and_complete_profile() -> None:
    client = client_with_mobile()
    assert client.get(BASE + "/profile").status_code == 401
    assert client.get(BASE + "/catalog").status_code == 401
    login(client)
    assert client.get(BASE + "/catalog").status_code == 409
    result = client.put(BASE + "/profile", headers=HEADERS, json=PROFILE)
    assert result.status_code == 200, result.text
    assert result.json()["birthday_year"] is None
    assert client.get(BASE + "/catalog").status_code == 200
    assert client.get("/api/v1/customers").status_code in (401, 403)
    assert "no-store" in client.get(BASE + "/profile").headers["cache-control"]
    assert "HttpOnly" in login(client).headers["set-cookie"]


def test_mobile_code_replay_attempts_expiry_and_logout() -> None:
    from restaurant_os import models

    client = client_with_mobile()
    start = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"})
    token = start.json()["challenge"]
    bad = {"challenge": token, "code": "000000"}
    for _ in range(5):
        assert client.post(BASE + "/access/verify", headers=HEADERS, json=bad).status_code == 401
    assert (
        client.post(
            BASE + "/access/verify", headers=HEADERS, json={"challenge": token, "code": "123456"}
        ).status_code
        == 401
    )
    login(client)
    assert client.post(BASE + "/logout", headers=HEADERS).status_code == 200
    assert client.get(BASE + "/profile").status_code == 401
    start = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"})
    verify = {"challenge": start.json()["challenge"], "code": "123456"}
    assert client.post(BASE + "/access/verify", headers=HEADERS, json=verify).status_code == 200
    assert client.post(BASE + "/access/verify", headers=HEADERS, json=verify).status_code == 401
    fresh = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"})
    verify = {"challenge": fresh.json()["challenge"], "code": "123456"}
    with _test_session_factory(client)() as session:
        session.execute(
            models.mobile_access_challenges.update().values(
                expires_at=datetime.now(timezone.utc) - timedelta(seconds=1)
            )
        )
        session.commit()
    assert client.post(BASE + "/access/verify", headers=HEADERS, json=verify).status_code == 401


def test_mobile_profile_calendar_and_strict_boundary() -> None:
    client = client_with_mobile()
    complete_profile(client)
    for changes in (
        {"birthday_year": 2025},
        {"birthday_month": 13},
        {"birthday_day": 30},
        {"birthday_year": 2999},
        {"birthday_day": True},
        {"name": " "},
        {"email": "bad"},
        {"customer_id": "other"},
        {"organization_id": "other"},
    ):
        response = client.put(BASE + "/profile", headers=HEADERS, json={**PROFILE, **changes})
        assert response.status_code in (400, 422), response.text
    assert (
        client.put(
            BASE + "/profile", headers=HEADERS, json={**PROFILE, "birthday_year": 2000}
        ).status_code
        == 200
    )
    assert client.put(BASE + "/profile", json=PROFILE).status_code == 403


def test_mobile_reuses_unique_customer_and_blocks_ambiguous_without_pii() -> None:
    client = client_with_mobile()
    customer = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={
            "name": "CRM existente",
            "branch_id": BRANCH_ID,
            "phones": [{"number": "6691234567"}],
        },
    ).json()
    assert complete_profile(client)["id"] == customer["id"]
    client.post(BASE + "/logout", headers=HEADERS)
    for name in ("Privado uno", "Privado dos"):
        assert (
            client.post(
                "/api/v1/customers",
                headers=_admin_headers(),
                json={
                    "name": name,
                    "branch_id": BRANCH_ID,
                    "phones": [{"number": "6697654321"}],
                },
            ).status_code
            == 200
        )
    start = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6697654321"})
    result = client.post(
        BASE + "/access/verify",
        headers=HEADERS,
        json={"challenge": start.json()["challenge"], "code": "123456"},
    )
    assert result.status_code == 409
    assert "Privado" not in result.text


def test_mobile_delivery_requires_email_address_and_links_consumption() -> None:
    from restaurant_os import models

    client = client_with_mobile()
    profile = complete_profile(client)
    body = {"order_type": "delivery", "lines": _payload()["lines"]}
    headers = {**HEADERS, "Idempotency-Key": "mobile-order-test-0001"}
    assert client.post(BASE + "/order-intents", headers=headers, json=body).status_code == 409
    address = {
        "creation_key": "test-address-creation-0001",
        "alias": "Casa",
        "street": "Prueba",
        "exterior_number": "12",
        "neighborhood": "Centro",
        "postal_code": "82000",
        "city": "Mazatlán",
        "municipality": "Mazatlán",
        "state": "Sinaloa",
    }
    saved = client.put(
        BASE + "/profile",
        headers=HEADERS,
        json={**PROFILE, "email": "ana@example.com", "address": address},
    )
    assert saved.status_code == 200, saved.text
    body["address_id"] = saved.json()["addresses"][0]["id"]
    first = client.post(BASE + "/order-intents", headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert client.post(BASE + "/order-intents", headers=headers, json=body).json() == first.json()
    with _test_session_factory(client)() as session:
        intent = (
            session.execute(
                sa.select(models.public_order_intents).where(
                    models.public_order_intents.c.public_reference
                    == first.json()["public_reference"]
                )
            )
            .mappings()
            .one()
        )
        assert intent["customer_id"] == profile["id"]
        assert intent["customer_snapshot"]["email"] == "ana@example.com"
    pickup = client.post(
        BASE + "/order-intents",
        headers={**headers, "Idempotency-Key": "mobile-pickup-test-0001"},
        json={"order_type": "takeout", "lines": _payload()["lines"]},
    )
    assert pickup.status_code == 201, pickup.text
    with _test_session_factory(client)() as session:
        iid = session.execute(
            sa.select(models.public_order_intents.c.id).where(
                models.public_order_intents.c.public_reference == pickup.json()["public_reference"]
            )
        ).scalar_one()
    accepted = client.post(
        f"/api/v1/order-intents/{iid}/accept",
        headers={**_admin_headers(), "Idempotency-Key": "mobile-pickup-accept-0001"},
        json={"expected_version": 1},
    )
    assert accepted.status_code in (200, 201), accepted.text
    client.put(BASE + "/profile", headers=HEADERS, json={**PROFILE, "name": "Nombre nuevo"})
    with _test_session_factory(client)() as session:
        order = (
            session.execute(
                sa.select(models.orders).where(models.orders.c.public_order_intent_id == iid)
            )
            .mappings()
            .one()
        )
        assert order["customer_id"] == profile["id"]
        assert order["customer_snapshot"]["name"] == PROFILE["name"]


def test_admin_can_edit_optional_birthday_without_changing_other_clients() -> None:
    client = client_with_mobile()
    created = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={
            "name": "Cliente admin",
            "branch_id": BRANCH_ID,
            "birthday_day": 1,
            "birthday_month": 10,
        },
    )
    assert created.status_code == 200
    assert created.json()["birthday_day"] == 1
    result = client.put(
        f"/api/v1/customers/{created.json()['id']}",
        headers=_admin_headers(),
        json={"branch_id": BRANCH_ID, "birthday_day": 31, "birthday_month": 2},
    )
    assert result.status_code == 409
    assert result.json()["detail"]["code"] == "invalid_birthday"


def test_mobile_retry_is_stable_after_profile_changes_and_cannot_cross_customers() -> None:
    client = client_with_mobile()
    complete_profile(client)
    headers = {**HEADERS, "Idempotency-Key": "mobile-retry-test-0001"}
    body = {"order_type": "takeout", "lines": _payload()["lines"]}
    first = client.post(BASE + "/order-intents", headers=headers, json=body)
    assert first.status_code == 201, first.text
    assert (
        client.put(BASE + "/profile", headers=HEADERS, json={"name": "Nombre distinto"}).status_code
        == 200
    )
    replay = client.post(BASE + "/order-intents", headers=headers, json=body)
    assert replay.status_code == 200, replay.text
    assert replay.json() == first.json()
    client.post(BASE + "/logout", headers=HEADERS)
    login(client, "6697654321")
    client.put(BASE + "/profile", headers=HEADERS, json=PROFILE)
    other = client.post(BASE + "/order-intents", headers=headers, json=body)
    assert other.status_code == 409
    assert first.json()["public_reference"] not in other.text


def test_mobile_address_creation_retry_and_foreign_address_are_safe() -> None:
    client = client_with_mobile()
    complete_profile(client)
    address = {
        "creation_key": "stable-address-key-0001",
        "alias": "Casa",
        "street": "Prueba",
        "exterior_number": "12",
        "interior_number": "7",
        "neighborhood": "Centro",
        "postal_code": "82000",
        "city": "Mazatlán",
        "municipality": "Mazatlán",
        "state": "Sinaloa",
        "references": "Timbre verde",
    }
    first = client.put(BASE + "/profile", headers=HEADERS, json={"address": address})
    assert first.status_code == 200, first.text
    replay = client.put(BASE + "/profile", headers=HEADERS, json={"address": address})
    assert len(replay.json()["addresses"]) == 1
    assert replay.json()["saved_address_id"] == first.json()["saved_address_id"]
    body = {
        "order_type": "delivery",
        "lines": _payload()["lines"],
        "address_id": first.json()["saved_address_id"],
    }
    client.put(BASE + "/profile", headers=HEADERS, json={"email": "a@example.com"})
    result = client.post(
        BASE + "/order-intents",
        json=body,
        headers={**HEADERS, "Idempotency-Key": "mobile-delivery-display-001"},
    )
    assert result.status_code == 201, result.text
    from restaurant_os import models

    with _test_session_factory(client)() as session:
        iid = session.scalar(
            sa.select(models.public_order_intents.c.id).where(
                models.public_order_intents.c.public_reference == result.json()["public_reference"]
            )
        )
    detail = client.get(f"/api/v1/orders/{iid}", headers=_admin_headers())
    assert detail.status_code == 200, detail.text
    assert "Int. 7" in detail.json()["delivery_address"]
    assert detail.json()["delivery_notes"] == "Timbre verde"
    client.post(BASE + "/logout", headers=HEADERS)
    login(client, "6697654321")
    client.put(BASE + "/profile", headers=HEADERS, json=PROFILE)
    foreign = client.put(
        BASE + "/profile",
        headers=HEADERS,
        json={"address": {**address, "id": first.json()["saved_address_id"]}},
    )
    assert foreign.status_code == 404


def test_mobile_phone_change_verifies_new_phone_and_keeps_one_primary() -> None:
    client = client_with_mobile()
    created = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={
            "name": "Dos teléfonos",
            "branch_id": BRANCH_ID,
            "phones": [
                {"number": "6697654321", "is_primary": True},
                {"number": "6691234567", "is_primary": False},
            ],
        },
    ).json()
    complete_profile(client)
    assert (
        client.put(BASE + "/profile", headers=HEADERS, json={"phone": "6690001111"}).status_code
        == 422
    )
    challenge = client.post(
        BASE + "/profile/phone/start", headers=HEADERS, json={"phone": "6690001111"}
    ).json()["challenge"]
    bad = client.post(
        BASE + "/access/verify", headers=HEADERS, json={"challenge": challenge, "code": "000000"}
    )
    assert bad.status_code == 401
    verified = client.post(
        BASE + "/access/verify", headers=HEADERS, json={"challenge": challenge, "code": "123456"}
    )
    assert verified.status_code == 200, verified.text
    assert verified.json()["phone"] == "+526690001111"
    from restaurant_os import models

    with _test_session_factory(client)() as session:
        phones = list(
            session.execute(
                sa.select(models.customer_phones).where(
                    models.customer_phones.c.customer_id == created["id"],
                    models.customer_phones.c.status == "active",
                )
            ).mappings()
        )
        assert sum(bool(p["is_primary"]) for p in phones) == 1
        assert next(p for p in phones if p["is_primary"])["normalized_number"] == "+526690001111"


def test_mobile_profile_rechecks_customer_created_after_verification() -> None:
    client = client_with_mobile()
    login(client)
    existing = client.post(
        "/api/v1/customers",
        headers=_admin_headers(),
        json={
            "name": "Alta por cajero",
            "branch_id": BRANCH_ID,
            "phones": [{"number": "6691234567"}],
        },
    ).json()
    saved = client.put(BASE + "/profile", headers=HEADERS, json=PROFILE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["id"] == existing["id"]


def test_mobile_failures_are_private_and_fail_closed(monkeypatch: Any, caplog: Any) -> None:
    from restaurant_os import mobile_customers
    from restaurant_os.phone_verification import VerificationUnavailable
    from sqlalchemy.exc import StatementError

    client = client_with_mobile()

    def broken(*args: Any, **kwargs: Any) -> Any:
        raise StatementError(
            "PRIVATE_SENTINEL", "insert phone", {"phone": "PRIVATE_SENTINEL"}, None
        )

    monkeypatch.setattr(mobile_customers, "start_access", broken)
    response = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"})
    assert response.status_code == 503
    assert "PRIVATE_SENTINEL" not in response.text + caplog.text
    monkeypatch.undo()

    class BrokenVerifier(Verifier):
        def start(self, phone: str) -> str:
            raise VerificationUnavailable()

    client.app.state.mobile_phone_verifier = BrokenVerifier()
    assert (
        client.post(
            BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"}
        ).status_code
        == 503
    )
    assert client.get(BASE + "/profile").status_code == 401
    oversized = client.post(BASE + "/access/start", headers=HEADERS, content=b"x" * 65537)
    assert oversized.status_code == 413


def test_mobile_expired_cookie_does_not_block_fresh_login() -> None:
    client = client_with_mobile()
    login(client)
    from restaurant_os import models

    with _test_session_factory(client)() as session:
        session.execute(models.mobile_customer_sessions.update().values(revoked=True))
        session.commit()
    assert login(client).status_code == 200


def test_mobile_cookie_is_organization_scoped() -> None:
    from restaurant_os import mobile_customers

    client = client_with_mobile()
    complete_profile(client)
    token = client.cookies.get(mobile_customers.COOKIE)
    with _test_session_factory(client)() as session:
        with pytest.raises(mobile_customers.MobileError, match="mobile_session_required"):
            mobile_customers.identity_for_session(session, token, "another-organization")


@pytest.mark.parametrize("denied,status", [(True, 429), (False, 503)])
def test_mobile_rate_limiter_failures_never_send_codes(denied: bool, status: int) -> None:
    client = client_with_mobile()

    class Limiter:
        def allow(self, *args: Any) -> bool:
            if denied:
                return False
            raise TimeoutError()

    class UncalledVerifier(Verifier):
        def start(self, phone: str) -> str:
            raise AssertionError("A limited request must not send an SMS")

    client.app.state.mobile_customer_rate_limiter = Limiter()
    client.app.state.mobile_phone_verifier = UncalledVerifier()
    response = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"})
    assert response.status_code == status
