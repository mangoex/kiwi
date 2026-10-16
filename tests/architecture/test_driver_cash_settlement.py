"""Architecture contract for PRD-FR-059 and PRD-FR-129."""

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def _read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_driver_cash_settlement_is_append_only_atomic_and_traceable() -> None:
    models = _read("apps/api/restaurant_os/models.py")
    operations = _read("apps/api/restaurant_os/operations.py")
    migration = _read(
        "apps/api/alembic/versions/202610160100_0096_driver_cash_settlements.py"
    )
    for table in (
        "driver_cash_settlements",
        "driver_cash_settlement_items",
        "driver_cash_settlement_commands",
    ):
        assert f'{table} = sa.Table(' in models
        assert f'"{table}"' in migration
    assert "def settle_driver_cash_orders(" in operations
    assert "driver_settlement_order_ineligible" in operations
    assert "driver_settlement_idempotency_conflict" in operations
    assert "models.cash_movements.insert" not in operations.split(
        "def settle_driver_cash_orders(", maxsplit=1
    )[1].split("def ", maxsplit=1)[0]
    assert "0096 downgrade blocked: driver cash settlement history exists" in migration
    assert "LOCK TABLE driver_cash_settlements" in migration
    assert "IN ACCESS EXCLUSIVE MODE" in migration
    postgres_test = _read("apps/api/tests/test_driver_cash_settlement_postgres.py")
    workflow = _read(".github/workflows/ci.yml")
    verifier = _read("scripts/verify_postgres_evidence.py")
    assert "DRIVER_CASH_TEST_POSTGRES_URL" in postgres_test
    assert "DRIVER_CASH_TEST_POSTGRES_URL" in workflow
    assert '"driver_cash_settlement"' in verifier


def test_driver_cash_settlement_specs_and_traceability_exist() -> None:
    prd = _read("docs/01-PRD.md")
    sdd = _read("docs/02-SDD.md")
    bdd = _read("docs/03-BDD-driver-cash-settlement.md")
    tdd = _read("docs/04-TDD-driver-cash-settlement.md")
    matrix = _read("docs/05-matriz-trazabilidad.md")
    for requirement in ("PRD-FR-059", "PRD-FR-129"):
        assert requirement in prd
        assert requirement in sdd
        assert requirement in bdd
        assert requirement in matrix
    for scenario in range(708, 715):
        assert f"BDD-SC-{scenario}" in bdd and f"BDD-SC-{scenario}" in matrix
    assert "TDD-TS-148" in tdd and "TDD-TS-148" in matrix
    for case in range(410, 416):
        assert f"TDD-TC-{case}" in tdd and f"TDD-TC-{case}" in matrix


def test_driver_cash_settlement_downgrade_blocks_history() -> None:
    path = ROOT / "apps/api/alembic/versions/202610160100_0096_driver_cash_settlements.py"
    spec = importlib.util.spec_from_file_location("driver_cash_migration", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    class Result:
        @staticmethod
        def first() -> tuple[int]:
            return (1,)

    class Bind:
        dialect = SimpleNamespace(name="sqlite")

        @staticmethod
        def execute(_statement: object) -> Result:
            return Result()

    module.op = SimpleNamespace(get_bind=lambda: Bind())
    with pytest.raises(RuntimeError, match="downgrade blocked"):
        module.downgrade()


def test_driver_cash_settlement_postgres_downgrade_locks_before_guard() -> None:
    path = ROOT / "apps/api/alembic/versions/202610160100_0096_driver_cash_settlements.py"
    spec = importlib.util.spec_from_file_location("driver_cash_migration_pg", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    statements: list[str] = []

    class Result:
        @staticmethod
        def first() -> tuple[int]:
            return (1,)

    class Bind:
        dialect = SimpleNamespace(name="postgresql")

        @staticmethod
        def execute(statement: object) -> Result:
            statements.append(str(statement))
            return Result()

    module.op = SimpleNamespace(get_bind=lambda: Bind())
    with pytest.raises(RuntimeError, match="downgrade blocked"):
        module.downgrade()

    assert statements[0].startswith("LOCK TABLE driver_cash_settlements")
    assert statements[1].startswith("SELECT 1 FROM driver_cash_settlement_commands")
