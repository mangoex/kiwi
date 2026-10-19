"""Disposable, loopback-only real API fixture for INV-VIEW browser regression."""

import os
from collections.abc import Generator
from pathlib import Path
from tempfile import TemporaryDirectory

import uvicorn
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from test_inventory_overview import ITEM, movement
from test_platform_api import (
    ADMIN_USER_ID,
    _admin_headers,
    _branch_admin_fixture,
    _seed,
    _test_session_factory,
)

# Uvicorn handles concurrent requests. Each session needs its own connection rather
# than the single DBAPI connection used by the in-memory unit-test StaticPool.
fixture_directory = TemporaryDirectory(prefix="restaurantos-inventory-browser-")
database_path = Path(fixture_directory.name) / "inventory.sqlite"
engine = create_engine(
    f"sqlite+pysqlite:///{database_path.as_posix()}",
    connect_args={"check_same_thread": False},
)
models.metadata.create_all(engine)
session_factory = sessionmaker(bind=engine, expire_on_commit=False)
with session_factory() as session:
    _seed(session)
app = create_app()


def fixture_session() -> Generator[Session, None, None]:
    with session_factory() as session:
        yield session


app.dependency_overrides[get_session] = fixture_session
app.state.test_session_factory = session_factory
client = TestClient(app)
branch = _branch_admin_fixture(client)
with _test_session_factory(client)() as session:
    # Keep the operational fallback at the original branch, independently of the query target.
    session.execute(
        models.branches.update()
        .where(models.branches.c.id == branch["branch_id"])
        .values(code="ZZ-NORTE")
    )
    movement(session, branch["branch_id"], branch["warehouse_id"], "OPENING_BALANCE", "10")
    movement(session, branch["branch_id"], branch["warehouse_id"], "SALE_RESERVATION", "-3")
    session.commit()
response = client.put(
    f"/api/v1/admin-catalog/stock-thresholds/{ITEM}?branch_id={branch['branch_id']}",
    headers=_admin_headers(),
    json={"minimum_quantity": "12.345678", "maximum_quantity": "20", "expected_version": None},
)
assert response.status_code == 200, response.text


@app.post("/__inventory_shutdown")
def shutdown():
    server.should_exit = True
    return {"stopping": True}


@app.get("/__inventory_fixture")
def fixture():
    return {
        "token": _admin_headers()["Authorization"].removeprefix("Bearer "),
        "north_id": branch["branch_id"],
        "item_id": ITEM,
        "admin_id": ADMIN_USER_ID,
        "local_token": create_session_token(
            {"sub": branch["supervisor_id"]}, get_settings().secret_key
        ),
    }


if __name__ == "__main__":
    server = uvicorn.Server(
        uvicorn.Config(
            app, host="127.0.0.1", port=int(os.environ.get("INV_VIEW_FIXTURE_PORT", "39993"))
        )
    )
    try:
        server.run()
    finally:
        engine.dispose()
        fixture_directory.cleanup()
