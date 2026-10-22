"""Expenses preserve individual commands without exposing historical financial reads."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, ORG_ID, OWNER_ID, OWNER_ROLE_ID
from test_corte_ciego_f106_movements import activate
from test_operating_expenses import command, draft, setup_expenses

KEY = "f106-expense-confirm"


@dataclass
class ExpenseWorld:
    client: Any
    factory: Any
    headers: dict[str, str]
    doc: dict[str, Any]

    def confirm(self, key: str = KEY) -> Any:
        return command(
            self.client,
            self.headers,
            f"/expenses/{self.doc['id']}/confirm",
            {
                "branch_id": BRANCH_A,
                "version": 1,
                "register_id": "CAJA-01",
                "expected_cash_shift_id": "expense-shift",
            },
            key=key,
        )

    def revoke(self, code: str) -> None:
        with self.factory() as session:
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            )
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == OWNER_ROLE_ID,
                    models.role_permissions.c.permission_id == permission,
                )
            )
            session.execute(
                models.role_authority_grants.delete().where(
                    models.role_authority_grants.c.role_id == OWNER_ROLE_ID
                )
            )
            session.commit()


@pytest.fixture
def expense_world() -> Iterator[ExpenseWorld]:
    client, headers = setup_expenses()
    try:
        yield ExpenseWorld(
            client, client.app.state.test_session_factory, headers, draft(client, headers)
        )
    finally:
        client.close()


def test_history_and_summary_need_financial_authority(expense_world: ExpenseWorld) -> None:
    world = expense_world
    assert world.confirm().status_code == 200
    activate(world.factory)
    for path, params in (
        ("/expenses", {"branch_id": BRANCH_A}),
        (f"/expenses/{world.doc['id']}", {}),
        (
            "/expenses/summary",
            {"branch_id": BRANCH_A, "from_date": "2026-01-01", "to_date": "2027-01-01"},
        ),
    ):
        response = world.client.get("/api/v1" + path, headers=world.headers, params=params)
        assert response.status_code == 403 and "30000" not in response.text, response.text


def test_confirm_receipt_and_recovery_do_not_return_money(expense_world: ExpenseWorld) -> None:
    world = expense_world
    activate(world.factory)
    result = world.confirm()
    assert result.status_code == 200 and "total_cents" not in result.json(), result.text
    assert result.json()["status"] == "confirmed" and result.json()["version"] == 2
    assert result.json()["projection"] == "operational"
    assert result.headers["cache-control"] == "no-store"
    world.revoke("expenses.manage")
    assert world.confirm().json() == result.json()
    recovered = world.client.get(f"/api/v1/expense-commands/{KEY}", headers=world.headers)
    assert recovered.status_code == 200 and recovered.json() == result.json(), recovered.text
    world.revoke("expenses.read")
    assert (
        world.client.get(f"/api/v1/expense-commands/{KEY}", headers=world.headers).status_code
        == 403
    )
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        assert session.scalar(sa.select(models.cash_movements.c.amount_cents)) == 30000
        assert (
            session.scalar(
                sa.select(models.expense_commands.c.result).where(
                    models.expense_commands.c.idempotency_key == KEY
                )
            )["total_cents"]
            == 30000
        )


def test_cash_context_does_not_select_money(expense_world: ExpenseWorld) -> None:
    world = expense_world
    activate(world.factory)
    statements: list[str] = []

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT") and "cash_shifts" in sql:
            statements.append(sql)

    engine = world.factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        response = world.client.get(
            "/api/v1/expenses/cash-context", headers=world.headers, params={"branch_id": BRANCH_A}
        )
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert (
        response.status_code == 200
        and response.json()["open_registers"][0]["cash_shift_id"] == "expense-shift"
    )
    assert statements and not any("_cents" in sql or "closure" in sql for sql in statements)


def body_from(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        key: doc[key]
        for key in (
            "branch_id",
            "concept_id",
            "document_date",
            "total_cents",
            "tax_cents",
            "payment_method",
            "reference",
            "notes",
            "evidence_refs",
        )
    }


def test_own_draft_needs_current_version_and_history_stays_financial(
    expense_world: ExpenseWorld,
) -> None:
    world = expense_world
    activate(world.factory)
    path = f"/api/v1/expenses/{world.doc['id']}"
    own = world.client.get(path, headers=world.headers, params={"expected_version": 1})
    assert own.status_code == 200 and own.json()["total_cents"] == 30000, own.text
    assert own.json()["projection"] == "own_operation"
    assert world.client.get(path, headers=world.headers).status_code == 403
    assert (
        world.client.get(path, headers=world.headers, params={"expected_version": 2}).status_code
        == 403
    )
    assert world.confirm().status_code == 200
    assert (
        world.client.get(path, headers=world.headers, params={"expected_version": 2}).status_code
        == 403
    )
    with world.factory() as session:
        session.execute(
            models.financial_owner_reviews.insert().values(
                organization_id=ORG_ID,
                user_id=OWNER_ID,
                authorization_version=1,
                manifest_digest="a" * 64,
                approval_reference="Synthetic expense Owner",
                reviewed_at=ops._now(),
            )
        )
        session.commit()
    history = world.client.get(path, headers=world.headers)
    assert history.status_code == 200 and history.json()["total_cents"] == 30000, history.text
    listing = world.client.get(
        "/api/v1/expenses", headers=world.headers, params={"branch_id": BRANCH_A}
    )
    assert listing.status_code == 200 and listing.json()["items"][0]["total_cents"] == 30000


def test_operational_page_and_creation_edit_receipts_are_closed(
    expense_world: ExpenseWorld,
) -> None:
    world = expense_world
    activate(world.factory)
    body = body_from(world.doc)
    create = command(world.client, world.headers, "/expenses", body, key="f106-expense-create")
    assert create.status_code == 200 and "total_cents" not in create.json(), create.text
    identifier = create.json()["id"]
    edit = command(
        world.client,
        world.headers,
        f"/expenses/{identifier}",
        {**body, "version": 1, "total_cents": 32000},
        key="f106-expense-edit",
        method="PATCH",
    )
    assert edit.status_code == 200 and "total_cents" not in edit.json(), edit.text
    detail = world.client.get(
        f"/api/v1/expenses/{identifier}", headers=world.headers, params={"expected_version": 2}
    )
    assert detail.status_code == 200 and detail.json()["total_cents"] == 32000, detail.text
    statements: list[str] = []

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT") and "expense_documents" in sql:
            statements.append(sql)

    engine = world.factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        params: dict[str, Any] = {"branch_id": BRANCH_A, "limit": 1}
        first = world.client.get("/api/v2/expenses", headers=world.headers, params=params)
        assert first.status_code == 200 and "total_cents" not in first.text, first.text
        params["cursor"] = first.json()["next_cursor"]
        second = world.client.get("/api/v2/expenses", headers=world.headers, params=params)
        assert (
            second.status_code == 200
            and second.json()["items"][0]["id"] != first.json()["items"][0]["id"]
        )
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert statements and not any(
        "_cents" in sql or "notes" in sql or "evidence_refs" in sql for sql in statements
    )


def test_cancel_receipt_preserves_compensation_and_originals(expense_world: ExpenseWorld) -> None:
    world = expense_world
    activate(world.factory)
    assert world.confirm().status_code == 200
    body = {
        "branch_id": BRANCH_A,
        "version": 2,
        "reason": "Synthetic return",
        "cash_returned": True,
        "evidence_refs": ["archivo:return"],
    }
    result = command(
        world.client,
        world.headers,
        f"/expenses/{world.doc['id']}/cancel",
        body,
        key="f106-expense-cancel",
    )
    assert result.status_code == 200 and "total_cents" not in result.json(), result.text
    assert result.json()["status"] == "cancelled"
    world.revoke("expenses.cancel")
    assert (
        command(
            world.client,
            world.headers,
            f"/expenses/{world.doc['id']}/cancel",
            body,
            key="f106-expense-cancel",
        ).json()
        == result.json()
    )
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 2
        assert session.scalar(sa.select(models.expense_documents.c.total_cents)) == 30000


def test_resolve_tombstone_and_recovery_cannot_change_identity(expense_world: ExpenseWorld) -> None:
    world = expense_world
    activate(world.factory)
    path = "/api/v1/expense-commands/f106-expense-abandoned/resolve"
    body = {"kind": "document.confirm", "target_id": world.doc["id"], "branch_id": BRANCH_A}
    result = world.client.post(path, headers=world.headers, json=body)
    assert result.status_code == 200 and result.json()["status"] == "abandoned", result.text
    assert world.confirm("f106-expense-abandoned").status_code == 409
    assert (
        world.client.post(
            path, headers=world.headers, json={**body, "kind": "document.cancel"}
        ).status_code
        == 409
    )
    assert (
        world.client.post(
            path,
            headers=world.headers,
            json={**body, "kind": "concept.create", "target_id": None, "branch_id": None},
        ).status_code
        == 409
    )
    world.revoke("expenses.manage")
    assert world.client.post(path, headers=world.headers, json=body).json() == result.json()
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_receipt_audit_failure_rolls_back_confirm(
    expense_world: ExpenseWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = expense_world
    activate(world.factory)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "expense.receipt_read":
            raise sa.exc.SQLAlchemyError("PRIVATE-EXPENSE-SQL")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = world.confirm()
    assert result.status_code == 503 and "PRIVATE-EXPENSE" not in result.text
    with world.factory() as session:
        assert session.scalar(sa.select(models.expense_documents.c.status)) == "draft"
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_revoked_after_confirm_cannot_receive_but_can_recover_later(
    expense_world: ExpenseWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = expense_world
    activate(world.factory)
    commit = Session.commit
    revoked = False

    def revoke(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            with world.factory() as other:
                other.execute(
                    models.users.update()
                    .where(models.users.c.id == OWNER_ID)
                    .values(status="inactive")
                )
                commit(other)

    monkeypatch.setattr(Session, "commit", revoke)
    result = world.confirm()
    assert revoked and result.status_code == 403, result.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        session.execute(
            models.users.update().where(models.users.c.id == OWNER_ID).values(status="active")
        )
        session.commit()
    assert (
        world.client.get(f"/api/v1/expense-commands/{KEY}", headers=world.headers).status_code
        == 200
    )


def test_recovery_never_selects_result_or_monetary_document(expense_world: ExpenseWorld) -> None:
    world = expense_world
    assert world.confirm().status_code == 200
    activate(world.factory)
    world.revoke("expenses.manage")
    statements: list[str] = []
    full_results: list[str] = []

    def observe(
        _conn: Any, _cursor: Any, sql: str, _params: Any, context: Any, *_args: Any
    ) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)
            statement = context.compiled.statement if context.compiled is not None else None
            if isinstance(statement, sa.sql.Select):
                full_results.extend(
                    column.name
                    for column in statement.selected_columns
                    if column is models.expense_commands.c.result
                )

    engine = world.factory.kw["bind"]
    sa.event.listen(engine, "before_cursor_execute", observe)
    try:
        result = world.client.get(f"/api/v1/expense-commands/{KEY}", headers=world.headers)
    finally:
        sa.event.remove(engine, "before_cursor_execute", observe)
    assert result.status_code == 200 and "total_cents" not in result.json(), result.text
    assert not full_results and not any("_cents" in sql for sql in statements)


def test_read_is_required_before_new_effect(expense_world: ExpenseWorld) -> None:
    world = expense_world
    activate(world.factory)
    world.revoke("expenses.read")
    assert world.confirm().status_code == 403
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


def test_other_actor_cannot_read_draft_or_recover_but_keeps_noncash_action(
    expense_world: ExpenseWorld,
) -> None:
    from test_cash_concepts import CASHIER_ID
    from test_operating_expenses import grant_cashier

    world = expense_world
    body = {**body_from(world.doc), "payment_method": "transfer"}
    created = command(world.client, world.headers, "/expenses", body, key="f106-expense-transfer")
    assert created.status_code == 200
    identifier = created.json()["id"]
    grant_cashier(world.client, "expenses.read", "expenses.manage")
    activate(world.factory)
    cashier = {"X-Actor-User-Id": CASHIER_ID}
    assert (
        world.client.get(
            f"/api/v1/expenses/{identifier}", headers=cashier, params={"expected_version": 1}
        ).status_code
        == 403
    )
    assert (
        world.client.get(
            "/api/v1/expense-commands/f106-expense-transfer", headers=cashier
        ).status_code
        == 403
    )
    confirmed = command(
        world.client,
        cashier,
        f"/expenses/{identifier}/confirm",
        {"branch_id": BRANCH_A, "version": 1},
        key="f106-expense-cashier-confirm",
    )
    assert confirmed.status_code == 200 and "total_cents" not in confirmed.json(), confirmed.text
    with world.factory() as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_expense_routes_reject_technical_identity(expense_world: ExpenseWorld, typ: str) -> None:
    from restaurant_os.auth import create_session_token
    from restaurant_os.config import get_settings

    world = expense_world
    activate(world.factory)
    token = create_session_token({"sub": OWNER_ID, "typ": typ}, get_settings().secret_key)
    headers = {"Authorization": f"Bearer {token}", "Idempotency-Key": KEY}
    for path, params in (
        ("/api/v1/expenses", {"branch_id": BRANCH_A}),
        ("/api/v2/expenses", {"branch_id": BRANCH_A}),
        (f"/api/v1/expenses/{world.doc['id']}", {"expected_version": 1}),
        ("/api/v1/expenses/cash-context", {"branch_id": BRANCH_A}),
        ("/api/v1/expenses/summary", {}),
        (f"/api/v1/expense-commands/{KEY}", {}),
    ):
        assert world.client.get(path, headers=headers, params=params).status_code == 403
    assert (
        world.client.post(
            f"/api/v1/expenses/{world.doc['id']}/confirm",
            headers=headers,
            json={"branch_id": BRANCH_A, "version": 1},
        ).status_code
        == 403
    )


def test_schemas_match_published_contracts() -> None:
    import json
    from pathlib import Path

    from restaurant_os.expense_views import (
        ExpenseCommandReceiptV2,
        ExpenseDraftV2,
        ExpenseOperationalPageV2,
    )

    for name, model in (
        ("expense-command-receipt-v2", ExpenseCommandReceiptV2),
        ("expense-operational-page-v2", ExpenseOperationalPageV2),
        ("expense-draft-v2", ExpenseDraftV2),
    ):
        schema = json.loads(
            (
                Path(__file__).resolve().parents[3]
                / f"packages/contracts/schemas/{name}.schema.json"
            ).read_text()
        )
        assert schema == model.model_json_schema()
        assert schema["additionalProperties"] is False


def test_expense_dataset_and_branch_are_exact_and_revocable(expense_world: ExpenseWorld) -> None:
    from corte_ciego_fixtures import grant_permission
    from restaurant_os.financial_access import FinancialAccessService
    from test_cash_concepts import BRANCH_B, CASHIER_ID, CASHIER_ROLE_ID

    world = expense_world
    assert world.confirm().status_code == 200
    activate(world.factory)
    with world.factory() as session:
        session.execute(
            models.financial_owner_reviews.insert().values(
                organization_id=ORG_ID,
                user_id=OWNER_ID,
                authorization_version=1,
                manifest_digest="b" * 64,
                approval_reference="Synthetic delegate review",
                reviewed_at=ops._now(),
            )
        )
        for code in ("financial.data.read", "expenses.read"):
            grant_permission(session, CASHIER_ROLE_ID, code)
        session.commit()
        service = FinancialAccessService(session, ORG_ID)
        service.issue(
            OWNER_ID,
            "f106-expense-wrong-scope",
            {
                "subject_user_id": CASHIER_ID,
                "reason": "Synthetic cross scopes",
                "scopes": [
                    {"branch_id": BRANCH_A, "dataset": "sales"},
                    {"branch_id": BRANCH_B, "dataset": "expenses"},
                ],
            },
        )
    headers = {"X-Actor-User-Id": CASHIER_ID}
    path = f"/api/v1/expenses/{world.doc['id']}"
    assert world.client.get(path, headers=headers).status_code == 403

    with world.factory() as session:
        granted = FinancialAccessService(session, ORG_ID).issue(
            OWNER_ID,
            "f106-expense-right-scope",
            {
                "subject_user_id": CASHIER_ID,
                "reason": "Synthetic exact scope",
                "scopes": [{"branch_id": BRANCH_A, "dataset": "expenses"}],
            },
        )
    allowed = world.client.get(path, headers=headers)
    assert allowed.status_code == 200 and allowed.json()["total_cents"] == 30000, allowed.text
    with world.factory() as session:
        FinancialAccessService(session, ORG_ID).revoke(
            OWNER_ID,
            granted["grant_id"],
            "f106-expense-revoke",
            {"reason": "Synthetic revoked scope"},
        )
    assert world.client.get(path, headers=headers).status_code == 403


def test_draft_changed_after_audit_commit_is_not_delivered(
    expense_world: ExpenseWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    from restaurant_os import expenses

    world = expense_world
    activate(world.factory)
    commit = Session.commit
    changed = False

    def edit_after_read(session: Session) -> None:
        nonlocal changed
        commit(session)
        if not changed:
            changed = True
            with world.factory() as other:
                expenses.command(
                    other,
                    OWNER_ID,
                    "document.edit",
                    world.doc["id"],
                    {
                        **body_from(world.doc),
                        "version": 1,
                        "total_cents": 31000,
                    },
                    "f106-expense-newer-version",
                )

    monkeypatch.setattr(Session, "commit", edit_after_read)
    result = world.client.get(
        f"/api/v1/expenses/{world.doc['id']}", headers=world.headers, params={"expected_version": 1}
    )
    assert changed and result.status_code == 403 and "30000" not in result.text, result.text
