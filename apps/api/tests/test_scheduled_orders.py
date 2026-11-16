# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-scheduled-orders-tests-v1
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.branch_schedule import (
    default_branch_operating_hours,
    upsert_branch_operating_hours,
)
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.models import metadata
from restaurant_os.operations import ORGANIZATION_ID
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _next_open_weekday_10am(tz_name: str = "America/Mazatlan") -> datetime:
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    candidate = (now_local + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    while candidate.weekday() >= 5:  # Mon-Fri (0..4)
        candidate += timedelta(days=1)
    return candidate


def _next_sunday_10am(tz_name: str = "America/Mazatlan") -> datetime:
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    candidate = (now_local + timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )
    while candidate.weekday() != 6:  # Sunday
        candidate += timedelta(days=1)
    return candidate


@pytest.fixture
def scheduled_test_env():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    now = datetime.now(timezone.utc)

    session.execute(
        models.organizations.insert().values(
            id=ORGANIZATION_ID,
            name="Kiwi Restaurante",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.legal_entities.insert().values(
            id="legal-kiwi-01",
            organization_id=ORGANIZATION_ID,
            name="Kiwi S.A. de C.V.",
            tax_id=None,
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.business_units.insert().values(
            id="unit-kiwi-01",
            organization_id=ORGANIZATION_ID,
            legal_entity_id="legal-kiwi-01",
            name="Operaciones Kiwi",
            code="KIWI",
            unit_type="restaurant",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    branch_id = "branch-chapultepec-01"
    session.execute(
        models.branches.insert().values(
            id=branch_id,
            organization_id=ORGANIZATION_ID,
            business_unit_id="unit-kiwi-01",
            legal_entity_id="legal-kiwi-01",
            name="Chapultepec",
            code="CHAP",
            timezone="America/Mazatlan",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    upsert_branch_operating_hours(
        session,
        organization_id=ORGANIZATION_ID,
        branch_id=branch_id,
        hours=default_branch_operating_hours(),
        now=now,
    )

    warehouse_id = "wh-chap-01"
    session.execute(
        models.warehouses.insert().values(
            id=warehouse_id,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            name="Almacén Principal",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    register_id = "CAJA-1"
    user_id = "user-cashier-01"
    session.execute(
        models.users.insert().values(
            id=user_id,
            organization_id=ORGANIZATION_ID,
            email="cashier@kiwi.test",
            display_name="Cajero Test",
            employee_code="999002",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    role_id = "role-cashier-01"
    session.execute(
        models.roles.insert().values(
            id=role_id,
            organization_id=ORGANIZATION_ID,
            name="Cajero Rol",
            scope="organization",
            created_at=now,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=user_id,
            role_id=role_id,
            branch_id=None,
        )
    )
    for idx, perm_code in enumerate(
        ["orders.create", "orders.read", "orders.fulfill", "orders.cancel"]
    ):
        perm_id = f"perm-sched-{idx}"
        session.execute(
            models.permissions.insert().values(
                id=perm_id,
                code=perm_code,
                description=f"Test {perm_code}",
                created_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(
                role_id=role_id,
                permission_id=perm_id,
            )
        )

    category_id = "cat-bebidas-01"
    session.execute(
        models.product_categories.insert().values(
            id=category_id,
            organization_id=ORGANIZATION_ID,
            name="Bebidas",
            display_order=1,
            status="active",
            configuration_version=1,
            created_at=now,
            updated_at=now,
        )
    )
    product_id = "prod-agua-01"
    session.execute(
        models.products.insert().values(
            id=product_id,
            organization_id=ORGANIZATION_ID,
            category_id=category_id,
            sku="AGU-001",
            name="Agua Fresca",
            station="BAR",
            status="active",
            catalog_scope="corporate",
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.price_versions.insert().values(
            id="pv-agua-01",
            organization_id=ORGANIZATION_ID,
            product_id=product_id,
            price_cents=4500,
            currency="MXN",
            valid_from=now - timedelta(days=1),
            created_at=now,
        )
    )
    unit_id = "unit-pz-01"
    session.execute(
        models.inventory_units.insert().values(
            id=unit_id,
            organization_id=ORGANIZATION_ID,
            code="pz",
            name="Pieza",
            dimension="count",
            precision_scale=2,
            created_at=now,
        )
    )
    item_id = "item-limon-01"
    session.execute(
        models.inventory_items.insert().values(
            id=item_id,
            organization_id=ORGANIZATION_ID,
            name="Limón",
            sku="INS-LIM",
            base_unit_id=unit_id,
            item_type="ingredient",
            catalog_scope="corporate",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    recipe_id = "rec-agua-01"
    session.execute(
        models.recipes.insert().values(
            id=recipe_id,
            organization_id=ORGANIZATION_ID,
            product_id=product_id,
            recipe_type="sale",
            version=1,
            status="active",
            yield_quantity=Decimal("1.00"),
            yield_unit_id=unit_id,
            valid_from=now - timedelta(days=1),
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.recipe_components.insert().values(
            recipe_id=recipe_id,
            item_id=item_id,
            quantity_base_units=Decimal("1.00"),
            unit_id=unit_id,
            net_quantity=Decimal("1.00"),
            waste_rate=Decimal("0.00"),
            gross_quantity=Decimal("1.00"),
            sort_order=1,
        )
    )
    session.execute(
        models.inventory_movements.insert().values(
            id="mov-init-01",
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            warehouse_id=warehouse_id,
            item_id=item_id,
            movement_type="INITIAL_BALANCE",
            quantity_delta=Decimal("100.00"),
            unit_id=unit_id,
            unit_cost=Decimal("1.00"),
            total_cost=Decimal("100.00"),
            effective_at=now - timedelta(days=1),
            reason="Initial stock",
            status="POSTED",
            created_at=now,
        )
    )
    session.commit()

    settings = get_settings()
    token = create_session_token(
        {
            "sub": user_id,
            "user_id": user_id,
            "email": "cashier@kiwi.test",
            "roles": ["Cajero Rol"],
            "scope": "organization",
            "org_id": ORGANIZATION_ID,
            "branch_ids": [branch_id],
            "permissions": [
                "orders.create",
                "orders.read",
                "orders.fulfill",
                "orders.cancel",
            ],
        },
        settings.secret_key,
    )
    app = create_app()
    app.dependency_overrides[get_session] = lambda: session
    client = TestClient(app)
    client.headers.update({"Authorization": f"Bearer {token}"})

    try:
        yield {
            "client": client,
            "session": session,
            "branch_id": branch_id,
            "register_id": register_id,
            "product_id": product_id,
            "user_id": user_id,
        }
    finally:
        app.dependency_overrides.clear()
        session.close()


def test_create_scheduled_order_without_shift_no_kitchen_no_inventory(scheduled_test_env):
    client = scheduled_test_env["client"]
    session = scheduled_test_env["session"]
    branch_id = scheduled_test_env["branch_id"]
    register_id = scheduled_test_env["register_id"]
    product_id = scheduled_test_env["product_id"]

    scheduled_dt = _next_open_weekday_10am()
    resp = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "María López",
            "customer_phone": "6671234567",
            "scheduled_for": scheduled_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert resp.status_code in (200, 201), resp.text
    data = resp.json()
    assert data["status"] == "SCHEDULED"
    assert data["cash_shift_id"] is None
    assert data["scheduled_for"] is not None

    task_count = session.execute(
        select(func.count()).select_from(models.production_tasks)
    ).scalar_one()
    assert task_count == 0

    mov_count = session.execute(
        select(func.count())
        .select_from(models.inventory_movements)
        .where(models.inventory_movements.c.movement_type == "SALE_RESERVATION")
    ).scalar_one()
    assert mov_count == 0


def test_create_scheduled_order_rejects_missing_phone_and_closed_hours(scheduled_test_env):
    client = scheduled_test_env["client"]
    branch_id = scheduled_test_env["branch_id"]
    register_id = scheduled_test_env["register_id"]
    product_id = scheduled_test_env["product_id"]

    open_dt = _next_open_weekday_10am()
    resp_no_phone = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Sin Teléfono",
            "scheduled_for": open_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert resp_no_phone.status_code == 409
    assert resp_no_phone.json()["detail"]["code"] == "scheduled_order_phone_required"

    sunday_dt = _next_sunday_10am()
    resp_closed = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Domingo Cerrado",
            "customer_phone": "6671234567",
            "scheduled_for": sunday_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert resp_closed.status_code == 409
    assert resp_closed.json()["detail"]["code"] == "branch_closed_at_scheduled_time"

    past_dt = datetime.now(timezone.utc) + timedelta(minutes=5)
    resp_past = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Muy Pronto",
            "customer_phone": "6671234567",
            "scheduled_for": past_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert resp_past.status_code == 409
    assert resp_past.json()["detail"]["code"] == "scheduled_time_in_past"


def test_pending_count_and_accounts_filter_for_scheduled_orders(scheduled_test_env):
    client = scheduled_test_env["client"]
    session = scheduled_test_env["session"]
    branch_id = scheduled_test_env["branch_id"]
    register_id = scheduled_test_env["register_id"]
    product_id = scheduled_test_env["product_id"]

    open_dt = _next_open_weekday_10am()
    r1 = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Cliente Lejano",
            "customer_phone": "6671111111",
            "scheduled_for": (open_dt + timedelta(hours=3)).isoformat(),
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert r1.status_code in (200, 201), r1.text
    id_far = r1.json()["id"]

    r2 = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Cliente Próximo",
            "customer_phone": "6672222222",
            "scheduled_for": open_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert r2.status_code in (200, 201), r2.text
    id_due = r2.json()["id"]

    # Force id_due to be 20 minutes from now (within 30-min alarm window)
    now_utc = datetime.now(timezone.utc)
    session.execute(
        sa.update(models.orders)
        .where(models.orders.c.id == id_due)
        .values(scheduled_for=now_utc + timedelta(minutes=20))
    )
    session.execute(
        sa.update(models.orders)
        .where(models.orders.c.id == id_far)
        .values(scheduled_for=now_utc + timedelta(hours=3))
    )
    session.commit()

    cnt_resp = client.get(f"/api/v1/orders/pending-count?branch_id={branch_id}")
    assert cnt_resp.status_code == 200
    cnt_data = cnt_resp.json()
    assert cnt_data["scheduled_count"] == 2
    assert cnt_data["scheduled_due_count"] == 1

    acc_resp = client.get(f"/api/v1/orders/accounts?branch_id={branch_id}&status=SCHEDULED")
    assert acc_resp.status_code == 200
    items = acc_resp.json()["items"]
    assert [item["id"] for item in items] == [id_due, id_far]


def test_release_scheduled_order_requires_open_shift_and_sends_to_kitchen(scheduled_test_env):
    client = scheduled_test_env["client"]
    session = scheduled_test_env["session"]
    branch_id = scheduled_test_env["branch_id"]
    register_id = scheduled_test_env["register_id"]
    product_id = scheduled_test_env["product_id"]
    user_id = scheduled_test_env["user_id"]

    open_dt = _next_open_weekday_10am()
    r = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Cliente Liberación",
            "customer_phone": "6673334444",
            "scheduled_for": open_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 2}],
        },
    )
    assert r.status_code in (200, 201), r.text
    order_id = r.json()["id"]

    # Fails without open cash shift
    fail_rel = client.post(
        f"/api/v1/orders/{order_id}/release-scheduled",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"register_id": register_id},
    )
    assert fail_rel.status_code == 409

    # Open a cash shift and release
    now = datetime.now(timezone.utc)
    shift_id = "shift-chap-01"
    session.execute(
        models.cash_shifts.insert().values(
            id=shift_id,
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            register_code=register_id,
            cashier_user_id=user_id,
            opening_cash_cents=100000,
            status="OPEN",
            opened_at=now,
            created_at=now,
        )
    )
    session.commit()

    ok_rel = client.post(
        f"/api/v1/orders/{order_id}/release-scheduled",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"register_id": register_id},
    )
    assert ok_rel.status_code == 200, ok_rel.text
    rel_data = ok_rel.json()
    assert rel_data["status"] == "ACCEPTED"
    assert rel_data["cash_shift_id"] == shift_id

    task_count = session.execute(
        select(func.count())
        .select_from(models.production_tasks)
        .where(models.production_tasks.c.order_id == order_id)
    ).scalar_one()
    assert task_count == 1


def test_reschedule_and_cancel_scheduled_order(scheduled_test_env):
    client = scheduled_test_env["client"]
    branch_id = scheduled_test_env["branch_id"]
    register_id = scheduled_test_env["register_id"]
    product_id = scheduled_test_env["product_id"]

    open_dt = _next_open_weekday_10am()
    r = client.post(
        "/api/v1/orders",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={
            "branch_id": branch_id,
            "register_id": register_id,
            "order_type": "takeout",
            "owner_name": "Cliente Reprogramar",
            "customer_phone": "6675556666",
            "scheduled_for": open_dt.isoformat(),
            "lines": [{"product_id": product_id, "quantity": 1}],
        },
    )
    assert r.status_code in (200, 201), r.text
    order_id = r.json()["id"]

    new_dt = open_dt + timedelta(hours=2)
    patch_resp = client.patch(
        f"/api/v1/orders/{order_id}/schedule",
        json={"scheduled_for": new_dt.isoformat()},
    )
    assert patch_resp.status_code == 200, patch_resp.text
    assert patch_resp.json()["status"] == "SCHEDULED"

    cancel_resp = client.post(
        f"/api/v1/orders/{order_id}/cancel",
        headers={"Idempotency-Key": str(uuid.uuid4())},
        json={"reason": "Cliente canceló por teléfono"},
    )
    assert cancel_resp.status_code == 200, cancel_resp.text
    assert cancel_resp.json()["status"] == "CANCELLED"


def test_alembic_0107_scheduled_orders_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "alembic_sched.db"
    db_url = f"sqlite:///{db_path}"
    monkeypatch.setenv("DATABASE_URL", db_url)
    get_settings.cache_clear()
    try:
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", db_url)

        command.upgrade(alembic_cfg, "0107_scheduled_orders")
        engine = create_engine(db_url)
        insp = sa.inspect(engine)
        order_cols = {col["name"] for col in insp.get_columns("orders")}
        expected_cols = {
            "scheduled_for",
            "scheduled_released_at",
            "scheduled_released_by_user_id",
        }
        assert expected_cols <= order_cols
        intent_cols = {col["name"] for col in insp.get_columns("public_order_intents")}
        assert "scheduled_for" in intent_cols

        command.downgrade(alembic_cfg, "0106_branch_operating_hours")
        insp_after = sa.inspect(engine)
        order_cols_after = {col["name"] for col in insp_after.get_columns("orders")}
        assert "scheduled_for" not in order_cols_after
        intent_cols_after = {col["name"] for col in insp_after.get_columns("public_order_intents")}
        assert "scheduled_for" not in intent_cols_after
    finally:
        get_settings.cache_clear()
