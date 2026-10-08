"""R3 gates: real PostgreSQL transactions, row locks and rollback. Local test DB only."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import expenses, models
from restaurant_os.operations import BusinessError, _now
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, ORG_ID, OWNER_ID, OWNER_ROLE_ID, _seed_cash_concept_scope


@pytest.fixture(scope="module")
def database():
    url = os.environ.get("EXP001_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("EXP001_TEST_POSTGRES_URL is required")
    parsed = sa.engine.make_url(url)
    assert parsed.host in {"localhost", "127.0.0.1"} and parsed.database.startswith("exp001_")
    schema = "expense_test_" + uuid4().hex
    root = sa.create_engine(url)
    with root.begin() as connection:
        connection.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        # Build this module's real tables and all transitive FK parents; unrelated
        # inventory/modifier schemas do not participate in the expense transaction.
        needed = {
            models.expense_concepts,
            models.expense_documents,
            models.expense_commands,
            models.cash_shifts,
            models.cash_movements,
            models.audit_events,
            models.role_permissions,
            models.user_roles,
            models.role_authority_grants,
        }
        pending = list(needed)
        while pending:
            for foreign_key in pending.pop().foreign_keys:
                parent = foreign_key.column.table
                if parent not in needed:
                    needed.add(parent)
                    pending.append(parent)
        models.metadata.create_all(engine, tables=list(needed))
        with Session(engine) as session:
            _seed_cash_concept_scope(session)
            for code in (
                "expense.concept.read",
                "expense.concept.manage",
                "expenses.read",
                "expenses.manage",
                "expenses.cancel",
                "cash.movement.withdraw",
                "cash.movement.compensate",
                "reports.expenses.read",
            ):
                identifier = str(uuid4())
                session.execute(
                    models.permissions.insert().values(
                        id=identifier, code=code, description=code, created_at=_now()
                    )
                )
                session.execute(
                    models.role_permissions.insert().values(
                        role_id=OWNER_ROLE_ID, permission_id=identifier
                    )
                )
            session.execute(
                models.cash_shifts.insert().values(
                    id="expense-shift",
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    register_code="CAJA-01",
                    cashier_user_id=OWNER_ID,
                    opening_cash_cents=200000,
                    status="OPEN",
                    opened_at=_now(),
                    created_at=_now(),
                )
            )
            session.commit()
        yield engine
    finally:
        engine.dispose()
        with root.begin() as connection:
            connection.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
        root.dispose()


def run(database, kind, target, body, key=None):
    with Session(database) as session:
        return expenses.command(session, OWNER_ID, kind, target, body, key or str(uuid4()))


def make_draft(database):
    concept = run(
        database, "concept.create", None, {"code": uuid4().hex, "name": "Luz", "description": ""}
    )
    return run(
        database,
        "document.create",
        None,
        {
            "branch_id": BRANCH_A,
            "concept_id": concept["id"],
            "document_date": "2026-10-08",
            "total_cents": 30000,
            "tax_cents": None,
            "payment_method": "cash",
            "reference": "PG receipt",
            "notes": "",
            "evidence_refs": ["archivo:pg-recibo"],
        },
    )


def confirm_body(doc):
    return {
        "branch_id": BRANCH_A,
        "version": doc["version"],
        "register_id": "CAJA-01",
        "expected_cash_shift_id": "expense-shift",
    }


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_confirm_is_one_withdrawal(database, same_key):
    doc = make_draft(database)
    gate = Barrier(2)
    shared_key = str(uuid4())

    def confirm():
        gate.wait(timeout=10)
        try:
            return run(
                database,
                "document.confirm",
                doc["id"],
                confirm_body(doc),
                shared_key if same_key else None,
            )
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(lambda _: confirm(), range(2)))
    assert sum(isinstance(a, dict) for a in answers) == (2 if same_key else 1)
    if same_key:
        assert answers[0] == answers[1]
    with Session(database) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.cash_movements)
                .where(models.cash_movements.c.source_id == doc["id"])
            )
            == 1
        )


def test_pg_audit_failure_rolls_back_cash_document_and_receipt(database, monkeypatch):
    doc = make_draft(database)
    key = str(uuid4())

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure after ledger insert")

    monkeypatch.setattr(expenses, "_audit", fail)
    with pytest.raises(RuntimeError, match="injected audit"):
        run(database, "document.confirm", doc["id"], confirm_body(doc), key)
    with Session(database) as session:
        assert (
            session.scalar(
                sa.select(models.expense_documents.c.status).where(
                    models.expense_documents.c.id == doc["id"]
                )
            )
            == "draft"
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.cash_movements)
                .where(models.cash_movements.c.source_id == doc["id"])
            )
            == 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.expense_commands)
                .where(models.expense_commands.c.idempotency_key == key)
            )
            == 0
        )


def test_confirm_waits_for_shared_close_lock_and_rejects_closed_shift(database):
    doc = make_draft(database)
    started = Event()
    with Session(database) as closer, ThreadPoolExecutor(max_workers=1) as pool:
        closer.execute(
            sa.select(models.cash_shifts)
            .where(models.cash_shifts.c.id == "expense-shift")
            .with_for_update()
        ).one()

        def confirm():
            started.set()
            return run(database, "document.confirm", doc["id"], confirm_body(doc))

        future = pool.submit(confirm)
        assert started.wait(5)
        closer.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == "expense-shift")
            .values(status="CLOSED", closed_at=_now())
        )
        closer.commit()
        with pytest.raises(BusinessError):
            future.result(timeout=15)
    with Session(database) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.cash_movements)
                .where(models.cash_movements.c.source_id == doc["id"])
            )
            == 0
        )
        session.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == "expense-shift")
            .values(status="OPEN", closed_at=None)
        )
        session.commit()


def test_concurrent_cancel_is_one_refund_and_summary_nets_zero(database):
    doc = make_draft(database)
    confirmed = run(database, "document.confirm", doc["id"], confirm_body(doc))
    gate = Barrier(2)

    def cancel():
        gate.wait(timeout=10)
        try:
            return run(
                database,
                "document.cancel",
                doc["id"],
                {
                    "branch_id": BRANCH_A,
                    "version": confirmed["version"],
                    "reason": "Devolución real",
                    "cash_returned": True,
                    "evidence_refs": ["archivo:devolucion"],
                },
            )
        except BusinessError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        answers = list(pool.map(lambda _: cancel(), range(2)))
    assert sum(isinstance(a, dict) for a in answers) == 1
    with Session(database) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.cash_movements)
                .where(models.cash_movements.c.source_id == doc["id"])
            )
            == 2
        )
        report = expenses.summary(
            session,
            OWNER_ID,
            {
                "branch_id": BRANCH_A,
                "from_utc": _now() - timedelta(days=1),
                "to_utc": _now() + timedelta(days=1),
                "concept_id": doc["concept_id"],
            },
        )
        assert report["confirmed_cents"] == report["reversed_cents"] == 30000
        assert report["net_cents"] == 0
