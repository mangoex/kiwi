"""Central, audited classification rollout; device acknowledgements are scope bound."""

from __future__ import annotations

import hashlib
import json
from typing import Any, cast

import sqlalchemy as sa
from sqlalchemy.engine import CursorResult
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _actor_has_organization_scope,
    _audit,
    _id,
    _now,
    require_permission,
)


def _lock(session: Session, organization_id: str = ORGANIZATION_ID) -> None:
    # Shared lock order: organization -> category/branch/lease. An UPDATE also serializes SQLite.
    result = session.execute(
        models.organizations.update()
        .where(
            models.organizations.c.id == organization_id,
            models.organizations.c.status == "active",
        )
        .values(status=models.organizations.c.status)
    )
    if cast(CursorResult[Any], result).rowcount != 1:
        raise BusinessError("organization_not_found", "Organization is unavailable")


def _corporate(session: Session, actor: str) -> None:
    require_permission(session, actor, "catalog.manage", None)
    user = session.execute(
        sa.select(models.users.c.id).where(
            models.users.c.id == actor,
            models.users.c.organization_id == ORGANIZATION_ID,
            models.users.c.status == "active",
        )
    ).first()
    if user is None or not _actor_has_organization_scope(session, actor):
        raise AuthorizationError("catalog_corporate_scope_required", "Corporate authority required")


def _state(session: Session, organization_id: str = ORGANIZATION_ID) -> dict[str, Any]:
    row = (
        session.execute(
            sa.select(models.catalog_classification_rollouts).where(
                models.catalog_classification_rollouts.c.organization_id == organization_id
            )
        )
        .mappings()
        .first()
    )
    return (
        dict(row)
        if row
        else {
            "organization_id": organization_id,
            "state": "legacy",
            "version": 0,
            "prepared_fingerprint": None,
            "online_readiness": {},
        }
    )


def require_category_write_allowed(session: Session, classification_code: Any, status: str) -> None:
    _lock(session)
    if (
        status == "active"
        and _state(session)["state"] != "legacy"
        and classification_code not in ("food", "drinks", "other")
    ):
        raise BusinessError("invalid_classification", "An active group requires classification")


def get_branch_classification_mode(session: Session, branch_id: str | None) -> str:
    if not branch_id:
        return "legacy"
    # Gateway projection reads its committed local installation rather than central rollout flags.
    from restaurant_os.offline_order_catalog import get_installed_classification_mode

    local = get_installed_classification_mode(session, branch_id)
    if local is not None:
        return local
    row = session.execute(
        sa.select(models.catalog_classification_branches.c.confirmed_mode).where(
            models.catalog_classification_branches.c.branch_id == branch_id,
            models.catalog_classification_branches.c.organization_id == ORGANIZATION_ID,
        )
    ).first()
    return str(row[0]) if row else "legacy"


def lock_catalog_projection(session: Session, branch_id: str) -> None:
    from restaurant_os.offline_order_catalog import get_installed_classification_metadata

    if get_installed_classification_metadata(session, branch_id) is not None:
        return
    if session.get_bind().dialect.name == "postgresql":
        session.execute(
            sa.select(models.organizations.c.id)
            .where(models.organizations.c.id == ORGANIZATION_ID)
            .with_for_update(read=True)
        ).scalar_one()
    else:
        _lock(session)


def get_branch_classification_metadata(session: Session, branch_id: str | None) -> dict[str, Any]:
    if branch_id:
        from restaurant_os.offline_order_catalog import get_installed_classification_metadata

        local = get_installed_classification_metadata(session, branch_id)
        if local is not None:
            return {**local, "catalog_projection_hash": _projection_hash(session)}
    row = _branch_rows(session).get(branch_id or "", {})
    return {
        "catalog_classification_mode": row.get("confirmed_mode", "legacy"),
        "catalog_generation": int(row.get("confirmed_generation", 0)),
        "catalog_hash": row.get("confirmed_hash") or "",
        "catalog_projection_hash": _projection_hash(session),
    }


