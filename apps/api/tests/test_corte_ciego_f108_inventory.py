"""CC-D09: legacy inventory authority cannot approve or inspect a protected count."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, BRANCH_B, CashWorld, cash_world, grant_permission
from restaurant_os import models
from restaurant_os import operations as ops
from test_corte_ciego_f105_intents import activate
from test_platform_api import (
    ADMIN_ROLE_ID,
    _admin_headers,
    _client_with_seeded_database,
    _test_session_factory,
)

__all__ = ["cash_world"]


@pytest.mark.parametrize("capability", ["inventory.count.review", "inventory.count.approve"])
def test_legacy_count_is_not_review_or_approval(cash_world: CashWorld, capability: str) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "inventory.count")
        session.commit()
        assert not ops._actor_has_permission(session, world.actors["cashier"], capability, BRANCH_A)
        with pytest.raises(ops.AuthorizationError):
            ops.require_permission(session, world.actors["cashier"], capability, BRANCH_A)


def test_explicit_review_does_not_grant_approval(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        grant_permission(session, world.roles["cashier"], "inventory.count.review")
        session.commit()
        ops.require_permission(session, world.actors["cashier"], "inventory.count.review", BRANCH_A)
        with pytest.raises(ops.AuthorizationError):
            ops.require_permission(
                session, world.actors["cashier"], "inventory.count.approve", BRANCH_A
            )


def test_unreviewed_organization_wildcard_cannot_approve(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        with pytest.raises(ops.AuthorizationError):
            ops.require_permission(
                session, cash_world.actors["accumulated"], "inventory.count.approve", BRANCH_A
            )
        ops.require_permission(
            session, cash_world.actors["owner"], "inventory.count.approve", BRANCH_A
        )
        ops.require_permission(
            session, cash_world.actors["owner"], "inventory.count.review", BRANCH_B
        )


def test_submitted_count_stays_blind_and_cannot_move_inventory_with_legacy_permission() -> None:
    with _client_with_seeded_database() as client:
        factory = _test_session_factory(client)
        created = client.post(
            "/api/v1/inventory/physical-counts",
            headers=_admin_headers(),
            json={"branch_id": BRANCH_A, "item_ids": ["018f6f73-2d0a-74f0-8f1c-000000000311"]},
        )
        assert created.status_code == 200, created.text
        count = created.json()
        path = f"/api/v1/inventory/physical-counts/{count['id']}"
        saved = client.put(
            f"{path}/lines/{count['lines'][0]['id']}",
            headers=_admin_headers(),
            json={"counted_quantity": "24800"},
        )
        assert saved.status_code == 200, saved.text
        submitted = client.post(f"{path}/submit", headers=_admin_headers(), json={})
        assert submitted.status_code == 200, submitted.text
        activate(factory)
        with factory() as session:
            before = list(session.execute(sa.select(models.inventory_movements)).mappings())
        listed = client.get(
            "/api/v1/inventory/physical-counts",
            headers=_admin_headers(),
            params={"branch_id": BRANCH_A},
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()[0]["can_review"] is False
        assert "theoretical_quantity" not in listed.text and "snapshot_unit_cost" not in listed.text
        assert client.post(f"{path}/approve", headers=_admin_headers(), json={}).status_code == 403
        with factory() as session:
            assert list(session.execute(sa.select(models.inventory_movements)).mappings()) == before
            grant_permission(session, ADMIN_ROLE_ID, "inventory.count.review")
            grant_permission(session, ADMIN_ROLE_ID, "inventory.count.approve")
            session.commit()
        reviewed = client.get(
            "/api/v1/inventory/physical-counts",
            headers=_admin_headers(),
            params={"branch_id": BRANCH_A},
        )
        assert reviewed.json()[0]["can_review"] is True
        result = client.post(f"{path}/approve", headers=_admin_headers(), json={})
        assert result.status_code == 200, result.text
        assert result.json()["status"] == "approved"
