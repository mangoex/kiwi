"""Administrative entry points use existing authorization and explicit branch scope."""

from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.operations import ORGANIZATION_ID
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _branch_admin_fixture,
    _client_with_seeded_database,
    _login_headers,
    _test_session_factory,
)

UTC = timezone.utc


def partial_account(codes: list[str]):
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    with _test_session_factory(client)() as db:
        roles = list(
            db.execute(
                sa.select(models.user_roles.c.role_id).where(
                    models.user_roles.c.user_id == fixture["supervisor_id"]
                )
            ).scalars()
        )
        ids = dict(
            db.execute(
                sa.select(models.permissions.c.code, models.permissions.c.id).where(
                    models.permissions.c.code.in_(codes)
                )
            ).all()
        )
        assert set(ids) == set(codes)
        db.execute(
            sa.delete(models.role_permissions).where(models.role_permissions.c.role_id.in_(roles))
        )
        db.execute(
            sa.insert(models.role_permissions),
            [{"role_id": roles[0], "permission_id": ids[code]} for code in codes],
        )
        db.commit()
    headers = _login_headers(client, "supervisor.norte@kiwi.local", "Temporal123+")
    return TestClient(client.app, raise_server_exceptions=False), fixture, headers


@pytest.mark.parametrize(
    "permission,endpoint",
    [
        ("inventory.waste", "/inventory/wastes"),
        ("inventory.transfer.send", "/inventory/transfers"),
    ],
)
def test_partial_inventory_permissions_reject_without_server_error(permission, endpoint):
    client, fixture, headers = partial_account(["pos.operate", permission])
    result = client.get(
        "/api/v1" + endpoint, params={"branch_id": fixture["branch_id"]}, headers=headers
    )
    assert result.status_code == 403, result.text
    assert result.json()["detail"]["code"] == "permission_denied"


def test_session_projects_compatible_capabilities_without_new_grants():
    client, fixture, headers = partial_account(["pos.operate", "purchases.manage", "admin.manage"])
    result = client.get("/api/v1/auth/session", headers=headers)
    caps = result.json()["admin_capabilities"]
    assert caps["purchases.read"] is True
    assert caps["purchases.manage"] is True
    assert caps["admin.manage"] is False
    assert caps["catalog.manage"] is False
    assert set(result.json()["permissions"]) == {"pos.operate", "purchases.manage", "admin.manage"}


def test_read_only_purchase_account_cannot_preview_write():
    client, fixture, headers = partial_account(["pos.operate", "purchases.read"])
    profile = client.get("/api/v1/auth/session", headers=headers).json()
    assert profile["admin_capabilities"]["purchases.read"] is True
    assert profile["admin_capabilities"]["purchases.manage"] is False
    result = client.post(
        "/api/v1/purchases/preview",
        headers=headers,
        json={
            "branch_id": fixture["branch_id"],
            "document_date": "2026-10-07",
            "document_type": "note",
            "folio": "QA-READONLY",
            "supplier_id": "synthetic",
            "payment_method": "other",
            "paid_from_cash": False,
            "lines": [
                {
                    "presentation_id": "synthetic",
                    "quantity": "1",
                    "unit_price": "1",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
    )
    assert result.status_code == 403, result.text


def test_explicit_availability_branch_does_not_modify_other_branch():
    client = _client_with_seeded_database()
    fixture = _branch_admin_fixture(client)
    headers = _admin_headers()
    before = client.get(
        "/api/v1/branch-administration/catalog/products",
        params={"branch_id": fixture["branch_id"]},
        headers=headers,
    ).json()
    products = client.get(
        "/api/v1/branch-administration/catalog/products",
        params={"branch_id": BRANCH_ID},
        headers=headers,
    ).json()
    result = client.put(
        "/api/v1/branch-administration/catalog/products/" + products[0]["id"] + "/availability",
        params={"branch_id": BRANCH_ID},
        headers=headers,
        json={"action": "unavailable"},
    )
    assert result.status_code == 200, result.text
    assert result.json()["branch_id"] == BRANCH_ID
    after = client.get(
        "/api/v1/branch-administration/catalog/products",
        params={"branch_id": fixture["branch_id"]},
        headers=headers,
    ).json()
    assert after == before


def test_production_recipes_use_the_requested_authorized_branch():
    client, fixture, headers = partial_account(["pos.operate", "production.manage"])
    with _test_session_factory(client)() as db:
        recipe_ids = list(db.execute(sa.select(models.recipes.c.id)).scalars())
        assert len(recipe_ids) >= 2
        db.execute(sa.update(models.recipes).values(branch_id=BRANCH_ID))
        db.execute(
            sa.update(models.recipes)
            .where(models.recipes.c.id == recipe_ids[0])
            .values(branch_id=fixture["branch_id"])
        )
        db.execute(
            sa.update(models.recipes)
            .where(models.recipes.c.id == recipe_ids[1])
            .values(branch_id=None)
        )
        db.commit()
    result = client.get(
        "/api/v1/recipes", params={"branch_id": fixture["branch_id"]}, headers=headers
    )
    assert result.status_code == 200, result.text
    assert {row["id"] for row in result.json()} == set(recipe_ids[:2])
    foreign = client.get("/api/v1/recipes", params={"branch_id": BRANCH_ID}, headers=headers)
    assert foreign.status_code == 403


def test_transfer_destinations_do_not_require_corporate_administration():
    client, fixture, headers = partial_account(
        ["pos.operate", "inventory.read", "inventory.transfer.send"]
    )
    result = client.get(
        "/api/v1/inventory/transfer-destinations",
        params={"branch_id": fixture["branch_id"]},
        headers=headers,
    )
    assert result.status_code == 200, result.text
    assert BRANCH_ID in {row["id"] for row in result.json()}
    assert fixture["branch_id"] not in {row["id"] for row in result.json()}
    assert all(set(row) == {"id", "name", "code", "status"} for row in result.json())
    foreign = client.get(
        "/api/v1/inventory/transfer-destinations", params={"branch_id": BRANCH_ID}, headers=headers
    )
    assert foreign.status_code == 403


def test_recipe_default_scope_does_not_expand_a_mixed_account():
    client, fixture, headers = partial_account(["pos.operate", "production.manage"])
    role_id = "018f6f73-2d0a-74f0-8f1c-000000009991"
    with _test_session_factory(client)() as db:
        db.execute(
            sa.insert(models.roles).values(
                id=role_id,
                organization_id=ORGANIZATION_ID,
                name="Observer QA",
                scope="organization",
                created_at=datetime(2026, 10, 7, tzinfo=UTC),
            )
        )
        db.execute(
            sa.insert(models.user_roles).values(
                user_id=fixture["supervisor_id"],
                role_id=role_id,
                branch_id=None,
            )
        )
        db.commit()
    # Organization visibility must not turn the North production grant into a global read.
    result = client.get("/api/v1/recipes", headers=headers)
    assert result.status_code == 403
    allowed = client.get(
        "/api/v1/recipes", params={"branch_id": fixture["branch_id"]}, headers=headers
    )
    assert allowed.status_code == 200


def test_session_branch_directory_is_limited_to_allowed_scope():
    client, fixture, headers = partial_account(["pos.operate", "purchases.read"])
    profile = client.get("/api/v1/auth/session", headers=headers).json()
    assert {row["id"] for row in profile["allowed_branches"]} == {fixture["branch_id"]}
    corporate = client.get("/api/v1/auth/session", headers=_admin_headers()).json()
    assert {row["id"] for row in corporate["allowed_branches"]} == set(
        corporate["scope"]["allowed_branch_ids"]
    )
