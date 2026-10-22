"""Real movement receipts retain idempotency, rollback and ledger snapshots in PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from typing import Any

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_cash_concepts import _concept_payload
from test_cash_ledger import _movement_payload
from test_corte_ciego_f106_intent_postgres import intent_pg
from test_platform_api import ADMIN_USER_ID, BRANCH_ID

__all__ = ["intent_pg"]


def setup(engine: sa.Engine) -> dict[str, Any]:
    with Session(engine) as session:
        ops.open_cash_shift_idempotently(
            session,
            BRANCH_ID,
            "CAJA-01",
            10000,
            "f106-movement-pg-shift",
            ADMIN_USER_ID,
        )
        concept = ops.create_cash_concept(
            session,
            _concept_payload(),
            "f106-movement-pg-concept",
            ADMIN_USER_ID,
        )
    return _movement_payload(concept["id"])


def test_simultaneous_human_commands_have_one_effect_and_closed_receipts(
    intent_pg: tuple[sa.Engine, str],
) -> None:
    engine, _ = intent_pg
    payload = setup(engine)
    ready = Barrier(2)

    def create() -> dict[str, Any]:
        with Session(engine) as session:
            ready.wait(10)
            return ops.create_cash_movement(
                session, payload, "f106-duplicate-movement", ADMIN_USER_ID
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(create) for _ in range(2)]
        results = [future.result(20) for future in futures]
    assert {r["replay"] for r in results} == {False, True}
    assert len({r["resource_id"] for r in results}) == 1
    assert all(r["projection"] == "operational" and "summary_at_commit" not in r for r in results)
    with Session(engine) as session:
        assert session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements)) == 1
        stored = session.scalar(sa.select(models.cash_movement_commands.c.result))
        assert stored["movement"]["amount_cents"] == 2000
        assert stored["summary_at_commit"]["expected_cash_cents"] == 8000


def test_outer_rollback_retains_ownership_of_effect_command_and_receipt(
    intent_pg: tuple[sa.Engine, str],
) -> None:
    engine, _ = intent_pg
    payload = setup(engine)
    with Session(engine) as session:
        receipt = ops.create_cash_movement(
            session,
            payload,
            "f106-outer-movement",
            ADMIN_USER_ID,
            commit=False,
        )
        assert receipt["projection"] == "operational"
        session.rollback()
    with Session(engine) as session:
        for table in (models.cash_movements, models.cash_movement_commands):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action.in_(
                        ("cash_movement.created", "cash_movement.receipt_read")
                    )
                )
            )
            == 0
        )


def test_receipt_audit_failure_rolls_back_real_movement(
    intent_pg: tuple[sa.Engine, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine, _ = intent_pg
    payload = setup(engine)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "cash_movement.receipt_read":
            raise sa.exc.SQLAlchemyError("SYNTHETIC-RECEIPT-FAILURE")
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    with Session(engine) as session:
        with pytest.raises(sa.exc.SQLAlchemyError):
            ops.create_cash_movement(session, payload, "f106-failed-movement", ADMIN_USER_ID)
    with Session(engine) as session:
        for table in (models.cash_movements, models.cash_movement_commands):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == 0
