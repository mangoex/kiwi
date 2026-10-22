"""CORTE-CIEGO-001 Phase 2: Blind cash cut by denominations, payment methods, custody, and error
reports.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.blind_cash_phase2_schema import ensure_phase2_tables
from restaurant_os.cash_views import CashCommandReceiptV2, CashViews
from restaurant_os.financial_authority import FinancialAuthority, deny, governance_lock
from restaurant_os.owner_alerts import emit_owner_alert

STANDARD_MXN_DENOMINATIONS: tuple[tuple[int, str, str], ...] = (
    (100_000, "$1,000.00", "bill"),
    (50_000, "$500.00", "bill"),
    (20_000, "$200.00", "bill"),
    (10_000, "$100.00", "bill"),
    (5_000, "$50.00", "bill"),
    (2_000, "$20.00", "bill"),
    (1_000, "$10.00", "coin"),
    (500, "$5.00", "coin"),
    (200, "$2.00", "coin"),
    (100, "$1.00", "coin"),
    (50, "$0.50", "coin"),
)

NON_CASH_METHODS = ("debit", "credit", "transfer", "platform")


def denomination_catalog_ready(session: Session, organization_id: str) -> bool:
    """Return True if at least one active MXN denomination is configured for the organization."""
    inspector = sa.inspect(session.connection())
    if not inspector.has_table("blind_cash_denominations"):
        return False
    count = session.scalar(
        sa.select(sa.func.count())
        .select_from(models.blind_cash_denominations)
        .where(
            models.blind_cash_denominations.c.organization_id == organization_id,
            models.blind_cash_denominations.c.is_active.is_(True),
        )
    )
    return bool(count and int(count) > 0)


def configure_denominations(
    session: Session,
    actor: str,
    payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Owner-only configuration of the MXN denomination catalog (CC-D04)."""
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    version = authority._begin()
    if not authority._owner(version):
        deny()

    use_standard = bool(payload.get("use_standard_mxn", False))
    raw_items = payload.get("denominations")
    if use_standard and raw_items is None:
        items_to_apply = [
            {
                "denomination_cents": cents,
                "label": label,
                "kind": kind,
                "is_active": True,
            }
            for cents, label, kind in STANDARD_MXN_DENOMINATIONS
        ]
    else:
        if not isinstance(raw_items, list) or not raw_items:
            raise ops.BusinessError(
                "denomination_catalog_invalid", "At least one denomination is required"
            )
        items_to_apply = raw_items

    seen_cents: set[int] = set()
    normalized: list[dict[str, Any]] = []
    for item in items_to_apply:
        if not isinstance(item, dict):
            raise ops.BusinessError("denomination_catalog_invalid", "Invalid denomination entry")
        cents = item.get("denomination_cents")
        if not isinstance(cents, int) or isinstance(cents, bool) or cents <= 0:
            raise ops.BusinessError(
                "denomination_catalog_invalid",
                "denomination_cents must be a positive integer in centavos",
            )
        if cents in seen_cents:
            raise ops.BusinessError(
                "denomination_catalog_invalid", "Duplicate denomination_cents in catalog"
            )
        seen_cents.add(cents)
        kind = str(item.get("kind", "bill" if cents >= 2000 else "coin"))
        if kind not in {"bill", "coin"}:
            raise ops.BusinessError("denomination_catalog_invalid", "kind must be bill or coin")
        label = str(item.get("label") or f"${cents / 100:,.2f}").strip()
        is_active = bool(item.get("is_active", True))
        normalized.append(
            {
                "denomination_cents": cents,
                "label": label,
                "kind": kind,
                "is_active": is_active,
            }
        )

    table = models.blind_cash_denominations
    now = ops._now()
    existing_rows = {
        int(row["denomination_cents"]): dict(row)
        for row in session.execute(
            sa.select(table).where(table.c.organization_id == ops.ORGANIZATION_ID)
        ).mappings()
    }

    if payload.get("replace_active", True):
        session.execute(
            table.update()
            .where(table.c.organization_id == ops.ORGANIZATION_ID)
            .values(is_active=False, updated_by_user_id=actor, updated_at=now)
        )

    for entry in normalized:
        cents = entry["denomination_cents"]
        if cents in existing_rows:
            session.execute(
                table.update()
                .where(table.c.id == existing_rows[cents]["id"])
                .values(
                    label=entry["label"],
                    kind=entry["kind"],
                    is_active=entry["is_active"],
                    updated_by_user_id=actor,
                    updated_at=now,
                )
            )
        else:
            session.execute(
                table.insert().values(
                    id=ops._id(),
                    organization_id=ops.ORGANIZATION_ID,
                    denomination_cents=cents,
                    label=entry["label"],
                    kind=entry["kind"],
                    is_active=entry["is_active"],
                    updated_by_user_id=actor,
                    created_at=now,
                    updated_at=now,
                )
            )

    session.commit()
    return [
        dict(row)
        for row in session.execute(
            sa.select(table)
            .where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.is_active.is_(True),
            )
            .order_by(table.c.denomination_cents.desc())
        ).mappings()
    ]


