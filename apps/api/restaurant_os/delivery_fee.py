"""Versioned delivery services and exact, server-authoritative order charges."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from collections.abc import Sequence
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal, localcontext
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os.config import get_settings
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    _acquire_idempotency_lock,
    _actor_has_organization_scope,
    _audit,
    _begin_cash_shift_serialization,
    require_permission,
)

QUOTE_SECONDS = 120
_SELECTION_ERROR = "Delivery selection is invalid"
_LEGACY_READ_REVISIONS = frozenset(
    {
        "0077_pos_branch_selection",
        "0087_fiscal_commands",
        "0099_mobile_password_access",
    }
)


def fee_table_available(session: Session, required: str) -> bool:
    """Only known pre-fee rollback schemas may omit every delivery table."""
    inspector = sa.inspect(session.connection())
    if inspector.has_table(required):
        return True
    from restaurant_os.delivery_fee_schema import tables

    names = [table.name for table in tables(sa.MetaData())]
    if not any(inspector.has_table(name) for name in names) and inspector.has_table(
        "alembic_version"
    ):
        revisions: Sequence[str] = (
            session.execute(sa.text("SELECT version_num FROM alembic_version")).scalars().all()
        )
        if len(revisions) == 1 and revisions[0] in _LEGACY_READ_REVISIONS:
            return False
    raise BusinessError(
        "delivery_schema_incomplete", "Delivery schema requires migration or repair"
    )


def allocate_adjustment(gross: list[int], adjustment: int) -> list[int]:
    """Allocate a captured product adjustment by largest remainder, in stable line order."""
    total = sum(gross)
    if adjustment < 0 or adjustment > total or any(value < 0 for value in gross):
        raise _invalid("Product adjustment cannot be allocated")
    if total == 0:
        return [0] * len(gross)
    result = [(value * adjustment) // total for value in gross]
    remainder = adjustment - sum(result)
    order = sorted(range(len(gross)), key=lambda i: (-(gross[i] * adjustment % total), i))
    for index in order[:remainder]:
        result[index] += 1
    return result


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid.uuid4())


def _invalid(message: str) -> BusinessError:
    return BusinessError("delivery_selection_invalid", message)


def _integer(value: Any, *, positive: bool = False) -> int:
    if type(value) is not int or value < (1 if positive else 0) or value > 2_000_000_000:
        raise _invalid("Delivery amounts and versions must be bounded integer cents")
    return value


def normalize_selection(value: Any) -> dict[str, str]:
    if value is None:
        return {"mode": "AUTO"}
    if not isinstance(value, dict) or value.keys() - {"mode", "tariff_id"}:
        raise _invalid(_SELECTION_ERROR)
    mode = value.get("mode")
    if not isinstance(mode, str):
        raise _invalid(_SELECTION_ERROR)
    if mode == "SELECTED":
        tariff_id = value.get("tariff_id")
        if not isinstance(tariff_id, str) or not 1 <= len(tariff_id) <= 36:
            raise _invalid(_SELECTION_ERROR)
        return {"mode": mode, "tariff_id": tariff_id}
    if mode not in {"AUTO", "REMOVED"} or "tariff_id" in value:
        raise _invalid(_SELECTION_ERROR)
    return {"mode": mode}


def calculate_charge(
    tariff: dict[str, Any], policy: dict[str, Any], selection: dict[str, str], subtotal: int
) -> dict[str, Any]:
    subtotal = _integer(subtotal)
    threshold = policy.get("free_threshold_cents")
    amount = _integer(tariff["amount_cents"])
    state = "CHARGED"
    if selection["mode"] == "REMOVED":
        state = "REMOVED"
    elif threshold is not None and subtotal >= threshold:
        state = "WAIVED_THRESHOLD"
    charged = amount if state == "CHARGED" else 0
    with localcontext() as context:
        context.prec = 36
        gross = Decimal(charged) / 100
        base = gross / (1 + Decimal(tariff["tax_rate"]))
        tax = gross - base
    return {
        "schema_version": "delivery-charge.v1",
        "state": state,
        "selection": selection,
        "tariff": tariff,
        "policy": policy,
        "list_cents": amount,
        "charged_cents": charged,
        "net_amount": str(base),
        "tax_amount": str(tax),
        "net_cents": int((base * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "tax_cents": int((tax * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        "eligible_subtotal_cents": subtotal,
        "free_threshold_cents": threshold,
        "currency": "MXN",
        "charged_by": "KIWI",
    }


def lock_catalog(session: Session) -> None:
    _begin_cash_shift_serialization(session)
    _acquire_idempotency_lock(session, "delivery-catalog", ORGANIZATION_ID)


def _branch(session: Session, branch_id: str) -> None:
    found = session.scalar(
        sa.select(models.branches.c.id).where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == ORGANIZATION_ID,
            models.branches.c.status == "active",
        )
    )
    if not found:
        raise BusinessError("delivery_tariff_ineligible", "Delivery branch is unavailable")


def _tariffs(session: Session) -> list[dict[str, Any]]:
    t, v = models.delivery_tariffs, models.delivery_tariff_versions
    latest = (
        sa.select(v.c.tariff_id, sa.func.max(v.c.version).label("version"))
        .group_by(v.c.tariff_id)
        .subquery()
    )
    query = (
        sa.select(
            t.c.id,
            t.c.code,
            v.c.name,
            v.c.amount_cents,
            v.c.version,
            v.c.active,
            v.c.fiscal_mapping,
        )
        .join(v, v.c.tariff_id == t.c.id)
        .join(latest, sa.and_(latest.c.tariff_id == v.c.tariff_id, latest.c.version == v.c.version))
        .where(t.c.organization_id == ORGANIZATION_ID)
        .order_by(t.c.code)
        .limit(101)
    )
    return [
        {**dict(row), "currency": "MXN", "tax_rate": "0.160000", "tax_included": True}
        for row in session.execute(query).mappings()
    ]


def current_policy(session: Session, branch_id: str) -> dict[str, Any] | None:
    if not fee_table_available(session, "delivery_policies"):
        return None
    p = models.delivery_policies
    for scope in (branch_id, "*"):
        row = (
            session.execute(
                sa.select(p)
                .where(p.c.organization_id == ORGANIZATION_ID, p.c.scope_key == scope)
                .order_by(p.c.version.desc())
                .limit(1)
            )
            .mappings()
            .first()
        )
        if row:
            return {
                "id": row["id"],
                "scope_key": scope,
                "version": row["version"],
                "enabled": row["enabled"],
                "eligible_tariff_ids": row["eligible_tariff_ids"],
                "default_tariff_id": row["default_tariff_id"],
                "free_threshold_cents": row["free_threshold_cents"],
            }
    return None


def options(session: Session, branch_id: str, actor_id: str) -> dict[str, Any]:
    require_permission(session, actor_id, "orders.create", branch_id)
    _branch(session, branch_id)
    policy = current_policy(session, branch_id)
    eligible = policy["eligible_tariff_ids"] if policy and policy["enabled"] else []
    return {
        "policy": policy,
        "tariffs": [t for t in _tariffs(session) if t["active"] and t["id"] in eligible],
    }


def catalog(session: Session, actor_id: str) -> dict[str, Any]:
    require_catalog_manager(session, actor_id)
    items = _tariffs(session)
    return {"items": items[:100], "has_more": len(items) > 100}


def require_catalog_manager(session: Session, actor_id: str) -> None:
    if not _actor_has_organization_scope(session, actor_id, "catalog.manage"):
        raise AuthorizationError(
            "permission_denied", "Delivery catalog requires organization scope"
        )
    require_permission(session, actor_id, "catalog.manage", None)


def _command(
    session: Session, actor_id: str, key: str, action: str, values: dict[str, Any]
) -> tuple[str, dict[str, Any] | None]:
    lock_catalog(session)
    require_catalog_manager(session, actor_id)
    if not isinstance(key, str) or not 12 <= len(key) <= 160:
        raise BusinessError("idempotency_key_required", "Idempotency-Key is required")
    digest = hashlib.sha256(
        json.dumps([action, actor_id, values], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    old = (
        session.execute(
            sa.select(models.delivery_catalog_commands).where(
                models.delivery_catalog_commands.c.organization_id == ORGANIZATION_ID,
                models.delivery_catalog_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if old:
        if old["request_hash"] != digest or old["actor_id"] != actor_id:
            raise BusinessError("idempotency_key_conflict", "Delivery intention changed")
        return digest, dict(old["response"])
    return digest, None


def _finish(
    session: Session, actor_id: str, key: str, digest: str, action: str, result: dict[str, Any]
) -> dict[str, Any]:
    session.execute(
        models.delivery_catalog_commands.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            actor_id=actor_id,
            idempotency_key=key,
            request_hash=digest,
            response=result,
            created_at=_now(),
        )
    )
    _audit(
        session,
        action=action,
        entity_type="delivery_configuration",
        entity_id=result["id"],
        payload={"version": result["version"]},
        actor_user_id=actor_id,
    )
    session.commit()
    return result


def save_tariff(
    session: Session, actor_id: str, key: str, values: dict[str, Any], tariff_id: str | None = None
) -> dict[str, Any]:
    action = "delivery.tariff_updated" if tariff_id else "delivery.tariff_created"
    digest, replay = _command(session, actor_id, key, action, {**values, "id": tariff_id})
    if replay is not None:
        return replay
    allowed = {"code", "name", "amount_cents", "expected_version", "active", "fiscal_mapping"}
    if values.keys() - allowed:
        raise _invalid("Unknown delivery tariff fields")
    name = values.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 160:
        raise _invalid("Delivery name is required")
    amount = _integer(values.get("amount_cents"))
    active = values.get("active", True)
    if type(active) is not bool:
        raise _invalid("Delivery active flag must be boolean")
    existing = next((t for t in _tariffs(session) if t["id"] == tariff_id), None)
    if tariff_id:
        if existing is None:
            raise BusinessError("delivery_tariff_ineligible", "Delivery tariff was not found")
        if _integer(values.get("expected_version")) != existing["version"]:
            raise BusinessError("delivery_policy_version_conflict", "Delivery tariff changed")
        if not active:
            # Every effective policy must retain a valid default, including inherited scopes.
            p = models.delivery_policies
            latest = (
                sa.select(p.c.scope_key, sa.func.max(p.c.version).label("version"))
                .where(p.c.organization_id == ORGANIZATION_ID)
                .group_by(p.c.scope_key)
                .subquery()
            )
            uses = session.scalar(
                sa.select(sa.func.count())
                .select_from(p)
                .join(
                    latest,
                    sa.and_(p.c.scope_key == latest.c.scope_key, p.c.version == latest.c.version),
                )
                .where(
                    p.c.organization_id == ORGANIZATION_ID,
                    p.c.enabled.is_(True),
                    p.c.default_tariff_id == tariff_id,
                )
            )
            if uses:
                raise BusinessError(
                    "delivery_default_invalid", "Replace the default before archiving"
                )
        code = existing["code"]
        version = existing["version"] + 1
    else:
        code = values.get("code")
        if not isinstance(code, str) or not 1 <= len(code.strip()) <= 40:
            raise _invalid("Delivery code is required")
        code = code.strip().upper()
        if session.scalar(
            sa.select(models.delivery_tariffs.c.id).where(
                models.delivery_tariffs.c.organization_id == ORGANIZATION_ID,
                models.delivery_tariffs.c.code == code,
            )
        ):
            raise BusinessError("delivery_policy_version_conflict", "Delivery code already exists")
        if len(_tariffs(session)) >= 100:
            raise _invalid("Delivery catalog limit reached")
        tariff_id, version = _id(), 1
        session.execute(
            models.delivery_tariffs.insert().values(
                id=tariff_id, organization_id=ORGANIZATION_ID, code=code, created_at=_now()
            )
        )
    mapping = values.get("fiscal_mapping", existing["fiscal_mapping"] if existing else {})
    if not isinstance(mapping, dict) or mapping.keys() - {"product_key", "unit_key", "emitter_id"}:
        raise _invalid("Delivery fiscal mapping is invalid")
    if any(not isinstance(v, str) or not 1 <= len(v) <= 64 for v in mapping.values()):
        raise _invalid("Delivery fiscal mapping is invalid")
    if existing and all(
        (
            existing["name"] == name.strip(),
            existing["amount_cents"] == amount,
            existing["active"] == active,
            existing["fiscal_mapping"] == mapping,
        )
    ):
        return _finish(session, actor_id, key, digest, action, existing)
    session.execute(
        models.delivery_tariff_versions.insert().values(
            id=_id(),
            tariff_id=tariff_id,
            version=version,
            name=name.strip(),
            amount_cents=amount,
            active=active,
            fiscal_mapping=mapping,
            actor_id=actor_id,
            created_at=_now(),
        )
    )
    result = {
        "id": tariff_id,
        "code": code,
        "version": version,
        "name": name.strip(),
        "amount_cents": amount,
        "active": active,
        "fiscal_mapping": mapping,
        "currency": "MXN",
        "tax_rate": "0.160000",
        "tax_included": True,
    }
    return _finish(session, actor_id, key, digest, action, result)


def save_policy(
    session: Session, actor_id: str, key: str, values: dict[str, Any]
) -> dict[str, Any]:
    digest, replay = _command(session, actor_id, key, "delivery.policy_published", values)
    if replay is not None:
        return replay
    if values.keys() - {
        "branch_id",
        "expected_version",
        "enabled",
        "eligible_tariff_ids",
        "default_tariff_id",
        "free_threshold_cents",
    }:
        raise _invalid("Unknown delivery policy fields")
    branch = values.get("branch_id")
    if branch is not None:
        if not isinstance(branch, str):
            raise _invalid("Delivery branch is invalid")
        _branch(session, branch)
    scope = branch if branch is not None else "*"
    p = models.delivery_policies
    old = session.execute(
        sa.select(p.c.version)
        .where(p.c.organization_id == ORGANIZATION_ID, p.c.scope_key == scope)
        .order_by(p.c.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    if _integer(values.get("expected_version")) != (old or 0):
        raise BusinessError("delivery_policy_version_conflict", "Delivery policy changed")
    enabled = values.get("enabled")
    eligible = values.get("eligible_tariff_ids")
    default = values.get("default_tariff_id")
    threshold = values.get("free_threshold_cents")
    if type(enabled) is not bool or not isinstance(eligible, list) or len(eligible) > 100:
        raise _invalid("Delivery policy fields are invalid")
    if any(not isinstance(t, str) for t in eligible) or len(set(eligible)) != len(eligible):
        raise _invalid("Delivery tariffs must be unique")
    if threshold is not None:
        _integer(threshold, positive=True)
    available = {t["id"] for t in _tariffs(session) if t["active"]}
    if not set(eligible) <= available or (enabled and default not in eligible):
        raise BusinessError(
            "delivery_default_invalid", "Delivery default or eligible tariffs are invalid"
        )
    if enabled:
        leases = models.offline_order_gateway_leases
        query = sa.select(leases.c.branch_id).where(
            leases.c.organization_id == ORGANIZATION_ID, leases.c.status != "RELEASED"
        )
        if branch is not None:
            query = query.where(leases.c.branch_id == branch)
        if session.scalar(query.limit(1)) is not None:
            raise BusinessError(
                "delivery_contract_upgrade_required",
                "Drain the offline gateway before enabling delivery tariffs",
            )
    result = {
        "id": _id(),
        "scope_key": scope,
        "version": (old or 0) + 1,
        "enabled": enabled,
        "eligible_tariff_ids": eligible,
        "default_tariff_id": default,
        "free_threshold_cents": threshold,
    }
    session.execute(
        p.insert().values(
            **result, organization_id=ORGANIZATION_ID, actor_id=actor_id, created_at=_now()
        )
    )
    return _finish(session, actor_id, key, digest, "delivery.policy_published", result)


def order_charge(session: Session, order_id: str) -> dict[str, Any] | None:
    if not fee_table_available(session, "delivery_charge_revisions"):
        return None
    row = session.execute(
        sa.select(models.delivery_charge_revisions.c.snapshot)
        .where(
            models.delivery_charge_revisions.c.organization_id == ORGANIZATION_ID,
            models.delivery_charge_revisions.c.order_id == order_id,
        )
        .order_by(models.delivery_charge_revisions.c.order_version.desc())
        .limit(1)
    ).scalar_one_or_none()
    return dict(row) if row is not None else None


def require_compatible_channel(
    session: Session, branch_id: str, order_type: str, channel: str
) -> None:
    # Publication and incompatible writers share the catalogue transaction lock.
    # Acquire the branch fence first, matching online orders and gateway leases.
    from restaurant_os.offline_orders import lock_gateway_branch

    lock_gateway_branch(session, organization_id=ORGANIZATION_ID, branch_id=branch_id)
    lock_catalog(session)
    policy = current_policy(session, branch_id)
    if order_type == "delivery" and policy and policy["enabled"] and channel != "POS":
        raise BusinessError(
            "delivery_contract_upgrade_required",
            "This delivery writer is not enabled for the tariff policy",
        )


def resolve_charge(
    session: Session,
    branch_id: str,
    order_type: str,
    selection_value: Any,
    subtotal: int,
    *,
    order_id: str | None = None,
    channel: str = "POS",
) -> dict[str, Any] | None:
    selection = normalize_selection(selection_value)
    if order_type != "delivery":
        if selection["mode"] == "SELECTED":
            raise _invalid("Delivery selection requires a delivery order")
        return None
    original = order_charge(session, order_id) if order_id else None
    if order_id and original is None:
        if selection["mode"] == "SELECTED":
            raise BusinessError(
                "delivery_policy_missing", "Historical order has no delivery charge"
            )
        return None
    policy = original["policy"] if original else current_policy(session, branch_id)
    if not policy or not policy["enabled"]:
        if selection["mode"] != "AUTO":
            raise BusinessError("delivery_policy_missing", "Delivery policy is not enabled")
        return None
    if channel != "POS":
        raise BusinessError(
            "delivery_contract_upgrade_required", "Delivery channel requires upgrade"
        )
    if original:
        if selection_value is None:
            selection = dict(original["selection"])
        tariff_id = selection.get("tariff_id", policy["default_tariff_id"])
        previous_id = original["tariff"]["id"]
        if selection_value is None or tariff_id == previous_id or selection["mode"] == "REMOVED":
            return calculate_charge(original["tariff"], policy, selection, subtotal)
    tariff_id = selection.get("tariff_id", policy["default_tariff_id"])
    tariff = next((t for t in _tariffs(session) if t["id"] == tariff_id and t["active"]), None)
    if tariff is None or tariff_id not in policy["eligible_tariff_ids"]:
        raise BusinessError("delivery_tariff_ineligible", "Delivery tariff is unavailable")
    return calculate_charge(tariff, policy, selection, subtotal)


def capture_charge(
    session: Session, order: dict[str, Any], actor_id: str, charge: dict[str, Any] | None
) -> None:
    if charge is None:
        return
    session.execute(
        models.delivery_charge_revisions.insert().values(
            id=_id(),
            organization_id=order["organization_id"],
            branch_id=order["branch_id"],
            order_id=order["id"],
            order_version=order["version"],
            snapshot=charge,
            actor_id=actor_id,
            created_at=_now(),
        )
    )
    _audit(
        session,
        action="delivery.charge_captured",
        entity_type="order",
        entity_id=order["id"],
        branch_id=order["branch_id"],
        actor_user_id=actor_id,
        payload={
            "version": order["version"],
            "state": charge["state"],
            "charged_cents": charge["charged_cents"],
            "tariff_id": charge["tariff"]["id"],
            "reason": "operator_removed" if charge["state"] == "REMOVED" else charge["state"],
        },
    )


def same_cart(lines: list[dict[str, Any]], historical: list[dict[str, Any]]) -> bool:
    """Compare operational selections, ignoring display labels and current catalog prices."""
    if len(lines) != len(historical):
        return False
    by_id = {line["id"]: line for line in historical}
    for index, item in enumerate(lines):
        old = by_id.get(item.get("source_line_id"), historical[index])
        if (
            item.get("product_id") != old["product_id"]
            or item.get("quantity", 1) != old["quantity"]
            or (item.get("notes") or "") != (old.get("line_notes") or "")
        ):
            return False
        desired = [
            (
                "modifier",
                str(m.get("option_id")),
                str(m.get("portions", 1)),
                str(m.get("text") or ""),
            )
            for m in item.get("modifiers", [])
        ]
        desired.extend(
            ("order_comment", str(c), "1", "") for c in item.get("comment_preset_ids", [])
        )
        desired.extend(
            ("ingredient_extra", str(e.get("extra_id")), str(e.get("portions", 1)), "")
            for e in item.get("ingredient_extras", [])
        )
        captured = []
        for m in old.get("selected_modifiers") or []:
            kind = m.get("selection_kind") or "modifier"
            identifier = m.get("extra_id", m.get("option_id", m.get("id")))
            captured.append(
                (
                    kind,
                    str(identifier),
                    str(m.get("portions", 1)),
                    str(m.get("text") or "") if kind == "modifier" else "",
                )
            )
        if sorted(desired) != sorted(captured):
            return False
    return True


def amend_charge_only(
    session: Session,
    order: dict[str, Any],
    old_lines: list[dict[str, Any]],
    lines: list[dict[str, Any]],
    selection: Any,
    reference: Any,
    actor: str,
    key: str,
    command_hash: str,
    *,
    commit: bool,
) -> dict[str, Any]:
    from restaurant_os.operations import _sanitize_for_json, get_order_detail

    original = order_charge(session, order["id"])
    if original is None:
        raise BusinessError("delivery_policy_missing", "Delivery snapshot is unavailable")
    lock_catalog(session)
    charge = resolve_charge(
        session,
        order["branch_id"],
        order["order_type"],
        selection,
        original["eligible_subtotal_cents"],
        order_id=order["id"],
    )
    if charge is None:
        raise BusinessError("delivery_policy_missing", "Delivery snapshot is unavailable")
    total = int(charge["eligible_subtotal_cents"]) + int(charge["charged_cents"])
    verify_quote(
        reference,
        actor,
        order["branch_id"],
        order["order_type"],
        lines,
        None,
        charge,
        total,
        order["id"],
    )
    version = int(order["version"]) + 1
    before = {
        "version": order["version"],
        "total_cents": order["total_cents"],
        "delivery_charge": original,
    }
    after = {
        "version": version,
        "total_cents": total,
        "delivery_charge": charge,
        "delivery_command_hash": command_hash,
    }
    session.execute(
        models.orders.update()
        .where(models.orders.c.id == order["id"])
        .values(version=version, total_cents=total)
    )
    capture_charge(session, {**order, "version": version}, actor, charge)
    session.execute(
        models.order_amendments.insert().values(
            id=_id(),
            order_id=order["id"],
            sequence=version - 1,
            expected_version=order["version"],
            resulting_version=version,
            before_snapshot=before,
            after_snapshot=after,
            actor_user_id=actor,
            idempotency_key=key.strip(),
            created_at=_now(),
        )
    )
    session.execute(
        models.order_events.insert().values(
            id=_id(),
            order_id=order["id"],
            event_type="DELIVERY_CHARGE_AMENDED",
            payload={
                "previous_version": order["version"],
                "version": version,
                "total_cents": total,
                "state": charge["state"],
            },
            created_at=_now(),
        )
    )
    response = get_order_detail(session, order["id"], actor)
    session.execute(
        models.order_amendments.update()
        .where(
            models.order_amendments.c.order_id == order["id"],
            models.order_amendments.c.idempotency_key == key.strip(),
        )
        .values(after_snapshot={**after, "delivery_response": _sanitize_for_json(response)})
    )
    if commit:
        session.commit()
    return response


def _quote_mac(value: str) -> str:
    key = get_settings().secret_key.encode()
    return hmac.new(key, b"delivery-quote.v1\0" + value.encode(), hashlib.sha256).hexdigest()


def quote_reference(
    actor: str,
    branch: str,
    order_type: str,
    lines: list[dict[str, Any]],
    adjustment: str | None,
    charge: dict[str, Any] | None,
    total: int,
    order_id: str | None = None,
    *,
    expires: int | None = None,
) -> str:
    body = json.dumps(
        [actor, branch, order_type, lines, adjustment, charge, total, order_id],
        sort_keys=True,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(body.encode()).hexdigest()
    value = f"{expires if expires is not None else int(time.time()) + QUOTE_SECONDS}.{digest}"
    return base64.urlsafe_b64encode(value.encode()).decode() + "." + _quote_mac(value)


def verify_quote(
    reference: Any,
    actor: str,
    branch: str,
    order_type: str,
    lines: list[dict[str, Any]],
    adjustment: str | None,
    charge: dict[str, Any] | None,
    total: int,
    order_id: str | None = None,
) -> None:
    if not isinstance(reference, str) or len(reference) > 250:
        raise BusinessError("delivery_contract_upgrade_required", "Delivery quote v2 is required")
    try:
        encoded, signature = reference.split(".")
        value = base64.urlsafe_b64decode(encoded).decode()
        expires = int(value.split(".")[0])
        if not hmac.compare_digest(signature, _quote_mac(value)) or expires < int(time.time()):
            raise ValueError("expired or invalid")
        expected = quote_reference(
            actor, branch, order_type, lines, adjustment, charge, total, order_id, expires=expires
        )
        if not hmac.compare_digest(reference, expected):
            raise ValueError("stale quote")
    except (ValueError, UnicodeError) as error:
        raise BusinessError(
            "delivery_quote_stale", "Delivery quote changed; quote again"
        ) from error
