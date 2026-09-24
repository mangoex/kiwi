"""Reviewable, resumable classification mapping through the canonical HTTP command.

Default is dry-run. Token is read from RESTAURANTOS_API_TOKEN and never printed.
The input is the groups array exported by GET /catalog/classification-rollout, edited by a human.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener


def mapping_commands(rows: Any) -> list[dict[str, Any]]:
    if not isinstance(rows, list) or not rows:
        raise ValueError("mapping must be a nonempty array")
    seen: set[str] = set()
    commands = []
    for row in rows:
        if not isinstance(row, dict) or set(row) - {"name"} != {
            "id",
            "classification_code",
            "configuration_version",
            "status",
        }:
            raise ValueError("use the groups array from rollout status")
        identifier = row["id"]
        version = row["configuration_version"]
        if not isinstance(identifier, str) or not identifier or identifier in seen:
            raise ValueError("duplicate or invalid category id")
        if (
            type(version) is not int
            or version < 1
            or row["classification_code"] not in ("food", "drinks", "other")
        ):
            raise ValueError("each row requires an explicit classification and expected version")
        seen.add(identifier)
        payload = {"classification_code": row["classification_code"], "expected_version": version}
        digest = hashlib.sha256(
            json.dumps([identifier, payload], sort_keys=True).encode()
        ).hexdigest()
        commands.append(
            {
                "category_id": identifier,
                "group_name": row.get("name"),
                "payload": payload,
                "idempotency_key": "classification-mapping-" + digest,
            }
        )
    return commands


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(
        self, req: Any, fp: Any, code: int, msg: str, headers: Any, newurl: str
    ) -> None:
        # Never forward the bearer token to a redirect destination.
        return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mapping", type=Path)
    parser.add_argument("--url", help="API origin, HTTPS except local test servers")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    commands = mapping_commands(json.loads(args.mapping.read_text(encoding="utf-8-sig")))
    if not args.apply:
        print(json.dumps({"mode": "dry-run", "commands": commands}, indent=2))
        return 0
    origin = urlparse(args.url or "")
    if (
        origin.username
        or origin.password
        or origin.query
        or origin.fragment
        or origin.path not in ("", "/")
        or not origin.hostname
        or (
            origin.scheme != "https"
            and not (origin.scheme == "http" and origin.hostname in ("127.0.0.1", "localhost"))
        )
    ):
        parser.error("--apply requires a valid HTTPS origin (HTTP only for localhost)")
    token = os.environ.get("RESTAURANTOS_API_TOKEN")
    if not token:
        parser.error("RESTAURANTOS_API_TOKEN is required")
    for command in commands:
        # IDs are path segments, never permit a supplied URL or path traversal.
        from urllib.parse import quote

        url = (
            (args.url or "").rstrip("/")
            + "/api/v1/categories/"
            + quote(command["category_id"], safe="")
        )
        request = Request(
            url,
            data=json.dumps(command["payload"]).encode(),
            method="PUT",
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/json",
                "Idempotency-Key": command["idempotency_key"],
            },
        )
        try:
            with build_opener(ProxyHandler({}), NoRedirect()).open(request, timeout=15) as response:
                result = json.load(response)
        except HTTPError as exc:
            print(
                json.dumps(
                    {
                        "status": "stopped",
                        "category_id": command["category_id"],
                        "http_status": exc.code,
                    }
                )
            )
            return 1
        print(
            json.dumps(
                {
                    "status": "confirmed",
                    "category_id": result["id"],
                    "version": result["configuration_version"],
                }
            )
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