def _projection_hash(session: Session) -> str:
    """Topology token for paired HTTP reads, distinct from the retained signed bundle hash."""
    categories = list(
        session.execute(
            sa.select(models.product_categories)
            .where(models.product_categories.c.organization_id == ORGANIZATION_ID)
            .order_by(models.product_categories.c.id)
        ).mappings()
    )
    groups = list(
        session.execute(
            sa.select(models.category_option_groups)
            .where(models.category_option_groups.c.organization_id == ORGANIZATION_ID)
            .order_by(models.category_option_groups.c.id)
        ).mappings()
    )
    ids = [row["id"] for row in groups]
    values = list(
        session.execute(
            sa.select(models.category_option_values)
            .where(models.category_option_values.c.group_id.in_(ids))
            .order_by(models.category_option_values.c.id)
        ).mappings()
    )
    assignments = list(
        session.execute(
            sa.select(models.product_option_value_assignments)
            .where(models.product_option_value_assignments.c.group_id.in_(ids))
            .order_by(
                models.product_option_value_assignments.c.product_id,
                models.product_option_value_assignments.c.group_id,
            )
        ).mappings()
    )
    products = list(
        session.execute(
            sa.select(
                models.products.c.id,
                models.products.c.category_id,
                models.products.c.status,
                models.products.c.updated_at,
            )
            .where(models.products.c.organization_id == ORGANIZATION_ID)
            .order_by(models.products.c.id)
        ).mappings()
    )
    return _hash(
        [
            [dict(row) for row in rows]
            for rows in (categories, groups, values, assignments, products)
        ]
    )


def _inventory(
    session: Session, organization_id: str = ORGANIZATION_ID
) -> tuple[list[dict[str, Any]], list[str], str]:
    categories = [
        dict(row)
        for row in session.execute(
            sa.select(
                models.product_categories.c.id,
                models.product_categories.c.name,
                models.product_categories.c.classification_code,
                models.product_categories.c.configuration_version,
                models.product_categories.c.status,
            )
            .where(models.product_categories.c.organization_id == organization_id)
            .order_by(models.product_categories.c.id)
        ).mappings()
    ]
    branches = list(
        session.scalars(
            sa.select(models.branches.c.id)
            .where(
                models.branches.c.organization_id == organization_id,
                models.branches.c.status == "active",
            )
            .order_by(models.branches.c.id)
        )
    )
    fingerprint = _hash({"groups": categories, "branches": branches})
    return categories, branches, fingerprint


