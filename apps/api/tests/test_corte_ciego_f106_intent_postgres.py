"""Real PostgreSQL JSON references and exact compensation evidence for intent recovery."""

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
import sqlalchemy as sa
from corte_ciego_storage import isolated_database
from fixture_metadata import create_fixture_tables
from restaurant_os import models, operational_intents
from restaurant_os import operations as ops
from restaurant_os.branch_workspaces import reissue_branch_context
from restaurant_os.cash_command_views import shift_command
from restaurant_os.config import get_settings
from sqlalchemy.orm import Session, sessionmaker
from test_branch_scope_selection import _grant_selection
from test_cash_concepts import _concept_payload
from test_cash_ledger import _movement_payload
from test_corte_ciego_f105_intents import activate
from test_operational_intents import _grant_permission
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, BRANCH_ID, _seed


@pytest.fixture
def intent_pg(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[sa.Engine, str]]:
    monkeypatch.setenv("RESTAURANTOS_BRANCH_SCOPE_V2_ENABLED", "true")
    get_settings.cache_clear()
    try:
        for engine in isolated_database("postgresql"):
            create_fixture_tables(engine)
            with Session(engine) as session:
                _seed(session)
                for code in (
                    "cash.concept.manage",
                    "cash.concept.read",
                    "cash.movement.withdraw",
                    "cash.movement.compensate",
                ):
                    _grant_permission(session, code)
                _grant_selection(session, ADMIN_ROLE_ID, workspace=False)
                profile = reissue_branch_context(
                    session,
                    ADMIN_USER_ID,
                    {"context_id": None, "expected_authorization_version": 1},
                    "f106-pg-intent-workspace",
                )
            activate(sessionmaker(bind=engine))
            yield engine, profile["branch_workspace_context"]
    finally:
        get_settings.cache_clear()


def test_real_shift_intents_recover_json_references_without_full_results(
    intent_pg: tuple[sa.Engine, str],
) -> None:
    engine, context = intent_pg
    body = {"branch_id": BRANCH_ID, "register_id": "F106-PG", "opening_cash_cents": 1234}
    statements: list[str] = []
    with Session(engine) as session:
        intent = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "cash.shift.open", "target_id": None, "payload": body},
            "f106-pg-open",
            context,
        )
        result = shift_command(
            session,
            ADMIN_USER_ID,
            "open",
            None,
            body,
            "f106-pg-open",
            intent=intent["id"],
            context=context,
        )
        shift = result["resource_id"]
        assert result["projection"] == "operational"
        operational_intents.recover_intent(session, ADMIN_USER_ID, intent["id"])
        intent = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {"kind": "cash.shift.close", "target_id": shift, "payload": {}},
            "f106-pg-close",
            context,
        )
        result = shift_command(
            session,
            ADMIN_USER_ID,
            "close",
            shift,
            {},
            "f106-pg-close",
            intent=intent["id"],
            context=context,
        )
        assert result["status"] == "OPERATIVELY_CLOSED"

        def observe(_conn, _cursor, sql, *_args):
            if sql.lstrip().upper().startswith("SELECT"):
                statements.append(sql)

        sa.event.listen(engine, "before_cursor_execute", observe)
        try:
            receipt = operational_intents.recover_intent(session, ADMIN_USER_ID, intent["id"])
        finally:
            sa.event.remove(engine, "before_cursor_execute", observe)
        assert receipt["state"] == "acknowledged"
        assert set(receipt) == {"id", "kind", "branch_id", "state", "resource_id"}
        assert not any(
            "expected_cash_cents" in sql or "opening_cash_cents" in sql for sql in statements
        )
        command_sql = [sql for sql in statements if "FROM cash_shift_commands" in sql]
        assert command_sql and all("->>" in sql for sql in command_sql)
        assert session.scalar(
            sa.select(models.cash_shift_commands.c.result).where(
                models.cash_shift_commands.c.idempotency_key == "f106-pg-open"
            )
        ) == {"cash_shift_id": shift}
        assert (
            session.scalar(
                sa.select(models.cash_shifts.c.opening_cash_cents).where(
                    models.cash_shifts.c.id == shift
                )
            )
            == 1234
        )


def test_compensation_proof_preserves_exact_amount_and_links_in_sql(
    intent_pg: tuple[sa.Engine, str],
) -> None:
    engine, _ = intent_pg
    with Session(engine) as session:
        ops.open_cash_shift_idempotently(
            session, BRANCH_ID, "CAJA-01", 10000, "f106-pg-proof-shift", ADMIN_USER_ID
        )
        concept = ops.create_cash_concept(
            session, _concept_payload(), "f106-pg-proof-concept", ADMIN_USER_ID
        )
        movement_receipt = ops.create_cash_movement(
            session, _movement_payload(concept["id"]), "f106-pg-proof-movement", ADMIN_USER_ID
        )
        assert movement_receipt["projection"] == "operational"
        movement = (
            session.execute(
                sa.select(models.cash_movements).where(
                    models.cash_movements.c.id == movement_receipt["resource_id"]
                )
            )
            .mappings()
            .one()
        )
        compensation = ops.compensate_cash_movement(
            session,
            movement["id"],
            {
                "reason": "Synthetic correction",
                "evidence_refs": ["evidence://synthetic/correction"],
            },
            "f106-pg-proof-compensation",
            ADMIN_USER_ID,
        )
        assert compensation["projection"] == "operational"
        intent = {
            "organization_id": ops.ORGANIZATION_ID,
            "branch_id": BRANCH_ID,
            "actor_user_id": ADMIN_USER_ID,
            "kind": "cash.movement.compensate",
            "target_id": movement["id"],
            "idempotency_key": "f106-pg-proof-compensation",
            "state": "prepared",
        }
        proof = operational_intents._proof(session, intent)
        assert proof["resource_id"] == compensation["resource_id"]
        # Corrupt only disposable fixture data to refute each persisted invariant.
        for mutation in (
            {"amount_cents": movement["amount_cents"] + 1},
            {"movement_type": movement["movement_type"]},
            {"compensates_movement_id": None},
        ):
            nested = session.begin_nested()
            session.execute(
                models.cash_movements.update()
                .where(models.cash_movements.c.id == compensation["resource_id"])
                .values(**mutation)
            )
            with pytest.raises(ops.BusinessError) as error:
                operational_intents._proof(session, intent)
            assert error.value.code == "operational_command_evidence_conflict"
            nested.rollback()
        assert operational_intents._proof(session, intent) == proof


def test_concurrent_recovery_records_only_one_no_effect_transition(
    intent_pg: tuple[sa.Engine, str],
) -> None:
    engine, context = intent_pg
    with Session(engine) as session:
        intent = operational_intents.prepare_intent(
            session,
            ADMIN_USER_ID,
            {
                "kind": "cash.shift.open",
                "target_id": None,
                "payload": {
                    "branch_id": BRANCH_ID,
                    "register_id": "F106-RACE",
                    "opening_cash_cents": 500,
                },
            },
            "f106-concurrent-recover",
            context,
        )
    ready = Barrier(2)

    def recover() -> dict:
        with Session(engine) as session:
            ready.wait(10)
            return operational_intents.recover_intent(session, ADMIN_USER_ID, intent["id"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(recover) for _ in range(2)]
        results = [future.result(20) for future in futures]
    assert results[0] == results[1] == {**intent, "state": "no_effect"}
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(
                    models.audit_events.c.action == "operational_command.no_effect",
                    models.audit_events.c.entity_id == intent["id"],
                )
            )
            == 1
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_shift_commands)) == 0
        )
