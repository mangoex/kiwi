"""Real PostgreSQL expense acknowledgements preserve one effect and terminal fences."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from corte_ciego_storage import isolated_database
from fixture_metadata import create_fixture_tables
from restaurant_os import expenses, models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session, sessionmaker
from test_cash_concepts import BRANCH_A, OWNER_ID, OWNER_ROLE_ID, _seed_cash_concept_scope
from test_cash_ledger import SHIFT_ID, _insert_shift
from test_corte_ciego_f106_movements import activate


@pytest.fixture
def expense_pg() -> Iterator[tuple[sa.Engine, dict[str, Any]]]:
    for engine in isolated_database("postgresql"):
        create_fixture_tables(engine)
        with Session(engine) as session:
            _seed_cash_concept_scope(session)
            _insert_shift(session)
            for code in (
                "expense.concept.manage",
                "expenses.read",
                "expenses.manage",
                "expenses.cancel",
                "cash.movement.withdraw",
                "cash.movement.compensate",
            ):
                grant_permission(session, OWNER_ROLE_ID, code)
            session.commit()
            concept = expenses.command(
                session,
                OWNER_ID,
                "concept.create",
                None,
                {"code": "PGEXP", "name": "Service", "description": ""},
                "pg-expense-concept",
            )
            doc = expenses.command(
                session,
                OWNER_ID,
                "document.create",
                None,
                {
                    "branch_id": BRANCH_A,
                    "concept_id": concept["id"],
                    "document_date": "2026-10-22",
                    "total_cents": 30000,
                    "tax_cents": None,
                    "payment_method": "cash",
                    "reference": "PG receipt",
                    "notes": "",
                    "evidence_refs": ["file:expense"],
                },
                "pg-expense-create",
            )
        activate(sessionmaker(bind=engine))
        yield engine, doc


def confirm(session: Session, identifier: str, key: str) -> dict[str, Any]:
    return expenses.command(
        session,
        OWNER_ID,
        "document.confirm",
        identifier,
        {
            "branch_id": BRANCH_A,
            "version": 1,
            "register_id": "CAJA-01",
            "expected_cash_shift_id": SHIFT_ID,
        },
        key,
    )


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_confirmations_withdraw_once(
    expense_pg: tuple[sa.Engine, dict[str, Any]], same_key: bool
) -> None:
    engine, doc = expense_pg
    barrier = Barrier(2)

    def run(index: int) -> tuple[str, Any]:
        with Session(engine) as session:
            barrier.wait(10)
            try:
                return "ok", confirm(
                    session, doc["id"], f"pg-expense-confirm-{0 if same_key else index}"
                )
            except ops.BusinessError as exc:
                session.rollback()
                return "denied", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (0, 1)))
    receipts = [value for status, value in results if status == "ok"]
    assert len(receipts) == (2 if same_key else 1)
    assert all(value["status"] == "confirmed" and "total_cents" not in value for value in receipts)
    if same_key:
        assert receipts[0] == receipts[1]
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        assert session.scalar(sa.select(models.cash_movements.c.amount_cents)) == 30000
        original = session.scalar(
            sa.select(models.expense_commands.c.result).where(
                models.expense_commands.c.command_type == "document.confirm"
            )
        )
        assert original["total_cents"] == 30000


def test_abandon_and_confirm_are_one_terminal_result(
    expense_pg: tuple[sa.Engine, dict[str, Any]],
) -> None:
    engine, doc = expense_pg
    barrier = Barrier(2)
    key = "pg-expense-resolve-race"

    def run(resolve: bool) -> tuple[str, Any]:
        with Session(engine) as session:
            barrier.wait(10)
            try:
                value = (
                    expenses.resolve_command(
                        session,
                        OWNER_ID,
                        key,
                        {
                            "kind": "document.confirm",
                            "target_id": doc["id"],
                            "branch_id": BRANCH_A,
                        },
                    )
                    if resolve
                    else confirm(session, doc["id"], key)
                )
                return "ok", value
            except ops.BusinessError as exc:
                session.rollback()
                return "denied", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, (True, False)))
    with Session(engine) as session:
        receipt = expenses.recover_command(session, OWNER_ID, key)
        assert receipt["status"] in {"confirmed", "abandoned"}
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == (
            1 if receipt["status"] == "confirmed" else 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.expense_commands)
                .where(models.expense_commands.c.idempotency_key == key)
            )
            == 1
        )
    for status, value in results:
        assert (status == "ok" and value == receipt) or (
            status == "denied" and value == "idempotency_key_conflict"
        )


def test_receipt_audit_failure_rolls_back_cash(
    expense_pg: tuple[sa.Engine, dict[str, Any]], monkeypatch: pytest.MonkeyPatch
) -> None:
    engine, doc = expense_pg
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "expense.receipt_read":
            raise sa.exc.SQLAlchemyError("synthetic receipt failure")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with Session(engine) as session, pytest.raises(sa.exc.SQLAlchemyError):
        confirm(session, doc["id"], "pg-expense-audit-failure")
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 0
        assert session.scalar(sa.select(models.expense_documents.c.status)) == "draft"


def test_own_draft_and_metadata_do_not_need_financial_grant(
    expense_pg: tuple[sa.Engine, dict[str, Any]],
) -> None:
    engine, doc = expense_pg
    with Session(engine) as session:
        value = expenses.get_document(session, OWNER_ID, doc["id"], expected_version=1)
        assert value["projection"] == "own_operation" and value["total_cents"] == 30000
        page = expenses.documents(session, OWNER_ID, BRANCH_A, operational=True)
        assert page["items"][0]["id"] == doc["id"] and "total_cents" not in str(page)
