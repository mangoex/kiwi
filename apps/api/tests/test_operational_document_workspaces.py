"""Direct document commands must keep the current actor workspace through commit."""

from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import expenses, models
from restaurant_os import operations as ops
from restaurant_os.config import get_settings
from test_branch_scope_selection import _grant_selection
from test_corporate_purchases import SECOND_BRANCH_ID
from test_operational_intents import _grant_permission
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _test_session_factory
from test_purchase_workspace import _presentation, _purchase_payload, _workspace


@pytest.fixture
def documents(monkeypatch):
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "false")
    get_settings.cache_clear()
    client, headers, suppliers = _workspace()
    factory = _test_session_factory(client)
    with factory() as session:
        for code in ("expense.concept.manage", "expenses.manage", "expenses.cancel"):
            _grant_permission(session, code)
        _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
        original = dict(
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        session.execute(
            models.branches.insert().values(
                **{**original, "id": SECOND_BRANCH_ID, "code": "QA-DOCUMENT-B", "name": "QA B"}
            )
        )
        concept = expenses.command(
            session,
            ADMIN_USER_ID,
            "concept.create",
            None,
            {"code": "QA-WORKSPACE", "name": "Synthetic", "description": "Synthetic"},
            "document-fixture-concept",
        )
    presentation = client.post(
        "/api/v1/purchase-presentations", headers=headers, json=_presentation(suppliers[0])
    )
    assert presentation.status_code == 200, presentation.text
    purchase_body = _purchase_payload(suppliers[0], presentation.json()["id"])
    expense_body = {
        "branch_id": BRANCH_ID,
        "concept_id": concept["id"],
        "document_date": "2026-10-14",
        "total_cents": 25000,
        "tax_cents": None,
        "payment_method": "transfer",
        "reference": "QA-DOCUMENT",
        "notes": "",
        "evidence_refs": [],
    }
    with factory() as session:
        purchase = ops.create_purchase_document(
            session, purchase_body, ADMIN_USER_ID, "document-fixture-purchase"
        )
        expense = expenses.command(
            session,
            ADMIN_USER_ID,
            "document.create",
            None,
            expense_body,
            "document-fixture-expense",
        )
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    selected = client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": "document-fixture-select"},
        json={"target_branch_id": BRANCH_ID, "expected_authorization_version": 1},
    )
    assert selected.status_code == 200, selected.text
    yield client, factory, headers, selected.json(), purchase, purchase_body, expense, expense_body
    get_settings.cache_clear()


def _request(case, operation):
    _, _, _, _, purchase, purchase_body, expense, expense_body = case
    if operation == "purchase.create":
        return "POST", "/purchases", {**purchase_body, "folio": "QA-NEW-DOCUMENT"}
    if operation == "purchase.confirm":
        return "POST", f"/purchases/{purchase['id']}/confirm", {}
    if operation.startswith("purchase."):
        return (
            "POST",
            f"/purchases/{purchase['id']}/{operation.split('.')[1]}",
            {"reason": "Synthetic correction"},
        )
    if operation == "expense.create":
        return "POST", "/expenses", {**expense_body, "reference": "QA-NEW-EXPENSE"}
    if operation == "expense.edit":
        return (
            "PATCH",
            f"/expenses/{expense['id']}",
            {**expense_body, "version": expense["version"], "notes": "Synthetic edit"},
        )
    if operation == "expense.resolve":
        return (
            "POST",
            "/expense-commands/document-resolve-001/resolve",
            {"kind": "document.create", "target_id": None, "branch_id": BRANCH_ID},
        )
    return (
        "POST",
        f"/expenses/{expense['id']}/{operation.split('.')[1]}",
        {
            "branch_id": BRANCH_ID,
            "version": expense["version"],
            **({"reason": "Synthetic correction"} if operation == "expense.cancel" else {}),
        },
    )


def _state(factory):
    with factory() as session:
        return {
            table.name: {
                tuple(str(row[column.name]) for column in table.primary_key): dict(row)
                for row in session.execute(sa.select(table)).mappings()
            }
            for table in (
                models.purchase_documents,
                models.purchase_document_lines,
                models.purchase_create_commands,
                models.expense_documents,
                models.expense_commands,
                models.inventory_movements,
                models.inventory_cost_states,
                models.cash_movements,
                models.branch_workspace_sessions,
                models.audit_events,
            )
        }


