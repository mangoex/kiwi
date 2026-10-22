"""TC-450/451: F1-04 common authority, real commands and HTTP boundary."""

from __future__ import annotations

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import (
    BRANCH_A,
    BRANCH_B,
    ORG_ID,
    OTHER_BRANCH,
    CashWorld,
    grant_permission,
    ident,
)
from corte_ciego_fixtures import (
    cash_world as cash_world,
)
from restaurant_os import models, operations
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.financial_access import FinancialAccessService
from restaurant_os.financial_authority import FinancialAuthority


def grant_payload(world: CashWorld, subject: str = "delegate", **overrides: Any) -> dict[str, Any]:
    return {
        "subject_user_id": world.actors[subject],
        "reason": "Explicit synthetic approval",
        "scopes": [{"branch_id": BRANCH_A, "dataset": "sales"}],
        **overrides,
    }


@pytest.mark.parametrize("token_type", ["agent", "device"])
def test_technical_token_cannot_impersonate_human_even_with_matching_subject(
    cash_world: CashWorld,
    token_type: str,
) -> None:
    token = create_session_token(
        {"sub": cash_world.actors["owner"], "typ": token_type}, get_settings().secret_key
    )
    response = cash_world.client.get(
        "/api/v2/financial-access/grants", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403


def test_human_token_is_authenticated_before_current_authority_check(cash_world: CashWorld) -> None:
    token = create_session_token({"sub": cash_world.actors["owner"]}, get_settings().secret_key)
    response = cash_world.client.get(
        "/api/v2/financial-access/grants", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert cash_world.client.get("/api/v2/financial-access/grants").status_code == 401


@pytest.mark.parametrize(
    "actor",
    [
        "cashier",
        "leader",
        "chief_cashier",
        "administrator",
        "supervisor",
        "accumulated",
        "delegate",
        "revoked",
        "foreign",
    ],
)
def test_financial_bit_and_legacy_authority_do_not_authorize_sales_a(
    cash_world: CashWorld,
    actor: str,
) -> None:
    with cash_world.sessions() as session:
        policy = FinancialAuthority(session, cash_world.actors[actor], ORG_ID)
        queried = []
        with pytest.raises(operations.AuthorizationError, match="not authorized"):
            policy.materialize([(BRANCH_A, "sales")], lambda: queried.append("money"))
        assert queried == []


@pytest.mark.parametrize(
    "actor,capability,allowed",
    [
        ("owner", "financial.delegations.manage", True),
        ("owner", "cash.user_cut.capture", False),
        ("owner", "cash.user_cut.finalize", True),
        ("leader", "cash.user_cut.capture", True),
        ("leader", "cash.user_cut.finalize", True),
        ("cashier", "cash.user_cut.capture", True),
        ("cashier", "cash.user_cut.finalize", False),
        ("delegate", "cash.user_cut.finalize", False),
        ("administrator", "cash.user_cut.finalize", False),
        ("accumulated", "cash.user_cut.finalize", False),
        ("leader", "cash.user_cut.reopen.authorize", False),
        ("delegate", "financial.delegations.manage", False),
        ("accumulated", "inventory.count.approve", False),
        ("delegate", "purchases.prices.read", False),
        ("delegate", "inventory.costs.read", False),
    ],
)
def test_capabilities_are_exact_separate_and_owner_gated(
    cash_world: CashWorld,
    actor: str,
    capability: str,
    allowed: bool,
) -> None:
    with cash_world.sessions() as session:
        grant_permission(session, cash_world.roles[actor], "inventory.count")
        session.commit()
        policy = FinancialAuthority(session, cash_world.actors[actor], ORG_ID)
        if allowed:
            assert policy.require_capability(capability, BRANCH_A) >= 1
        else:
            with pytest.raises(operations.AuthorizationError):
                policy.require_capability(capability, BRANCH_A)


def test_owner_default_needs_both_review_and_current_governance(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        policy = FinancialAuthority(session, cash_world.actors["owner"], ORG_ID)
        assert policy.require_financial([(BRANCH_A, "sales"), (BRANCH_B, "cash.cuts")]) == 1
        session.execute(
            models.role_authority_grants.delete().where(
                models.role_authority_grants.c.role_id == cash_world.roles["owner"],
            )
        )
        session.commit()
        with pytest.raises(operations.AuthorizationError):
            policy.require_financial([(BRANCH_A, "sales")])


def test_union_of_pairs_is_not_cartesian_and_branch_assignment_is_bound(
    cash_world: CashWorld,
) -> None:
    with cash_world.sessions() as session:
        policy = FinancialAuthority(session, cash_world.actors["delegate"], ORG_ID)
        assert policy.require_financial([(BRANCH_A, "cash.cuts"), (BRANCH_B, "sales")]) == 1
        for pairs in (
            [],
            [(BRANCH_A, "sales")],
            [(BRANCH_B, "cash.cuts")],
            [(OTHER_BRANCH, "sales")],
            [(BRANCH_A, "*")],
        ):
            with pytest.raises(operations.AuthorizationError):
                policy.require_financial(pairs)
        session.execute(
            models.roles.update()
            .where(
                models.roles.c.id == cash_world.roles["delegate"],
            )
            .values(scope="branch")
        )
        session.execute(
            models.user_roles.update()
            .where(
                models.user_roles.c.user_id == cash_world.actors["delegate"],
            )
            .values(branch_id=BRANCH_A)
        )
        session.commit()
        policy.require_financial([(BRANCH_A, "cash.cuts")])
        with pytest.raises(operations.AuthorizationError):
            policy.require_financial([(BRANCH_B, "sales")])


def test_owner_review_expires_on_governed_authority_change(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        owner = cash_world.actors["owner"]
        operations.assign_user_role(session, owner, cash_world.roles["leader"], None, owner)
        with pytest.raises(operations.AuthorizationError):
            FinancialAuthority(session, owner, ORG_ID).require_financial([(BRANCH_A, "sales")])
        with pytest.raises(operations.BusinessError) as error:
            FinancialAuthority(session, owner, ORG_ID).require_financial(
                [(BRANCH_A, "sales")],
                expected_version=1,
            )
        assert error.value.code == "cash_authorization_changed"


def test_delegate_cannot_read_without_explicit_bit_after_role_change(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        operations.update_role_permissions(
            session, cash_world.roles["delegate"], [], cash_world.actors["owner"]
        )
        with pytest.raises(operations.AuthorizationError):
            FinancialAuthority(session, cash_world.actors["delegate"], ORG_ID).require_financial(
                [(BRANCH_B, "sales")],
            )


def test_issue_replay_conflict_revocation_and_overlapping_grants(cash_world: CashWorld) -> None:
    before = cash_world.snapshot()
    with cash_world.sessions() as session:
        service = FinancialAccessService(session, ORG_ID)
        owner, delegate = cash_world.actors["owner"], cash_world.actors["delegate"]
        payload = grant_payload(cash_world)
        issued = service.issue(owner, "issue-one", payload)
        replay = service.issue(owner, "issue-one", payload)
        assert replay == {**issued, "replay": True}
        with pytest.raises(operations.BusinessError) as error:
            service.issue(owner, "issue-one", {**payload, "reason": "other"})
        assert error.value.code == "idempotency_key_conflict"
        policy = FinancialAuthority(session, delegate, ORG_ID)
        policy.require_financial([(BRANCH_A, "sales")])
        session.commit()
        second = service.issue(owner, "overlap", payload)
        service.revoke(owner, issued["grant_id"], "revoke-one", {"reason": "Withdraw first"})
        policy.require_financial([(BRANCH_A, "sales")])
        session.commit()
        revoked = service.revoke(
            owner, second["grant_id"], "revoke-two", {"reason": "Withdraw last"}
        )
        assert service.revoke(
            owner, second["grant_id"], "revoke-two", {"reason": "Withdraw last"}
        ) == {
            **revoked,
            "replay": True,
        }
        with pytest.raises(operations.AuthorizationError):
            policy.require_financial([(BRANCH_A, "sales")])
        session.rollback()
        assert (
            service.revoke(owner, second["grant_id"], "another-key", {"reason": "Retry"})["outcome"]
            == "already_revoked"
        )
        version = session.scalar(
            sa.select(models.users.c.authorization_version).where(
                models.users.c.id == delegate,
            )
        )
        assert version == 5  # two issuances and two revocations, never a replay
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action.like("financial_access.%"),
                )
            )
            == 6
        )  # includes fixture revocation and explicit already-revoked command
    assert cash_world.snapshot() == before


@pytest.mark.parametrize("failure_point", ["audit", "command", "scope"])
def test_issue_failure_rolls_back_grant_version_and_audit(
    cash_world: CashWorld,
    monkeypatch: pytest.MonkeyPatch,
    failure_point: str,
) -> None:
    with cash_world.sessions() as session:
        baseline = session.scalar(
            sa.select(sa.func.count()).select_from(models.financial_access_grants)
        )
        if failure_point == "audit":

            def fail_audit(*args: Any, **kwargs: Any) -> None:
                raise RuntimeError("injected failure")

            monkeypatch.setattr(operations, "_audit", fail_audit)
        else:
            target = (
                "financial_access_commands"
                if failure_point == "command"
                else "financial_access_grant_scopes"
            )

            def fail_insert(
                conn: Any,
                cursor: Any,
                statement: str,
                parameters: Any,
                context: Any,
                executemany: bool,
            ) -> None:
                if statement.startswith(f"INSERT INTO {target} "):
                    raise RuntimeError("injected failure")

            sa.event.listen(cash_world.engine, "before_cursor_execute", fail_insert)
        try:
            with pytest.raises(RuntimeError, match="injected failure"):
                FinancialAccessService(session, ORG_ID).issue(
                    cash_world.actors["owner"],
                    "fail-atomic",
                    grant_payload(cash_world),
                )
        finally:
            if failure_point != "audit":
                sa.event.remove(cash_world.engine, "before_cursor_execute", fail_insert)
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.financial_access_grants))
            == baseline
        )
        assert (
            session.scalar(
                sa.select(models.users.c.authorization_version).where(
                    models.users.c.id == cash_world.actors["delegate"],
                )
            )
            == 1
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.financial_access_commands)
                .where(
                    models.financial_access_commands.c.idempotency_key == "fail-atomic",
                )
            )
            == 0
        )


