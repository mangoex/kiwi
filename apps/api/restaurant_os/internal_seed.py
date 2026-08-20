from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import _audit


def apply_manifest(
    session: Session,
    manifest: dict[str, Any],
    *,
    apply: bool,
    actor_id: str,
) -> dict[str, Any]:
    """Validate an internal, explicit seed manifest without exposing an HTTP surface."""
    if set(manifest) != {"organization_id", "environment", "operations"}:
        raise ValueError("seed_manifest_invalid")
    if (
        manifest["environment"] == "production"
        or not isinstance(manifest["operations"], list)
        or not actor_id
    ):
        raise ValueError("seed_manifest_invalid")
    operations = manifest["operations"]
    if any(
        set(operation) != {"type", "id", "name"} or operation["type"] != "ensure_organization"
        for operation in operations
    ):
        raise ValueError("seed_manifest_invalid")
    if any(operation["id"] != manifest["organization_id"] for operation in operations):
        raise ValueError("seed_manifest_invalid")
    manifest_id = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    result = {"dry_run": not apply, "operations": len(manifest["operations"]), "replayed": False}
    if apply:
        existing = session.execute(
            sa.select(models.audit_events.c.id).where(
                models.audit_events.c.action == "internal_seed.applied",
                models.audit_events.c.entity_id == manifest_id,
            )
        ).first()
        if existing:
            return {**result, "replayed": True}
        for operation in operations:
            row = session.execute(
                sa.select(models.organizations.c.id).where(
                    models.organizations.c.id == operation["id"]
                )
            ).first()
            if not row:
                now = datetime.now(timezone.utc)
                session.execute(
                    models.organizations.insert().values(
                        id=operation["id"],
                        name=operation["name"],
                        status="active",
                        created_at=now,
                        updated_at=now,
                    )
                )
        _audit(
            session,
            action="internal_seed.applied",
            entity_type="seed_manifest",
            entity_id=manifest_id,
            payload={"operation_count": len(manifest["operations"]), "actor_id": actor_id},
            organization_id=str(manifest["organization_id"]),
        )
        session.commit()
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--actor", required=True)
    parser.add_argument("--confirm-environment", required=True)
    parser.add_argument("--sqlite-url", required=True)
    args = parser.parse_args()
    manifest = json.loads(Path(args.manifest).read_text())
    if manifest.get("environment") != args.confirm_environment:
        raise SystemExit("seed_environment_confirmation_required")
    if manifest["environment"] == "production" or not args.sqlite_url.startswith("sqlite"):
        raise SystemExit("seed_environment_denied")
    engine = create_engine(args.sqlite_url)
    models.metadata.create_all(engine)
    with Session(engine) as session:
        result = apply_manifest(session, manifest, apply=args.apply, actor_id=args.actor)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
