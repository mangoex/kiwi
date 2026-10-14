"""Controlled preparation of existing offline authority; no automatic readiness."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.branch_workspaces import _lock_actor
from restaurant_os.offline_authorization import (
    LEGACY_TTL,
    _utc,
    authority_now,
    registry_available,
    rollback_reconciliation,
)
from restaurant_os.order_execution import without_order_execution_context


def cutover_matches(row: Mapping[str, Any], started: datetime, drained: datetime) -> bool:
    return (
        _utc(row["registration_started_at"]) == started
        and _utc(row["legacy_drain_until"]) == drained
        and drained == started + LEGACY_TTL
        and bool(re.fullmatch(r"[0-9a-f]{64}", row["retirement_evidence_sha256"]))
    )


def _receipt(row: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "organization_id": row["organization_id"],
        "state": "draining",
        "registration_started_at": _utc(row["registration_started_at"]).isoformat(),
        "legacy_drain_until": _utc(row["legacy_drain_until"]).isoformat(),
    }


def _import_retained(session: Session, now: datetime) -> int:
    source = models.offline_order_grants
    rows = (
        session.execute(
            sa.select(source)
            .where(
                source.c.organization_id == ops.ORGANIZATION_ID,
                ~sa.exists(
                    sa.select(models.offline_authorization_leases.c.id).where(
                        models.offline_authorization_leases.c.organization_id
                        == source.c.organization_id,
                        models.offline_authorization_leases.c.source_grant_id == source.c.id,
                    )
                ),
            )
            .order_by(source.c.id)
            .with_for_update()
        )
        .mappings()
        .all()
    )
    for row in rows:
        started, expires = _utc(row["issued_at"]), _utc(row["expires_at"])
        bindings = session.execute(
            sa.select(source.c.id)
            .select_from(
                source.join(
                    models.users,
                    sa.and_(
                        models.users.c.id == source.c.actor_id,
                        models.users.c.organization_id == source.c.organization_id,
                    ),
                )
                .join(
                    models.branches,
                    sa.and_(
                        models.branches.c.id == source.c.branch_id,
                        models.branches.c.organization_id == source.c.organization_id,
                    ),
                )
                .join(
                    models.device_credentials,
                    sa.and_(
                        models.device_credentials.c.id == source.c.device_id,
                        models.device_credentials.c.organization_id == source.c.organization_id,
                        models.device_credentials.c.branch_id == source.c.branch_id,
                    ),
                )
                .join(
                    models.offline_order_bundles,
                    sa.and_(
                        models.offline_order_bundles.c.id == source.c.bundle_id,
                        models.offline_order_bundles.c.organization_id == source.c.organization_id,
                        models.offline_order_bundles.c.branch_id == source.c.branch_id,
                        models.offline_order_bundles.c.device_id == source.c.device_id,
                        models.offline_order_bundles.c.bundle_hash == source.c.bundle_hash,
                    ),
                )
            )
            .where(source.c.id == row["id"])
        ).first()
        if (
            not bindings
            or type(row["lease_epoch"]) is not int
            or row["lease_epoch"] <= 0
            or started > now
            or expires < started
            or expires > started + LEGACY_TTL
            or not isinstance(row["token"], str)
            or not row["token"]
        ):
            raise ops.BusinessError(
                "offline_adoption_retained_invalid",
                "Retained offline identity requires review",
            )
        session.execute(
            models.offline_authorization_leases.insert().values(
                id=ops._id(),
                organization_id=ops.ORGANIZATION_ID,
                actor_user_id=row["actor_id"],
                branch_id=row["branch_id"],
                grant_kind="orders",
                grant_hash=hashlib.sha256(row["token"].encode("utf-8")).hexdigest(),
                authorization_version=None,
                provenance="retained_legacy",
                source_device_id=row["device_id"],
                bundle_id=row["bundle_id"],
                source_grant_id=row["id"],
                lease_epoch=row["lease_epoch"],
                issued_at=started,
                expires_at=expires,
                revoked_at=None,
                state="expired" if expires < now else "active",
            )
        )
    return len(rows)


def prepare_offline_adoption(
    session: Session,
    actor: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    with without_order_execution_context():
        return _prepare_unit(session, actor, payload, idempotency_key)


def _prepare_unit(
    session: Session,
    actor: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    try:
        return _prepare(session, actor, payload, idempotency_key)
    except SQLAlchemyError:
        rollback_reconciliation(session)
        raise ops.BusinessError(
            "offline_adoption_persistence_unavailable",
            "Offline preparation is unavailable",
        ) from None
    except Exception:
        rollback_reconciliation(session)
        raise


def _prepare(
    session: Session,
    actor: str,
    payload: dict[str, Any],
    key: str,
) -> dict[str, Any]:
    if (
        type(payload) is not dict
        or set(payload) != {"retired_unregistered_issuers", "retirement_evidence_sha256"}
        or payload["retired_unregistered_issuers"] is not True
        or not isinstance(payload["retirement_evidence_sha256"], str)
        or not re.fullmatch(r"[0-9a-f]{64}", payload["retirement_evidence_sha256"])
    ):
        raise ops.BusinessError(
            "offline_adoption_payload_invalid", "Verified cutover evidence required"
        )
    if not isinstance(key, str) or not 12 <= len(key) <= 180 or key != key.strip():
        raise ops.BusinessError("idempotency_key_invalid", "A stable command identity is required")
    if not registry_available(session) or not sa.inspect(session.connection()).has_table(
        "offline_authorization_cutovers"
    ):
        raise ops.BusinessError(
            "offline_adoption_migration_required", "Cutover migration is required"
        )
    ops._authority_governance_lock(session)
    ops._require_active_profile_transition_organization(session, ops.ORGANIZATION_ID)
    ops._require_transition_authority(session, actor, ops.ORGANIZATION_ID)
    _lock_actor(session, actor)
    rollout = (
        session.execute(
            sa.select(models.offline_authorization_rollouts)
            .where(
                models.offline_authorization_rollouts.c.organization_id == ops.ORGANIZATION_ID,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    now = _utc(authority_now())
    expected = {
        "actor_user_id": actor,
        "idempotency_key_hash": hashlib.sha256(key.encode("utf-8")).hexdigest(),
        "request_hash": hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest(),
    }
    old = (
        session.execute(
            sa.select(models.offline_authorization_cutovers).where(
                models.offline_authorization_cutovers.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if old:
        if any(old[field] != value for field, value in expected.items()):
            raise ops.BusinessError(
                "offline_adoption_command_conflict", "Cutover already has an identity"
            )
        if (
            not rollout
            or rollout["state"] != "draining"
            or not rollout["registration_started_at"]
            or not rollout["legacy_drain_until"]
            or not cutover_matches(
                dict(old),
                _utc(rollout["registration_started_at"]),
                _utc(rollout["legacy_drain_until"]),
            )
        ):
            raise ops.BusinessError(
                "offline_adoption_evidence_conflict", "Cutover evidence is inconsistent"
            )
        receipt = _receipt(dict(old))
        session.commit()
        return receipt
    if not rollout or rollout["state"] != "unprepared":
        raise ops.BusinessError(
            "offline_adoption_state_conflict", "Organization requires cutover review"
        )
    imported = _import_retained(session, now)
    row = {
        "organization_id": ops.ORGANIZATION_ID,
        **expected,
        "retirement_evidence_sha256": payload["retirement_evidence_sha256"],
        "registration_started_at": now,
        "legacy_drain_until": now + LEGACY_TTL,
    }
    session.execute(models.offline_authorization_cutovers.insert().values(**row))
    session.execute(
        models.offline_authorization_rollouts.update()
        .where(
            models.offline_authorization_rollouts.c.organization_id == ops.ORGANIZATION_ID,
        )
        .values(state="draining", registration_started_at=now, legacy_drain_until=now + LEGACY_TTL)
    )
    ops._audit(
        session,
        "auth.offline_adoption_prepared",
        "offline_authorization_cutover",
        ops.ORGANIZATION_ID,
        {
            "retained_legacy_count": imported,
            "retirement_evidence_sha256": payload["retirement_evidence_sha256"],
            "legacy_drain_until": (now + LEGACY_TTL).isoformat(),
        },
        actor_user_id=actor,
        branch_id=None,
    )
    receipt = _receipt(row)
    session.commit()
    return receipt


def main(argv: list[str] | None = None) -> int:
    """Operator command; possession of central DB access is a separate operational authorization."""
    import argparse
    import os
    import sys

    parser = argparse.ArgumentParser(description="Prepare audited offline issuer cutover")
    parser.add_argument("--actor-id", required=True)
    parser.add_argument("--retirement-evidence-sha256", required=True)
    parser.add_argument("--idempotency-key", required=True)
    parser.add_argument(
        "--confirm-retired-unregistered-issuers", action="store_true", required=True
    )
    args = parser.parse_args(argv)
    target = os.environ.get("RESTAURANTOS_DATABASE_URL", "")
    try:
        if not target or not sa.engine.make_url(target).drivername.startswith("postgresql"):
            raise ValueError
    except (ValueError, sa.exc.ArgumentError):
        print("offline_adoption_explicit_postgres_required", file=sys.stderr)
        return 1
    engine: sa.Engine | None = None
    receipt: dict[str, Any] | None = None
    error: str | None = None
    try:
        engine = sa.create_engine(target)
        with Session(engine) as session:
            receipt = prepare_offline_adoption(
                session,
                args.actor_id,
                {
                    "retired_unregistered_issuers": args.confirm_retired_unregistered_issuers,
                    "retirement_evidence_sha256": args.retirement_evidence_sha256,
                },
                args.idempotency_key,
            )
    except ops.BusinessError as exc:
        error = exc.code
    except SQLAlchemyError:
        error = "offline_adoption_persistence_unavailable"
    finally:
        if engine is not None:
            try:
                engine.dispose()
            except SQLAlchemyError:
                error = "offline_adoption_persistence_unavailable"
    if error:
        print(error, file=sys.stderr)
        return 1
    if receipt is None:
        print("offline_adoption_persistence_unavailable", file=sys.stderr)
        return 1
    print(json.dumps(receipt, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
