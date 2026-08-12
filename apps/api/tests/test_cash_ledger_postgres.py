"""Opt-in PCO-003 PostgreSQL concurrency verification; never reads DATABASE_URL."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
from threading import Barrier
from urllib.parse import urlparse

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BusinessError,
    calculate_expected_cash,
    close_cash_shift_with_cut,
    compensate_cash_movement,
    confirm_purchase_document,
    create_cash_concept,
    create_cash_movement,
)
from sqlalchemy.orm import Session
from test_cash_concepts import (
    BRANCH_A,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    ORG_ID,
    OWNER_ID,
    _concept_payload,
    _seed_cash_concept_scope,
)
from test_platform_api import ADMIN_USER_ID, _seed

SHIFT_ID = "018f6f73-2d0a-74f0-8f1c-000000009901"
NOW = datetime(2026, 8, 12, tzinfo=timezone.utc)


def _postgres_url() -> str:
    url = os.environ.get("PCO003_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("PCO003_TEST_POSTGRES_URL is required")
    parsed = urlparse(url)
    if parsed.hostname not in {"127.0.0.1", "localhost"} or not parsed.path.startswith(
        "/pco003_"
    ):
        raise RuntimeError("PCO-003 PostgreSQL tests require local pco003_* database")
    return url


def _truncate(engine: sa.Engine) -> None:
    tables = (
        "audit_events, cash_movement_commands, cash_movements, cash_shift_cuts, "
        "cash_shifts, cash_concept_commands, cash_movement_concept_versions, "
        "cash_movement_concepts, role_authority_grants, role_permissions, user_roles, "
        "permissions, users, roles, branches, business_units, legal_entities, organizations"
    )
    with engine.begin() as connection:
        connection.execute(sa.text(f"TRUNCATE {tables} CASCADE"))


def _grant_cash_permissions(session: Session) -> None:
    codes = (
        "cash.movement.withdraw",
        "cash.movement.deposit",
        "cash.movement.compensate",
        "cash.movement.read",
        "cash.shift.close",
    )
    rows = []
    grants = []
    for offset, code in enumerate(codes, start=1):
        permission_id = f"018f6f73-2d0a-74f0-8f1c-0000000013{offset:02d}"
        rows.append(
            {
                "id": permission_id,
                "code": code,
                "description": code,
                "created_at": NOW,
            }
        )
        grants.append({"role_id": CASHIER_ROLE_ID, "permission_id": permission_id})
    session.execute(models.permissions.insert(), rows)
    session.execute(models.role_permissions.insert(), grants)


def _setup(engine: sa.Engine) -> dict[str, object]:
    _truncate(engine)
    with Session(engine) as session:
        _seed_cash_concept_scope(session)
        _grant_cash_permissions(session)
        session.execute(
            models.cash_shifts.insert().values(
                id=SHIFT_ID,
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                register_code="CAJA-01",
                status="OPEN",
                opening_cash_cents=10_000,
                opened_at=NOW,
                closed_at=None,
                created_at=NOW,
            )
        )
        session.commit()
        return create_cash_concept(session, _concept_payload(), "postgres-concept", OWNER_ID)


def _payload(concept_id: str, amount_cents: int = 2_000) -> dict[str, object]:
    return {
        "branch_id": BRANCH_A,
        "register_id": "CAJA-01",
        "movement_type": "withdrawal",
        "concept_id": concept_id,
        "amount_cents": amount_cents,
        "reference": "PG-001",
        "evidence_refs": ["evidence://pg/1"],
    }


def test_postgres_same_and_different_idempotency_keys_are_serialized() -> None:
    engine = sa.create_engine(_postgres_url(), pool_pre_ping=True)
    concept = _setup(engine)

    def create(key: str, amount_cents: int, barrier: Barrier) -> tuple[str, object]:
        with Session(engine) as session:
            barrier.wait()
            try:
                return (
                    "ok",
                    create_cash_movement(
                        session,
                        _payload(str(concept["id"]), amount_cents),
                        key,
                        CASHIER_ID,
                    ),
                )
            except BusinessError as exc:
                return "error", exc.code

    same_barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        same = list(
            pool.map(
                lambda _: create("postgres-same", 2_000, same_barrier),
                range(2),
            )
        )
    assert [state for state, _ in same] == ["ok", "ok"]
    assert len({result["movement"]["id"] for _, result in same}) == 1

    different_barrier = Barrier(2)
    with ThreadPoolExecutor(max_workers=2) as pool:
        different = list(
            pool.map(
                lambda amount: create("postgres-different", amount, different_barrier),
                (1_000, 2_000),
            )
        )
    assert sorted(result for state, result in different if state == "error") == [
        "idempotency_conflict"
    ]
    with Session(engine) as session:
        assert calculate_expected_cash(session, SHIFT_ID)["expected_cash_cents"] in {
            6_000,
            7_000,
        }
    original_id = same[0][1]["movement"]["id"]
    compensation_barrier = Barrier(2)

    def compensate(key: str) -> tuple[str, object]:
        with Session(engine) as session:
            compensation_barrier.wait()
            try:
                return (
                    "ok",
                    compensate_cash_movement(
                        session,
                        original_id,
                        {"reason": "Concurrent correction", "evidence_refs": ["evidence://pg/c"]},
                        key,
                        OWNER_ID,
                    ),
                )
            except BusinessError as exc:
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        compensation = list(pool.map(compensate, ("postgres-comp-a", "postgres-comp-b")))
    assert sorted(state for state, _ in compensation) == ["error", "ok"]
    assert [result for state, result in compensation if state == "error"] == [
        "cash_movement_already_compensated"
    ]
    engine.dispose()


def test_postgres_close_and_movement_race_share_the_open_shift_guard() -> None:
    engine = sa.create_engine(_postgres_url(), pool_pre_ping=True)
    concept = _setup(engine)
    barrier = Barrier(2)

    def close() -> tuple[str, object]:
        with Session(engine) as session:
            barrier.wait()
            try:
                return (
                    "ok",
                    close_cash_shift_with_cut(
                        session,
                        10_000,
                        "CAJA-01",
                        BRANCH_A,
                        OWNER_ID,
                    ),
                )
            except BusinessError as exc:
                return "error", exc.code

    def movement() -> tuple[str, object]:
        with Session(engine) as session:
            barrier.wait()
            try:
                return (
                    "ok",
                    create_cash_movement(
                        session,
                        _payload(str(concept["id"])),
                        "postgres-close-race",
                        CASHIER_ID,
                    ),
                )
            except BusinessError as exc:
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        close_result, movement_result = list(pool.map(lambda action: action(), (close, movement)))
    assert close_result[0] == "ok"
    if movement_result[0] == "ok":
        assert close_result[1]["cut"]["expected_cash_cents"] == 8_000
    else:
        assert movement_result[1] == "cash_shift_not_open"
        assert close_result[1]["cut"]["expected_cash_cents"] == 10_000
    engine.dispose()


def test_postgres_close_and_cash_purchase_race_share_the_open_shift_guard() -> None:
    engine = sa.create_engine(_postgres_url(), pool_pre_ping=True)
    _truncate(engine)
    purchase_id = "018f6f73-2d0a-74f0-8f1c-000000009991"
    with Session(engine) as session:
        _seed(session)
        organization_id = session.execute(sa.select(models.organizations.c.id)).scalar_one()
        item = session.execute(
            sa.select(models.inventory_items).where(models.inventory_items.c.status == "active")
        ).mappings().first()
        assert item is not None
        supplier_id = "018f6f73-2d0a-74f0-8f1c-000000009992"
        presentation_id = "018f6f73-2d0a-74f0-8f1c-000000009993"
        session.execute(models.suppliers.insert().values(
            id=supplier_id, organization_id=organization_id, code="RACE-SUPPLIER",
            commercial_name="Race supplier", delivery_days=[], payment_methods=["cash"],
            status="active", created_at=NOW, updated_at=NOW,
        ))
        session.execute(models.purchase_presentations.insert().values(
            id=presentation_id, organization_id=organization_id, supplier_id=supplier_id,
            item_id=item["id"], code="RACE-PRESENTATION", name="Race presentation",
            package_type="unit", commercial_quantity=Decimal("1"),
            commercial_unit_id=item["base_unit_id"], base_unit_id=item["base_unit_id"],
            base_unit_yield=Decimal("1"), usable_content=Decimal("1"),
            yield_percent=Decimal("1"), tax_rate=Decimal("0"), last_net_price=Decimal("1"),
            cost_per_base_unit=Decimal("1"), status="active", created_at=NOW, updated_at=NOW,
        ))
        session.execute(models.cash_shifts.insert().values(
            id=SHIFT_ID, organization_id=organization_id, branch_id=BRANCH_A,
            register_code="CAJA-01", status="OPEN", opening_cash_cents=10_000,
            opened_at=NOW, closed_at=None, created_at=NOW,
        ))
        session.execute(models.purchase_documents.insert().values(
            id=purchase_id, organization_id=organization_id, branch_id=BRANCH_A,
            supplier_id=supplier_id, document_type="invoice", folio="RACE-001",
            document_date=NOW, subtotal=Decimal("1"), discount_total=Decimal("0"),
            tax_total=Decimal("0"), freight_total=Decimal("0"), total=Decimal("1"),
            payment_method="cash", paid_from_cash=True, cash_movement_id=None, evidence_url=None,
            notes=None, status="draft", created_by=ADMIN_USER_ID, confirmed_by=None,
            cancelled_by=None, confirmation_idempotency_key=None, cancellation_reason=None,
            created_at=NOW, confirmed_at=None, cancelled_at=None,
        ))
        session.execute(models.purchase_document_lines.insert().values(
            id="018f6f73-2d0a-74f0-8f1c-000000009994", purchase_document_id=purchase_id,
            presentation_id=presentation_id, item_id=item["id"],
            presentation_snapshot={"base_unit_id": item["base_unit_id"], "usable_content": "1"},
            presentation_quantity=Decimal("1"), base_quantity=Decimal("1"), unit_price=Decimal("1"),
            discount=Decimal("0"), tax=Decimal("0"), line_total=Decimal("1"),
            inventory_cost=Decimal("1"), cost_per_base_unit=Decimal("1"), created_at=NOW,
        ))
        session.commit()
    barrier = Barrier(2)

    def close() -> tuple[str, object]:
        with Session(engine) as session:
            barrier.wait()
            try:
                return "ok", close_cash_shift_with_cut(
                    session, 10_000, "CAJA-01", BRANCH_A, ADMIN_USER_ID
                )
            except BusinessError as exc:
                return "error", exc.code

    def confirm() -> tuple[str, object]:
        with Session(engine) as session:
            barrier.wait()
            try:
                return "ok", confirm_purchase_document(
                    session, purchase_id, "purchase-race", "CAJA-01", ADMIN_USER_ID
                )
            except BusinessError as exc:
                return "error", exc.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        close_result, purchase_result = list(pool.map(lambda action: action(), (close, confirm)))
    assert close_result[0] == "ok"
    with Session(engine) as session:
        purchase = session.execute(sa.select(models.purchase_documents).where(
            models.purchase_documents.c.id == purchase_id
        )).mappings().one()
        cash_count = session.execute(
            sa.select(sa.func.count())
            .select_from(models.cash_movements)
            .where(models.cash_movements.c.source_id == purchase_id)
        ).scalar_one()
        inventory_count = session.execute(
            sa.select(sa.func.count())
            .select_from(models.inventory_movements)
            .where(models.inventory_movements.c.source_id == purchase_id)
        ).scalar_one()
    if purchase_result[0] == "ok":
        assert purchase["status"] == "confirmed"
        assert cash_count == 1 and inventory_count == 1
        assert close_result[1]["cut"]["expected_cash_cents"] == 9_900
    else:
        assert purchase_result[1] == "cash_shift_not_open"
        assert purchase["status"] == "draft"
        assert cash_count == 0 and inventory_count == 0
    engine.dispose()
