"""Synthetic local browser database; never accepts an existing or non-test database."""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.auth import create_session_token
from sqlalchemy.orm import Session
from test_platform_api import ADMIN_ROLE_ID, ADMIN_USER_ID, _seed

path = Path(sys.argv[1]).resolve()
if path.name != "delivery_fee_browser.sqlite" or path.exists():
    raise RuntimeError("A fresh, explicitly named browser fixture is required")
engine = sa.create_engine("sqlite:///" + path.as_posix())
models.metadata.create_all(engine)
with Session(engine) as session:
    _seed(session)
    permission = session.scalar(
        sa.select(models.permissions.c.id).where(models.permissions.c.code == "reports.sales.read")
    )
    if permission is None:
        permission = "delivery-browser-report-permission"
        session.execute(
            models.permissions.insert().values(
                id=permission,
                code="reports.sales.read",
                description="Synthetic browser report fixture",
                created_at=datetime.now(timezone.utc),
            )
        )
    if not session.scalar(
        sa.select(models.role_permissions.c.role_id).where(
            models.role_permissions.c.role_id == ADMIN_ROLE_ID,
            models.role_permissions.c.permission_id == permission,
        )
    ):
        session.execute(
            models.role_permissions.insert().values(role_id=ADMIN_ROLE_ID, permission_id=permission)
        )
    session.commit()
engine.dispose()
print(
    json.dumps(
        {
            "token": create_session_token(
                {"sub": ADMIN_USER_ID}, os.environ["RESTAURANTOS_SECRET_KEY"]
            )
        }
    )
)
