"""GROKBOT-001 governed external-agent boundary.

One conversational orchestrator may coordinate four private specialists, but Kiwi always
authorizes the technical identity attached to the concrete tool credential. External writes are
limited to reviewable proposals and purchase drafts; no endpoint applies catalog, receives stock,
or moves cash.
"""

from __future__ import annotations

import base64
import hashlib
import ipaddress
import json
import logging
import secrets
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Annotated, Any, Literal, NoReturn, Optional
from urllib.parse import parse_qs, urlparse
from uuid import UUID, uuid4

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    ValidationError,
    field_validator,
    model_validator,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from restaurant_os import admin_ai, models
from restaurant_os.auth import (
    create_session_token,
    generate_password_salt,
    hash_password,
    verify_password,
    verify_session_token,
)
from restaurant_os.catalog_policy import canonical_category_name, is_numeric_sku, is_uppercase_name
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.operations import ORGANIZATION_ID, BusinessError, require_permission
from restaurant_os.purchase_workspace import create_agent_purchase_draft

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["agent-tools"])
SessionDep = Annotated[Session, Depends(get_session)]
AuthorizationDep = Annotated[Optional[str], Header(alias="Authorization")]
ActorHeaderDep = Annotated[Optional[str], Header(alias="X-Actor-User-Id")]
IdempotencyDep = Annotated[Optional[str], Header(alias="Idempotency-Key")]
CorrelationDep = Annotated[Optional[str], Header(alias="X-Correlation-Id")]

PositiveDecimalText = Annotated[
    str,
    StringConstraints(
        strict=True,
        max_length=19,
        pattern=r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?$",
    ),
]
NonNegativeDecimalText = Annotated[
    str,
    StringConstraints(
        strict=True,
        max_length=19,
        pattern=r"^(?:0|[1-9][0-9]{0,11})(?:\.[0-9]{1,6})?$",
    ),
]
WasteRateText = Annotated[
    str,
    StringConstraints(strict=True, max_length=8, pattern=r"^0(?:\.[0-9]{1,6})?$"),
]
UuidText = Annotated[
    str,
    StringConstraints(
        strict=True,
        pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-8][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-[0-9a-fA-F]{12}$",
    ),
]

PROFILES = ("administrator", "kitchen", "inventory", "purchasing")
BASELINE_CAPABILITIES: dict[str, frozenset[str]] = {
    "administrator": frozenset(
        {"agent.context.read", "agent.catalog.read", "agent.catalog.propose"}
    ),
    "kitchen": frozenset(
        {
            "agent.context.read",
            "agent.catalog.read",
            "agent.inventory.read",
            "agent.recipes.read",
            "agent.recipe.propose",
        }
    ),
    "inventory": frozenset(
        {
            "agent.context.read",
            "agent.inventory.read",
            "agent.recipes.read",
            "agent.inventory_item.propose",
        }
    ),
    "purchasing": frozenset(
        {
            "agent.context.read",
            "agent.inventory.read",
            "agent.suppliers.read",
            "agent.purchase_needs.read",
            "agent.purchase_draft.create",
        }
    ),
}
TOKEN_TTL_SECONDS = 300


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> str:
    return str(uuid4())


def _fail(
    status_code: int,
    code: str,
    message: str,
    correlation_id: str | None = None,
) -> NoReturn:
    raise HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "correlation_id": correlation_id},
    )


def _json(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str))


def _human_admin(
    session: Session,
    authorization: str | None,
) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        _fail(403, "permission_denied", "Administrator authentication is required")
    payload = verify_session_token(
        authorization.removeprefix("Bearer ").strip(), get_settings().secret_key
    )
    if not payload or payload.get("typ") == "agent" or not payload.get("sub"):
        _fail(403, "permission_denied", "Administrator authentication is required")
    actor_id = str(payload["sub"])
    try:
        require_permission(session, actor_id, "admin.manage")
    except Exception as exc:
        _fail(403, "permission_denied", str(exc))
    return actor_id


