"""Real PostgreSQL cash materialization versus revocation and duplicate commands."""

from __future__ import annotations

from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier, Event
from typing import Any
from uuid import uuid4

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import grant_permission
from corte_ciego_storage import isolated_database, seed_authority
from fixture_metadata import create_fixture_tables
from restaurant_os import models, operations
from restaurant_os.cash_command_views import shift_command
from restaurant_os.cash_views import CashViews
from restaurant_os.financial_access import FinancialAccessService
from sqlalchemy.orm import Session
from test_cash_concepts import (
    BRANCH_A,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    ORG_ID,
    OWNER_ID,
    OWNER_ROLE_ID,
)
from test_cash_ledger import NOW
from test_corte_ciego_f104_postgres import wait_until_blocked


@pytest.fixture
def pg_cash() -> Iterator[tuple[sa.Engine, str, str]]:
    for engine in isolated_database("postgresql"):
        # Existing domain tables with real FKs; authority uses the real 0101 migration.
        create_fixture_tables(engine)
        seed_authority(engine)
        shift = str(uuid4())
        with Session(engine) as session:
            grant_permission(session, OWNER_ROLE_ID, "admin.manage")
            session.execute(
                models.blind_cash_policy_revisions.insert().values(
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    revision=1,
                    manifest_digest="b" * 64,
                    minimum_api_version=2,
                    minimum_client_version=2,
                    minimum_gateway_version=2,
                    event="activated",
                    created_at=NOW,
                )
            )
            session.execute(
                models.cash_shifts.insert().values(
                    id=shift,
                    organization_id=ORG_ID,
                    branch_id=BRANCH_A,
                    register_code="F105-PG",
                    cashier_user_id=CASHIER_ID,
                    status="OPEN",
                    opening_cash_cents=12_345,
                    opened_at=NOW,
                    created_at=NOW,
                )
            )
            session.commit()
            grant = FinancialAccessService(session, ORG_ID).issue(
                OWNER_ID,
                "cash-read",
                {
                    "subject_user_id": CASHIER_ID,
                    "reason": "Synthetic cash reader",
                    "scopes": [{"branch_id": BRANCH_A, "dataset": "cash.shifts"}],
                },
            )["grant_id"]
        yield engine, shift, grant


@pytest.mark.parametrize("reader_first", [True, False])
@pytest.mark.parametrize("mutation", ["revoke", "role"])
def test_real_cash_dto_and_revocation_serialize(
    pg_cash: tuple[sa.Engine, str, str],
    monkeypatch: pytest.MonkeyPatch,
    reader_first: bool,
    mutation: str,
) -> None:
    engine, shift, grant = pg_cash
    arrived, release, contender_started = Event(), Event(), Event()
    pids: list[int] = []
    original_summary, original_audit = operations._cash_summary_for_shift, operations._audit

    def summary_barrier(*args: Any, **kwargs: Any) -> dict[str, int]:
        result = original_summary(*args, **kwargs)
        if reader_first:
            arrived.set()
            assert release.wait(10)
        return result

    def audit_barrier(*args: Any, **kwargs: Any) -> None:
        original_audit(*args, **kwargs)
        if not reader_first:
            arrived.set()
            assert release.wait(10)

    monkeypatch.setattr(operations, "_cash_summary_for_shift", summary_barrier)
    monkeypatch.setattr(operations, "_audit", audit_barrier)

    def reader() -> bool:
        with Session(engine) as session:
            if not reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender_started.set()
            try:
                result = CashViews(session, CASHIER_ID).detail("shift", shift, financial=True)
                assert result["current_summary"]["expected_cash_cents"] == 12_345
                session.commit()
                return True
            except operations.AuthorizationError:
                return False

    def writer() -> None:
        with Session(engine) as session:
            if reader_first:
                pids.append(int(session.scalar(sa.text("SELECT pg_backend_pid()"))))
                contender_started.set()
            if mutation == "revoke":
                FinancialAccessService(session, ORG_ID).revoke(
                    OWNER_ID,
                    grant,
                    "f105-stop",
                    {"reason": "Synthetic stop"},
                )
            else:
                operations.update_role_permissions(session, CASHIER_ROLE_ID, [], OWNER_ID)

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(reader if reader_first else writer)
        second = None
        try:
            assert arrived.wait(10)
            second = executor.submit(writer if reader_first else reader)
            assert contender_started.wait(5)
            wait_until_blocked(engine, pids[0])
        finally:
            release.set()
        assert second is not None
        first_result, second_result = first.result(timeout=15), second.result(timeout=15)
        assert (first_result if reader_first else second_result) is reader_first


