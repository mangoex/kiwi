"""Local-only synthetic mobile journey; never connects to a delivery provider."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from shutil import copytree


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=8158)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]
    directory = args.directory.resolve()
    if directory.exists():
        raise RuntimeError("Refusing to reuse a customer fixture")
    directory.mkdir(parents=True)
    for app in ("mobile-web", "admin-web"):
        copytree(root / "apps" / app / "dist", directory / "static" / app)
    os.environ["STATIC_DIR"] = str(directory / "static")
    os.environ["RESTAURANTOS_ENVIRONMENT"] = "test"
    os.environ["RESTAURANTOS_MOBILE_CUSTOMER_ACCESS_ENABLED"] = "false"
    os.environ["RESTAURANTOS_REDIS_URL"] = ""
    sys.path[:0] = [str(root / "apps/api"), str(root / "apps/api/tests")]
    import uvicorn
    from restaurant_os.auth import create_session_token
    from restaurant_os.config import get_settings
    from test_mobile_customer_profile import client_with_mobile
    from test_platform_api import ADMIN_USER_ID

    client = client_with_mobile()
    (directory / "manifest.json").write_text(
        json.dumps(
            {
                "synthetic_only": True,
                "token": create_session_token({"sub": ADMIN_USER_ID}, get_settings().secret_key),
            }
        ),
        encoding="utf-8",
    )
    uvicorn.run(client.app, host="127.0.0.1", port=args.port, access_log=False)


if __name__ == "__main__":
    main()
