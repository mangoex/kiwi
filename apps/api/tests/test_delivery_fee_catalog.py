from fastapi.testclient import TestClient
from test_platform_api import BRANCH_ID, _admin_headers, _client_with_seeded_database


def create_tariff(client: TestClient, code: str = "STANDARD", amount: int = 2800) -> dict:
    response = client.post(
        "/api/v1/delivery-tariffs",
        headers=_admin_headers(),
        json={"code": code, "name": code, "amount_cents": amount},
    )
    assert response.status_code == 200, response.text
    return response.json()


def enable_policy(client: TestClient, tariff_id: str, threshold: int | None = None) -> dict:
    response = client.post(
        "/api/v1/delivery-policies",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "expected_version": 0,
            "enabled": True,
            "eligible_tariff_ids": [tariff_id],
            "default_tariff_id": tariff_id,
            "free_threshold_cents": threshold,
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_catalog_versions_policy_and_defaults_have_no_product_or_recipe() -> None:
    client = _client_with_seeded_database()
    first = create_tariff(client)
    assert first["amount_cents"] == 2800
    policy = enable_policy(client, first["id"], 50000)
    assert policy["version"] == 1
    options = client.get(
        "/api/v1/delivery-options", headers=_admin_headers(), params={"branch_id": BRANCH_ID}
    )
    assert options.status_code == 200, options.text
    assert options.json()["policy"]["default_tariff_id"] == first["id"]
    assert options.json()["tariffs"][0]["amount_cents"] == 2800
    revised = client.post(
        f"/api/v1/delivery-tariffs/{first['id']}/revisions",
        headers=_admin_headers(),
        json={"expected_version": 1, "name": "Nuevo precio", "amount_cents": 3000, "active": True},
    )
    assert revised.status_code == 200, revised.text
    assert revised.json()["version"] == 2
    assert "product_id" not in revised.json()


def test_invalid_configuration_and_untrusted_authority_fail_closed() -> None:
    client = _client_with_seeded_database()
    first = create_tariff(client)
    enable_policy(client, first["id"])
    invalid = client.post(
        "/api/v1/delivery-policies",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "expected_version": 1,
            "enabled": True,
            "eligible_tariff_ids": [],
            "default_tariff_id": first["id"],
            "free_threshold_cents": 0,
        },
    )
    assert invalid.status_code == 422
    unauthorized = client.get("/api/v1/delivery-tariffs")
    assert unauthorized.status_code == 401
    conflicting = client.post(
        "/api/v1/delivery-policies",
        headers=_admin_headers(),
        json={
            "branch_id": BRANCH_ID,
            "expected_version": 0,
            "enabled": True,
            "eligible_tariff_ids": [first["id"]],
            "default_tariff_id": first["id"],
        },
    )
    assert conflicting.status_code == 409


def test_unchanged_tariff_preserves_version_and_branch_role_cannot_publish() -> None:
    from restaurant_os import models
    from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, _test_session_factory

    client = _client_with_seeded_database()
    first = create_tariff(client)
    unchanged = client.post(
        f"/api/v1/delivery-tariffs/{first['id']}/revisions",
        headers=_admin_headers(),
        json={
            "expected_version": 1,
            "name": first["name"],
            "amount_cents": first["amount_cents"],
            "active": True,
        },
    )
    assert unchanged.status_code == 200, unchanged.text
    assert unchanged.json()["version"] == 1
    with _test_session_factory(client)() as session:
        session.execute(
            models.roles.update().where(models.roles.c.id == ADMIN_ROLE_ID).values(scope="branch")
        )
        session.execute(
            models.user_roles.update()
            .where(models.user_roles.c.user_id == ADMIN_USER_ID)
            .values(branch_id=BRANCH_ID)
        )
        session.commit()
    denied = client.post(
        "/api/v1/delivery-tariffs",
        headers=_admin_headers(),
        json={"code": "DENIED", "name": "Branch", "amount_cents": 2800},
    )
    assert denied.status_code == 403, denied.text