def test_duplicate_shift_command_one_effect_two_safe_receipts(
    pg_cash: tuple[sa.Engine, str, str],
) -> None:
    engine, _, _ = pg_cash
    barrier = Barrier(2)

    def open_shift() -> dict[str, Any]:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            return shift_command(
                session,
                OWNER_ID,
                "open",
                None,
                {
                    "branch_id": BRANCH_A,
                    "register_id": "CONCURRENT",
                    "opening_cash_cents": 99,
                },
                "f105-duplicate",
                intent=None,
                context=None,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(open_shift), executor.submit(open_shift)
        results = [first.result(timeout=15), second.result(timeout=15)]
    assert results[0]["command_id"] == results[1]["command_id"]
    assert sorted(result["replay"] for result in results) == [False, True]
    assert all("opening_cash_cents" not in result for result in results)
    with Session(engine) as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.cash_shift_commands)
                .where(models.cash_shift_commands.c.idempotency_key == "f105-duplicate")
            )
            == 1
        )


def test_duplicate_cut_finalize_and_historical_count_receipt(
    pg_cash: tuple[sa.Engine, str, str],
) -> None:
    engine, shift, _ = pg_cash
    cut_id, end = str(uuid4()), NOW + timedelta(hours=1)
    with Session(engine) as session:
        grant_permission(session, CASHIER_ROLE_ID, "cash.user_cut.operational.read")
        session.execute(
            models.cash_shifts.update()
            .where(models.cash_shifts.c.id == shift)
            .values(status="OPERATIVELY_CLOSED", closed_at=end)
        )
        session.execute(
            models.cash_shift_closures.insert().values(
                id=str(uuid4()),
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                cash_shift_id=shift,
                register_code_snapshot="F105-PG",
                closed_by_user_id=OWNER_ID,
                summary_snapshot={},
                closed_at=end,
                created_at=end,
            )
        )
        cut = {
            "id": cut_id,
            "organization_id": ORG_ID,
            "branch_id": BRANCH_A,
            "cash_shift_id": shift,
            "register_code_snapshot": "F105-PG",
            "cashier_user_id": CASHIER_ID,
            "timezone": "America/Chihuahua",
            "period_start": NOW,
            "period_end": end,
            "status": "COUNTED",
            "opening_cash_cents": 12_345,
            "counted_cash_cents": 100,
            "version": 2,
            "created_by_user_id": CASHIER_ID,
            "created_at": end,
            "counted_at": end,
        }
        session.execute(models.user_cash_cuts.insert().values(**cut))
        service = operations.UserCashCutService(session)
        session.execute(
            models.user_cash_cut_commands.insert().values(
                id=str(uuid4()),
                organization_id=ORG_ID,
                actor_user_id=CASHIER_ID,
                cash_cut_id=cut_id,
                command_type="count",
                idempotency_key="historic-count",
                request_hash=service._hash(
                    "count", CASHIER_ID, cut_id, {"counted_cash_cents": 100, "version": 1}
                ),
                result=operations._sanitize_for_json({"cash_cut": cut}),
                created_at=end,
            )
        )
        session.commit()
    barrier = Barrier(2)

    def finalize() -> dict[str, Any]:
        with Session(engine) as session:
            barrier.wait(timeout=10)
            return operations.UserCashCutService(session).finalize(
                cut_id,
                {"version": 2},
                "f105-finalize-race",
                OWNER_ID,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        first, second = executor.submit(finalize), executor.submit(finalize)
        results = [first.result(timeout=15), second.result(timeout=15)]
    assert results[0]["command_id"] == results[1]["command_id"]
    assert sorted(result["replay"] for result in results) == [False, True]
    assert all("difference_cents" not in result for result in results)
    with Session(engine) as session:
        receipt = operations.UserCashCutService(session).counted_cash(
            cut_id,
            {"counted_cash_cents": 100, "version": 1},
            "historic-count",
            CASHIER_ID,
        )
        assert receipt["status"] == "COUNTED" and receipt["version"] == 2
        assert (
            session.scalar(
                sa.select(models.user_cash_cuts.c.version).where(
                    models.user_cash_cuts.c.id == cut_id,
                )
            )
            == 3
        )
