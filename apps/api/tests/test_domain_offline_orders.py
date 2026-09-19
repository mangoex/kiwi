from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.combo import save_composition
from restaurant_os.operations import (
    AuthorizationError,
    _price_order_line,
    create_local_order,
    require_permission,
)
from restaurant_os.order_execution import (
    ExecutionContext,
    defer_authorization_audit,
    next_id,
    order_execution_context,
)
from test_cash_ledger import BRANCH_A, NOW, _new_session
from test_combo_compositions import (
    ACTOR,
    BURGER,
    COMBO,
    DRINK,
    _seed,
    _seed_combo_recipes_and_order_scope,
)

UTC = timezone.utc
COMMAND_ID = "018f6f73-2d0a-74f0-8f1c-00000000aa01"
ACCEPTED_AT = datetime(2026, 9, 19, 12, 0, tzinfo=UTC)
FOLIO = "SUC02-CAJA01-018f6f732d0a74f08f1c00000000aa01-000001"


def _context(*, catalog_session=None) -> ExecutionContext:
    return ExecutionContext(
        command_id=COMMAND_ID,
        accepted_at=ACCEPTED_AT,
        folio=FOLIO,
        catalog_session=catalog_session,
        gateway_epoch=1,
        execution_mode="offline_reconcile",
    )


def _seed_combo_order_scope(session) -> None:
    _seed(session)
    _seed_combo_recipes_and_order_scope(session)
    session.execute(
        models.inventory_cost_states.insert().values(
            branch_id=BRANCH_A,
            warehouse_id="combo-warehouse",
            item_id="018f6f73-2d0a-74f0-8f1c-000000009307",
            quantity_on_hand=Decimal("10"),
            average_unit_cost=Decimal("10"),
            last_unit_cost=Decimal("10"),
            last_supplier_id=None,
            last_cost_at=None,
            updated_at=NOW,
        )
    )
    session.commit()
    save_composition(
        session,
        ACTOR,
        COMBO,
        None,
        expected_version=0,
        idempotency_key="offline-domain-composition-001",
        components=[
            {"product_id": BURGER, "quantity": "1"},
            {"product_id": DRINK, "quantity": "1"},
        ],
    )


def _create_combo_without_commit() -> tuple[dict[str, object], tuple[tuple[str, ...], ...]]:
    engine, session = _new_session()
    try:
        _seed_combo_order_scope(session)
        before_orders = session.scalar(sa.select(sa.func.count()).select_from(models.orders))
        with order_execution_context(_context()):
            order = create_local_order(
                session,
                [{"product_id": COMBO, "quantity": 1}],
                register_id="CAJA-01",
                actor_user_id=ACTOR,
                idempotency_key="offline-domain-order-001",
                commit=False,
            )
        task_ids = tuple(sorted(str(task["id"]) for task in order["production_tasks"]))
        snapshot_ids = tuple(
            sorted(
                str(row["id"])
                for row in session.execute(
                    sa.select(models.order_line_component_snapshots).where(
                        models.order_line_component_snapshots.c.order_line_id
                        == order["lines"][0]["id"]
                    )
                ).mappings()
            )
        )
        movement_ids = tuple(
            sorted(
                str(item)
                for item in session.scalars(
                    sa.select(models.inventory_movements.c.id).where(
                        models.inventory_movements.c.source_id == order["id"]
                    )
                )
            )
        )
        result = {
            "id": order["id"],
            "folio": order["folio"],
            "line_id": order["lines"][0]["id"],
            "total_cents": order["total_cents"],
            "cost": order["consumption_snapshots"][0]["total_theoretical_cost"],
        }
        session.rollback()
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == before_orders
        )
        return result, (task_ids, snapshot_ids, movement_ids)
    finally:
        session.close()
        engine.dispose()


def test_execution_context_restarts_deterministic_uuidv7_stream_per_entry_and_isolated() -> None:
    context = _context()

    def execute() -> tuple[str | None, str | None]:
        with order_execution_context(context):
            return next_id(), next_id()

    assert execute() == execute()
    with ThreadPoolExecutor(max_workers=2) as workers:
        assert list(workers.map(lambda _: execute(), range(2))) == [execute(), execute()]