def _validate_external_https_url(value: Any, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        _fail(400, "agent_schema_invalid", f"{field} must be a string")
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 600:
        _fail(400, "agent_schema_invalid", f"{field} must not exceed 600 characters")
    parsed = urlparse(normalized)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        _fail(400, "agent_schema_invalid", f"{field} must be an HTTPS URL without credentials")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        _fail(400, "callback_destination_denied", f"{field} uses a forbidden host")
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        _fail(400, "callback_destination_denied", f"{field} uses a non-public address")
    return normalized


def _integration_row(session: Session) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.select(models.external_agent_integrations).where(
                models.external_agent_integrations.c.organization_id == ORGANIZATION_ID,
                models.external_agent_integrations.c.provider == "GROKBOT",
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row else None


def _identity_rows(session: Session, integration_id: str) -> list[dict[str, Any]]:
    rows = (
        session.execute(
            sa.select(models.external_agent_identities)
            .where(models.external_agent_identities.c.integration_id == integration_id)
            .order_by(models.external_agent_identities.c.profile)
        )
        .mappings()
        .all()
    )
    branches = (
        session.execute(
            sa.select(models.external_agent_identity_branches).where(
                models.external_agent_identity_branches.c.identity_id.in_(
                    [str(row["id"]) for row in rows]
                )
            )
        )
        .mappings()
        .all()
        if rows
        else []
    )
    by_identity: dict[str, list[str]] = {}
    for branch in branches:
        by_identity.setdefault(str(branch["identity_id"]), []).append(str(branch["branch_id"]))
    return [
        {
            "id": str(row["id"]),
            "profile": str(row["profile"]),
            "client_id": row["client_id"],
            "is_enabled": bool(row["is_enabled"]),
            "corporate_scope": bool(row["corporate_scope"]),
            "authorization_version": int(row["authorization_version"]),
            "capabilities": list(row["capabilities"] or []),
            "branch_ids": sorted(by_identity.get(str(row["id"]), [])),
            "last_rotated_at": row["last_rotated_at"],
        }
        for row in rows
    ]


def _config_view(session: Session) -> dict[str, Any]:
    integration = _integration_row(session)
    if integration is None:
        identities = [
            {
                "id": None,
                "profile": profile,
                "client_id": None,
                "is_enabled": False,
                "corporate_scope": False,
                "authorization_version": 1,
                "capabilities": sorted(BASELINE_CAPABILITIES[profile]),
                "branch_ids": [],
                "last_rotated_at": None,
            }
            for profile in PROFILES
        ]
        return {
            "id": None,
            "provider": "GROKBOT",
            "orchestrator_label": "Administrador Kiwi",
            "display_name": "Administrador Kiwi",
            "base_url": None,
            "callback_url": None,
            "has_callback_secret_ref": False,
            "is_enabled": False,
            "state": "DISCONNECTED",
            "identities": identities,
        }
    return {
        "id": integration["id"],
        "provider": "GROKBOT",
        "orchestrator_label": "Administrador Kiwi",
        "display_name": integration["display_name"],
        "base_url": integration["base_url"],
        "callback_url": integration["callback_url"],
        "has_callback_secret_ref": bool(integration["callback_secret_ref"]),
        "is_enabled": bool(integration["is_enabled"]),
        "state": integration["state"],
        "identities": _identity_rows(session, str(integration["id"])),
    }


def _audit(
    session: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    *,
    actor_user_id: str | None = None,
    actor_agent_identity_id: str | None = None,
    branch_id: str | None = None,
    payload: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    session.execute(
        models.audit_events.insert().values(
            id=_id(),
            organization_id=ORGANIZATION_ID,
            branch_id=branch_id,
            actor_user_id=actor_user_id,
            actor_agent_identity_id=actor_agent_identity_id,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            payload=_json(payload or {}),
            correlation_id=correlation_id,
            created_at=_now(),
        )
    )


@router.get("/integrations/grokbot/config")
def get_grokbot_config(
    session: SessionDep,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    _human_admin(session, authorization)
    return _config_view(session)


@router.put("/integrations/grokbot/config")
def save_grokbot_config(
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _human_admin(session, authorization)
    allowed = {"display_name", "base_url", "callback_url", "callback_secret_ref", "is_enabled"}
    if set(payload) - allowed:
        _fail(400, "agent_schema_invalid", "Unsupported GrokBot configuration field")
    display_name = str(payload.get("display_name") or "Administrador Kiwi").strip()
    if not display_name or len(display_name) > 120:
        _fail(400, "agent_schema_invalid", "display_name is required, up to 120 characters")
    base_url = _validate_external_https_url(payload.get("base_url"), "base_url")
    callback_url = _validate_external_https_url(payload.get("callback_url"), "callback_url")
    integration = _integration_row(session)
    callback_secret_ref = (integration or {}).get("callback_secret_ref")
    if "callback_secret_ref" in payload:
        raw_secret_ref = payload["callback_secret_ref"]
        if not isinstance(raw_secret_ref, str):
            _fail(400, "agent_schema_invalid", "callback_secret_ref must be a string")
        callback_secret_ref = raw_secret_ref.strip()
        if not 1 <= len(callback_secret_ref) <= 240:
            _fail(
                400,
                "agent_schema_invalid",
                "callback_secret_ref requires 1 to 240 characters",
            )
    is_enabled = payload.get("is_enabled", False)
    if not isinstance(is_enabled, bool):
        _fail(400, "agent_schema_invalid", "is_enabled must be boolean")
    now = _now()
    values = {
        "display_name": display_name,
        "base_url": base_url,
        "callback_url": callback_url,
        "callback_secret_ref": callback_secret_ref,
        "callback_key_id": (integration or {}).get("callback_key_id")
        or f"grokbot-{secrets.token_hex(6)}",
        "is_enabled": is_enabled,
        "state": "CONNECTED" if is_enabled else "DISCONNECTED",
        "updated_at": now,
    }
    if integration is None:
        integration_id = _id()
        session.execute(
            models.external_agent_integrations.insert().values(
                id=integration_id,
                organization_id=ORGANIZATION_ID,
                provider="GROKBOT",
                created_by_user_id=actor_id,
                created_at=now,
                **values,
            )
        )
        for profile in PROFILES:
            session.execute(
                models.external_agent_identities.insert().values(
                    id=_id(),
                    organization_id=ORGANIZATION_ID,
                    integration_id=integration_id,
                    profile=profile,
                    client_id=None,
                    is_enabled=False,
                    corporate_scope=False,
                    authorization_version=1,
                    capabilities=sorted(BASELINE_CAPABILITIES[profile]),
                    created_at=now,
                    updated_at=now,
                    last_rotated_at=None,
                )
            )
    else:
        integration_id = str(integration["id"])
        session.execute(
            sa.update(models.external_agent_integrations)
            .where(models.external_agent_integrations.c.id == integration_id)
            .values(**values)
        )
    _audit(
        session,
        "agent.integration.configured",
        "external_agent_integration",
        integration_id,
        actor_user_id=actor_id,
        payload={"enabled": is_enabled, "has_callback": callback_url is not None},
    )
    session.commit()
    return _config_view(session)


def _identity(session: Session, profile: str) -> dict[str, Any]:
    if profile not in PROFILES:
        _fail(404, "agent_identity_not_found", "Agent identity was not found")
    integration = _integration_row(session)
    if integration is None:
        _fail(409, "agent_integration_not_configured", "Configure GrokBot first")
    row = (
        session.execute(
            sa.select(models.external_agent_identities)
            .where(
                models.external_agent_identities.c.integration_id == integration["id"],
                models.external_agent_identities.c.profile == profile,
            )
            .with_for_update()
        )
        .mappings()
        .first()
    )
    if not row:
        _fail(404, "agent_identity_not_found", "Agent identity was not found")
    return dict(row)


@router.put("/integrations/grokbot/identities/{profile}")
def update_grokbot_identity(
    profile: str,
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _human_admin(session, authorization)
    identity = _identity(session, profile)
    allowed = {
        "is_enabled",
        "corporate_scope",
        "capabilities",
        "branch_ids",
        "expected_authorization_version",
    }
    if set(payload) - allowed:
        _fail(400, "agent_schema_invalid", "Unsupported identity policy field")
    expected_version = payload.get("expected_authorization_version")
    if not isinstance(expected_version, int) or isinstance(expected_version, bool):
        _fail(400, "agent_schema_invalid", "expected_authorization_version is required")
    if expected_version != int(identity["authorization_version"]):
        _fail(409, "stale_reference", "Identity policy changed; reload before saving")
    capabilities = payload.get("capabilities", identity["capabilities"])
    if not isinstance(capabilities, list) or not all(
        isinstance(value, str) for value in capabilities
    ):
        _fail(400, "agent_schema_invalid", "capabilities must be a string list")
    capability_set = set(capabilities)
    if not capability_set <= BASELINE_CAPABILITIES[profile]:
        _fail(400, "agent_capability_denied", "Policy cannot expand the profile baseline")
    current_branch_ids = list(
        session.scalars(
            sa.select(models.external_agent_identity_branches.c.branch_id).where(
                models.external_agent_identity_branches.c.identity_id == identity["id"]
            )
        ).all()
    )
    branch_ids = payload.get("branch_ids", current_branch_ids)
    if not isinstance(branch_ids, list) or not all(isinstance(value, str) for value in branch_ids):
        _fail(400, "agent_schema_invalid", "branch_ids must be a string list")
    if len(set(branch_ids)) != len(branch_ids):
        _fail(400, "agent_schema_invalid", "branch_ids must be unique")
    known = (
        set(
            session.scalars(
                sa.select(models.branches.c.id).where(
                    models.branches.c.organization_id == ORGANIZATION_ID,
                    models.branches.c.status == "active",
                    models.branches.c.id.in_(branch_ids),
                )
            ).all()
        )
        if branch_ids
        else set()
    )
    if known != set(branch_ids):
        _fail(400, "agent_branch_denied", "Every branch must belong to the organization")
    enabled = payload.get("is_enabled", identity["is_enabled"])
    corporate_scope = payload.get("corporate_scope", identity["corporate_scope"])
    if not isinstance(enabled, bool) or not isinstance(corporate_scope, bool):
        _fail(400, "agent_schema_invalid", "Identity flags must be boolean")
    if enabled and not identity.get("client_id"):
        _fail(409, "agent_unauthorized", "Rotate a credential before enabling the identity")
    now = _now()
    updated = session.execute(
        sa.update(models.external_agent_identities)
        .where(
            models.external_agent_identities.c.id == identity["id"],
            models.external_agent_identities.c.authorization_version == expected_version,
        )
        .values(
            is_enabled=enabled,
            corporate_scope=corporate_scope,
            capabilities=sorted(capability_set),
            authorization_version=expected_version + 1,
            updated_at=now,
        )
    )
    if getattr(updated, "rowcount", 0) != 1:
        session.rollback()
        _fail(409, "stale_reference", "Identity policy changed; reload before saving")
    session.execute(
        sa.delete(models.external_agent_identity_branches).where(
            models.external_agent_identity_branches.c.identity_id == identity["id"]
        )
    )
    if branch_ids:
        session.execute(
            models.external_agent_identity_branches.insert(),
            [
                {
                    "identity_id": identity["id"],
                    "branch_id": branch_id,
                    "organization_id": ORGANIZATION_ID,
                    "created_at": now,
                }
                for branch_id in branch_ids
            ],
        )
    _audit(
        session,
        "agent.identity.policy_updated",
        "external_agent_identity",
        str(identity["id"]),
        actor_user_id=actor_id,
        payload={
            "profile": profile,
            "enabled": enabled,
            "corporate_scope": corporate_scope,
            "capability_count": len(capability_set),
            "branch_count": len(branch_ids),
        },
    )
    session.commit()
    integration = _integration_row(session)
    assert integration is not None
    return next(
        row for row in _identity_rows(session, str(integration["id"])) if row["profile"] == profile
    )


@router.post("/integrations/grokbot/identities/{profile}/rotate-secret")
def rotate_grokbot_identity_secret(
    profile: str,
    session: SessionDep,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    actor_id = _human_admin(session, authorization)
    identity = _identity(session, profile)
    now = _now()
    version = int(identity["authorization_version"]) + 1
    client_id = str(identity.get("client_id") or f"gkb_{profile}_{secrets.token_urlsafe(12)}")
    secret = secrets.token_urlsafe(32)
    salt = generate_password_salt()
    session.execute(
        sa.update(models.external_agent_credentials)
        .where(
            models.external_agent_credentials.c.identity_id == identity["id"],
            models.external_agent_credentials.c.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    session.execute(
        models.external_agent_credentials.insert().values(
            id=_id(),
            identity_id=identity["id"],
            version=version,
            secret_salt=salt,
            secret_hash=hash_password(secret, salt),
            created_at=now,
            revoked_at=None,
        )
    )
    session.execute(
        sa.update(models.external_agent_identities)
        .where(models.external_agent_identities.c.id == identity["id"])
        .values(
            client_id=client_id,
            is_enabled=False,
            authorization_version=version,
            last_rotated_at=now,
            updated_at=now,
        )
    )
    _audit(
        session,
        "agent.credential.rotated",
        "external_agent_identity",
        str(identity["id"]),
        actor_user_id=actor_id,
        payload={"profile": profile, "authorization_version": version},
    )
    session.commit()
    return {
        "profile": profile,
        "client_id": client_id,
        "client_secret": secret,
        "authorization_version": version,
        "warning": "Se mostrará una sola vez",
    }


@dataclass(frozen=True)
class AgentPrincipal:
    identity_id: str
    integration_id: str
    organization_id: str
    profile: str
    authorization_version: int
    capabilities: frozenset[str]
    branch_ids: frozenset[str]
    corporate_scope: bool
    callback_url: str | None
    callback_key_id: str | None


def _principal_from_row(
    session: Session, identity: dict[str, Any], integration: dict[str, Any]
) -> AgentPrincipal:
    branches = frozenset(
        str(value)
        for value in session.scalars(
            sa.select(models.external_agent_identity_branches.c.branch_id).where(
                models.external_agent_identity_branches.c.identity_id == identity["id"]
            )
        ).all()
    )
    return AgentPrincipal(
        identity_id=str(identity["id"]),
        integration_id=str(integration["id"]),
        organization_id=str(identity["organization_id"]),
        profile=str(identity["profile"]),
        authorization_version=int(identity["authorization_version"]),
        capabilities=frozenset(str(value) for value in identity["capabilities"] or []),
        branch_ids=branches,
        corporate_scope=bool(identity["corporate_scope"]),
        callback_url=str(integration["callback_url"]) if integration["callback_url"] else None,
        callback_key_id=(
            str(integration["callback_key_id"]) if integration["callback_key_id"] else None
        ),
    )


def _parse_basic(authorization: str | None) -> tuple[str, str]:
    if not authorization or not authorization.startswith("Basic "):
        _fail(401, "agent_unauthorized", "HTTP Basic client credentials are required")
    try:
        decoded = base64.b64decode(
            authorization.removeprefix("Basic ").strip(), validate=True
        ).decode()
        client_id, client_secret = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        _fail(401, "agent_unauthorized", "Client credentials are invalid")
    if not client_id or not client_secret:
        _fail(401, "agent_unauthorized", "Client credentials are invalid")
    return client_id, client_secret


@router.post("/agent-auth/token")
async def issue_agent_token(
    request: Request,
    session: SessionDep,
    authorization: AuthorizationDep = None,
) -> dict[str, Any]:
    try:
        form = parse_qs((await request.body()).decode(), strict_parsing=True)
    except (UnicodeDecodeError, ValueError):
        _fail(400, "agent_schema_invalid", "Token request body is invalid")
    if form != {"grant_type": ["client_credentials"]}:
        _fail(400, "agent_schema_invalid", "grant_type must be client_credentials")
    client_id, client_secret = _parse_basic(authorization)
    row = (
        session.execute(
            sa.select(models.external_agent_identities).where(
                models.external_agent_identities.c.client_id == client_id,
                models.external_agent_identities.c.organization_id == ORGANIZATION_ID,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        _fail(401, "agent_unauthorized", "Client credentials are invalid")
    identity = dict(row)
    integration_row = _integration_row(session)
    if not integration_row or identity["integration_id"] != integration_row["id"]:
        _fail(401, "agent_unauthorized", "Client credentials are invalid")
    if not identity["is_enabled"] or not integration_row["is_enabled"]:
        _fail(403, "agent_disabled", "Integration or identity is disabled")
    if integration_row["state"] != "CONNECTED":
        _fail(403, "agent_disabled", "Integration is not accepting new tokens")
    credential = (
        session.execute(
            sa.select(models.external_agent_credentials)
            .where(
                models.external_agent_credentials.c.identity_id == identity["id"],
                models.external_agent_credentials.c.revoked_at.is_(None),
            )
            .order_by(models.external_agent_credentials.c.version.desc())
        )
        .mappings()
        .first()
    )
    if not credential or not verify_password(
        client_secret, str(credential["secret_salt"]), str(credential["secret_hash"])
    ):
        _fail(401, "agent_unauthorized", "Client credentials are invalid")
    token = create_session_token(
        {
            "typ": "agent",
            "aud": "kiwi-agent-tools-v1",
            "sub": identity["id"],
            "org": identity["organization_id"],
            "integration": identity["integration_id"],
            "profile": identity["profile"],
            "authorization_version": identity["authorization_version"],
            "jti": _id(),
        },
        get_settings().secret_key,
        ttl_seconds=TOKEN_TTL_SECONDS,
    )
    logger.info(
        "agent.request.accepted",
        extra={"profile": identity["profile"], "operation": "token.issue", "result": "accepted"},
    )
    return {"access_token": token, "token_type": "Bearer", "expires_in": TOKEN_TTL_SECONDS}


def _agent(
    session: Session,
    authorization: str | None,
    actor_header: str | None,
) -> AgentPrincipal:
    if actor_header:
        _fail(401, "agent_unauthorized", "X-Actor-User-Id is forbidden for Agent Tools")
    if not authorization or not authorization.startswith("Bearer "):
        _fail(401, "agent_unauthorized", "Agent bearer token is required")
    payload = verify_session_token(
        authorization.removeprefix("Bearer ").strip(), get_settings().secret_key
    )
    if not payload or payload.get("typ") != "agent" or payload.get("aud") != "kiwi-agent-tools-v1":
        _fail(401, "agent_unauthorized", "Agent token is invalid or expired")
    identity = (
        session.execute(
            sa.select(models.external_agent_identities).where(
                models.external_agent_identities.c.id == str(payload.get("sub", "")),
                models.external_agent_identities.c.organization_id == str(payload.get("org", "")),
            )
        )
        .mappings()
        .first()
    )
    integration = _integration_row(session)
    if not identity or not integration:
        _fail(403, "agent_disabled", "Agent authority no longer exists")
    if (
        not identity["is_enabled"]
        or not integration["is_enabled"]
        or integration["state"] != "CONNECTED"
        or int(payload.get("authorization_version", 0)) != int(identity["authorization_version"])
    ):
        _fail(403, "agent_disabled", "Agent authority was disabled or rotated")
    if (
        payload.get("profile") != identity["profile"]
        or payload.get("integration") != identity["integration_id"]
    ):
        _fail(401, "agent_unauthorized", "Agent token claims are inconsistent")
    return _principal_from_row(session, dict(identity), integration)


def _capability(principal: AgentPrincipal, capability: str) -> None:
    if (
        capability not in principal.capabilities
        or capability not in BASELINE_CAPABILITIES[principal.profile]
    ):
        _fail(403, "agent_capability_denied", "Agent capability is not allowed")


def _branch(session: Session, principal: AgentPrincipal, branch_id: str) -> str:
    try:
        UUID(branch_id)
    except (ValueError, TypeError, AttributeError):
        _fail(400, "agent_schema_invalid", "branch_id must be a UUID")
    if branch_id not in principal.branch_ids:
        _fail(403, "agent_branch_denied", "Branch is outside the agent allowlist")
    exists = session.scalar(
        sa.select(models.branches.c.id).where(
            models.branches.c.id == branch_id,
            models.branches.c.organization_id == principal.organization_id,
            models.branches.c.status == "active",
        )
    )
    if not exists:
        _fail(403, "agent_branch_denied", "Branch is outside the agent organization")
    return branch_id


def _corporate(principal: AgentPrincipal) -> None:
    if not principal.corporate_scope:
        _fail(403, "agent_capability_denied", "Corporate scope is not enabled")


def _catalog_scope(table: sa.FromClause, branch_id: str | None) -> sa.ColumnElement[bool]:
    if branch_id is None:
        return table.c.catalog_scope == "organization"
    return sa.or_(
        table.c.catalog_scope == "organization",
        table.c.source_branch_id == branch_id,
    )


@router.get("/agent-tools/context")
def agent_context(
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.context.read")
    branches = (
        session.execute(
            sa.select(models.branches.c.id, models.branches.c.code, models.branches.c.name)
            .where(
                models.branches.c.organization_id == principal.organization_id,
                models.branches.c.id.in_(principal.branch_ids),
                models.branches.c.status == "active",
            )
            .order_by(models.branches.c.id)
        )
        .mappings()
        .all()
        if principal.branch_ids
        else []
    )
    return {
        "identity_id": principal.identity_id,
        "profile": principal.profile,
        "authorization_version": principal.authorization_version,
        "capabilities": sorted(principal.capabilities),
        "corporate_scope": principal.corporate_scope,
        "branches": [dict(row) for row in branches],
    }


def _limit(value: int) -> int:
    if not 1 <= value <= 100:
        _fail(400, "agent_schema_invalid", "limit must be between 1 and 100")
    return value


def _cursor(value: str | None) -> str | None:
    if not value:
        return None
    if len(value) > 512:
        _fail(400, "agent_schema_invalid", "cursor must not exceed 512 characters")
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
    except (ValueError, json.JSONDecodeError):
        _fail(400, "agent_schema_invalid", "cursor is invalid")
    after = decoded.get("after") if isinstance(decoded, dict) else None
    if not isinstance(after, str):
        _fail(400, "agent_schema_invalid", "cursor is invalid")
    return after


def _page(rows: list[dict[str, Any]], limit: int) -> dict[str, Any]:
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        raw = json.dumps({"after": visible[-1]["id"]}, separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    return {"items": _json(visible), "page": {"next_cursor": next_cursor, "has_more": has_more}}


def _resource_version(updated_at: datetime) -> int:
    aware = updated_at if updated_at.tzinfo else updated_at.replace(tzinfo=timezone.utc)
    return max(1, int(aware.timestamp() * 1_000_000))


@router.get("/agent-tools/catalog/items")
def list_agent_catalog(
    session: SessionDep,
    branch_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.catalog.read")
    if branch_id:
        _branch(session, principal, branch_id)
    else:
        _corporate(principal)
    after = _cursor(cursor)
    query = sa.select(
        models.products.c.id,
        models.products.c.sku,
        models.products.c.name,
        (models.products.c.status == "active").label("active"),
        models.products.c.updated_at,
    ).where(
        models.products.c.organization_id == principal.organization_id,
        _catalog_scope(models.products, branch_id),
    )
    if after:
        query = query.where(models.products.c.id > after)
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(models.products.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    for row in rows:
        row["version"] = _resource_version(row.pop("updated_at"))
    return _page(rows, limit)


@router.get("/agent-tools/inventory/items")
def list_agent_inventory_items(
    session: SessionDep,
    branch_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.inventory.read")
    if branch_id:
        _branch(session, principal, branch_id)
    else:
        _corporate(principal)
    after = _cursor(cursor)
    query = sa.select(
        models.inventory_items.c.id,
        models.inventory_items.c.sku,
        models.inventory_items.c.name,
        models.inventory_items.c.base_unit_id.label("unit_id"),
        (models.inventory_items.c.status == "active").label("active"),
        models.inventory_items.c.updated_at,
    ).where(
        models.inventory_items.c.organization_id == principal.organization_id,
        _catalog_scope(models.inventory_items, branch_id),
    )
    if after:
        query = query.where(models.inventory_items.c.id > after)
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(models.inventory_items.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    for row in rows:
        row["version"] = _resource_version(row.pop("updated_at"))
    return _page(rows, limit)


@router.get("/agent-tools/inventory/stock")
def list_agent_stock(
    branch_id: str,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.inventory.read")
    authorized_branch = _branch(session, principal, branch_id)
    after = _cursor(cursor)
    state = models.inventory_cost_states.alias("agent_stock_state")
    query = (
        sa.select(
            models.inventory_items.c.id,
            models.inventory_items.c.id.label("item_id"),
            models.inventory_items.c.base_unit_id.label("unit_id"),
            sa.func.coalesce(state.c.quantity_on_hand, 0).label("available_quantity"),
            sa.func.coalesce(state.c.updated_at, _now()).label("as_of"),
        )
        .select_from(
            models.inventory_items.outerjoin(
                state,
                sa.and_(
                    state.c.item_id == models.inventory_items.c.id,
                    state.c.branch_id == authorized_branch,
                ),
            )
        )
        .where(
            models.inventory_items.c.organization_id == principal.organization_id,
            _catalog_scope(models.inventory_items, authorized_branch),
        )
    )
    if after:
        query = query.where(models.inventory_items.c.id > after)
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(models.inventory_items.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    for row in rows:
        row["available_quantity"] = str(row["available_quantity"])
    page = _page(rows, limit)
    for item in page["items"]:
        item.pop("id", None)
    return page


@router.get("/agent-tools/recipes")
def list_agent_recipes(
    session: SessionDep,
    branch_id: str | None = None,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.recipes.read")
    if branch_id:
        _branch(session, principal, branch_id)
    elif not principal.corporate_scope:
        _fail(403, "agent_branch_denied", "A permitted branch is required")
    after = _cursor(cursor)
    scoped_component = models.recipe_components.alias("agent_recipe_component_scope")
    scoped_item = models.inventory_items.alias("agent_recipe_item_scope")
    has_out_of_scope_component = sa.exists(
        sa.select(scoped_component.c.item_id).where(
            scoped_component.c.recipe_id == models.recipes.c.id,
            ~sa.exists(
                sa.select(scoped_item.c.id).where(
                    scoped_item.c.id == scoped_component.c.item_id,
                    scoped_item.c.organization_id == principal.organization_id,
                    _catalog_scope(scoped_item, branch_id),
                )
            ),
        )
    )
    query = sa.select(models.recipes).where(
        models.recipes.c.organization_id == principal.organization_id,
        models.recipes.c.status == "active",
        models.recipes.c.valid_to.is_(None),
        ~has_out_of_scope_component,
        sa.or_(
            sa.and_(
                models.recipes.c.recipe_type == "sale",
                sa.exists(
                    sa.select(models.products.c.id).where(
                        models.products.c.id == models.recipes.c.product_id,
                        models.products.c.organization_id == principal.organization_id,
                        _catalog_scope(models.products, branch_id),
                    )
                ),
            ),
            sa.and_(
                models.recipes.c.recipe_type == "production",
                sa.exists(
                    sa.select(models.inventory_items.c.id).where(
                        models.inventory_items.c.id == models.recipes.c.output_item_id,
                        models.inventory_items.c.organization_id == principal.organization_id,
                        _catalog_scope(models.inventory_items, branch_id),
                    )
                ),
            ),
        ),
    )
    if branch_id:
        query = query.where(
            sa.or_(models.recipes.c.branch_id == branch_id, models.recipes.c.branch_id.is_(None))
        )
    else:
        query = query.where(models.recipes.c.branch_id.is_(None))
    if after:
        query = query.where(models.recipes.c.id > after)
    recipe_rows = [
        dict(row)
        for row in session.execute(
            query.order_by(models.recipes.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    result: list[dict[str, Any]] = []
    for recipe in recipe_rows:
        components = (
            session.execute(
                sa.select(models.recipe_components)
                .where(models.recipe_components.c.recipe_id == recipe["id"])
                .order_by(models.recipe_components.c.sort_order)
            )
            .mappings()
            .all()
        )
        result.append(
            {
                "id": recipe["id"],
                "recipe_type": recipe["recipe_type"],
                "target_id": recipe["product_id"] or recipe["output_item_id"],
                "version": recipe["version"],
                "yield_quantity": str(recipe["yield_quantity"]),
                "yield_unit_id": recipe["yield_unit_id"],
                "components": [
                    {
                        "item_id": component["item_id"],
                        "unit_id": component["unit_id"],
                        "net_quantity": str(component["net_quantity"]),
                        "waste_rate": str(component["waste_rate"]),
                    }
                    for component in components
                ],
            }
        )
    return _page(result, limit)


@router.get("/agent-tools/suppliers")
def list_agent_suppliers(
    branch_id: str,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.suppliers.read")
    authorized_branch = _branch(session, principal, branch_id)
    after = _cursor(cursor)
    disabled = sa.exists(
        sa.select(models.supplier_branch_terms.c.supplier_id).where(
            models.supplier_branch_terms.c.supplier_id == models.suppliers.c.id,
            models.supplier_branch_terms.c.branch_id == authorized_branch,
            models.supplier_branch_terms.c.is_enabled.is_(False),
        )
    )
    query = sa.select(
        models.suppliers.c.id,
        models.suppliers.c.code,
        models.suppliers.c.commercial_name.label("business_name"),
        (models.suppliers.c.status == "active").label("active"),
    ).where(
        models.suppliers.c.organization_id == principal.organization_id,
        models.suppliers.c.status == "active",
        ~disabled,
    )
    if after:
        query = query.where(models.suppliers.c.id > after)
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(models.suppliers.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    return _page(rows, limit)


@router.get("/agent-tools/purchase-needs")
def list_agent_purchase_needs(
    branch_id: str,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.purchase_needs.read")
    authorized_branch = _branch(session, principal, branch_id)
    after = _cursor(cursor)
    state = models.inventory_cost_states.alias("agent_need_state")
    query = (
        sa.select(
            models.inventory_stock_thresholds.c.id,
            models.inventory_stock_thresholds.c.item_id,
            models.inventory_items.c.base_unit_id.label("unit_id"),
            models.inventory_stock_thresholds.c.minimum_quantity,
            sa.func.coalesce(state.c.quantity_on_hand, 0).label("quantity_on_hand"),
            models.inventory_stock_thresholds.c.updated_at.label("as_of"),
        )
        .join(
            models.inventory_items,
            models.inventory_items.c.id == models.inventory_stock_thresholds.c.item_id,
        )
        .outerjoin(
            state,
            sa.and_(
                state.c.item_id == models.inventory_stock_thresholds.c.item_id,
                state.c.branch_id == authorized_branch,
                state.c.warehouse_id == models.inventory_stock_thresholds.c.warehouse_id,
            ),
        )
        .where(
            models.inventory_stock_thresholds.c.organization_id == principal.organization_id,
            models.inventory_stock_thresholds.c.branch_id == authorized_branch,
            _catalog_scope(models.inventory_items, authorized_branch),
        )
    )
    if after:
        query = query.where(models.inventory_stock_thresholds.c.id > after)
    raw = [
        dict(row)
        for row in session.execute(
            query.order_by(models.inventory_stock_thresholds.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    rows = []
    for row in raw:
        suggested = max(
            Decimal(str(row["minimum_quantity"])) - Decimal(str(row["quantity_on_hand"])),
            Decimal("0"),
        )
        rows.append(
            {
                "id": row["id"],
                "item_id": row["item_id"],
                "unit_id": row["unit_id"],
                "suggested_quantity": str(suggested),
                "reason_code": "below_minimum" if suggested > 0 else "no_suggestion",
                "as_of": row["as_of"],
            }
        )
    page = _page(rows, limit)
    for item in page["items"]:
        item.pop("id", None)
    return page


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CorporateScope(_StrictModel):
    kind: Literal["corporate"]


class BranchScope(_StrictModel):
    kind: Literal["branch"]
    branch_id: UuidText


class CatalogFields(_StrictModel):
    sku: str | None = Field(default=None, min_length=1, max_length=64)
    name: str | None = Field(default=None, min_length=1, max_length=160)
    category_name: str | None = Field(default=None, min_length=1, max_length=120)
    station: Literal["kitchen", "drinks", "packing"] | None = None
    price_cents: int | None = Field(default=None, ge=1, le=2_147_483_647)
    image_url: str | None = Field(default=None, max_length=512)
    status: Literal["active", "inactive"] | None = None


class CatalogProposal(_StrictModel):
    scope: CorporateScope
    action: Literal["product.create", "product.update"]
    target_id: UuidText | None = None
    expected_version: int | None = Field(default=None, ge=1)
    fields: CatalogFields

    @model_validator(mode="after")
    def validate_action(self) -> CatalogProposal:
        values = self.fields.model_dump(exclude_none=True)
        if self.action == "product.create":
            required = {"name", "sku", "category_name", "station", "price_cents"}
            if (
                self.target_id is not None
                or self.expected_version is not None
                or not required <= values.keys()
            ):
                raise ValueError("product.create requires the complete allowlist and no target")
            if "status" in values:
                raise ValueError("product.create cannot set status")
        elif not self.target_id or self.expected_version is None:
            raise ValueError("product.update requires target_id and expected_version")
        if not values:
            raise ValueError("fields cannot be empty")
        if "name" in values and not is_uppercase_name(values["name"]):
            raise ValueError("product name must be uppercase")
        if "sku" in values and not is_numeric_sku(values["sku"]):
            raise ValueError("product SKU must contain only digits")
        if "category_name" in values and values["category_name"] != canonical_category_name(
            values["category_name"]
        ):
            raise ValueError("category name must be uppercase")
        return self


class InventoryProposal(_StrictModel):
    scope: CorporateScope
    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=160)
    base_unit_id: UuidText
    item_type: Literal["ingredient"] = "ingredient"

    @model_validator(mode="after")
    def validate_catalog_policy(self) -> InventoryProposal:
        if not is_numeric_sku(self.sku):
            raise ValueError("inventory SKU must contain only digits")
        return self


class RecipeComponent(_StrictModel):
    item_id: UuidText
    unit_id: UuidText
    net_quantity: PositiveDecimalText
    waste_rate: WasteRateText

    @field_validator("net_quantity")
    @classmethod
    def net_quantity_must_be_positive(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("net_quantity must be greater than zero")
        return value


class RecipeProposal(_StrictModel):
    scope: CorporateScope | BranchScope
    target_id: UuidText
    expected_active_recipe_id: UuidText | None
    yield_quantity: PositiveDecimalText
    yield_unit_id: UuidText
    components: list[RecipeComponent] = Field(min_length=1, max_length=200)

    @field_validator("yield_quantity")
    @classmethod
    def yield_quantity_must_be_positive(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("yield_quantity must be greater than zero")
        return value


class PurchaseLine(_StrictModel):
    presentation_id: UuidText
    quantity: PositiveDecimalText
    unit_price: NonNegativeDecimalText
    discount: NonNegativeDecimalText
    tax: NonNegativeDecimalText

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, value: str) -> str:
        if Decimal(value) <= 0:
            raise ValueError("quantity must be greater than zero")
        return value


class PurchaseDraft(_StrictModel):
    branch_id: UuidText
    supplier_id: UuidText
    document_type: Literal["invoice", "receipt", "ticket", "note"]
    folio: str = Field(min_length=1, max_length=80)
    document_date: date
    payment_method: Literal["cash", "transfer", "card", "other"]
    paid_from_cash: bool
    freight_total: Literal["0"] = "0"
    lines: list[PurchaseLine] = Field(min_length=1, max_length=200)

    @model_validator(mode="after")
    def validate_cash(self) -> PurchaseDraft:
        if (self.payment_method == "cash") != self.paid_from_cash:
            raise ValueError("paid_from_cash must match payment_method")
        return self


def _validated(model: type[_StrictModel], payload: dict[str, Any]) -> _StrictModel:
    try:
        return model.model_validate(payload)
    except ValidationError as exc:
        _fail(400, "agent_schema_invalid", exc.errors()[0]["msg"])


def _command_hash(path: str, branch_id: str | None, payload: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"method": "POST", "path": path, "version": 1, "branch_id": branch_id, "body": payload},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


def _operation_view(row: dict[str, Any]) -> dict[str, Any]:
    def timestamp(value: Any) -> str:
        if not isinstance(value, datetime):
            return str(value)
        aware = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return aware.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    return {
        "operation_id": row["id"],
        "operation_type": row["operation_type"],
        "status": row["status"],
        "resource_id": row["resource_id"],
        "reason_code": row["reason_code"],
        "created_at": timestamp(row["created_at"]),
        "updated_at": timestamp(row["updated_at"]),
    }


def _existing_command(
    session: Session,
    principal: AgentPrincipal,
    key: str,
    digest: str,
) -> dict[str, Any] | None:
    row = (
        session.execute(
            sa.select(models.external_agent_commands).where(
                models.external_agent_commands.c.organization_id == principal.organization_id,
                models.external_agent_commands.c.identity_id == principal.identity_id,
                models.external_agent_commands.c.idempotency_key == key,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        return None
    if row["request_hash"] != digest:
        _fail(409, "idempotency_conflict", "Idempotency key belongs to another request")
    return dict(row)


def _key(value: str | None) -> str:
    key = (value or "").strip()
    if not 8 <= len(key) <= 180:
        _fail(400, "agent_schema_invalid", "Idempotency-Key requires 8 to 180 characters")
    return key


def _queue_callback(
    session: Session,
    principal: AgentPrincipal,
    operation: dict[str, Any],
) -> None:
    if not principal.callback_url:
        return
    event_id = _id()
    payload = {
        "event_id": event_id,
        "event_type": "agent.operation.status_changed",
        "occurred_at": operation["updated_at"],
        "operation_id": operation["id"],
        "operation_type": operation["operation_type"],
        "status": operation["status"],
        "reason_code": operation["reason_code"],
    }
    session.execute(
        models.external_agent_callback_outbox.insert().values(
            id=_id(),
            operation_id=operation["id"],
            event_id=event_id,
            destination=principal.callback_url,
            key_id=principal.callback_key_id,
            payload=_json(payload),
            status="PENDING",
            attempt_count=0,
            next_attempt_at=operation["updated_at"],
            leased_until=None,
            last_error_code=None,
            created_at=operation["updated_at"],
            updated_at=operation["updated_at"],
        )
    )


def _persist_command(
    session: Session,
    principal: AgentPrincipal,
    *,
    operation_type: str,
    branch_id: str | None,
    key: str,
    digest: str,
    status: str,
    resource_id: str,
    correlation_id: str | None,
) -> dict[str, Any]:
    if correlation_id is not None and not 1 <= len(correlation_id) <= 100:
        _fail(400, "agent_schema_invalid", "X-Correlation-Id requires 1 to 100 characters")
    now = _now()
    operation: dict[str, Any] = {
        "id": _id(),
        "organization_id": principal.organization_id,
        "integration_id": principal.integration_id,
        "identity_id": principal.identity_id,
        "branch_id": branch_id,
        "operation_type": operation_type,
        "idempotency_key": key,
        "request_hash": digest,
        "status": status,
        "resource_id": resource_id,
        "reason_code": None,
        "correlation_id": correlation_id,
        "result": {"resource_id": resource_id},
        "created_at": now,
        "updated_at": now,
    }
    try:
        session.execute(models.external_agent_commands.insert().values(**operation))
    except IntegrityError:
        session.rollback()
        previous = _existing_command(session, principal, key, digest)
        if previous:
            return previous
        _fail(409, "stale_reference", "A canonical reference changed during the command")
    _queue_callback(session, principal, operation)
    _audit(
        session,
        "agent.operation.created",
        "external_agent_command",
        operation["id"],
        actor_agent_identity_id=principal.identity_id,
        branch_id=branch_id,
        correlation_id=correlation_id,
        payload={"profile": principal.profile, "operation": operation_type, "status": status},
    )
    return operation


def _commit_or_replay(
    session: Session,
    principal: AgentPrincipal,
    key: str,
    digest: str,
    operation: dict[str, Any],
) -> dict[str, Any]:
    """Close the idempotent transaction and recover the winner of a concurrent race."""
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        previous = _existing_command(session, principal, key, digest)
        if previous:
            return _operation_view(previous)
        _fail(409, "stale_reference", "A canonical reference changed during the command")
    return _operation_view(operation)


def _proposal(
    session: Session,
    principal: AgentPrincipal,
    *,
    branch_id: str | None,
    change: dict[str, Any],
    sources: list[str],
) -> str:
    now = _now()
    context = admin_ai.build_context(session, branch_id)
    proposal_id = _id()
    session.execute(
        models.admin_ai_proposals.insert().values(
            id=proposal_id,
            organization_id=principal.organization_id,
            branch_id=branch_id,
            actor_user_id=None,
            actor_agent_identity_id=principal.identity_id,
            origin="GROKBOT",
            status="READY_FOR_REVIEW",
            base_fingerprint=admin_ai.context_fingerprint(context),
            payload={
                "answer": "Propuesta externa lista para revisión humana.",
                "sources": sources,
                "questions": [],
                "warnings": [],
                "change_set": [change],
            },
            created_at=now,
            updated_at=now,
            expires_at=now + timedelta(hours=24),
            reviewed_by_user_id=None,
            apply_idempotency_key=None,
            result=None,
            applied_at=None,
            rejected_at=None,
        )
    )
    _audit(
        session,
        "admin_ai.proposal_created",
        "admin_ai_proposal",
        proposal_id,
        actor_agent_identity_id=principal.identity_id,
        branch_id=branch_id,
        payload={"origin": "GROKBOT", "kind": change["kind"], "status": "READY_FOR_REVIEW"},
    )
    return proposal_id


@router.post("/agent-tools/proposals/catalog", status_code=202)
def create_catalog_proposal(
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
    idempotency_key: IdempotencyDep = None,
    correlation_id: CorrelationDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.catalog.propose")
    _corporate(principal)
    command = _validated(CatalogProposal, payload)
    assert isinstance(command, CatalogProposal)
    normalized = _json(command.model_dump(exclude_none=False))
    key = _key(idempotency_key)
    digest = _command_hash("/api/v1/agent-tools/proposals/catalog", None, normalized)
    previous = _existing_command(session, principal, key, digest)
    if previous:
        return _operation_view(previous)
    fields = command.fields.model_dump(exclude_none=True)
    current = None
    if command.action == "product.update":
        current = (
            session.execute(
                sa.select(models.products).where(
                    models.products.c.id == command.target_id,
                    models.products.c.organization_id == principal.organization_id,
                    _catalog_scope(models.products, None),
                )
            )
            .mappings()
            .first()
        )
        if not current or command.expected_version != _resource_version(current["updated_at"]):
            _fail(409, "stale_reference", "Product reference is stale")
    elif session.scalar(
        sa.select(models.products.c.id).where(
            models.products.c.organization_id == principal.organization_id,
            models.products.c.sku == fields["sku"],
        )
    ):
        _fail(409, "stale_reference", "Product SKU already exists")
    proposal_id = _proposal(
        session,
        principal,
        branch_id=None,
        change={
            "kind": command.action,
            "target_id": command.target_id,
            "current": _json(dict(current)) if current else None,
            "proposed": fields,
            "evidence": [{"source": "GROKBOT", "reference": "agent-tools-v1"}],
        },
        sources=["PRD-FR-272", "GROKBOT-001"],
    )
    operation = _persist_command(
        session,
        principal,
        operation_type="catalog_proposal",
        branch_id=None,
        key=key,
        digest=digest,
        status="READY_FOR_REVIEW",
        resource_id=proposal_id,
        correlation_id=correlation_id,
    )
    return _commit_or_replay(session, principal, key, digest, operation)


@router.post("/agent-tools/proposals/inventory-items", status_code=202)
def create_inventory_item_proposal(
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
    idempotency_key: IdempotencyDep = None,
    correlation_id: CorrelationDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.inventory_item.propose")
    _corporate(principal)
    command = _validated(InventoryProposal, payload)
    assert isinstance(command, InventoryProposal)
    normalized = _json(command.model_dump())
    key = _key(idempotency_key)
    digest = _command_hash("/api/v1/agent-tools/proposals/inventory-items", None, normalized)
    previous = _existing_command(session, principal, key, digest)
    if previous:
        return _operation_view(previous)
    unit = session.scalar(
        sa.select(models.inventory_units.c.id).where(
            models.inventory_units.c.id == command.base_unit_id,
            models.inventory_units.c.organization_id == principal.organization_id,
        )
    )
    duplicate = session.scalar(
        sa.select(models.inventory_items.c.id).where(
            models.inventory_items.c.organization_id == principal.organization_id,
            models.inventory_items.c.sku == command.sku,
        )
    )
    if not unit or duplicate:
        _fail(409, "stale_reference", "Inventory reference is invalid or stale")
    proposal_id = _proposal(
        session,
        principal,
        branch_id=None,
        change={
            "kind": "inventory_item.create",
            "target_id": None,
            "current": None,
            "proposed": {
                "sku": command.sku,
                "name": command.name,
                "base_unit_id": command.base_unit_id,
                "item_type": command.item_type,
            },
            "evidence": [{"source": "GROKBOT", "reference": "agent-tools-v1"}],
        },
        sources=["PRD-FR-272", "GROKBOT-001"],
    )
    operation = _persist_command(
        session,
        principal,
        operation_type="inventory_item_proposal",
        branch_id=None,
        key=key,
        digest=digest,
        status="READY_FOR_REVIEW",
        resource_id=proposal_id,
        correlation_id=correlation_id,
    )
    return _commit_or_replay(session, principal, key, digest, operation)


@router.post("/agent-tools/proposals/recipes", status_code=202)
def create_recipe_proposal(
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
    idempotency_key: IdempotencyDep = None,
    correlation_id: CorrelationDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.recipe.propose")
    command = _validated(RecipeProposal, payload)
    assert isinstance(command, RecipeProposal)
    branch_id = command.scope.branch_id if isinstance(command.scope, BranchScope) else None
    if branch_id:
        _branch(session, principal, branch_id)
    else:
        _corporate(principal)
    normalized = _json(command.model_dump())
    key = _key(idempotency_key)
    digest = _command_hash("/api/v1/agent-tools/proposals/recipes", branch_id, normalized)
    previous = _existing_command(session, principal, key, digest)
    if previous:
        return _operation_view(previous)
    product = session.scalar(
        sa.select(models.products.c.id).where(
            models.products.c.id == command.target_id,
            models.products.c.organization_id == principal.organization_id,
            _catalog_scope(models.products, branch_id),
        )
    )
    if not product:
        _fail(409, "stale_reference", "Recipe product was not found")
    active = session.scalar(
        sa.select(models.recipes.c.id)
        .where(
            models.recipes.c.product_id == command.target_id,
            models.recipes.c.recipe_type == "sale",
            models.recipes.c.branch_id.is_(None)
            if branch_id is None
            else models.recipes.c.branch_id == branch_id,
            models.recipes.c.status == "active",
            models.recipes.c.valid_to.is_(None),
        )
        .order_by(models.recipes.c.version.desc())
    )
    if active != command.expected_active_recipe_id:
        _fail(409, "stale_reference", "Active recipe changed")
    item_ids = {component.item_id for component in command.components}
    unit_ids = {component.unit_id for component in command.components} | {command.yield_unit_id}
    known_items = set(
        session.scalars(
            sa.select(models.inventory_items.c.id).where(
                models.inventory_items.c.organization_id == principal.organization_id,
                models.inventory_items.c.id.in_(item_ids),
                _catalog_scope(models.inventory_items, branch_id),
            )
        ).all()
    )
    known_units = set(
        session.scalars(
            sa.select(models.inventory_units.c.id).where(
                models.inventory_units.c.organization_id == principal.organization_id,
                models.inventory_units.c.id.in_(unit_ids),
            )
        ).all()
    )
    if known_items != item_ids or known_units != unit_ids:
        _fail(409, "stale_reference", "Recipe component reference is invalid")
    proposal_id = _proposal(
        session,
        principal,
        branch_id=branch_id,
        change={
            "kind": "recipe.version",
            "target_id": command.target_id,
            "current": {"id": active} if active else None,
            "proposed": {
                "yield_quantity": str(command.yield_quantity),
                "yield_unit_id": command.yield_unit_id,
                "components": [
                    {
                        "item_id": item.item_id,
                        "unit_id": item.unit_id,
                        "net_quantity": str(item.net_quantity),
                        "waste_rate": str(item.waste_rate),
                    }
                    for item in command.components
                ],
            },
            "evidence": [{"source": "GROKBOT", "reference": "agent-tools-v1"}],
        },
        sources=["PRD-FR-272", "GROKBOT-001"],
    )
    operation = _persist_command(
        session,
        principal,
        operation_type="recipe_proposal",
        branch_id=branch_id,
        key=key,
        digest=digest,
        status="READY_FOR_REVIEW",
        resource_id=proposal_id,
        correlation_id=correlation_id,
    )
    return _commit_or_replay(session, principal, key, digest, operation)


@router.post("/agent-tools/purchase-drafts", status_code=202)
def create_purchase_draft(
    payload: dict[str, Any],
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
    idempotency_key: IdempotencyDep = None,
    correlation_id: CorrelationDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.purchase_draft.create")
    command = _validated(PurchaseDraft, payload)
    assert isinstance(command, PurchaseDraft)
    branch_id = _branch(session, principal, command.branch_id)
    normalized = _json(command.model_dump())
    key = _key(idempotency_key)
    digest = _command_hash("/api/v1/agent-tools/purchase-drafts", branch_id, normalized)
    previous = _existing_command(session, principal, key, digest)
    if previous:
        return _operation_view(previous)
    purchase_payload = {
        **normalized,
        "document_date": command.document_date.isoformat(),
        "lines": [
            {
                "presentation_id": line.presentation_id,
                "quantity": str(line.quantity),
                "unit_price": str(line.unit_price),
                "discount": str(line.discount),
                "tax": str(line.tax),
            }
            for line in command.lines
        ],
    }
    try:
        purchase, line_count = create_agent_purchase_draft(
            session,
            purchase_payload,
            principal.identity_id,
            branch_id,
        )
    except BusinessError as exc:
        session.rollback()
        if exc.code == "purchase_document_identity_conflict":
            winner = _existing_command(session, principal, key, digest)
            if winner:
                return _operation_view(winner)
        if exc.code in {
            "purchase_supplier_or_branch_not_found",
            "presentation_reference_not_found",
            "inventory_item_not_found",
            "purchase_document_identity_conflict",
        }:
            _fail(409, "stale_reference", "Purchase references are stale", correlation_id)
        _fail(400, "agent_schema_invalid", "Purchase draft input is invalid", correlation_id)
    purchase_id = str(purchase["id"])
    _audit(
        session,
        "purchase.created",
        "purchase_document",
        purchase_id,
        actor_agent_identity_id=principal.identity_id,
        branch_id=branch_id,
        payload={"origin": "GROKBOT", "line_count": line_count},
    )
    operation = _persist_command(
        session,
        principal,
        operation_type="purchase_draft",
        branch_id=branch_id,
        key=key,
        digest=digest,
        status="DRAFT_CREATED",
        resource_id=purchase_id,
        correlation_id=correlation_id,
    )
    return _commit_or_replay(session, principal, key, digest, operation)


@router.get("/agent-tools/operations/{operation_id}")
def get_agent_operation(
    operation_id: str,
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    try:
        UUID(operation_id)
    except (ValueError, TypeError, AttributeError):
        _fail(400, "agent_schema_invalid", "operation_id must be a UUID")
    row = (
        session.execute(
            sa.select(models.external_agent_commands).where(
                models.external_agent_commands.c.id == operation_id,
                models.external_agent_commands.c.organization_id == principal.organization_id,
                models.external_agent_commands.c.identity_id == principal.identity_id,
            )
        )
        .mappings()
        .first()
    )
    if not row:
        _fail(404, "operation_not_found", "Operation was not found")
    if row["branch_id"]:
        _branch(session, principal, str(row["branch_id"]))
    elif not principal.corporate_scope:
        _fail(403, "agent_capability_denied", "Corporate operation is no longer authorized")
    return _operation_view(dict(row))