@pytest.mark.parametrize(
    "actor", ["cashier", "leader", "delegate", "administrator", "accumulated", "foreign"]
)
def test_http_management_denies_non_owner_and_explicit_manage_bit(
    cash_world: CashWorld,
    actor: str,
) -> None:
    with cash_world.sessions() as session:
        grant_permission(session, cash_world.roles[actor], "financial.delegations.manage")
        session.commit()
    for method, path, body in (
        ("GET", "/api/v2/financial-access/grants", None),
        ("POST", "/api/v2/financial-access/grants", grant_payload(cash_world)),
        (
            "POST",
            f"/api/v2/financial-access/grants/{ident('grant:sales-b')}/revoke",
            {"reason": "No"},
        ),
    ):
        response = cash_world.client.request(
            method, path, json=body, headers=cash_world.headers(actor, key="denied")
        )
        assert response.status_code == 403, response.text
        assert response.json()["detail"]["code"] == "financial_access_denied"


def test_http_owner_contract_and_replay_after_lost_authority(cash_world: CashWorld) -> None:
    path = "/api/v2/financial-access/grants"
    kwargs = {
        "json": grant_payload(cash_world),
        "headers": cash_world.headers("owner", key="http-issue"),
    }
    response = cash_world.client.post(path, **kwargs)
    assert response.status_code == 200, response.text
    assert response.headers["cache-control"] == "no-store"
    assert set(response.json()) == {
        "command_id",
        "grant_id",
        "action",
        "outcome",
        "replay",
        "accepted_at",
    }
    listed = cash_world.client.get(path, headers=cash_world.headers("owner"))
    assert listed.status_code == 200 and len(listed.json()["grants"]) == 5
    with cash_world.sessions() as session:
        operations.delete_user(session, cash_world.actors["owner"], cash_world.actors["owner"])
    assert cash_world.client.post(path, **kwargs).status_code == 403


