"""Branch-scoped POS catalog appearance contract."""

from datetime import datetime, timezone

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.operations import ORGANIZATION_ID
from test_platform_api import (
    BRANCH_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)


def test_admin_updates_catalog_appearance_and_session_exposes_it():
    client = _client_with_seeded_database()
    response = client.put(
        f"/api/v1/branches/{BRANCH_ID}/pos-catalog-appearance",
        headers=_admin_headers(),
        json={"visuals_enabled": False},
    )
    assert response.status_code == 200, response.text
    assert response.json() == {"branch_id": BRANCH_ID, "visuals_enabled": False}

    profile = client.get("/api/v1/auth/session", headers=_admin_headers())
    assert profile.status_code == 200
    assert profile.json()["active_branch"]["pos_catalog_visuals_enabled"] is False
    with _test_session_factory(client)() as session:
        audit = session.execute(
            sa.select(models.audit_events).where(
                models.audit_events.c.action == "pos.catalog_appearance.updated"
            )
        ).mappings().one()
        assert audit["branch_id"] == BRANCH_ID
        assert audit["payload"] == {"visuals_enabled": False}


def test_catalog_appearance_rejects_unknown_fields_and_missing_actor_without_effect():
    client = _client_with_seeded_database()
    rejected = client.put(
        f"/api/v1/branches/{BRANCH_ID}/pos-catalog-appearance",
        headers=_admin_headers(),
        json={"visuals_enabled": False, "icons_in_top_menu": False},
    )
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "pos_catalog_appearance_invalid"
    assert client.put(
        f"/api/v1/branches/{BRANCH_ID}/pos-catalog-appearance",
        json={"visuals_enabled": False},
    ).status_code == 403
    with _test_session_factory(client)() as session:
        value = session.scalar(
            sa.select(models.branches.c.pos_catalog_visuals_enabled).where(
                models.branches.c.id == BRANCH_ID
            )
        )
        assert value is True


def test_authenticated_actor_without_admin_manage_cannot_change_appearance():
    client = _client_with_seeded_database()
    user_id = "018f6f73-2d0a-74f0-8f1c-000000009981"
    role_id = "018f6f73-2d0a-74f0-8f1c-000000009982"
    now = datetime(2026, 10, 3, tzinfo=timezone.utc)
    with _test_session_factory(client)() as session:
        session.execute(
            models.roles.insert().values(
                id=role_id,
                organization_id=ORGANIZATION_ID,
                name="Operador sin administración",
                scope="branch",
                created_at=now,
            )
        )
        session.execute(
            models.users.insert().values(
                id=user_id,
                organization_id=ORGANIZATION_ID,
                email="operator-no-admin@example.test",
                display_name="Operador sin administración",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.user_roles.insert().values(
                user_id=user_id,
                role_id=role_id,
                branch_id=BRANCH_ID,
            )
        )
        session.commit()
    token = create_session_token({"sub": user_id}, get_settings().secret_key)
    denied = client.put(
        f"/api/v1/branches/{BRANCH_ID}/pos-catalog-appearance",
        headers={"Authorization": f"Bearer {token}"},
        json={"visuals_enabled": False},
    )
    assert denied.status_code == 403
    with _test_session_factory(client)() as session:
        assert session.scalar(
            sa.select(models.branches.c.pos_catalog_visuals_enabled).where(
                models.branches.c.id == BRANCH_ID
            )
        ) is True
        assert session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "pos.catalog_appearance.updated")
        ) == 0
