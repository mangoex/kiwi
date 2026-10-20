"""Run the public tracking browser journey against a fresh, local SQLite fixture."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
from pathlib import Path
from uuid import uuid4


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8149)
    args = parser.parse_args()
    directory = args.directory.resolve()
    directory.mkdir(parents=True, exist_ok=True)
    database = directory / "tracking.sqlite"
    manifest = directory / "manifest.json"
    if database.exists() or manifest.exists():
        raise RuntimeError("Refusing to reuse a public tracking fixture")
    root = Path(__file__).resolve().parents[2]
    sys.path[:0] = [str(root / "apps/api"), str(root / "apps/api/tests")]
    os.environ["RESTAURANTOS_ENVIRONMENT"] = "test"
    os.environ["RESTAURANTOS_DATABASE_URL"] = f"sqlite+pysqlite:///{database}"
    os.environ.pop("DATABASE_URL", None)
    os.environ["RESTAURANTOS_REDIS_URL"] = ""
    os.environ["RESTAURANTOS_SECRET_KEY"] = secrets.token_urlsafe(48)
    os.environ["RESTAURANTOS_PUBLIC_ORDER_INTENTS_ENABLED"] = "true"

    # serve_spa expects STATIC_DIR/mobile-web; use a fixture-specific copy of dist.
    from shutil import copytree

    import sqlalchemy as sa
    import uvicorn
    from restaurant_os import models
    from restaurant_os.auth import create_session_token
    from restaurant_os.config import get_settings
    from restaurant_os.main import create_app
    from restaurant_os.public_order_rate_limit import InMemoryPublicOrderRateLimiter
    from sqlalchemy.orm import Session
    from test_mobile_customer_profile import Verifier
    from test_platform_api import ADMIN_USER_ID, BRANCH_ID, ORGANIZATION_ID, _seed

    static = directory / "static"
    copytree(root / "apps/mobile-web/dist", static / "mobile-web")
    os.environ["STATIC_DIR"] = str(static)
    get_settings.cache_clear()
    engine = sa.create_engine(os.environ["RESTAURANTOS_DATABASE_URL"])
    other_id, public_key = str(uuid4()), f"tracking-fixture-{uuid4().hex}"
    try:
        models.metadata.create_all(engine)
        with Session(engine) as session:
            _seed(session)
            branch = dict(session.execute(sa.select(models.branches).where(
                models.branches.c.id == BRANCH_ID,
            )).mappings().one())
            branch.update(id=other_id, code="TRACKING-NORTE", name="Norte")
            session.execute(models.branches.insert().values(**branch))
            for branch_id, key in ((BRANCH_ID, public_key), (other_id, public_key + "-north")):
                session.execute(models.public_order_keys.insert().values(
                    public_key=key, organization_id=ORGANIZATION_ID, branch_id=branch_id,
                    status="active",
                ))
            session.commit()
    finally:
        engine.dispose()
    manifest.write_text(json.dumps({
        "synthetic_only": True, "branch_id": BRANCH_ID, "other_branch_id": other_id,
        "public_key": public_key, "product_id": "018f6f73-2d0a-74f0-8f1c-000000000111",
        "token": create_session_token({"sub": ADMIN_USER_ID}, get_settings().secret_key),
    }), encoding="utf-8")
    app = create_app()
    app.state.mobile_customer_access_enabled = True
    app.state.mobile_phone_verifier = Verifier()
    app.state.mobile_customer_rate_limiter = InMemoryPublicOrderRateLimiter(
        300, 15, get_settings().secret_key
    )
    uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