@pytest.mark.parametrize(
    "override",
    [
        {"scopes": []},
        {"reason": " "},
        {"extra": "must reject"},
        {"scopes": [{"branch_id": BRANCH_A, "dataset": "*"}]},
        {"scopes": [{"branch_id": "*", "dataset": "sales"}]},
    ],
)
def test_http_rejects_invalid_or_extended_contract(
    cash_world: CashWorld, override: dict[str, Any]
) -> None:
    response = cash_world.client.post(
        "/api/v2/financial-access/grants",
        json=grant_payload(cash_world, **override),
        headers=cash_world.headers("owner", key="invalid"),
    )
    assert response.status_code == 422, response.text


@pytest.mark.parametrize(
    "override",
    [
        {"subject_user_id": ident("user:foreign")},
        {"scopes": [{"branch_id": OTHER_BRANCH, "dataset": "sales"}]},
    ],
)
def test_owner_cannot_issue_across_organizations(
    cash_world: CashWorld, override: dict[str, Any]
) -> None:
    response = cash_world.client.post(
        "/api/v2/financial-access/grants",
        json=grant_payload(cash_world, **override),
        headers=cash_world.headers("owner", key="foreign"),
    )
    assert response.status_code == 403, response.text


def test_operational_report_and_policy_read_use_server_authority(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        policy = FinancialAuthority(session, cash_world.actors["delegate"], ORG_ID)
        policy.require_operational_report(BRANCH_B)
        assert policy.policy_revision(BRANCH_A) == 1
        with pytest.raises(operations.AuthorizationError):
            policy.require_operational_report(BRANCH_A)


@pytest.mark.parametrize("attack", ["permissions", "assignment", "scope"])
def test_admin_cannot_self_escalate_through_governance(cash_world: CashWorld, attack: str) -> None:
    with cash_world.sessions() as session:
        admin, role = cash_world.actors["administrator"], cash_world.roles["administrator"]
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "cash.user_cut.finalize",
            )
        )
        assert permission is not None
        if attack == "scope":
            session.execute(
                models.user_roles.insert().values(
                    user_id=admin,
                    role_id=cash_world.roles["supervisor"],
                    branch_id=None,
                )
            )
            session.execute(
                models.roles.update().where(models.roles.c.id == role).values(scope="branch")
            )
            session.execute(
                models.user_roles.update()
                .where(models.user_roles.c.role_id == role)
                .values(branch_id=BRANCH_A)
            )
            session.commit()
        with pytest.raises(operations.AuthorizationError) as error:
            if attack == "permissions":
                operations.update_role_permissions(session, role, [permission], admin)
            elif attack == "assignment":
                operations.assign_user_role(session, admin, cash_world.roles["leader"], None, admin)
            else:
                operations.update_role(session, role, scope="organization", actor_user_id=admin)
        assert error.value.code == "financial_access_denied"