def test_offline_permission_denial_defers_audit_without_taking_outer_transaction(
    monkeypatch,
) -> None:
    engine, session = _new_session()
    try:
        pending_organization = "offline-deferred-authorization"
        session.execute(
            models.organizations.insert().values(
                id=pending_organization,
                name="Pending authorization transaction",
                status="active",
                created_at=ACCEPTED_AT,
                updated_at=ACCEPTED_AT,
            )
        )
        rollbacks: list[bool] = []
        commits: list[bool] = []
        with monkeypatch.context() as scoped_patch:
            scoped_patch.setattr(session, "rollback", lambda: rollbacks.append(True))
            scoped_patch.setattr(session, "commit", lambda: commits.append(True))
            with defer_authorization_audit() as denials:
                with order_execution_context(_context()):
                    with pytest.raises(AuthorizationError, match="not authorized"):
                        require_permission(
                            session,
                            "unknown-offline-actor",
                            "orders.create",
                            BRANCH_A,
                        )
        assert rollbacks == []
        assert commits == []
        assert denials == [
            {
                "actor_user_id": None,
                "permission_code": "orders.create",
                "branch_id": BRANCH_A,
                "reason": "actor_not_found",
            }
        ]
        assert (
            session.scalar(
                sa.select(models.organizations.c.id).where(
                    models.organizations.c.id == pending_organization
                )
            )
            == pending_organization
        )
        assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == 0
        session.rollback()
    finally:
        session.close()
        engine.dispose()


def test_same_combo_command_is_deterministic_across_sqlite_copies() -> None:
    first, first_artifacts = _create_combo_without_commit()
    second, second_artifacts = _create_combo_without_commit()

    assert first == second
    assert first["folio"] == FOLIO
    assert first["total_cents"] == 15_900
    assert Decimal(str(first["cost"])) == Decimal("5.000000")
    assert first_artifacts == second_artifacts


def test_price_reads_frozen_catalog_session_not_operational_catalog() -> None:
    operational_engine, operational = _new_session()
    catalog_engine, catalog = _new_session()
    try:
        _seed_combo_order_scope(operational)
        _seed_combo_order_scope(catalog)
        for database_session in (operational, catalog):
            database_session.execute(
                models.price_versions.insert().values(
                    id="018f6f73-2d0a-74f0-8f1c-000000009399",
                    organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                    product_id=BURGER,
                    price_cents=5_000,
                    currency="MXN",
                    valid_from=NOW,
                    valid_to=None,
                    created_at=NOW,
                )
            )
            database_session.commit()
        operational.execute(
            models.price_versions.update()
            .where(
                models.price_versions.c.product_id == COMBO,
                models.price_versions.c.valid_to.is_(None),
            )
            .values(price_cents=999)
        )
        operational.execute(
            models.inventory_cost_states.update()
            .where(
                models.inventory_cost_states.c.branch_id == BRANCH_A,
                models.inventory_cost_states.c.item_id == "018f6f73-2d0a-74f0-8f1c-000000009307",
            )
            .values(average_unit_cost=Decimal("99"))
        )
        with order_execution_context(_context(catalog_session=catalog)):
            priced = _price_order_line(
                operational,
                {"product_id": COMBO, "quantity": 1},
                BRANCH_A,
                "018f6f73-2d0a-74f0-8f1c-00000000ab01",
                "018f6f73-2d0a-74f0-8f1c-00000000ab02",
                ACCEPTED_AT,
            )
        assert priced["line_total_cents"] == 15_900
        assert priced["product"]["price_cents"] == 15_900
        with order_execution_context(_context(catalog_session=catalog)):
            burger = _price_order_line(
                operational,
                {"product_id": BURGER, "quantity": 1},
                BRANCH_A,
                "018f6f73-2d0a-74f0-8f1c-00000000ab03",
                "018f6f73-2d0a-74f0-8f1c-00000000ab04",
                ACCEPTED_AT,
            )
        assert burger["line_total_cents"] == 5_000
        assert Decimal(str(burger["snapshot"]["total_theoretical_cost"])) == Decimal("2.500000")
    finally:
        operational.close()
        catalog.close()
        operational_engine.dispose()
        catalog_engine.dispose()
