from __future__ import annotations

# ruff: noqa: E501
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

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
    _failure_hook: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Validate an internal, explicit seed manifest without exposing an HTTP surface."""
    if set(manifest) != {"organization_id", "environment", "operations"}:
        raise ValueError("seed_manifest_invalid")
    if (
        manifest["environment"] not in {"development", "test", "staging"}
        or not isinstance(manifest["organization_id"], str)
        or not manifest["organization_id"].strip()
        or not isinstance(manifest["operations"], list)
        or not isinstance(actor_id, str)
        or not actor_id.strip()
    ):
        raise ValueError("seed_manifest_invalid")
    operations = manifest["operations"]
    if any(
        not isinstance(operation, dict)
        or set(operation) != {"type", "id", "name"}
        or operation["type"] != "ensure_organization"
        or not isinstance(operation["id"], str)
        or not operation["id"].strip()
        or not isinstance(operation["name"], str)
        or not operation["name"].strip()
        for operation in operations
    ):
        raise ValueError("seed_manifest_invalid")
    if any(operation["id"] != manifest["organization_id"] for operation in operations):
        raise ValueError("seed_manifest_invalid")
    manifest_id = hashlib.sha256(
        json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    _require_migrated_schema(session)
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
        try:
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
                            name=operation["name"].strip(),
                            status="active",
                            created_at=now,
                            updated_at=now,
                        )
                    )
            if _failure_hook:
                _failure_hook()
            persisted_actor = session.execute(
                sa.select(models.users.c.id).where(
                    models.users.c.id == actor_id,
                    models.users.c.organization_id == manifest["organization_id"],
                    models.users.c.status == "active",
                )
            ).scalar_one_or_none()
            _audit(
                session,
                action="internal_seed.applied",
                entity_type="seed_manifest",
                entity_id=manifest_id,
                payload={
                    "operation_count": len(manifest["operations"]),
                    "operator_id": actor_id,
                },
                branch_id=None,
                organization_id=str(manifest["organization_id"]),
                actor_user_id=persisted_actor,
            )
            session.commit()
        except Exception:
            session.rollback()
            raise
    return result


def _require_migrated_schema(session: Session) -> None:
    table_names = set(sa.inspect(session.get_bind()).get_table_names())
    if not {"organizations", "users", "audit_events"} <= table_names:
        raise ValueError("seed_database_not_migrated")


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
    with Session(engine) as session:
        result = apply_manifest(session, manifest, apply=args.apply, actor_id=args.actor)
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    main()