def list_denominations(
    session: Session,
    actor: str,
    branch_id: str,
) -> list[dict[str, Any]]:
    """Return active MXN denominations for a branch operator or Owner."""
    ensure_phase2_tables(session)
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    version = authority._begin()
    authority._branches([branch_id])
    if not (
        authority._owner(version)
        or authority._explicit("cash.user_cut.capture", branch_id)
        or authority._explicit("cash.user_cut.operational.read", branch_id)
        or authority._explicit("cash.user_cut.finalize", branch_id)
    ):
        deny()

    table = models.blind_cash_denominations
    return [
        {
            "id": row["id"],
            "denomination_cents": int(row["denomination_cents"]),
            "label": row["label"],
            "kind": row["kind"],
            "is_active": bool(row["is_active"]),
        }
        for row in session.execute(
            sa.select(table)
            .where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.is_active.is_(True),
            )
            .order_by(table.c.denomination_cents.desc())
        ).mappings()
    ]


def _validate_and_compute_declaration(
    session: Session,
    payload: dict[str, Any],
) -> tuple[int, list[dict[str, Any]], dict[str, dict[str, Any]]]:
    """Validate denomination pieces and payment methods in Python, rejecting client totals."""
    forbidden_client_totals = {
        "counted_cash_cents",
        "total_cents",
        "expected_cash_cents",
        "difference_cents",
    }
    if forbidden_client_totals & set(payload):
        raise ops.BusinessError(
            "client_total_forbidden",
            "Client-calculated totals are not accepted; submit denomination piece counts only",
        )
    allowed_keys = {
        "denominations",
        "payment_methods",
        "substitution_reason",
        "version",
    }
    if set(payload) - allowed_keys:
        raise ops.BusinessError(
            "cash_declaration_payload_invalid", "Unsupported declaration fields"
        )

    active_denoms = {
        int(row["denomination_cents"]): dict(row)
        for row in session.execute(
            sa.select(models.blind_cash_denominations).where(
                models.blind_cash_denominations.c.organization_id == ops.ORGANIZATION_ID,
                models.blind_cash_denominations.c.is_active.is_(True),
            )
        ).mappings()
    }
    if not active_denoms:
        raise ops.BusinessError("cash_capture_not_ready", "Denomination catalog is not configured")

    raw_denoms = payload.get("denominations")
    if not isinstance(raw_denoms, list) or not raw_denoms:
        raise ops.BusinessError("cash_denominations_required", "Denomination breakdown is required")

    seen_denoms: set[int] = set()
    denom_snapshot: list[dict[str, Any]] = []
    counted_cash_cents = 0

    for item in raw_denoms:
        if not isinstance(item, dict) or set(item) - {"denomination_cents", "piece_count"}:
            raise ops.BusinessError(
                "cash_denomination_invalid",
                "Each denomination line must specify only denomination_cents and piece_count",
            )
        cents = item.get("denomination_cents")
        pieces = item.get("piece_count")
        if not isinstance(cents, int) or isinstance(cents, bool) or cents not in active_denoms:
            raise ops.BusinessError(
                "cash_denomination_unknown",
                f"Denomination {cents} is not enabled in the catalog",
            )
        if (
            not isinstance(pieces, int)
            or isinstance(pieces, bool)
            or pieces < 0
            or pieces > 1_000_000
        ):
            raise ops.BusinessError(
                "cash_piece_count_invalid",
                "piece_count must be a non-negative integer",
            )
        if cents in seen_denoms:
            raise ops.BusinessError(
                "cash_denomination_duplicate", "Duplicate denomination in declaration"
            )
        seen_denoms.add(cents)
        subtotal = cents * pieces
        counted_cash_cents += subtotal
        cat = active_denoms[cents]
        denom_snapshot.append(
            {
                "denomination_cents": cents,
                "label": str(cat["label"]),
                "kind": str(cat["kind"]),
                "piece_count": pieces,
                "subtotal_cents": subtotal,
            }
        )

    denom_snapshot.sort(key=lambda d: int(d["denomination_cents"]), reverse=True)

    raw_methods = payload.get("payment_methods", {})
    if not isinstance(raw_methods, dict) or set(raw_methods) - set(NON_CASH_METHODS):
        raise ops.BusinessError(
            "cash_payment_methods_invalid",
            "payment_methods must map only supported non-cash methods",
        )

    methods_snapshot: dict[str, dict[str, Any]] = {}
    for method in NON_CASH_METHODS:
        entry = raw_methods.get(method)
        if entry is None:
            # Empty means not counted, distinct from explicit zero (CC-D04).
            methods_snapshot[method] = {
                "declared_cents": None,
                "voucher_count": 0,
                "references": [],
                "explicit_zero": False,
            }
            continue
        if not isinstance(entry, dict) or set(entry) - {
            "declared_cents",
            "voucher_count",
            "references",
        }:
            raise ops.BusinessError(
                "cash_payment_method_entry_invalid",
                f"Invalid declaration entry for payment method {method}",
            )
        declared = entry.get("declared_cents")
        if declared is not None and (
            not isinstance(declared, int) or isinstance(declared, bool) or declared < 0
        ):
            raise ops.BusinessError(
                "cash_payment_method_amount_invalid",
                f"declared_cents for {method} must be null or a non-negative integer in centavos",
            )
        vouchers = entry.get("voucher_count", 0)
        if not isinstance(vouchers, int) or isinstance(vouchers, bool) or vouchers < 0:
            raise ops.BusinessError(
                "cash_payment_method_vouchers_invalid",
                f"voucher_count for {method} must be a non-negative integer",
            )
        refs = entry.get("references", [])
        if not isinstance(refs, list) or any(not isinstance(r, str) or not r.strip() for r in refs):
            raise ops.BusinessError(
                "cash_payment_method_references_invalid",
                f"references for {method} must be a list of non-empty strings",
            )
        methods_snapshot[method] = {
            "declared_cents": declared,
            "voucher_count": vouchers,
            "references": [r.strip() for r in refs],
            "explicit_zero": declared == 0,
        }

    return counted_cash_cents, denom_snapshot, methods_snapshot


