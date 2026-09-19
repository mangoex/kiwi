# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-admin-retro-e2e-v1
#!/usr/bin/env python3
"""Create an isolated SQLite fixture for the ADMIN-RETRO browser journey.

The fixture refuses an existing path, uses only the canonical test seed, and
prints no credentials beyond the deliberate synthetic manifest it writes.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000003"
ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
PRODUCT_IDS = [
    "018f6f73-2d0a-74f0-8f1c-000000000111",
    "018f6f73-2d0a-74f0-8f1c-000000000112",
]
UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
USER_ID = "018f6f73-2d0a-74f0-8f1c-000000000006"
EMAIL = "qa.adminretro@example.invalid"
PASSWORD = "QA-AdminRetro-2026!"


def _load_platform_seed(repo_root: Path) -> Any:
    module_path = repo_root / "apps/api/tests/test_platform_api.py"
    spec = importlib.util.spec_from_file_location("adminretro_platform_seed", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load synthetic seed from {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module._seed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    args = parser.parse_args()
    database_path = args.database.resolve()
    manifest_path = args.manifest.resolve()
    if database_path.exists() or manifest_path.exists():
        raise SystemExit("Refusing to overwrite an ADMIN-RETRO synthetic fixture")
    database_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)

    repo_root = Path(__file__).resolve().parents[2]
    sys.path.insert(0, str(repo_root / "apps/api"))
    os.environ["RESTAURANTOS_ENVIRONMENT"] = "test"
    os.environ["RESTAURANTOS_DATABASE_URL"] = f"sqlite+pysqlite:///{database_path}"
    os.environ["RESTAURANTOS_SECRET_KEY"] = "admin-retro-e2e-local-only-secret-key"

    import sqlalchemy as sa
    from restaurant_os import models
    from restaurant_os.auth import generate_password_salt, hash_password
    from sqlalchemy.orm import Session

    engine = sa.create_engine(os.environ["RESTAURANTOS_DATABASE_URL"])
    try:
        models.metadata.create_all(engine)
        with Session(engine) as session:
            _load_platform_seed(repo_root)(session)
            salt = generate_password_salt()
            session.execute(
                models.users.update()
                .where(models.users.c.id == USER_ID)
                .values(email=EMAIL, display_name="Administradora QA Retro")
            )
            session.execute(
                models.user_credentials.update()
                .where(models.user_credentials.c.user_id == USER_ID)
                .values(password_hash=hash_password(PASSWORD, salt), password_salt=salt)
            )
            corporate_role_id = session.execute(
                sa.select(models.user_roles.c.role_id)
                .join(models.roles, models.roles.c.id == models.user_roles.c.role_id)
                .where(
                    models.user_roles.c.user_id == USER_ID,
                    models.roles.c.scope == "organization",
                )
            ).scalar_one()
            authority_exists = session.execute(
                sa.select(models.role_authority_grants.c.role_id).where(
                    models.role_authority_grants.c.role_id == corporate_role_id
                )
            ).scalar_one_or_none()
            if authority_exists is None:
                session.execute(
                    models.role_authority_grants.insert().values(
                        role_id=corporate_role_id,
                        authority_kind="organization_all_permissions",
                        created_at=datetime.now(timezone.utc),
                    )
                )
            session.commit()
    finally:
        engine.dispose()

    manifest = {
        "schema_version": 1,
        "synthetic_only": True,
        "database_url": os.environ["RESTAURANTOS_DATABASE_URL"],
        "api_port": 8002,
        "admin_base_url": "http://127.0.0.1:8002/admin",
        "login": {"email": EMAIL, "password": PASSWORD},
        "branch_id": BRANCH_ID,
        "item_id": ITEM_ID,
        "product_ids": PRODUCT_IDS,
        "unit_id": UNIT_ID,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
