# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-mobile-password-tests-v1
# Password literals are synthetic fixtures scoped to the local test database.
"""Password access must work without a provider and must not claim existing CRM data."""

from typing import Any

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.config import Settings
from test_mobile_customer_profile import BASE, HEADERS, PROFILE, client_with_mobile
from test_platform_api import BRANCH_ID, _admin_headers, _test_session_factory

PASSWORD = "Mi desayuno favorito 2026!"


def register(client: Any, phone: str = "6691234567") -> Any:
    return client.post(BASE + "/access/register", headers=HEADERS,
                       json={"phone": phone, "password": PASSWORD})


def test_production_otp_without_redis_fails_closed_but_password_access_works(
    monkeypatch: Any,
) -> None:
    from restaurant_os.main import create_app

    settings = Settings(
        _env_file=None, environment="production", secret_key="x" * 32,
        redis_url=None, twilio_account_sid="AC" + "1" * 32,
        twilio_auth_token="synthetic-fixture", twilio_verify_service_sid="VA" + "2" * 32,
    )
    monkeypatch.setattr("restaurant_os.main.get_settings", lambda: settings)
    configured = create_app()
    client = client_with_mobile()
    client.app.state.mobile_customer_rate_limiter = configured.state.mobile_customer_rate_limiter

    class UncalledVerifier:
        def start(self, phone: str) -> str:
            raise AssertionError("OTP must not reach the provider without a shared limiter")

    client.app.state.mobile_phone_verifier = UncalledVerifier()
    response = client.post(BASE + "/access/start", headers=HEADERS, json={"phone": "6691234567"})
    assert response.status_code == 503, response.text
    assert configured.state.mobile_customer_rate_limiter is None
    assert register(client).status_code == 200
    assert client.post(BASE + "/logout", headers=HEADERS).status_code == 200
    assert client.post(BASE + "/access/login", headers=HEADERS,
                       json={"phone": "6691234567", "password": PASSWORD}).status_code == 200


def test_password_access_works_without_sms_and_defaults_enabled() -> None:
    settings = Settings(_env_file=None, environment="production", secret_key="x" * 32)
    assert settings.mobile_customer_access_enabled
    client = client_with_mobile()
    client.app.state.mobile_phone_verifier = None
    client.app.state.mobile_customer_rate_limiter = None
    response = register(client)
    assert response.status_code == 200, response.text
    assert response.json()["complete"] is False
    assert "HttpOnly" in response.headers["set-cookie"]
    assert client.get(BASE + "/catalog").status_code == 409
    assert client.put(BASE + "/profile", headers=HEADERS, json=PROFILE).status_code == 200
    assert client.get(BASE + "/catalog").status_code == 200
    assert client.post(BASE + "/logout", headers=HEADERS).status_code == 200
    result = client.post(BASE + "/access/login", headers=HEADERS,
                         json={"phone": "6691234567", "password": PASSWORD})
    assert result.status_code == 200, result.text
    assert result.json()["name"] == PROFILE["name"]


def test_password_registration_cannot_read_or_modify_existing_crm() -> None:
    client = client_with_mobile()
    historical = client.post("/api/v1/customers", headers=_admin_headers(), json={
        "name": "Nombre privado anterior", "branch_id": BRANCH_ID,
        "phones": [{"number": "6691234567"}],
    }).json()
    result = register(client)
    assert result.status_code == 200, result.text
    assert result.json()["name"] is None
    assert result.json()["addresses"] == []
    profile = client.put(BASE + "/profile", headers=HEADERS, json=PROFILE)
    assert profile.status_code == 200, profile.text
    assert profile.json()["id"] != historical["id"]
    with _test_session_factory(client)() as session:
        assert session.scalar(sa.select(models.customers.c.name).where(
            models.customers.c.id == historical["id"])) == "Nombre privado anterior"
        phone = session.execute(sa.select(models.customer_phones).where(
            models.customer_phones.c.customer_id == profile.json()["id"])).mappings().one()
        assert phone["is_verified"] is False


def test_login_and_validation_errors_do_not_echo_credentials() -> None:
    client = client_with_mobile()
    assert register(client).status_code == 200
    bad = "wrong-but-private-password"
    responses = [client.post(BASE + "/access/login", headers=HEADERS,
                 json={"phone": phone, "password": bad})
                 for phone in ("6691234567", "6690000000")]
    assert all(r.status_code == 401 for r in responses)
    assert responses[0].json() == responses[1].json()
    result = client.post(BASE + "/access/register", headers=HEADERS,
                         json={"phone": "6691234568", "password": "private"})
    assert result.status_code == 422
    assert "private" not in result.text
    assert client.post(BASE + "/access/login", json={
        "phone": "6691234567", "password": PASSWORD}).status_code == 403


def test_password_hashes_and_repeated_registration_preserve_the_owner() -> None:
    client = client_with_mobile()
    assert register(client).status_code == 200
    assert register(client).status_code == 409
    assert register(client, "6691234568").status_code == 200
    with _test_session_factory(client)() as session:
        rows = session.execute(sa.select(models.mobile_customer_credentials)).mappings().all()
        assert len(rows) == 2
        assert rows[0]["password_hash"] != rows[1]["password_hash"]
        assert rows[0]["password_salt"] != rows[1]["password_salt"]
        assert PASSWORD not in str(rows)
    result = client.post(BASE + "/access/login", headers=HEADERS,
                         json={"phone": "6691234567", "password": PASSWORD})
    assert result.status_code == 200