def _hash(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def _branch_rows(
    session: Session, organization_id: str = ORGANIZATION_ID
) -> dict[str, dict[str, Any]]:
    return {
        str(row["branch_id"]): dict(row)
        for row in session.execute(
            sa.select(models.catalog_classification_branches).where(
                models.catalog_classification_branches.c.organization_id == organization_id
            )
        ).mappings()
    }


def rollout_status(session: Session, actor: str) -> dict[str, Any]:
    _corporate(session, actor)
    state = _state(session)
    categories, branches, fingerprint = _inventory(session)
    branch_rows = _branch_rows(session)
    return {
        **state,
        "fingerprint": fingerprint,
        "groups": categories,
        "pending_group_ids": [
            r["id"]
            for r in categories
            if r["status"] == "active" and r["classification_code"] is None
        ],
        "branches": [{"branch_id": b, **branch_rows.get(b, {})} for b in branches],
    }


def _transition_rollout(
    session: Session, actor: str, payload: dict[str, Any], key: str
) -> dict[str, Any]:
    _corporate(session, actor)
    if not isinstance(key, str) or not key.strip() or len(key) > 180:
        raise BusinessError("idempotency_key_required", "Idempotency-Key is required")
    if set(payload) - {"action", "expected_version", "online_readiness"}:
        raise BusinessError("classification_rollout_invalid", "Unexpected fields")
    version = payload.get("expected_version")
    if isinstance(version, bool) or not isinstance(version, int) or version < 0:
        raise BusinessError("classification_rollout_invalid", "Expected version required")
    _lock(session)
    commands = models.catalog_classification_rollout_commands
    digest = _hash(payload)
    previous = (
        session.execute(
            sa.select(commands).where(
                commands.c.organization_id == ORGANIZATION_ID,
                commands.c.actor_id == actor,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if previous:
        if previous["payload_hash"] != digest:
            raise BusinessError("idempotency_key_conflict", "Conflicting intention")
        replay = dict(previous["result"])
        session.commit()
        return replay
    current = _state(session)
    if current["version"] != version:
        raise BusinessError("category_version_conflict", "Rollout version changed")
    categories, branches, fingerprint = _inventory(session)
    action = payload.get("action")
    next_state = dict(current)
    if action == "prepare":
        if current["state"] not in ("legacy", "preparing"):
            raise BusinessError(
                "classification_rollout_invalid_transition", "Revert before preparing again"
            )
        if not branches or any(
            r["status"] == "active" and r["classification_code"] is None for r in categories
        ):
            raise BusinessError("classification_rollout_incomplete", "Classify every active group")
        # This is a corporate deployment attestation, not automatic detection of unseen browsers.
        readiness = payload.get("online_readiness")
        if (
            not isinstance(readiness, dict)
            or set(readiness) != set(branches)
            or any(value != "cat-class/v1" for value in readiness.values())
        ):
            raise BusinessError(
                "classification_clients_unready", "Confirm compatible online clients per branch"
            )
        next_state.update(
            state="preparing", prepared_fingerprint=fingerprint, online_readiness=readiness
        )
    elif action == "publish":
        if current["state"] != "preparing" or current["prepared_fingerprint"] != fingerprint:
            raise BusinessError(
                "classification_rollout_incomplete", "Prepare current catalog first"
            )
        rows = _branch_rows(session)
        for branch in branches:
            row = rows.get(branch)
            lease = (
                session.execute(
                    sa.select(models.offline_order_gateway_leases).where(
                        models.offline_order_gateway_leases.c.branch_id == branch,
                        models.offline_order_gateway_leases.c.organization_id == ORGANIZATION_ID,
                        models.offline_order_gateway_leases.c.status == "ACTIVE",
                        models.offline_order_gateway_leases.c.expires_at > _now(),
                    )
                )
                .mappings()
                .first()
            )
            if (
                row is None
                or lease is None
                or row["device_id"] != lease["device_id"]
                or row["lease_epoch"] != lease["lease_epoch"]
                or row["confirmed_generation"] < 1
                or row["confirmed_generation"] != row["generation"]
                or row["confirmed_hash"] != row["issued_hash"]
            ):
                raise BusinessError(
                    "classification_clients_unready",
                    "Gateway installation acknowledgement required",
                )
        next_state["state"] = "adopting"
    elif action == "revert":
        next_state.update(state="reverting", prepared_fingerprint=fingerprint)
    else:
        raise BusinessError("classification_rollout_invalid", "Unknown rollout action")
    next_state.update(version=version + 1, updated_at=_now())
    table = models.catalog_classification_rollouts
    if (
        current["version"] == 0
        and session.get_bind() is not None
        and not session.scalar(
            sa.select(table.c.organization_id).where(table.c.organization_id == ORGANIZATION_ID)
        )
    ):
        session.execute(table.insert().values(**next_state))
    else:
        session.execute(
            table.update().where(table.c.organization_id == ORGANIZATION_ID).values(**next_state)
        )
    result = {k: v for k, v in next_state.items() if k != "updated_at"}
    _audit(
        session,
        action="catalog.classification.rollout",
        entity_type="organization",
        entity_id=ORGANIZATION_ID,
        actor_user_id=actor,
        payload={"before": current["state"], "after": next_state["state"], "version": version + 1},
    )
    session.execute(
        commands.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            actor_id=actor,
            idempotency_key=key,
            payload_hash=digest,
            result=result,
            created_at=_now(),
        )
    )
    session.commit()
    return result


def next_bundle_metadata(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    lease_epoch: int,
    catalog_schema: str | None,
) -> dict[str, Any]:
    _lock(session, organization_id)
    table = models.catalog_classification_branches
    row = _branch_rows(session, organization_id).get(branch_id)
    if catalog_schema not in (None, "ord-off-catalog/v2", "ord-off-catalog/v3"):
        raise BusinessError("classification_schema_unsupported", "Unsupported catalog schema")
    if catalog_schema != "ord-off-catalog/v3":
        if row and row["generation"] > 0:
            raise BusinessError(
                "classification_client_downgrade", "Gateway must retain v3 capability"
            )
        return {}
    state = _state(session, organization_id)
    if (
        state["state"] == "adopting"
        and _inventory(session, organization_id)[2] != state["prepared_fingerprint"]
    ):
        raise BusinessError(
            "classification_rollout_incomplete", "Catalog changed during preparation"
        )
    mode = "explicit" if state["state"] in ("adopting", "explicit") else "legacy"
    generation = (int(row["generation"]) if row else 0) + 1
    if generation > 2_147_483_647:
        raise BusinessError("classification_generation_exhausted", "Generation exhausted")
    values = {
        "organization_id": organization_id,
        "device_id": device_id,
        "lease_epoch": lease_epoch,
        "generation": generation,
        "rollout_version": int(state["version"]),
        "issued_hash": None,
        "issued_mode": mode,
        "updated_at": _now(),
    }
    if row:
        session.execute(table.update().where(table.c.branch_id == branch_id).values(**values))
    else:
        session.execute(table.insert().values(branch_id=branch_id, **values))
    return {"catalog_generation": generation, "catalog_classification_mode": mode}


def record_bundle_hash(session: Session, branch_id: str, digest: str) -> None:
    session.execute(
        models.catalog_classification_branches.update()
        .where(models.catalog_classification_branches.c.branch_id == branch_id)
        .values(issued_hash=digest)
    )


def _acknowledge_installation(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    if set(payload) != {
        "catalog_generation",
        "catalog_classification_mode",
        "bundle_hash",
        "lease_epoch",
    }:
        raise BusinessError("classification_ack_invalid", "Invalid acknowledgement")
    _lock(session, organization_id)
    rows = _branch_rows(session, organization_id)
    row = rows.get(branch_id)
    lease = (
        session.execute(
            sa.select(models.offline_order_gateway_leases).where(
                models.offline_order_gateway_leases.c.organization_id == organization_id,
                models.offline_order_gateway_leases.c.branch_id == branch_id,
                models.offline_order_gateway_leases.c.device_id == device_id,
                models.offline_order_gateway_leases.c.status == "ACTIVE",
                models.offline_order_gateway_leases.c.expires_at > _now(),
            )
        )
        .mappings()
        .first()
    )
    if (
        row is None
        or lease is None
        or row["device_id"] != device_id
        or row["lease_epoch"] != lease["lease_epoch"]
    ):
        raise BusinessError("classification_ack_invalid", "Current gateway is required")
    generation = payload["catalog_generation"]
    epoch = payload["lease_epoch"]
    if (
        isinstance(generation, bool)
        or not isinstance(generation, int)
        or isinstance(epoch, bool)
        or not isinstance(epoch, int)
    ):
        raise BusinessError("classification_ack_invalid", "Integer generation and epoch required")
    if (
        generation != row["generation"]
        or payload["bundle_hash"] != row["issued_hash"]
        or payload["catalog_classification_mode"] != row["issued_mode"]
        or epoch != row["lease_epoch"]
    ):
        raise BusinessError(
            "classification_ack_invalid", "Acknowledge the exact issued installation"
        )
    state = _state(session, organization_id)
    if (
        state["state"] == "adopting"
        and _inventory(session, organization_id)[2] != state["prepared_fingerprint"]
    ):
        raise BusinessError(
            "classification_rollout_incomplete", "Catalog changed during preparation"
        )
    is_replay = (
        row["confirmed_generation"] == generation and row["confirmed_hash"] == row["issued_hash"]
    )
    confirmed = {
        "confirmed_generation": generation,
        "confirmed_hash": row["issued_hash"],
        "confirmed_mode": row["issued_mode"],
        "updated_at": _now(),
    }
    session.execute(
        models.catalog_classification_branches.update()
        .where(models.catalog_classification_branches.c.branch_id == branch_id)
        .values(**confirmed)
    )
    rows[branch_id].update(confirmed)
    target = {"adopting": "explicit", "reverting": "legacy"}.get(state["state"])
    if target:
        branches = _inventory(session, organization_id)[1]
        if branches and all(
            b in rows
            and rows[b]["rollout_version"] == state["version"]
            and rows[b]["confirmed_mode"] == target
            and rows[b]["issued_mode"] == target
            and rows[b]["generation"] == rows[b]["confirmed_generation"]
            and rows[b]["issued_hash"] == rows[b]["confirmed_hash"]
            for b in branches
        ):
            session.execute(
                models.catalog_classification_rollouts.update()
                .where(models.catalog_classification_rollouts.c.organization_id == organization_id)
                .values(state=target, version=state["version"] + 1, updated_at=_now())
            )
    if not is_replay:
        _audit(
            session,
            action="catalog.classification.installed",
            entity_type="branch",
            entity_id=branch_id,
            branch_id=branch_id,
            organization_id=organization_id,
            actor_user_id=None,
            payload={"generation": generation, "mode": row["issued_mode"], "device_id": device_id},
        )
    session.commit()
    return {"status": "acknowledged", "catalog_generation": generation, "mode": row["issued_mode"]}


def transition_rollout(
    session: Session, actor: str, payload: dict[str, Any], key: str
) -> dict[str, Any]:
    try:
        return _transition_rollout(session, actor, payload, key)
    except Exception:
        session.rollback()
        raise


def acknowledge_installation(
    session: Session,
    *,
    organization_id: str,
    branch_id: str,
    device_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _acknowledge_installation(
            session,
            organization_id=organization_id,
            branch_id=branch_id,
            device_id=device_id,
            payload=payload,
        )
    except Exception:
        session.rollback()
        raise