def test_owner_can_assign_reviewed_capability_without_granting_financial_reads(
    cash_world: CashWorld,
) -> None:
    with cash_world.sessions() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "cash.user_cut.finalize",
            )
        )
        assert permission is not None
        operations.update_role_permissions(
            session, cash_world.roles["leader"], [permission], cash_world.actors["owner"]
        )
        policy = FinancialAuthority(session, cash_world.actors["leader"], ORG_ID)
        policy.require_capability("cash.user_cut.finalize", BRANCH_A)
        with pytest.raises(operations.AuthorizationError):
            policy.require_financial([(BRANCH_A, "cash.cuts")])


def test_self_delegation_rejected_without_invalidating_owner(cash_world: CashWorld) -> None:
    with cash_world.sessions() as session:
        with pytest.raises(operations.BusinessError) as error:
            FinancialAccessService(session, ORG_ID).issue(
                cash_world.actors["owner"],
                "self",
                grant_payload(cash_world, "owner"),
            )
        assert error.value.code == "financial_owner_delegation_unnecessary"
        assert (
            FinancialAuthority(session, cash_world.actors["owner"], ORG_ID).require_capability(
                "financial.delegations.manage",
                None,
            )
            == 1
        )


@pytest.mark.parametrize("code", ["inventory.count.review", "inventory.count.approve"])
def test_admin_cannot_add_inventory_review_authority_under_new_policy(
    cash_world: CashWorld,
    code: str,
) -> None:
    with cash_world.sessions() as session:
        grant_permission(session, cash_world.roles["owner"], code)
        session.commit()
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == code,
            )
        )
        assert permission is not None
        with pytest.raises(operations.AuthorizationError) as error:
            operations.update_role_permissions(
                session,
                cash_world.roles["administrator"],
                [permission],
                cash_world.actors["administrator"],
            )
        assert error.value.code == "financial_access_denied"


def test_http_database_failure_never_exposes_sql_or_parameters(
    cash_world: CashWorld,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fail(
        conn: Any, cursor: Any, statement: str, parameters: Any, context: Any, executemany: bool
    ) -> None:
        if statement.startswith("INSERT INTO financial_access_grants "):
            raise sa.exc.IntegrityError(statement, parameters, Exception("sensitive-db-detail"))

    sa.event.listen(cash_world.engine, "before_cursor_execute", fail)
    try:
        response = cash_world.client.post(
            "/api/v2/financial-access/grants",
            json=grant_payload(cash_world, reason="sensitive-reason"),
            headers=cash_world.headers("owner", key="sensitive-key"),
        )
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", fail)
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "financial_access_unavailable"
    for secret in ("INSERT", "sensitive-db-detail", "sensitive-key", "sensitive-reason"):
        assert secret not in response.text and secret not in caplog.text
