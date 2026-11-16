# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-branch-operating-hours-tests-v1
from __future__ import annotations

from datetime import datetime, timezone
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
    validate_branch_open_at,
)
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.models import metadata
from restaurant_os.operations import ORGANIZATION_ID, BusinessError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def test_db():
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
    admin_user_id = "user-admin-01"
    session.execute(
        models.users.insert().values(
            id=admin_user_id,
            organization_id=ORGANIZATION_ID,
            email="admin@kiwi.test",
            display_name="Admin Test",
            employee_code="999001",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    admin_role_id = "role-admin-01"
    session.execute(
        models.roles.insert().values(
            id=admin_role_id,
            organization_id=ORGANIZATION_ID,
            name="Admin Rol",
            scope="organization",
            created_at=now,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=admin_user_id,
            role_id=admin_role_id,
            branch_id=None,
        )
    )
    for perm_id, perm_code in [
        ("p1", "admin.manage"),
        ("p2", "catalog.manage"),
        ("p3", "orders.create"),
    ]:
        session.execute(
            models.permissions.insert().values(
                id=perm_id,
                code=perm_code,
                description=f"Test {perm_code}",
                created_at=now,
            )
        )
        session.execute(
            models.role_permissions.insert().values(role_id=admin_role_id, permission_id=perm_id)
        )
    session.commit()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(test_db: Session):
    app = create_app()

    def override_get_session():
        yield test_db

    app.dependency_overrides[get_session] = override_get_session
    return TestClient(app)


def _auth_headers() -> dict[str, str]:
    settings = get_settings()
    token = create_session_token(
        {
            "sub": "user-admin-01",
            "user_id": "user-admin-01",
            "email": "admin@kiwi.test",
            "roles": ["Admin Rol"],
            "permissions": ["admin.manage", "catalog.manage", "orders.create"],
            "scope": "organization",
        },
        settings.secret_key,
    )
    return {"Authorization": f"Bearer {token}"}


def test_branch_defaults_update_and_schedule_validation(client: TestClient, test_db: Session):
    headers = _auth_headers()
    create_resp = client.post(
        "/api/v1/branches",
        headers=headers,
        json={
            "name": "Centro",
            "code": "SUC01",
            "business_unit_id": "unit-kiwi-01",
        },
    )
    assert create_resp.status_code == 200, create_resp.text
    created = create_resp.json()
    branch_id = created["id"]
    assert created["operating_hours"] == default_branch_operating_hours()

    list_resp = client.get("/api/v1/branches", headers=headers)
    assert list_resp.status_code == 200
    assert list_resp.json()[0]["operating_hours"] == default_branch_operating_hours()

    hours_resp = client.get(f"/api/v1/branches/{branch_id}/operating-hours", headers=headers)
    assert hours_resp.status_code == 200
    assert hours_resp.json()["operating_hours"] == default_branch_operating_hours()

    # Validate in branch timezone (America/Chihuahua)
    tz = ZoneInfo("America/Chihuahua")
    # Monday 10:00 -> open
    mon_open = datetime(2026, 11, 16, 10, 0, tzinfo=tz)
    assert validate_branch_open_at(test_db, branch_id, mon_open)["open"] is True

    # Saturday 07:15 -> closed (opens at 07:30)
    sat_early = datetime(2026, 11, 21, 7, 15, tzinfo=tz)
    with pytest.raises(BusinessError, match="07:30") as exc_sat:
        validate_branch_open_at(test_db, branch_id, sat_early)
    assert exc_sat.value.code == "branch_closed_at_scheduled_time"

    # Sunday 12:00 -> closed
    sun_noon = datetime(2026, 11, 22, 12, 0, tzinfo=tz)
    with pytest.raises(BusinessError) as exc_sun:
        validate_branch_open_at(test_db, branch_id, sun_noon)
    assert exc_sun.value.code == "branch_closed_at_scheduled_time"

    # Past time check
    with pytest.raises(BusinessError) as exc_past:
        validate_branch_open_at(
            test_db,
            branch_id,
            mon_open,
            now_utc=datetime(2026, 11, 16, 17, 0, tzinfo=timezone.utc),
            min_lead_minutes=30,
        )
    assert exc_past.value.code == "scheduled_time_in_past"

    # Reject invalid update (open_time >= close_time)
    bad_hours = default_branch_operating_hours()
    bad_hours[0] = {"day_of_week": 0, "is_open": True, "open_time": "18:00", "close_time": "07:00"}
    bad_resp = client.put(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"operating_hours": bad_hours},
    )
    assert bad_resp.status_code == 409
    assert bad_resp.json()["detail"]["code"] == "invalid_branch_operating_hours"

    # Valid update: open Sunday 08:00-14:00
    custom_hours = default_branch_operating_hours()
    custom_hours[6] = {
        "day_of_week": 6,
        "is_open": True,
        "open_time": "08:00",
        "close_time": "14:00",
    }
    ok_resp = client.put(
        f"/api/v1/branches/{branch_id}",
        headers=headers,
        json={"operating_hours": custom_hours},
    )
    assert ok_resp.status_code == 200, ok_resp.text
    assert ok_resp.json()["operating_hours"][6] == custom_hours[6]
    assert validate_branch_open_at(test_db, branch_id, sun_noon)["open"] is True


def test_migration_0106_upgrade_and_downgrade(tmp_path, monkeypatch):
    db_path = tmp_path / "mig_0106.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    get_settings.cache_clear()
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    command.upgrade(cfg, "0105_mcp_oauth_bindings")

    engine = create_engine(f"sqlite:///{db_path}")
    now = datetime.now(timezone.utc)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, status, created_at, updated_at) "
                "VALUES ('org-1', 'Kiwi', 'active', :now, :now)"
            ),
            {"now": now},
        )
        conn.execute(
            sa.text(
                "INSERT INTO legal_entities "
                "(id, organization_id, name, status, created_at, updated_at) "
                "VALUES ('le-1', 'org-1', 'Kiwi SA', 'active', :now, :now)"
            ),
            {"now": now},
        )
        conn.execute(
            sa.text(
                "INSERT INTO business_units "
                "(id, organization_id, legal_entity_id, name, code, unit_type, status, "
                "created_at, updated_at) "
                "VALUES ('bu-1', 'org-1', 'le-1', 'Ops', 'OPS', 'restaurant', 'active', "
                ":now, :now)"
            ),
            {"now": now},
        )
        conn.execute(
            sa.text(
                "INSERT INTO branches "
                "(id, organization_id, legal_entity_id, business_unit_id, name, code, "
                "timezone, status, pos_catalog_visuals_enabled, created_at, updated_at) "
                "VALUES ('br-1', 'org-1', 'le-1', 'bu-1', 'Centro', 'SUC01', "
                "'America/Chihuahua', 'active', 1, :now, :now)"
            ),
            {"now": now},
        )

    command.upgrade(cfg, "0106_branch_operating_hours")
    with engine.connect() as conn:
        rows = conn.execute(
            sa.text(
                "SELECT day_of_week, is_open, open_time, close_time "
                "FROM branch_operating_hours WHERE branch_id = 'br-1' ORDER BY day_of_week"
            )
        ).fetchall()
    assert len(rows) == 7
    assert rows[0] == (0, 1, "07:00", "18:00")
    assert rows[5] == (5, 1, "07:30", "16:00")
    assert rows[6] == (6, 0, None, None)

    command.downgrade(cfg, "0105_mcp_oauth_bindings")
    inspector = sa.inspect(engine)
    assert "branch_operating_hours" not in inspector.get_table_names()