def _authorize_capture_actor(
    views: CashViews,
    meta: dict[str, Any],
    actor: str,
    substitution_reason: str | None,
) -> tuple[bool, str | None]:
    """Enforce CC-D03: Cashier on own shift, or Manager substitution with reason. Never Owner by
    inference.
    """
    branch = str(meta["branch_id"])
    views.authority._begin()
    # Initial capture by Owner is not granted by inference unless explicitly holding
    # cash.user_cut.capture
    if not views.authority._explicit("cash.user_cut.capture", branch):
        deny()
    views.authority.require_capability("cash.user_cut.operational.read", branch)

    responsible = str(meta["cashier_user_id"])
    if actor == responsible:
        return False, None

    # Substitute must have manager finalization authority on the branch and provide a reason
    # (CC-D03).
    if not views.authority._explicit("cash.user_cut.finalize", branch):
        deny()
    reason = (substitution_reason or "").strip()
    if not reason:
        raise ops.BusinessError(
            "cash_substitution_reason_required",
            "Manager substitution capture requires an explicit substitution_reason",
        )
    return True, reason


def save_declaration_draft(
    session: Session,
    actor: str,
    cut_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Save or update an editable blind declaration draft before single confirmation (CC-D04)."""
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    views = CashViews(session, actor)
    meta = views.metadata("cut", cut_id)
    branch = str(meta["branch_id"])
    policy_version = views.revision(branch)

    is_sub, sub_reason = _authorize_capture_actor(
        views, meta, actor, payload.get("substitution_reason")
    )
    cut_row = (
        session.execute(
            sa.select(
                models.user_cash_cuts.c.status, models.user_cash_cuts.c.cashier_user_id
            ).where(
                models.user_cash_cuts.c.id == cut_id,
                models.user_cash_cuts.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .one()
    )
    if cut_row["status"] != "DRAFT":
        raise ops.BusinessError(
            "cash_cut_already_counted",
            "Confirmed or finalized declarations cannot be edited",
        )

    counted_cash_cents, denom_snapshot, methods_snapshot = _validate_and_compute_declaration(
        session, payload
    )
    decl_table = models.user_cash_cut_declarations
    existing = (
        session.execute(
            sa.select(decl_table).where(
                decl_table.c.cash_cut_id == cut_id,
                decl_table.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    now = ops._now()
    history_entry = {
        "revision": 1 if existing is None else int(existing["revision"]) + 1,
        "actor_user_id": actor,
        "saved_at": now.isoformat(),
        "counted_cash_cents": counted_cash_cents,
        "denominations_snapshot": denom_snapshot,
        "payment_methods_snapshot": methods_snapshot,
        "is_substitution": is_sub,
        "substitution_reason": sub_reason,
    }

    if existing is None:
        draft_history = [history_entry]
        revision = 1
        session.execute(
            decl_table.insert().values(
                cash_cut_id=cut_id,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=branch,
                responsible_user_id=str(cut_row["cashier_user_id"]),
                capturer_user_id=actor,
                is_substitution=is_sub,
                substitution_reason=sub_reason,
                state="DRAFT",
                revision=revision,
                counted_cash_cents=counted_cash_cents,
                denominations_snapshot=denom_snapshot,
                payment_methods_snapshot=methods_snapshot,
                draft_history=draft_history,
                confirmed_at=None,
                updated_at=now,
            )
        )
    else:
        if existing["state"] != "DRAFT":
            raise ops.BusinessError(
                "cash_cut_already_counted",
                "Confirmed declaration cannot be modified",
            )
        revision = int(existing["revision"]) + 1
        draft_history = [*list(existing["draft_history"]), history_entry]
        session.execute(
            decl_table.update()
            .where(decl_table.c.cash_cut_id == cut_id)
            .values(
                capturer_user_id=actor,
                is_substitution=is_sub,
                substitution_reason=sub_reason,
                revision=revision,
                counted_cash_cents=counted_cash_cents,
                denominations_snapshot=denom_snapshot,
                payment_methods_snapshot=methods_snapshot,
                draft_history=draft_history,
                updated_at=now,
            )
        )

    session.commit()
    return {
        "projection": "own_declaration",
        "schema_version": 2,
        "policy_version": policy_version,
        "resource_id": cut_id,
        "responsible_user_id": str(cut_row["cashier_user_id"]),
        "capturer_user_id": actor,
        "is_substitution": is_sub,
        "substitution_reason": sub_reason,
        "state": "DRAFT",
        "revision": revision,
        "counted_cash_cents": counted_cash_cents,
        "denominations": denom_snapshot,
        "payment_methods": methods_snapshot,
        "draft_revisions_count": len(draft_history),
    }


def confirm_declaration(
    session: Session,
    actor: str,
    cut_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """Confirm the single immutable blind cash & payment-method declaration (CC-D03, CC-D04)."""
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    views = CashViews(session, actor)
    meta = views.metadata("cut", cut_id)
    branch = str(meta["branch_id"])
    policy_version = views.revision(branch)
    key = ops.UserCashCutService._key(idempotency_key)

    canonical_hash = hashlib.sha256(
        json.dumps(
            {
                "action": "confirm_declaration",
                "actor": actor,
                "cut_id": cut_id,
                "payload": payload,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()

    decl_table = models.user_cash_cut_declarations
    existing_decl = (
        session.execute(
            sa.select(decl_table).where(
                decl_table.c.cash_cut_id == cut_id,
                decl_table.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )

    commands = models.user_cash_cut_commands
    stored_cmd = (
        session.execute(
            sa.select(commands).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if stored_cmd is not None:
        if stored_cmd["actor_user_id"] != actor:
            deny()
        views.require_cut_read(meta)
        if existing_decl is not None and existing_decl["state"] == "CONFIRMED":
            # Verify payload matches confirmed declaration
            counted_cash_cents, denom_snapshot, methods_snapshot = (
                _validate_and_compute_declaration(session, payload)
            )
            if (
                counted_cash_cents != existing_decl["counted_cash_cents"]
                or denom_snapshot != existing_decl["denominations_snapshot"]
                or methods_snapshot != existing_decl["payment_methods_snapshot"]
            ):
                raise ops.BusinessError("idempotency_conflict", "Command identity changed")
            cut_ver = session.scalar(
                sa.select(models.user_cash_cuts.c.version).where(
                    models.user_cash_cuts.c.id == cut_id
                )
            )
            return CashCommandReceiptV2(
                command_id=stored_cmd["id"],
                resource_id=cut_id,
                action="count",
                status="COUNTED",
                version=int(cut_ver or 2),
                accepted_at=stored_cmd["created_at"],
                replay=True,
                correlation_id=stored_cmd["id"],
                policy_version=policy_version,
            ).model_dump(mode="json")

    is_sub, sub_reason = _authorize_capture_actor(
        views, meta, actor, payload.get("substitution_reason")
    )
    cut_row = (
        session.execute(
            sa.select(
                models.user_cash_cuts.c.status,
                models.user_cash_cuts.c.version,
                models.user_cash_cuts.c.cashier_user_id,
            ).where(
                models.user_cash_cuts.c.id == cut_id,
                models.user_cash_cuts.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .one()
    )
    if cut_row["status"] != "DRAFT" or (
        existing_decl is not None and existing_decl["state"] == "CONFIRMED"
    ):
        raise ops.BusinessError(
            "cash_cut_already_counted",
            "Declaration has already been confirmed and cannot be replaced",
        )

    counted_cash_cents, denom_snapshot, methods_snapshot = _validate_and_compute_declaration(
        session, payload
    )
    expected_version = int(payload.get("version", cut_row["version"]))
    now = ops._now()

    # Execute canonical UserCashCutService.counted_cash body inside our transaction
    service = ops.UserCashCutService(session)
    raw_counted = getattr(
        ops.UserCashCutService.counted_cash, "__wrapped__", ops.UserCashCutService.counted_cash
    )
    raw_counted(
        service,
        cut_id,
        {"counted_cash_cents": counted_cash_cents, "version": expected_version},
        key,
        actor,
    )

    history_entry = {
        "revision": 1 if existing_decl is None else int(existing_decl["revision"]) + 1,
        "actor_user_id": actor,
        "saved_at": now.isoformat(),
        "confirmed": True,
        "request_hash": canonical_hash,
        "counted_cash_cents": counted_cash_cents,
        "denominations_snapshot": denom_snapshot,
        "payment_methods_snapshot": methods_snapshot,
        "is_substitution": is_sub,
        "substitution_reason": sub_reason,
    }
    if existing_decl is None:
        session.execute(
            decl_table.insert().values(
                cash_cut_id=cut_id,
                organization_id=ops.ORGANIZATION_ID,
                branch_id=branch,
                responsible_user_id=str(cut_row["cashier_user_id"]),
                capturer_user_id=actor,
                is_substitution=is_sub,
                substitution_reason=sub_reason,
                state="CONFIRMED",
                revision=1,
                counted_cash_cents=counted_cash_cents,
                denominations_snapshot=denom_snapshot,
                payment_methods_snapshot=methods_snapshot,
                draft_history=[history_entry],
                confirmed_at=now,
                updated_at=now,
            )
        )
    else:
        session.execute(
            decl_table.update()
            .where(decl_table.c.cash_cut_id == cut_id)
            .values(
                capturer_user_id=actor,
                is_substitution=is_sub,
                substitution_reason=sub_reason,
                state="CONFIRMED",
                revision=int(existing_decl["revision"]) + 1,
                counted_cash_cents=counted_cash_cents,
                denominations_snapshot=denom_snapshot,
                payment_methods_snapshot=methods_snapshot,
                draft_history=[*list(existing_decl["draft_history"]), history_entry],
                confirmed_at=now,
                updated_at=now,
            )
        )
    # Preserve original responsible cashier on user_cash_cuts if substitution occurred (CC-D03)
    if is_sub:
        session.execute(
            models.user_cash_cuts.update()
            .where(models.user_cash_cuts.c.id == cut_id)
            .values(cashier_user_id=str(cut_row["cashier_user_id"]))
        )
    session.commit()

    cmd_row = (
        session.execute(
            sa.select(commands.c.id, commands.c.created_at).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .one()
    )
    return CashCommandReceiptV2(
        command_id=cmd_row["id"],
        resource_id=cut_id,
        action="count",
        status="COUNTED",
        version=expected_version + 1,
        accepted_at=cmd_row["created_at"],
        replay=False,
        correlation_id=cmd_row["id"],
        policy_version=policy_version,
    ).model_dump(mode="json")


def finalize_blind_cut(
    session: Session,
    actor: str,
    cut_id: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> dict[str, Any]:
    """Finalize a Phase 2 blind cut, computing per-method reconciliation & difference alerts
    (CC-D03,
    D05, D06).
    """
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    views = CashViews(session, actor)
    meta = views.metadata("cut", cut_id)
    branch = str(meta["branch_id"])
    policy_version = views.revision(branch)
    key = ops.UserCashCutService._key(idempotency_key)

    decl = (
        session.execute(
            sa.select(models.user_cash_cut_declarations).where(
                models.user_cash_cut_declarations.c.cash_cut_id == cut_id,
                models.user_cash_cut_declarations.c.organization_id == ops.ORGANIZATION_ID,
                models.user_cash_cut_declarations.c.state == "CONFIRMED",
            )
        )
        .mappings()
        .first()
    )
    if decl is None:
        # Legacy flat-counted cuts without Phase 2 declaration cannot use Phase 2 HTTP finalize gate
        views.authority.require_capability("cash.user_cut.finalize", branch)
        raise ops.BusinessError("cash_capture_not_ready", "Phase 2 capture is not active")

    commands = models.user_cash_cut_commands
    stored_cmd = (
        session.execute(
            sa.select(commands).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if stored_cmd is not None:
        if stored_cmd["actor_user_id"] != actor:
            deny()
        views.require_cut_read(meta)
        cut_ver = session.scalar(
            sa.select(models.user_cash_cuts.c.version).where(models.user_cash_cuts.c.id == cut_id)
        )
        return CashCommandReceiptV2(
            command_id=stored_cmd["id"],
            resource_id=cut_id,
            action="finalize",
            status="FINALIZED",
            version=int(cut_ver or 3),
            accepted_at=stored_cmd["created_at"],
            replay=True,
            correlation_id=stored_cmd["id"],
            policy_version=policy_version,
        ).model_dump(mode="json")

    views.authority.require_capability("cash.user_cut.finalize", branch)
    views.require_cut_read(meta)

    # CC-D10 completeness guard: unknown local operations or sync conflicts block finalization
    pending_sync = session.scalar(
        sa.select(sa.func.count())
        .select_from(models.offline_order_inbox)
        .where(
            models.offline_order_inbox.c.organization_id == ops.ORGANIZATION_ID,
            models.offline_order_inbox.c.branch_id == branch,
            models.offline_order_inbox.c.status == "CONFLICT",
        )
    )
    if pending_sync:
        raise ops.BusinessError(
            "cash_shift_sync_incomplete",
            "Cannot finalize cut while offline sync conflicts remain unresolved",
        )

    cut_before = (
        session.execute(
            sa.select(models.user_cash_cuts).where(
                models.user_cash_cuts.c.id == cut_id,
                models.user_cash_cuts.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .one()
    )
    expected_version = int(payload.get("version", cut_before["version"]))
    external_pendings: dict[str, str] = {}
    raw_pendings = payload.get("external_pending_methods", {})
    if isinstance(raw_pendings, dict):
        for m_name, reason in raw_pendings.items():
            if m_name not in NON_CASH_METHODS or not isinstance(reason, str) or not reason.strip():
                raise ops.BusinessError(
                    "cash_reconciliation_pending_invalid",
                    "external_pending_methods must map valid non-cash methods to non-empty reasons",
                )
            external_pendings[m_name] = reason.strip()

    service = ops.UserCashCutService(session)
    raw_finalize = getattr(
        ops.UserCashCutService.finalize, "__wrapped__", ops.UserCashCutService.finalize
    )
    raw_finalize(
        service,
        cut_id,
        {"version": expected_version},
        key,
        actor,
    )

    cut_after = (
        session.execute(
            sa.select(models.user_cash_cuts).where(
                models.user_cash_cuts.c.id == cut_id,
                models.user_cash_cuts.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .one()
    )

    # Compute per-method reconciliation (CC-D05, CC-D06: zero tolerance, never net across methods)
    reconcil_table = models.user_cash_cut_method_reconciliations
    session.execute(reconcil_table.delete().where(reconcil_table.c.cash_cut_id == cut_id))
    now = ops._now()

    expected_cash = int(cut_after["expected_cash_cents"])
    declared_cash = int(decl["counted_cash_cents"])
    cash_diff = declared_cash - expected_cash

    method_rows: list[dict[str, Any]] = [
        {
            "id": ops._id(),
            "cash_cut_id": cut_id,
            "organization_id": ops.ORGANIZATION_ID,
            "branch_id": branch,
            "payment_method": "cash",
            "declared_cents": declared_cash,
            "expected_cents": expected_cash,
            "difference_cents": cash_diff,
            "reconciliation_status": "RECONCILED",
            "pending_reason": None,
            "source_references": [f"shift:{cut_after['cash_shift_id']}"],
            "created_at": now,
            "updated_at": now,
        }
    ]

    # Query confirmed non-cash payments in the shift period
    p_table = models.payments
    o_table = models.orders
    shift_payments = list(
        session.execute(
            sa.select(
                p_table.c.id,
                p_table.c.method,
                p_table.c.amount_cents,
            )
            .select_from(p_table.join(o_table, p_table.c.order_id == o_table.c.id))
            .where(
                p_table.c.organization_id == ops.ORGANIZATION_ID,
                o_table.c.branch_id == branch,
                p_table.c.status == "CONFIRMED",
                p_table.c.created_at >= cut_after["period_start"],
                p_table.c.created_at < cut_after["period_end"],
                p_table.c.method != "cash",
            )
        ).mappings()
    )

    methods_snap: dict[str, Any] = dict(decl["payment_methods_snapshot"] or {})
    for method in NON_CASH_METHODS:
        m_entry = methods_snap.get(method) or {}
        declared_val = m_entry.get("declared_cents")
        if method in external_pendings:
            # Insufficient external source: preserve declaration and pending reason, never fake 0
            # (CC-D05)
            method_rows.append(
                {
                    "id": ops._id(),
                    "cash_cut_id": cut_id,
                    "organization_id": ops.ORGANIZATION_ID,
                    "branch_id": branch,
                    "payment_method": method,
                    "declared_cents": declared_val,
                    "expected_cents": None,
                    "difference_cents": None,
                    "reconciliation_status": "PENDING_EXTERNAL",
                    "pending_reason": external_pendings[method],
                    "source_references": list(m_entry.get("references", [])),
                    "created_at": now,
                    "updated_at": now,
                }
            )
            continue

        matching = [
            p
            for p in shift_payments
            if str(p["method"]).lower() == method
            or (method == "debit" and str(p["method"]).lower() == "card")
        ]
        expected_val = sum(int(p["amount_cents"]) for p in matching)
        if declared_val is None and expected_val == 0:
            diff_val: int | None = 0
        elif declared_val is None:
            # Not counted while payments exist -> pending reconciliation with reason
            method_rows.append(
                {
                    "id": ops._id(),
                    "cash_cut_id": cut_id,
                    "organization_id": ops.ORGANIZATION_ID,
                    "branch_id": branch,
                    "payment_method": method,
                    "declared_cents": None,
                    "expected_cents": None,
                    "difference_cents": None,
                    "reconciliation_status": "PENDING_EXTERNAL",
                    "pending_reason": "method_not_declared",
                    "source_references": [str(p["id"]) for p in matching],
                    "created_at": now,
                    "updated_at": now,
                }
            )
            continue
        else:
            diff_val = int(declared_val) - expected_val

        method_rows.append(
            {
                "id": ops._id(),
                "cash_cut_id": cut_id,
                "organization_id": ops.ORGANIZATION_ID,
                "branch_id": branch,
                "payment_method": method,
                "declared_cents": declared_val,
                "expected_cents": expected_val,
                "difference_cents": diff_val,
                "reconciliation_status": "RECONCILED",
                "pending_reason": None,
                "source_references": [str(p["id"]) for p in matching],
                "created_at": now,
                "updated_at": now,
            }
        )

    for m_row in method_rows:
        session.execute(reconcil_table.insert().values(**m_row))

    # CC-D06: 0.00 MXN tolerance -> any confirmed non-zero difference in ANY method triggers Owner
    # alert
    non_zero_methods = [
        {
            "payment_method": r["payment_method"],
            "declared_cents": r["declared_cents"],
            "expected_cents": r["expected_cents"],
            "difference_cents": r["difference_cents"],
        }
        for r in method_rows
        if r["reconciliation_status"] == "RECONCILED"
        and r["difference_cents"] is not None
        and int(r["difference_cents"]) != 0
    ]
    if non_zero_methods:
        emit_owner_alert(
            session,
            branch_id=branch,
            alert_type="cash_cut_difference",
            severity="critical",
            resource_type="user_cash_cut",
            resource_id=cut_id,
            dedupe_key=f"cash_cut_diff:{cut_id}",
            title=f"Diferencia confirmada en corte de caja {cut_id}",
            payload={
                "cash_cut_id": cut_id,
                "cash_shift_id": str(cut_after["cash_shift_id"]),
                "responsible_user_id": str(decl["responsible_user_id"]),
                "capturer_user_id": str(decl["capturer_user_id"]),
                "finalized_by_user_id": actor,
                "differences": non_zero_methods,
            },
        )

    if "retained_fund_cents" in payload and payload["retained_fund_cents"] is not None:
        retained = int(payload["retained_fund_cents"])
        if retained < 0 or retained > declared_cash:
            raise ops.BusinessError(
                "cash_retained_fund_invalid",
                "retained_fund_cents must be between 0 and counted_cash_cents",
            )
        session.execute(
            models.user_cash_cut_declarations.update()
            .where(models.user_cash_cut_declarations.c.cash_cut_id == cut_id)
            .values(retained_fund_cents=retained, updated_at=now)
        )

    session.commit()
    cmd_row = (
        session.execute(
            sa.select(commands.c.id, commands.c.created_at).where(
                commands.c.organization_id == ops.ORGANIZATION_ID,
                commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .one()
    )
    return CashCommandReceiptV2(
        command_id=cmd_row["id"],
        resource_id=cut_id,
        action="finalize",
        status="FINALIZED",
        version=int(cut_after["version"]),
        accepted_at=cmd_row["created_at"],
        replay=False,
        correlation_id=cmd_row["id"],
        policy_version=policy_version,
    ).model_dump(mode="json")


def record_custody_delivery(
    session: Session,
    actor: str,
    cut_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Record custody receiver and UTC timestamp without altering the count (CC-D04)."""
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    views = CashViews(session, actor)
    meta = views.metadata("cut", cut_id)
    branch = str(meta["branch_id"])
    policy_version = views.revision(branch)
    views.require_cut_read(meta)

    receiver_id = str(payload.get("receiver_user_id", "")).strip()
    notes = str(payload.get("notes", "")).strip() or None
    if not receiver_id:
        raise ops.BusinessError("custody_receiver_required", "receiver_user_id is required")

    decl_table = models.user_cash_cut_declarations
    decl = (
        session.execute(
            sa.select(decl_table).where(
                decl_table.c.cash_cut_id == cut_id,
                decl_table.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if decl is None or decl["state"] != "CONFIRMED":
        raise ops.BusinessError(
            "cash_cut_not_confirmed", "Custody delivery requires a confirmed declaration"
        )

    now = ops._now()
    session.execute(
        decl_table.update()
        .where(decl_table.c.cash_cut_id == cut_id)
        .values(
            custody_delivered_at=now,
            custody_receiver_user_id=receiver_id,
            custody_notes=notes,
            updated_at=now,
        )
    )
    session.commit()
    return {
        "projection": "operational",
        "schema_version": 2,
        "policy_version": policy_version,
        "cash_cut_id": cut_id,
        "custody_receiver_user_id": receiver_id,
        "custody_delivered_at": now.isoformat(),
        "custody_notes": notes,
    }


def report_cut_error(
    session: Session,
    actor: str,
    cut_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Allow Cashier or Manager to report a declaration error without editing or exposing expected
    (CC-D07).
    """
    ensure_phase2_tables(session)
    governance_lock(session, ops.ORGANIZATION_ID, write=True)
    views = CashViews(session, actor)
    meta = views.metadata("cut", cut_id)
    branch = str(meta["branch_id"])
    policy_version = views.revision(branch)
    views.require_cut_read(meta)

    reason = str(payload.get("reason", "")).strip()
    evidence_refs = payload.get("evidence_refs", [])
    if not reason:
        raise ops.BusinessError("error_report_reason_required", "A non-empty reason is required")
    if not isinstance(evidence_refs, list) or any(
        not isinstance(r, str) or not r.strip() for r in evidence_refs
    ):
        raise ops.BusinessError(
            "error_report_evidence_invalid", "evidence_refs must be a list of strings"
        )

    report_id = ops._id()
    now = ops._now()
    session.execute(
        models.user_cash_cut_error_reports.insert().values(
            id=report_id,
            cash_cut_id=cut_id,
            organization_id=ops.ORGANIZATION_ID,
            branch_id=branch,
            reporter_user_id=actor,
            reason=reason,
            evidence_refs=[r.strip() for r in evidence_refs],
            created_at=now,
        )
    )
    session.commit()
    return {
        "projection": "operational",
        "schema_version": 2,
        "policy_version": policy_version,
        "report_id": report_id,
        "cash_cut_id": cut_id,
        "reporter_user_id": actor,
        "reported_at": now.isoformat(),
    }


def get_financial_reconciliation_detail(
    session: Session,
    actor: str,
    cut_id: str,
) -> dict[str, Any]:
    """Return full financial reconciliation by method, declaration snapshot, and error reports
    (CC-D01,
    D05, D07).
    """
    ensure_phase2_tables(session)
    views = CashViews(session, actor)
    base = views.detail("cut", cut_id, financial=True)

    decl = (
        session.execute(
            sa.select(models.user_cash_cut_declarations).where(
                models.user_cash_cut_declarations.c.cash_cut_id == cut_id,
                models.user_cash_cut_declarations.c.organization_id == ops.ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    reconciliations = [
        dict(row)
        for row in session.execute(
            sa.select(models.user_cash_cut_method_reconciliations)
            .where(
                models.user_cash_cut_method_reconciliations.c.cash_cut_id == cut_id,
                models.user_cash_cut_method_reconciliations.c.organization_id
                == ops.ORGANIZATION_ID,
            )
            .order_by(models.user_cash_cut_method_reconciliations.c.payment_method)
        ).mappings()
    ]
    error_reports = [
        dict(row)
        for row in session.execute(
            sa.select(models.user_cash_cut_error_reports)
            .where(
                models.user_cash_cut_error_reports.c.cash_cut_id == cut_id,
                models.user_cash_cut_error_reports.c.organization_id == ops.ORGANIZATION_ID,
            )
            .order_by(models.user_cash_cut_error_reports.c.created_at)
        ).mappings()
    ]
    return {
        **base,
        "declaration": dict(decl) if decl is not None else None,
        "method_reconciliations": reconciliations,
        "error_reports": error_reports,
    }
