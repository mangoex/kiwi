"""Read-only CC-D11 preparation. No function in this module activates a policy."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import (
    FinancialAuthority,
    governance_lock,
    protected_policy_revision,
)


class Review(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    user_id: str
    authorization_version: int = Field(ge=1)
    permissions_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    approval_reference: str = Field(min_length=1, max_length=500)


class ClientEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    component: Literal["pos", "admin", "gateway"]
    instance_id: str = Field(min_length=1, max_length=180)
    protocol_version: int = Field(ge=1)
    verification_reference: str = Field(min_length=1, max_length=500)


class TransitionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    users: list[Review] = Field(default_factory=list, max_length=5000)
    clients: list[ClientEvidence] = Field(default_factory=list, max_length=5000)
    reconciliation_reference: str | None = Field(default=None, min_length=1, max_length=500)


def block_legacy_gateway(session: Session, organization: str, branch: str) -> None:
    # Older isolated fixtures may predate 0101. Production must migrate before activation.
    if not sa.inspect(session.connection()).has_table("blind_cash_policy_revisions"):
        return
    governance_lock(session, organization)
    if protected_policy_revision(session, organization, branch) is not None:
        raise ops.BusinessError(
            "cash_gateway_upgrade_required", "A compatible protected gateway is required"
        )


def preflight(
    session: Session, actor: str, branch: str, evidence: TransitionInput
) -> dict[str, Any]:
    authority = FinancialAuthority(session, actor, ops.ORGANIZATION_ID)
    authority.require_capability("financial.delegations.manage", None)
    authority._branches([branch])
    blockers: list[dict[str, Any]] = []

    def block(code: str, **details: Any) -> None:
        blockers.append({"code": code, **details})

    def pending(table: sa.Table, condition: Any, code: str) -> None:
        count = session.scalar(
            sa.select(sa.func.count())
            .select_from(table)
            .where(
                table.c.organization_id == ops.ORGANIZATION_ID,
                table.c.branch_id == branch,
                condition,
            )
        )
        if count:
            block(code, count=int(count))

    pending(models.cash_shifts, models.cash_shifts.c.status == "OPEN", "open_shifts")
    pending(models.user_cash_cuts, models.user_cash_cuts.c.status != "FINALIZED", "pending_cuts")
    pending(
        models.physical_count_sessions,
        models.physical_count_sessions.c.status.in_(("counting", "submitted", "approved")),
        "pending_inventory_counts",
    )
    pending(
        models.operational_command_intents,
        models.operational_command_intents.c.state.in_(("ISSUED", "PENDING", "IN_FLIGHT")),
        "pending_commands",
    )
    pending(
        models.offline_order_inbox,
        models.offline_order_inbox.c.status == "CONFLICT",
        "sync_conflicts",
    )
    pending(
        models.offline_authorization_leases,
        models.offline_authorization_leases.c.expires_at >= ops._now(),
        "undrained_authority_leases",
    )
    pending(
        models.offline_order_grants,
        models.offline_order_grants.c.expires_at >= ops._now(),
        "undrained_order_grants",
    )
    pending(
        models.offline_order_gateway_leases,
        models.offline_order_gateway_leases.c.expires_at >= ops._now(),
        "undrained_gateway_leases",
    )
    correction_count = session.scalar(
        sa.select(sa.func.count())
        .select_from(models.user_cash_cut_reopen_requests.join(models.user_cash_cuts))
        .where(
            models.user_cash_cuts.c.organization_id == ops.ORGANIZATION_ID,
            models.user_cash_cuts.c.branch_id == branch,
            models.user_cash_cut_reopen_requests.c.status.in_(("REQUESTED", "APPROVED")),
        )
    )
    if correction_count:
        block("pending_corrections", count=int(correction_count))

    assignments = models.user_roles.join(models.roles)
    scoped = sa.and_(
        models.roles.c.organization_id == ops.ORGANIZATION_ID,
        sa.or_(
            sa.and_(
                models.roles.c.scope == "organization", models.user_roles.c.branch_id.is_(None)
            ),
            sa.and_(models.roles.c.scope == "branch", models.user_roles.c.branch_id == branch),
        ),
    )
    people = session.execute(
        sa.select(models.users.c.id, models.users.c.authorization_version)
        .where(
            models.users.c.organization_id == ops.ORGANIZATION_ID,
            models.users.c.status == "active",
            sa.exists(
                sa.select(models.user_roles.c.user_id)
                .select_from(assignments)
                .where(scoped, models.user_roles.c.user_id == models.users.c.id)
            ),
        )
        .order_by(models.users.c.id)
    ).all()
    supplied = {row.user_id: row for row in evidence.users}
    if len(supplied) != len(evidence.users) or set(supplied) - {row.id for row in people}:
        block("review_subjects_invalid")
    users = []
    for user_id, version in people:
        permissions = session.scalars(
            sa.select(models.permissions.c.code)
            .select_from(assignments.join(models.role_permissions).join(models.permissions))
            .where(scoped, models.user_roles.c.user_id == user_id)
            .distinct()
            .order_by(models.permissions.c.code)
        ).all()
        grants = (
            session.execute(
                sa.select(models.role_authority_grants.c.authority_kind)
                .select_from(assignments.join(models.role_authority_grants))
                .where(scoped, models.user_roles.c.user_id == user_id)
                .order_by(models.role_authority_grants.c.authority_kind)
            )
            .scalars()
            .all()
        )
        candidate = FinancialAuthority(session, str(user_id), ops.ORGANIZATION_ID)
        candidate._begin()
        is_owner = candidate._owner(int(version))
        caps, datasets = candidate.describe_scopes([branch], expected_version=int(version))[branch]
        digest = hashlib.sha256(
            json.dumps(
                {
                    "permissions": list(permissions),
                    "general_grants": list(grants),
                    "capabilities": caps,
                    "datasets": datasets,
                    "reviewed_owner": is_owner,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        users.append(
            {
                "user_id": str(user_id),
                "authorization_version": int(version),
                "permissions_digest": digest,
                "permissions": list(permissions),
                "general_grants": list(grants),
                "capabilities": caps,
                "datasets": datasets,
                "reviewed_owner": is_owner,
            }
        )
        review = supplied.get(str(user_id))
        if review is None:
            block("individual_review_missing", user_id=str(user_id))
        elif (review.authorization_version, review.permissions_digest) != (
            version,
            digest,
        ) or not review.approval_reference.strip():
            block("individual_review_stale", user_id=str(user_id))
        if "organization_all_permissions" in grants and not is_owner:
            block("unreviewed_general_authority", user_id=str(user_id))
    seen_clients = set()
    for client in evidence.clients:
        identity = (client.component, client.instance_id)
        if identity in seen_clients or not client.verification_reference.strip():
            block("client_evidence_invalid", instance_id=client.instance_id)
        seen_clients.add(identity)
        if client.protocol_version < 2:
            block("client_upgrade_required", instance_id=client.instance_id)
        if client.component == "gateway":
            block("gateway_protected_workflow_not_ready", instance_id=client.instance_id)
    if not {"pos", "admin"}.issubset({row.component for row in evidence.clients}):
        block("clients_not_verified")
    # A queue count cannot prove that disconnected devices have sent their last command.
    if not evidence.reconciliation_reference or not evidence.reconciliation_reference.strip():
        block("source_reconciliation_unverified")
    from restaurant_os.blind_cash_phase2 import denomination_catalog_ready

    if not denomination_catalog_ready(session, ops.ORGANIZATION_ID):
        block("phase2_capture_not_ready")
    result = {
        "branch_id": branch,
        "activation_allowed": False,
        "mode": "dry_run",
        "users": users,
        "blockers": blockers,
        "evidence": evidence.model_dump(mode="json"),
        "checked_at": ops._now().isoformat(),
    }
    result["manifest_digest"] = hashlib.sha256(
        json.dumps(result, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return result
