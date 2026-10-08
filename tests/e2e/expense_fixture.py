"""Create synthetic EXP-001 browser data. Refuses existing database via base fixture."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4


def main():
    root = Path(__file__).resolve().parents[2]
    subprocess.run(
        [sys.executable, str(root / "tests/e2e/admin_retro_fixture.py"), *sys.argv[1:]], check=True
    )
    manifest_path = Path(sys.argv[sys.argv.index("--manifest") + 1])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["synthetic_only"] is True
    os.environ["RESTAURANTOS_ENVIRONMENT"] = "test"
    sys.path.insert(0, str(root / "apps/api"))
    import sqlalchemy as sa
    from restaurant_os import models
    from restaurant_os.operations import _now

    engine = sa.create_engine(manifest["database_url"])
    with engine.begin() as connection:
        for code in (
            "expense.concept.read",
            "expense.concept.manage",
            "expenses.read",
            "expenses.manage",
            "expenses.cancel",
            "reports.expenses.read",
            "cash.movement.withdraw",
            "cash.movement.compensate",
        ):
            if connection.scalar(
                sa.select(models.permissions.c.id).where(models.permissions.c.code == code)
            ):
                continue
            connection.execute(
                models.permissions.insert().values(
                    id=str(uuid4()), code=code, description=code, created_at=_now()
                )
            )
    engine.dispose()


if __name__ == "__main__":
    main()