def test_password_rotation_rejects_wrong_password_and_revokes_previous_sessions() -> None:
    from restaurant_os.mobile_customers import COOKIE

    client = client_with_mobile()
    assert register(client).status_code == 200
    previous = client.cookies.get(COOKIE)
    updated = PASSWORD + " actualizado"
    wrong = client.put(BASE + "/profile/password", headers=HEADERS, json={
        "current_password": "Incorrecta", "new_password": updated,
    })
    assert wrong.status_code == 401
    assert client.get(BASE + "/profile").status_code == 200
    response = client.put(BASE + "/profile/password", headers=HEADERS, json={
        "current_password": PASSWORD, "new_password": updated,
    })
    assert response.status_code == 200, response.text
    assert client.cookies.get(COOKIE) != previous
    stale = client.get(BASE + "/profile", headers={"Cookie": f"{COOKIE}={previous}"})
    assert stale.status_code == 401
    for password, expected in ((PASSWORD, 401), (updated, 200)):
        assert client.post(BASE + "/access/login", headers=HEADERS, json={
            "phone": "6691234567", "password": password,
        }).status_code == expected


def test_phone_change_requires_password_and_keeps_the_customer() -> None:
    from restaurant_os.mobile_customers import COOKIE

    client = client_with_mobile()
    assert register(client).status_code == 200
    customer = client.put(BASE + "/profile", headers=HEADERS, json=PROFILE).json()
    previous = client.cookies.get(COOKIE)
    assert client.put(BASE + "/profile/phone", headers=HEADERS, json={
        "phone": "6691112222", "current_password": "incorrecta",
    }).status_code == 401
    response = client.put(BASE + "/profile/phone", headers=HEADERS, json={
        "phone": "6691112222", "current_password": PASSWORD,
    })
    assert response.status_code == 200, response.text
    assert response.json()["id"] == customer["id"]
    assert response.json()["phone"] == "+526691112222"
    stale = client.get(BASE + "/profile", headers={"Cookie": f"{COOKIE}={previous}"})
    assert stale.status_code == 401
    assert client.post(BASE + "/access/login", headers=HEADERS, json={
        "phone": "6691112222", "password": PASSWORD,
    }).status_code == 200
    with _test_session_factory(client)() as session:
        phones = session.execute(sa.select(models.customer_phones).where(
            models.customer_phones.c.customer_id == customer["id"],
            models.customer_phones.c.status == "active",
        )).mappings().all()
        assert len(phones) == 1 and phones[0]["is_primary"]
        assert not phones[0]["is_verified"]


def test_phone_change_does_not_take_an_existing_identity_or_crm_phone() -> None:
    client = client_with_mobile()
    assert register(client).status_code == 200
    client.post("/api/v1/customers", headers=_admin_headers(), json={
        "name": "Otro cliente", "branch_id": BRANCH_ID,
        "phones": [{"number": "6691112222"}],
    })
    assert client.put(BASE + "/profile/phone", headers=HEADERS, json={
        "phone": "6691112222", "current_password": PASSWORD,
    }).status_code == 409
    assert client.get(BASE + "/profile").json()["phone"] == "+526691234567"


def test_password_throttle_survives_a_new_http_client_and_does_not_store_pii() -> None:
    from fastapi.testclient import TestClient

    client = client_with_mobile()
    for _ in range(10):
        response = client.post(BASE + "/access/login", headers=HEADERS, json={
            "phone": "6691234567", "password": PASSWORD,
        })
        assert response.status_code == 401, response.text
    other = TestClient(client.app)
    response = other.post(BASE + "/access/login", headers=HEADERS, json={
        "phone": "+526691234567", "password": PASSWORD,
    })
    assert response.status_code == 429
    with _test_session_factory(client)() as session:
        rows = session.execute(sa.select(models.mobile_auth_attempts)).mappings().all()
        assert len(rows) == 3
        assert "6691234567" not in str(rows)
        assert all(len(row["bucket_key"]) == 64 for row in rows)


def test_legacy_session_can_set_password_but_registration_and_otp_cannot_replace_it() -> None:
    from test_mobile_customer_profile import login

    client = client_with_mobile()
    login(client)
    assert register(client).status_code == 409
    # An approved old challenge must not bypass a subsequently established password.
    challenge = client.post(BASE + "/access/start", headers=HEADERS,
                            json={"phone": "6691234567"}).json()["challenge"]
    phone_challenge = client.post(BASE + "/profile/phone/start", headers=HEADERS,
                                  json={"phone": "6691112222"}).json()["challenge"]
    assert client.put(BASE + "/profile/password", headers=HEADERS,
                       json={"new_password": PASSWORD}).status_code == 200
    for token in (challenge, phone_challenge):
        result = client.post(BASE + "/access/verify", headers=HEADERS,
                             json={"challenge": token, "code": "123456"})
        assert result.status_code == 409, result.text
    assert client.get(BASE + "/profile").json()["phone"] == "+526691234567"


def test_disabled_access_blocks_registration_and_storage_failure_remains_private() -> None:
    client = client_with_mobile()
    client.app.state.mobile_customer_access_enabled = False
    assert register(client).status_code == 503
    client.app.state.mobile_customer_access_enabled = True
    with _test_session_factory(client)() as session:
        session.execute(sa.text("DROP TABLE mobile_auth_attempts"))
        session.commit()
    response = register(client)
    assert response.status_code == 503
    assert "mobile_storage_unavailable" in response.text
    assert "password" not in response.text and "SELECT" not in response.text
