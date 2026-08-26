#!/usr/bin/env python3
"""Execute one explicit cross-branch denial through the local API boundary."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import httpx


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--base-url", default="http://127.0.0.1:8765")
    args = parser.parse_args()
    if args.base_url != "http://127.0.0.1:8765":
        raise RuntimeError("This test only permits the isolated local API")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    if manifest.get("database_name") != "kiwi_cashier_e2e" or not manifest.get("synthetic_only"):
        raise RuntimeError("Refusing non-synthetic cross-branch evidence")

    actor, attempted = manifest["cashiers"][1:3]
    line = manifest["account_matrix"][0]["lines"][0]
    request_key = "pg-e2e-cross-branch-denied-v2"
    started_at = datetime.now(timezone.utc).isoformat()
    with httpx.Client(base_url=args.base_url, timeout=30) as client:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": actor["email"], "password": actor["password"]},
        )
        login.raise_for_status()
        response = client.post(
            "/api/v1/orders",
            headers={
                "Authorization": f"Bearer {login.json()['token']}",
                "Idempotency-Key": request_key,
            },
            json={
                "branch_id": attempted["branch_id"],
                "lines": [{"product_id": line["product_id"], "quantity": 1}],
            },
        )
    completed_at = datetime.now(timezone.utc).isoformat()
    body = response.json()
    if response.status_code != 403 or body["detail"]["code"] != "permission_denied":
        raise AssertionError(f"Unexpected cross-branch response: {response.status_code} {body}")
    result = {
        "status": "ok",
        "executed": True,
        "started_at_utc": started_at,
        "completed_at_utc": completed_at,
        "request_key": request_key,
        "actor_user_id": actor["user_id"],
        "actor": actor["email"],
        "actor_branch": actor["branch_code"],
        "attempted_branch_id": attempted["branch_id"],
        "attempted_branch": attempted["branch_code"],
        "http_status": response.status_code,
        "error_code": body["detail"]["code"],
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