@pytest.mark.parametrize(
    "operation",
    [
        "purchase.create",
        "purchase.confirm",
        "purchase.cancel",
        "expense.create",
        "expense.edit",
        "expense.confirm",
        "expense.cancel",
        "expense.resolve",
    ],
)
def test_document_writes_without_workspace_do_not_reach_effects(documents, operation):
    client, factory, headers, *_ = documents
    method, path, body = _request(documents, operation)
    before = _state(factory)
    response = client.request(
        method,
        "/api/v1" + path,
        headers={**headers, "Idempotency-Key": "document-command-without-context"},
        json=body,
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "branch_context_required"
    after = _state(factory)
    previous_audits = before.pop("audit_events")
    current_audits = after.pop("audit_events")
    assert after == before
    assert {key: current_audits[key] for key in previous_audits} == previous_audits
    added = [row for key, row in current_audits.items() if key not in previous_audits]
    assert len(added) == 1 and added[0]["action"] == "authorization.denied"


@pytest.mark.parametrize("operation", ["purchase.confirm", "expense.confirm"])
@pytest.mark.parametrize("failure", ["superseded", "cross_branch", "version", "recovery_only"])
def test_document_resource_uses_its_own_branch_and_current_authority(documents, operation, failure):
    client, factory, headers, profile, *_ = documents
    secret = profile["branch_workspace_context"]
    if failure == "superseded":
        refreshed = client.post(
            "/api/v1/auth/branch-context-reissues",
            headers={**headers, "Idempotency-Key": "document-context-rotate"},
            json={
                "context_id": profile["branch_workspace_context_id"],
                "expected_authorization_version": 1,
            },
        )
        assert refreshed.status_code == 200, refreshed.text
    elif failure == "cross_branch":
        changed = client.post(
            "/api/v1/auth/branch-selections",
            headers={**headers, "Idempotency-Key": "document-context-switch"},
            json={"target_branch_id": SECOND_BRANCH_ID, "expected_authorization_version": 1},
        )
        assert changed.status_code == 200, changed.text
        secret = changed.json()["branch_workspace_context"]
    else:
        with factory() as session:
            if failure == "version":
                session.execute(
                    models.users.update()
                    .where(models.users.c.id == ADMIN_USER_ID)
                    .values(authorization_version=2)
                )
            else:
                session.execute(
                    models.branch_workspace_sessions.update()
                    .where(
                        models.branch_workspace_sessions.c.id
                        == profile["branch_workspace_context_id"]
                    )
                    .values(state="recovery_only")
                )
            session.commit()
    method, path, body = _request(documents, operation)
    before = _state(factory)
    response = client.request(
        method,
        "/api/v1" + path,
        headers={**headers, "X-Branch-Context": secret, "Idempotency-Key": str(uuid4())},
        json=body,
    )
    assert response.status_code == 403, response.text
    assert (
        response.json()["detail"]["code"]
        == {
            "superseded": "branch_context_superseded",
            "cross_branch": "branch_context_mismatch",
            "version": "authorization_version_conflict",
            "recovery_only": "branch_context_recovery_only",
        }[failure]
    )
    after = _state(factory)
    before.pop("audit_events")
    after.pop("audit_events")
    assert after == before


@pytest.mark.parametrize(
    "operation",
    [
        "purchase.create",
        "purchase.confirm",
        "purchase.cancel",
        "expense.create",
        "expense.edit",
        "expense.confirm",
        "expense.cancel",
        "expense.resolve",
    ],
)
def test_authorized_document_write_and_replay_keep_one_effect(documents, operation):
    client, factory, headers, profile, *_ = documents
    method, path, body = _request(documents, operation)
    scoped = {
        **headers,
        "X-Branch-Context": profile["branch_workspace_context"],
        "Idempotency-Key": "document-authorized-command",
    }
    before = _state(factory)
    created = client.request(method, "/api/v1" + path, headers=scoped, json=body)
    assert created.status_code == 200, created.text
    applied = _state(factory)
    assert applied != before
    replay = client.request(method, "/api/v1" + path, headers=scoped, json=body)
    assert replay.status_code == 200 and replay.json() == created.json(), replay.text
    assert _state(factory) == applied


def test_expense_body_never_moves_the_persisted_document_branch(documents):
    client, factory, headers, profile, _, _, expense, expense_body = documents
    before = _state(factory)
    changed = client.patch(
        f"/api/v1/expenses/{expense['id']}",
        headers={
            **headers,
            "X-Branch-Context": profile["branch_workspace_context"],
            "Idempotency-Key": "document-body-branch-override",
        },
        json={**expense_body, "version": expense["version"], "branch_id": SECOND_BRANCH_ID},
    )
    assert (
        changed.status_code == 409 and changed.json()["detail"]["code"] == "expense_scope_mismatch"
    )
    assert _state(factory) == before


def test_expense_resolution_cannot_mask_existing_document_as_global_concept(documents):
    client, factory, headers, profile, _, _, expense, _ = documents
    changed = client.post(
        "/api/v1/auth/branch-selections",
        headers={**headers, "Idempotency-Key": "document-resolution-switch"},
        json={"target_branch_id": SECOND_BRANCH_ID, "expected_authorization_version": 1},
    )
    assert changed.status_code == 200, changed.text
    before = _state(factory)
    spoof = client.post(
        "/api/v1/expense-commands/document-fixture-expense/resolve",
        headers={**headers, "X-Branch-Context": changed.json()["branch_workspace_context"]},
        json={"kind": "concept.create", "target_id": expense["id"], "branch_id": None},
    )
    assert spoof.status_code == 403 and spoof.json()["detail"]["code"] == "branch_context_mismatch"
    after = _state(factory)
    before.pop("audit_events")
    after.pop("audit_events")
    assert after == before


def test_global_expense_concept_resolution_does_not_require_operational_workspace(documents):
    client, factory, headers, *_ = documents
    before = _state(factory)
    result = client.post(
        "/api/v1/expense-commands/document-fixture-concept/resolve",
        headers=headers,
        json={"kind": "concept.create", "target_id": None, "branch_id": None},
    )
    assert result.status_code == 200, result.text
    assert result.json()["code"] == "QA-WORKSPACE"
    assert _state(factory) == before


@pytest.mark.parametrize("operation", ["purchase.create", "expense.create"])
def test_non_pos_document_writer_can_acquire_required_context(documents, operation):
    client, factory, headers, profile, *_ = documents
    with factory() as session:
        session.execute(
            models.role_authority_grants.update()
            .where(models.role_authority_grants.c.role_id == ADMIN_ROLE_ID)
            .values(authority_kind="organization_branch_workspaces")
        )
        session.execute(
            models.roles.update().where(models.roles.c.id == ADMIN_ROLE_ID).values(scope="branch")
        )
        session.execute(
            models.user_roles.update()
            .where(
                models.user_roles.c.user_id == ADMIN_USER_ID,
                models.user_roles.c.role_id == ADMIN_ROLE_ID,
            )
            .values(branch_id=profile["active_branch"]["id"])
        )
        no_workspace_codes = {
            "pos.operate",
            "invoicing.read",
            "invoicing.issue",
            "invoicing.cancel",
            "invoicing.receipt.create",
        }
        permission_ids = sa.select(models.permissions.c.id).where(
            models.permissions.c.code.in_(no_workspace_codes)
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == ADMIN_ROLE_ID,
                models.role_permissions.c.permission_id.in_(permission_ids),
            )
        )
        code = "purchases.manage" if operation.startswith("purchase.") else "expenses.manage"
        ops.require_permission(session, ADMIN_USER_ID, code, profile["active_branch"]["id"])
        session.commit()
    # The stock browser does exactly this: it clears the secret for a document-only profile.
    session_response = client.get("/api/v1/auth/session", headers=headers)
    assert session_response.status_code == 200, session_response.text
    assert session_response.json()["admin_capabilities"][code]
    reissued = client.post(
        "/api/v1/auth/branch-context-reissues",
        headers={**headers, "Idempotency-Key": "sol-document-only-context-001"},
        json={
            "context_id": profile["branch_workspace_context_id"],
            "expected_authorization_version": 1,
        },
    )
    assert reissued.status_code == 200, reissued.text
    method, path, body = _request(documents, operation)
    written = client.request(
        method,
        "/api/v1" + path,
        headers={
            **headers,
            "X-Branch-Context": reissued.json()["branch_workspace_context"],
            "Idempotency-Key": "document-only-authorized-001",
        },
        json=body,
    )
    assert written.status_code == 200, written.text
    new_profile = reissued.json()
    assert new_profile["active_branch"]["id"] == profile["active_branch"]["id"]
    assert not new_profile["admin_capabilities"]["pos.operate"]
