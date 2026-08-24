"""TDD test suite for extended supplier fields (phone, supplier_type, address, postal_code, email, status, accounting_reference)."""

# ruff: noqa: E501

from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import (
    ORGANIZATION_ID,
    create_supplier,
    delete_supplier,
    list_suppliers,
    update_supplier,
)
from sqlalchemy.orm import Session

SUPERADMIN_ID = "018f6f73-2d0a-74f0-8f1c-000000000002"


@pytest.fixture
def setup_db(tmp_path: Path):
    db_path = tmp_path / "test_suppliers.db"
    engine = sa.create_engine(f"sqlite:///{db_path}")
    models.metadata.create_all(engine)
    now = sa.func.now()
    with Session(engine) as session:
        session.execute(models.organizations.insert().values(
            id=ORGANIZATION_ID,
            name="Kiwi Natural Org",
            status="active",
            created_at=now,
            updated_at=now,
        ))
        session.execute(models.users.insert().values(
            id=SUPERADMIN_ID,
            organization_id=ORGANIZATION_ID,
            email="superadmin@kiwi.local",
            display_name="Super Admin",
            status="active",
            created_at=now,
            updated_at=now,
        ))
        session.execute(models.permissions.insert().values([
            {"id": "p1", "code": "catalog.manage", "description": "Manage catalog", "created_at": now},
            {"id": "p2", "code": "purchases.read", "description": "Read purchases", "created_at": now},
            {"id": "p3", "code": "admin.manage", "description": "Manage admin", "created_at": now},
        ]))
        session.execute(models.roles.insert().values(
            id="r-admin",
            organization_id=ORGANIZATION_ID,
            name="Dueño",
            scope="organization",
            created_at=now,
        ))
        session.execute(models.role_permissions.insert().values([
            {"role_id": "r-admin", "permission_id": "p1"},
            {"role_id": "r-admin", "permission_id": "p2"},
            {"role_id": "r-admin", "permission_id": "p3"},
        ]))
        session.execute(models.user_roles.insert().values(
            user_id=SUPERADMIN_ID,
            role_id="r-admin",
            branch_id=None,
        ))
        session.commit()
    return engine


def test_create_supplier_with_all_extended_fields(setup_db: sa.Engine):
    with Session(setup_db) as session:
        supplier = create_supplier(
            session,
            payload={
                "code": "PROV-001",
                "commercial_name": "Carnes Selectas de Culiacan",
                "legal_name": "Carnes del Noroeste SA de CV",
                "tax_id": "CNO900101XYZ",
                "address": "Av. Alvaro Obregon 1234, Col. Centro",
                "postal_code": "80000",
                "municipality": "Culiacan",
                "state": "Sinaloa",
                "phone": "6671234567",
                "email": "ventas@carnesnoroeste.com",
                "supplier_type": "insumos",
                "status": "active",
                "accounting_reference": "201-01-001",
                "credit_days": 15,
            },
            actor_user_id=SUPERADMIN_ID,
        )

        assert supplier["code"] == "PROV-001"
        assert supplier["commercial_name"] == "Carnes Selectas de Culiacan"
        assert supplier["fiscal_address"] == "Av. Alvaro Obregon 1234, Col. Centro"
        assert supplier["fiscal_postal_code"] == "80000"
        assert supplier["phone"] == "6671234567"
        assert supplier["billing_email"] == "ventas@carnesnoroeste.com"
        assert supplier["supplier_type"] == "insumos"
        assert supplier["status"] == "active"
        assert supplier["accounting_reference"] == "201-01-001"
        assert supplier["credit_days"] == 15


def test_update_supplier_extended_fields(setup_db: sa.Engine):
    with Session(setup_db) as session:
        supplier = create_supplier(
            session,
            payload={
                "code": "PROV-002",
                "commercial_name": "Empaques Sinaloa",
                "phone": "6677000000",
                "supplier_type": "empaque",
            },
            actor_user_id=SUPERADMIN_ID,
        )

        updated = update_supplier(
            session,
            supplier_id=supplier["id"],
            payload={
                "phone": "6679998877",
                "address": "Blvd. Zapata 555, Col. El Palmito",
                "postal_code": "80160",
                "email": "contacto@empaquessinaloa.com",
                "accounting_reference": "201-02-005",
                "status": "active",
            },
            actor_user_id=SUPERADMIN_ID,
        )

        assert updated["phone"] == "6679998877"
        assert updated["fiscal_address"] == "Blvd. Zapata 555, Col. El Palmito"
        assert updated["fiscal_postal_code"] == "80160"
        assert updated["billing_email"] == "contacto@empaquessinaloa.com"
        assert updated["accounting_reference"] == "201-02-005"


def test_delete_supplier_deactivates(setup_db: sa.Engine):
    with Session(setup_db) as session:
        supplier = create_supplier(
            session,
            payload={
                "code": "PROV-003",
                "commercial_name": "Servicios de Limpieza",
                "supplier_type": "servicios",
            },
            actor_user_id=SUPERADMIN_ID,
        )

        res = delete_supplier(session, supplier["id"], actor_user_id=SUPERADMIN_ID)
        assert res["status"] == "inactive"

        all_suppliers = list_suppliers(session)
        matching = next(s for s in all_suppliers if s["id"] == supplier["id"])
        assert matching["status"] == "inactive"


def test_supplier_api_endpoints(setup_db: sa.Engine):
    app = create_app()

    def override_session():
        with Session(setup_db) as s:
            yield s

    app.dependency_overrides[get_session] = override_session
    client = TestClient(app)
    headers = {"X-Actor-User-Id": SUPERADMIN_ID}

    # POST create
    post_res = client.post(
        "/api/v1/suppliers",
        json={
            "code": "PROV-API-01",
            "commercial_name": "Frutería La Palma",
            "tax_id": "FLP880101ABC",
            "address": "Mercado de Abastos Nave 3 Loc 12",
            "postal_code": "80290",
            "phone": "6673334455",
            "email": "abastos@fruterialapalma.com",
            "supplier_type": "insumos",
            "status": "active",
            "accounting_reference": "201-01-045",
        },
        headers=headers,
    )
    assert post_res.status_code == 200, post_res.text
    supplier_id = post_res.json()["id"]

    # PUT update
    put_res = client.put(
        f"/api/v1/suppliers/{supplier_id}",
        json={
            "phone": "6679991122",
            "notes": "Entrega de 6 a 9 am",
        },
        headers=headers,
    )
    assert put_res.status_code == 200, put_res.text
    assert put_res.json()["phone"] == "6679991122"

    # GET list
    get_res = client.get("/api/v1/suppliers", headers=headers)
    assert get_res.status_code == 200
    items = get_res.json()
    item = next(s for s in items if s["id"] == supplier_id)
    assert item["phone"] == "6679991122"
    assert item["fiscal_address"] == "Mercado de Abastos Nave 3 Loc 12"
    assert item["accounting_reference"] == "201-01-045"
    assert item["supplier_type"] == "insumos"

    # DELETE
    del_res = client.delete(f"/api/v1/suppliers/{supplier_id}", headers=headers)
    assert del_res.status_code == 200
    assert del_res.json()["status"] == "inactive"

    app.dependency_overrides.clear()
