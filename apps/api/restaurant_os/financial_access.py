"""Transactional, idempotent administration of human financial read grants."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Any, Literal
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError
from sqlalchemy.orm import Session

from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.financial_authority import FinancialAuthority, governance_lock

Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)]
Dataset = Literal[
    "cash.shifts", "cash.cuts", "cash.movements", "sales", "reconciliation", "expenses"
]


class ScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    branch_id: UUID
    dataset: Dataset


class GrantInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject_user_id: UUID
    reason: Reason
    scopes: list[ScopeInput] = Field(min_length=1, max_length=1000)


class RevokeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Reason


def _receipt(command: sa.RowMapping, replay: bool) -> dict[str, Any]:
    return {
        "command_id": command["id"],
        "grant_id": command["grant_id"],
        "action": command["action"],
        "outcome": command["outcome"],
        "replay": replay,
        "accepted_at": ops._sanitize_for_json(command["created_at"]),
    }


class FinancialAccessService:
    def __init__(self, session: Session, organization_id: str) -> None:
        self.session, self.organization_id = session, organization_id

    def issue(self, actor: str, key: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._command(actor, key, payload, None)

    def revoke(
        self, actor: str, grant_id: str, key: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return self._command(actor, key, payload, grant_id)

    def _command(
        self, actor: str, key: str, payload: dict[str, Any], grant_id: str | None
    ) -> dict[str, Any]:
        try:
            return self._execute(actor, key, payload, grant_id)
        except BaseException:
            self.session.rollback()
            raise

    def _execute(
        self, actor: str, key: str, payload: dict[str, Any], grant_id: str | None
    ) -> dict[str, Any]:
        session, org = self.session, self.organization_id
        governance_lock(session, org, write=True)
        # Reauthorize BEFORE replay or loading a grant belonging to someone else.
        FinancialAuthority(session, actor, org).require_capability(
            "financial.delegations.manage", None
        )
        if not key.strip() or len(key) > 180:
            raise ops.BusinessError("invalid_idempotency_key", "A bounded command key is required")
        key = key.strip()
        try:
            request = (
                RevokeInput.model_validate(payload)
                if grant_id
                else GrantInput.model_validate(payload)
            )
        except ValidationError as exc:
            raise ops.BusinessError(
                "financial_request_invalid", "Invalid financial access command"
            ) from exc
        data = request.model_dump(mode="json")
        if isinstance(request, GrantInput):
            data["scopes"] = sorted(
                data["scopes"], key=lambda item: (item["branch_id"], item["dataset"])
            )
            pairs = {(str(item.branch_id), item.dataset) for item in request.scopes}
            if len(pairs) != len(request.scopes):
                raise ops.BusinessError("financial_request_invalid", "Duplicate financial scope")
        action = "revoke" if grant_id else "issue"
        digest = hashlib.sha256(
            json.dumps(
                {"action": action, "grant_id": grant_id, "payload": data},
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        ).hexdigest()
        commands = models.financial_access_commands
        previous = (
            session.execute(
                sa.select(commands).where(
                    commands.c.organization_id == org,
                    commands.c.actor_user_id == actor,
                    commands.c.idempotency_key == key,
                )
            )
            .mappings()
            .first()
        )
        if previous:
            if previous["request_hash"] != digest:
                raise ops.BusinessError(
                    "idempotency_key_conflict", "Command key has another payload"
                )
            result = _receipt(previous, True)
            session.commit()
            return result
        grants = models.financial_access_grants
        if grant_id:
            grant = (
                session.execute(
                    sa.select(grants).where(
                        grants.c.id == grant_id,
                        grants.c.organization_id == org,
                    )
                )
                .mappings()
                .first()
            )
            if grant is None:
                raise ops.AuthorizationError(
                    "financial_access_denied", "Requested access is not authorized"
                )
            subject = str(grant["subject_user_id"])
        else:
            assert isinstance(request, GrantInput)
            subject = str(request.subject_user_id)
            if subject == actor:
                raise ops.BusinessError(
                    "financial_owner_delegation_unnecessary",
                    "Owner already has default read access",
                )
        # The exclusive organization lock prevents a competing user/grant mutation.
        users = list(
            session.execute(
                sa.select(
                    models.users.c.id, models.users.c.status, models.users.c.authorization_version
                )
                .where(
                    models.users.c.organization_id == org,
                    models.users.c.id.in_(sorted({actor, subject})),
                )
                .order_by(models.users.c.id)
                .with_for_update()
            ).mappings()
        )
        subject_row = next((row for row in users if row["id"] == subject), None)
        if subject_row is None or (not grant_id and subject_row["status"] != "active"):
            raise ops.AuthorizationError(
                "financial_access_denied", "Requested access is not authorized"
            )
        command_id, now = ops._id(), ops._now()
        changed = True
        if not grant_id:
            assert isinstance(request, GrantInput)
            branches = sorted({str(item.branch_id) for item in request.scopes})
            actual = session.scalars(
                sa.select(models.branches.c.id)
                .where(
                    models.branches.c.organization_id == org,
                    models.branches.c.id.in_(branches),
                )
                .order_by(models.branches.c.id)
                .with_for_update()
            ).all()
            if set(actual) != set(branches):
                raise ops.AuthorizationError(
                    "financial_access_denied", "Requested access is not authorized"
                )
            ops._bump_authority_versions(session, [subject], org)
            grant_id = ops._id()
            session.execute(
                grants.insert().values(
                    id=grant_id,
                    organization_id=org,
                    subject_user_id=subject,
                    issuer_user_id=actor,
                    issued_at=now,
                    reason=request.reason,
                    authorization_version_at_issue=int(subject_row["authorization_version"]) + 1,
                )
            )
            session.execute(
                models.financial_access_grant_scopes.insert(),
                [{"organization_id": org, "grant_id": grant_id, **item} for item in data["scopes"]],
            )
            outcome = "issued"
        else:
            revoked = session.scalar(
                sa.select(models.financial_access_grant_revocations.c.grant_id).where(
                    models.financial_access_grant_revocations.c.grant_id == grant_id,
                )
            )
            changed = revoked is None
            outcome = "revoked" if changed else "already_revoked"
            if changed:
                ops._bump_authority_versions(session, [subject], org)
        session.execute(
            commands.insert().values(
                id=command_id,
                organization_id=org,
                actor_user_id=actor,
                idempotency_key=key,
                request_hash=digest,
                action=action,
                grant_id=grant_id,
                outcome=outcome,
                created_at=now,
            )
        )
        if action == "revoke" and changed:
            session.execute(
                models.financial_access_grant_revocations.insert().values(
                    organization_id=org,
                    grant_id=grant_id,
                    revoked_by=actor,
                    revoked_at=now,
                    reason=request.reason,
                    command_id=command_id,
                )
            )
        ops._audit(
            session,
            f"financial_access.{outcome}",
            "financial_access_grant",
            grant_id,
            {"command_id": command_id, "subject_user_id": subject, "reason": request.reason},
            organization_id=org,
            branch_id=None,
            actor_user_id=actor,
        )
        stored = (
            session.execute(sa.select(commands).where(commands.c.id == command_id)).mappings().one()
        )
        result = _receipt(stored, False)
        session.commit()
        return result

    def list_grants(self, actor: str, *, limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
        FinancialAuthority(self.session, actor, self.organization_id).require_capability(
            "financial.delegations.manage",
            None,
        )
        if not 1 <= limit <= 100 or offset < 0:
            raise ops.BusinessError("financial_request_invalid", "Invalid page")
        grants, scopes, revoked = (
            models.financial_access_grants,
            models.financial_access_grant_scopes,
            models.financial_access_grant_revocations,
        )
        rows = (
            self.session.execute(
                sa.select(grants)
                .where(
                    grants.c.organization_id == self.organization_id,
                )
                .order_by(grants.c.issued_at, grants.c.id)
                .limit(limit)
                .offset(offset)
            )
            .mappings()
            .all()
        )
        result = []
        for row in rows:
            pairs = self.session.execute(
                sa.select(scopes.c.branch_id, scopes.c.dataset)
                .where(
                    scopes.c.grant_id == row["id"],
                    scopes.c.organization_id == self.organization_id,
                )
                .order_by(scopes.c.branch_id, scopes.c.dataset)
            ).all()
            result.append(
                {
                    "id": row["id"],
                    "subject_user_id": row["subject_user_id"],
                    "issuer_user_id": row["issuer_user_id"],
                    "reason": row["reason"],
                    "issued_at": ops._sanitize_for_json(row["issued_at"]),
                    "scopes": [{"branch_id": pair[0], "dataset": pair[1]} for pair in pairs],
                    "revoked": self.session.scalar(
                        sa.select(revoked.c.grant_id).where(
                            revoked.c.grant_id == row["id"],
                        )
                    )
                    is not None,
                }
            )
        return result
