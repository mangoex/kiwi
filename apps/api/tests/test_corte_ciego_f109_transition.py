"""Transition preparation cannot issue incompatible offline authority or activate phase 2."""

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_A, CashWorld
from corte_ciego_fixtures import cash_world as cash_world
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.offline_authorization import lock_grant_actor


def test_active_policy_blocks_legacy_offline_issuance(cash_world: CashWorld):
    world = cash_world
    with world.sessions() as session, pytest.raises(ops.BusinessError) as failure:
        lock_grant_actor(session, world.actors["cashier"], ops.ORGANIZATION_ID, BRANCH_A)
    assert failure.value.code == "cash_gateway_upgrade_required"


def test_preflight_reports_real_pending_and_never_activates(cash_world: CashWorld):
    from restaurant_os.blind_cash_transition import (
        ClientEvidence,
        Review,
        TransitionInput,
        preflight,
    )

    world = cash_world
    with world.sessions() as session:
        before = session.scalar(
            sa.select(sa.func.count()).select_from(models.blind_cash_policy_revisions)
        )
        result = preflight(session, world.actors["owner"], BRANCH_A, TransitionInput())
        assert result["activation_allowed"] is False
        codes = {row["code"] for row in result["blockers"]}
        assert {
            "phase2_capture_not_ready",
            "pending_cuts",
            "unreviewed_general_authority",
            "individual_review_missing",
            "clients_not_verified",
            "source_reconciliation_unverified",
        } <= codes
        assert (
            session.scalar(
                sa.select(sa.func.count()).select_from(models.blind_cash_policy_revisions)
            )
            == before
        )
        assert all("permissions_digest" in user for user in result["users"])

        session.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == world.payload["cash_shift_id"])
            .values(status="OPEN")
        )
        reviews = [
            Review(
                user_id=user["user_id"],
                authorization_version=user["authorization_version"],
                permissions_digest=user["permissions_digest"],
                approval_reference=f"review:{user['user_id']}",
            )
            for user in result["users"]
        ]
        with_open_shift = preflight(
            session,
            world.actors["owner"],
            BRANCH_A,
            TransitionInput(
                users=reviews,
                clients=[
                    ClientEvidence(
                        component="pos",
                        instance_id="pos-1",
                        protocol_version=1,
                        verification_reference="v1",
                    ),
                    ClientEvidence(
                        component="admin",
                        instance_id="adm-1",
                        protocol_version=2,
                        verification_reference="v2",
                    ),
                    ClientEvidence(
                        component="gateway",
                        instance_id="gw-1",
                        protocol_version=2,
                        verification_reference="v2",
                    ),
                ],
                reconciliation_reference="recon-ref-001",
            ),
        )
        open_codes = {row["code"] for row in with_open_shift["blockers"]}
        assert "open_shifts" in open_codes
        assert "individual_review_missing" not in open_codes
        assert "clients_not_verified" not in open_codes
        assert "source_reconciliation_unverified" not in open_codes
        assert {
            "client_upgrade_required",
            "gateway_protected_workflow_not_ready",
            "phase2_capture_not_ready",
        } <= open_codes
        assert with_open_shift["activation_allowed"] is False

    http_res = world.client.post(
        f"/api/v2/financial-access/branches/{BRANCH_A}/preflight",
        headers=world.headers("owner"),
        json={},
    )
    assert http_res.status_code == 200, http_res.text
    assert http_res.json()["activation_allowed"] is False
    assert http_res.headers.get("cache-control") == "no-store"


def test_preflight_requires_owner(cash_world: CashWorld):
    from restaurant_os.blind_cash_transition import TransitionInput, preflight

    with cash_world.sessions() as session, pytest.raises(ops.AuthorizationError):
        preflight(session, cash_world.actors["cashier"], BRANCH_A, TransitionInput())
