"""GROKBOT-001 governed external-agent boundary.

One conversational orchestrator may coordinate four private specialists, but Kiwi always
authorizes the technical identity attached to the concrete tool credential. External writes are
limited to reviewable proposals and purchase drafts; no endpoint applies catalog, receives stock,
or moves cash.
"""

from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
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
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
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
from restaurant_os.financial_reads import RECONCILIATION_DATASETS, require_financial_read
from restaurant_os.operations import (
    ORGANIZATION_ID,
    AuthorizationError,
    BusinessError,
    require_permission,
)
from restaurant_os.purchase_workspace import create_agent_purchase_draft
from restaurant_os.reconciliation_reports import get_branch_daily_reconciliation

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
        {
            "agent.context.read",
            "agent.catalog.read",
            "agent.sales.read",
            "agent.cash_cuts.read",
            "agent.operating_expenses.read",
            "agent.payment_methods.read",
            "agent.cash_reconciliation.read",
            "agent.cash_personal_data.read",
            "agent.catalog.propose",
        }
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
            "agent.purchases.read",
            "agent.purchase_needs.read",
            "agent.purchase_draft.create",
        }
    ),
}
ADMINISTRATOR_OPT_IN_CAPABILITIES = frozenset(
    {
        "agent.cash_cuts.read",
        "agent.operating_expenses.read",
        "agent.payment_methods.read",
        "agent.cash_reconciliation.read",
        "agent.cash_personal_data.read",
    }
)
DEFAULT_CAPABILITIES: dict[str, frozenset[str]] = {
    **BASELINE_CAPABILITIES,
    "administrator": BASELINE_CAPABILITIES["administrator"] - ADMINISTRATOR_OPT_IN_CAPABILITIES,
    "purchasing": BASELINE_CAPABILITIES["purchasing"] - {"agent.purchases.read"},
}
EXTERNAL_SALES_CHANNELS = frozenset({"UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP"})
KNOWN_PAYMENT_METHODS = frozenset(
    {
        "cash",
        "debit_card",
        "credit_card",
        "card",
        "transfer",
        "bank_transfer",
        "spei",
        "credit",
        "customer_credit",
    }
)
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
        headers={"X-Kiwi-Error-Code": code},
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
                "capabilities": sorted(DEFAULT_CAPABILITIES[profile]),
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
                    capabilities=sorted(DEFAULT_CAPABILITIES[profile]),
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
    previous_capability_set = set(identity["capabilities"] or [])
    if not capability_set <= BASELINE_CAPABILITIES[profile]:
        _fail(400, "agent_capability_denied", "Policy cannot expand the profile baseline")
    current_branch_ids: list[str] = list(
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
    known: set[str] = (
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
            "enabled_before": bool(identity["is_enabled"]),
            "enabled_after": enabled,
            "corporate_scope_before": bool(identity["corporate_scope"]),
            "corporate_scope_after": corporate_scope,
            "capability_count": len(capability_set),
            "capabilities_added": sorted(capability_set - previous_capability_set),
            "capabilities_removed": sorted(previous_capability_set - capability_set),
            "branch_count": len(branch_ids),
            "branches_added": sorted(set(branch_ids) - set(current_branch_ids)),
            "branches_removed": sorted(set(current_branch_ids) - set(branch_ids)),
            "authorization_version_before": expected_version,
            "authorization_version_after": expected_version + 1,
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
    branch_rows: list[str] = list(
        session.scalars(
            sa.select(models.external_agent_identity_branches.c.branch_id).where(
                models.external_agent_identity_branches.c.identity_id == identity["id"]
            )
        ).all()
    )
    branches = frozenset(str(value) for value in branch_rows)
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
    response: Response,
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
        extra={
            "identity_id": str(identity["id"]),
            "profile": identity["profile"],
            "operation": "token.issue",
            "result": "accepted",
        },
    )
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
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
            sa.select(
                models.branches.c.id,
                models.branches.c.code,
                models.branches.c.name,
                models.branches.c.timezone,
            )
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


def _inventory_movement_cursor_signature(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    message = b"agent-inventory-movement-cursor-v1\0" + raw
    return hmac.new(get_settings().secret_key.encode(), message, hashlib.sha256).hexdigest()


def _inventory_movement_cursor(
    value: str | None,
    *,
    branch_id: str,
    start: datetime,
    end: datetime,
) -> tuple[datetime, str] | None:
    if not value:
        return None
    if len(value) > 512:
        _fail(400, "agent_schema_invalid", "cursor must not exceed 512 characters")
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        expected_keys = {"branch_id", "effective_at", "from_utc", "id", "signature", "to_utc"}
        if not isinstance(decoded, dict) or set(decoded) != expected_keys:
            raise ValueError
        if not all(isinstance(decoded[key], str) for key in expected_keys):
            raise ValueError
        signed_payload = {key: decoded[key] for key in expected_keys if key != "signature"}
        expected_signature = _inventory_movement_cursor_signature(signed_payload)
        if not hmac.compare_digest(decoded["signature"], expected_signature):
            raise ValueError
        if (
            decoded["branch_id"] != branch_id
            or decoded["from_utc"] != start.isoformat()
            or decoded["to_utc"] != end.isoformat()
        ):
            raise ValueError
        effective_at_text = decoded["effective_at"]
        movement_id = decoded["id"]
        effective_at = datetime.fromisoformat(effective_at_text.replace("Z", "+00:00"))
        UUID(movement_id)
        if effective_at.tzinfo is None:
            raise ValueError
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        _fail(400, "agent_schema_invalid", "cursor is invalid")
    return effective_at.astimezone(timezone.utc), movement_id


def _inventory_movement_page(
    rows: list[dict[str, Any]],
    limit: int,
    *,
    branch_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last_effective_at = visible[-1]["effective_at"]
        if last_effective_at.tzinfo is None:
            last_effective_at = last_effective_at.replace(tzinfo=timezone.utc)
        signed_payload = {
            "branch_id": branch_id,
            "effective_at": last_effective_at.astimezone(timezone.utc).isoformat(),
            "from_utc": start.isoformat(),
            "id": visible[-1]["id"],
            "to_utc": end.isoformat(),
        }
        payload = {
            **signed_payload,
            "signature": _inventory_movement_cursor_signature(signed_payload),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    for row in visible:
        row["quantity_delta"] = str(row["quantity_delta"])
        effective_at = row["effective_at"]
        if effective_at.tzinfo is None:
            effective_at = effective_at.replace(tzinfo=timezone.utc)
        row["effective_at"] = effective_at.astimezone(timezone.utc).isoformat()
    return {"items": visible, "page": {"next_cursor": next_cursor, "has_more": has_more}}


def _purchase_history_cursor_signature(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    message = b"agent-purchase-history-cursor-v1\0" + raw
    return hmac.new(get_settings().secret_key.encode(), message, hashlib.sha256).hexdigest()


def _purchase_history_cursor(
    value: str | None,
    *,
    branch_id: str,
    start: datetime,
    end: datetime,
) -> tuple[datetime, str] | None:
    if not value:
        return None
    if len(value) > 512:
        _fail(400, "agent_schema_invalid", "cursor must not exceed 512 characters")
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        expected_keys = {
            "branch_id",
            "confirmed_at",
            "from_utc",
            "id",
            "signature",
            "to_utc",
        }
        if not isinstance(decoded, dict) or set(decoded) != expected_keys:
            raise ValueError
        if not all(isinstance(decoded[key], str) for key in expected_keys):
            raise ValueError
        signed_payload = {key: decoded[key] for key in expected_keys if key != "signature"}
        expected_signature = _purchase_history_cursor_signature(signed_payload)
        if not hmac.compare_digest(decoded["signature"], expected_signature):
            raise ValueError
        if (
            decoded["branch_id"] != branch_id
            or decoded["from_utc"] != start.isoformat()
            or decoded["to_utc"] != end.isoformat()
        ):
            raise ValueError
        confirmed_at = datetime.fromisoformat(decoded["confirmed_at"].replace("Z", "+00:00"))
        purchase_id = decoded["id"]
        UUID(purchase_id)
        if confirmed_at.tzinfo is None:
            raise ValueError
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        _fail(400, "agent_schema_invalid", "cursor is invalid")
    return confirmed_at.astimezone(timezone.utc), purchase_id


def _purchase_history_page(
    rows: list[dict[str, Any]],
    limit: int,
    *,
    branch_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last_confirmed_at = visible[-1]["confirmed_at"]
        if last_confirmed_at.tzinfo is None:
            last_confirmed_at = last_confirmed_at.replace(tzinfo=timezone.utc)
        signed_payload = {
            "branch_id": branch_id,
            "confirmed_at": last_confirmed_at.astimezone(timezone.utc).isoformat(),
            "from_utc": start.isoformat(),
            "id": visible[-1]["id"],
            "to_utc": end.isoformat(),
        }
        payload = {
            **signed_payload,
            "signature": _purchase_history_cursor_signature(signed_payload),
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    document_amounts = (
        "subtotal",
        "discount_total",
        "tax_total",
        "freight_total",
        "total",
    )
    line_amounts = (
        "presentation_quantity",
        "base_quantity",
        "unit_price",
        "discount",
        "tax",
        "line_total",
        "inventory_cost",
        "cost_per_base_unit",
    )
    for row in visible:
        for field in document_amounts:
            row[field] = str(row[field])
        for field in ("document_date", "confirmed_at", "cancelled_at"):
            value = row[field]
            if value is not None:
                if value.tzinfo is None:
                    value = value.replace(tzinfo=timezone.utc)
                row[field] = value.astimezone(timezone.utc).isoformat()
        for line in row["lines"]:
            for field in line_amounts:
                line[field] = str(line[field])
    return {"items": visible, "page": {"next_cursor": next_cursor, "has_more": has_more}}


def _cash_cut_cursor_signature(payload: dict[str, str]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    message = b"agent-cash-cut-cursor-v1\0" + raw
    return hmac.new(get_settings().secret_key.encode(), message, hashlib.sha256).hexdigest()


def _cash_cut_cursor(
    value: str | None,
    *,
    branch_id: str,
    start: datetime,
    end: datetime,
) -> tuple[datetime, str] | None:
    if not value:
        return None
    if len(value) > 512:
        _fail(400, "agent_schema_invalid", "cursor must not exceed 512 characters")
    try:
        decoded = json.loads(base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)))
        expected_keys = {"branch_id", "from_utc", "id", "period_start", "signature", "to_utc"}
        if not isinstance(decoded, dict) or set(decoded) != expected_keys:
            raise ValueError
        if not all(isinstance(decoded[key], str) for key in expected_keys):
            raise ValueError
        signed_payload = {key: decoded[key] for key in expected_keys if key != "signature"}
        if not hmac.compare_digest(
            decoded["signature"], _cash_cut_cursor_signature(signed_payload)
        ):
            raise ValueError
        if (
            decoded["branch_id"] != branch_id
            or decoded["from_utc"] != start.isoformat()
            or decoded["to_utc"] != end.isoformat()
        ):
            raise ValueError
        period_start = datetime.fromisoformat(decoded["period_start"].replace("Z", "+00:00"))
        cut_id = decoded["id"]
        UUID(cut_id)
        if period_start.tzinfo is None:
            raise ValueError
    except (
        binascii.Error,
        KeyError,
        TypeError,
        UnicodeDecodeError,
        ValueError,
        json.JSONDecodeError,
    ):
        _fail(400, "agent_schema_invalid", "cursor is invalid")
    return period_start.astimezone(timezone.utc), cut_id


def _cash_cut_page(
    rows: list[dict[str, Any]],
    limit: int,
    *,
    branch_id: str,
    start: datetime,
    end: datetime,
) -> dict[str, Any]:
    has_more = len(rows) > limit
    visible = rows[:limit]
    next_cursor = None
    if has_more and visible:
        last_period_start = visible[-1]["period_start"]
        if last_period_start.tzinfo is None:
            last_period_start = last_period_start.replace(tzinfo=timezone.utc)
        signed_payload = {
            "branch_id": branch_id,
            "from_utc": start.isoformat(),
            "id": visible[-1]["id"],
            "period_start": last_period_start.astimezone(timezone.utc).isoformat(),
            "to_utc": end.isoformat(),
        }
        payload = {**signed_payload, "signature": _cash_cut_cursor_signature(signed_payload)}
        raw = json.dumps(payload, separators=(",", ":")).encode()
        next_cursor = base64.urlsafe_b64encode(raw).decode().rstrip("=")
    for row in visible:
        for field in ("period_start", "period_end", "finalized_at"):
            value = row[field]
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            row[field] = value.astimezone(timezone.utc).isoformat()
    return {"items": visible, "page": {"next_cursor": next_cursor, "has_more": has_more}}


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
    catalog_from = models.products.join(
        models.product_categories,
        models.product_categories.c.id == models.products.c.category_id,
    ).outerjoin(
        models.price_versions,
        sa.and_(
            models.price_versions.c.product_id == models.products.c.id,
            models.price_versions.c.valid_to.is_(None),
        ),
    )
    availability_column: sa.ColumnElement[Any]
    if branch_id:
        catalog_from = catalog_from.outerjoin(
            models.branch_product_availability,
            sa.and_(
                models.branch_product_availability.c.product_id == models.products.c.id,
                models.branch_product_availability.c.branch_id == branch_id,
            ),
        )
        availability_column = models.branch_product_availability.c.is_available
    else:
        availability_column = sa.literal(None)
    query = (
        sa.select(
            models.products.c.id,
            models.products.c.sku,
            models.products.c.name,
            models.product_categories.c.name.label("category_name"),
            models.products.c.station,
            models.price_versions.c.price_cents,
            models.price_versions.c.currency,
            availability_column.label("availability_override"),
            (models.products.c.status == "active").label("active"),
            models.products.c.updated_at,
        )
        .select_from(catalog_from)
        .where(
            models.products.c.organization_id == principal.organization_id,
            _catalog_scope(models.products, branch_id),
        )
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
        if branch_id:
            row["available"] = bool(row["active"]) and (
                bool(row["availability_override"])
                if row["availability_override"] is not None
                else True
            )
            row["sellable"] = bool(row["available"]) and bool(
                row["price_cents"] is not None and int(row["price_cents"]) > 0
            )
        else:
            row["available"] = None
            row["sellable"] = None
        row.pop("availability_override")
        row["version"] = _resource_version(row.pop("updated_at"))
    return _page(rows, limit)


def _require_financial_audience(
    session: Session,
    branch_id: str,
    datasets: tuple[str, ...] = ("sales",),
) -> None:
    # No approved human-audience protocol exists in F1. A technical capability
    # cannot act as a financial grant, even when issued by a reviewed Owner.
    try:
        require_financial_read(session, None, branch_id, datasets)
    except AuthorizationError:
        _fail(403, "financial_access_denied", "An authorized human audience is required")


def _utc_window(from_utc: datetime, to_utc: datetime, label: str) -> tuple[datetime, datetime]:
    if from_utc.tzinfo is None or to_utc.tzinfo is None:
        _fail(400, "agent_schema_invalid", "from_utc and to_utc must include a timezone")
    start = from_utc.astimezone(timezone.utc)
    end = to_utc.astimezone(timezone.utc)
    if start >= end or end - start > timedelta(days=31):
        _fail(400, "agent_schema_invalid", f"{label} period must be positive and at most 31 days")
    return start, end


def _administrator(principal: AgentPrincipal) -> None:
    if principal.profile != "administrator":
        _fail(403, "agent_capability_denied", "This read requires the administrator profile")


def _calendar_date(value: str, field: str) -> date:
    if len(value) != 10 or value[4] != "-" or value[7] != "-":
        _fail(400, "agent_schema_invalid", f"{field} must be YYYY-MM-DD")
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        _fail(400, "agent_schema_invalid", f"{field} must be YYYY-MM-DD")
    if parsed.isoformat() != value or parsed.year == 9999:
        _fail(400, "agent_schema_invalid", f"{field} must be YYYY-MM-DD")
    return parsed


def _exact_cents(value: Decimal) -> int:
    scaled = Decimal(value) * 100
    cents = scaled.quantize(Decimal("1"))
    if cents != scaled:
        _fail(503, "dependency_unavailable", "Reconciliation amount is not an exact cent")
    return int(cents)


@router.get("/agent-tools/sales/summary")
def get_agent_sales_summary(
    branch_id: str,
    from_utc: datetime,
    to_utc: datetime,
    session: SessionDep,
    top_limit: int = 10,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    """Return a minimized aggregate over immutable confirmed-sale snapshots."""
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.sales.read")
    authorized_branch = _branch(session, principal, branch_id)
    _require_financial_audience(session, authorized_branch)
    if from_utc.tzinfo is None or to_utc.tzinfo is None:
        _fail(400, "agent_schema_invalid", "from_utc and to_utc must include a timezone")
    start = from_utc.astimezone(timezone.utc)
    end = to_utc.astimezone(timezone.utc)
    if start >= end or end - start > timedelta(days=31):
        _fail(400, "agent_schema_invalid", "Sales period must be positive and at most 31 days")
    if not 1 <= top_limit <= 20:
        _fail(400, "agent_schema_invalid", "top_limit must be between 1 and 20")

    snapshots = models.sales_operation_snapshots
    snapshot_currency = sa.func.upper(snapshots.c.currency)
    snapshot_scope = (
        snapshots.c.organization_id == principal.organization_id,
        snapshots.c.branch_id == authorized_branch,
        snapshots.c.confirmed_at >= start,
        snapshots.c.confirmed_at < end,
    )
    totals_by_currency = [
        dict(row)
        for row in session.execute(
            sa.select(
                snapshot_currency.label("currency"),
                sa.func.sum(snapshots.c.gross_cents).label("gross_cents"),
                sa.func.sum(snapshots.c.net_cents).label("net_cents"),
                sa.func.sum(sa.func.coalesce(snapshots.c.discount_cents, 0)).label(
                    "discount_cents"
                ),
                sa.func.sum(sa.func.coalesce(snapshots.c.courtesy_cents, 0)).label(
                    "courtesy_cents"
                ),
                sa.func.sum(sa.func.coalesce(snapshots.c.tax_cents, 0)).label("tax_cents"),
                sa.func.sum(sa.case((snapshots.c.discount_cents.is_(None), 1), else_=0)).label(
                    "unknown_discount_operation_count"
                ),
                sa.func.sum(sa.case((snapshots.c.courtesy_cents.is_(None), 1), else_=0)).label(
                    "unknown_courtesy_operation_count"
                ),
                sa.func.sum(sa.case((snapshots.c.tax_cents.is_(None), 1), else_=0)).label(
                    "unknown_tax_operation_count"
                ),
            )
            .where(*snapshot_scope)
            .group_by(snapshot_currency)
            .order_by(snapshot_currency)
        ).mappings()
    ]
    services = [
        dict(row)
        for row in session.execute(
            sa.select(
                snapshots.c.service_type_snapshot.label("service_type"),
                snapshot_currency.label("currency"),
                sa.func.count(sa.distinct(snapshots.c.order_id)).label("order_count"),
                sa.func.sum(snapshots.c.gross_cents).label("gross_cents"),
                sa.func.sum(snapshots.c.net_cents).label("net_cents"),
            )
            .where(*snapshot_scope)
            .group_by(snapshot_currency, snapshots.c.service_type_snapshot)
            .order_by(snapshot_currency, snapshots.c.service_type_snapshot)
        ).mappings()
    ]

    lines = models.sales_operation_line_snapshots
    line_scope = (
        sa.select(
            lines.c.product_id,
            lines.c.product_name_snapshot,
            snapshot_currency.label("currency"),
            snapshots.c.confirmed_at,
            lines.c.id.label("line_id"),
            lines.c.quantity,
            lines.c.gross_cents,
        )
        .join(snapshots, snapshots.c.id == lines.c.sales_operation_snapshot_id)
        .where(*snapshot_scope)
        .subquery()
    )
    product_aggregates = (
        sa.select(
            line_scope.c.product_id,
            line_scope.c.currency,
            sa.func.sum(line_scope.c.quantity).label("quantity"),
            sa.func.sum(line_scope.c.gross_cents).label("gross_cents"),
        )
        .group_by(line_scope.c.product_id, line_scope.c.currency)
        .subquery()
    )
    latest_product_names = sa.select(
        line_scope.c.product_id,
        line_scope.c.currency,
        line_scope.c.product_name_snapshot.label("product_name"),
        sa.func.row_number()
        .over(
            partition_by=(line_scope.c.product_id, line_scope.c.currency),
            order_by=(line_scope.c.confirmed_at.desc(), line_scope.c.line_id.desc()),
        )
        .label("name_rank"),
    ).subquery()
    product_totals = (
        sa.select(
            product_aggregates.c.product_id,
            latest_product_names.c.product_name,
            product_aggregates.c.currency,
            product_aggregates.c.quantity,
            product_aggregates.c.gross_cents,
        )
        .select_from(
            product_aggregates.join(
                latest_product_names,
                sa.and_(
                    latest_product_names.c.product_id == product_aggregates.c.product_id,
                    latest_product_names.c.currency == product_aggregates.c.currency,
                    latest_product_names.c.name_rank == 1,
                ),
            )
        )
        .subquery()
    )
    ranked_products = sa.select(
        product_totals,
        sa.func.row_number()
        .over(
            partition_by=product_totals.c.currency,
            order_by=(
                product_totals.c.gross_cents.desc(),
                product_totals.c.product_id.asc(),
            ),
        )
        .label("currency_rank"),
    ).subquery()
    top_products = [
        {key: value for key, value in dict(row).items() if key != "currency_rank"}
        for row in session.execute(
            sa.select(ranked_products)
            .where(ranked_products.c.currency_rank <= top_limit)
            .order_by(ranked_products.c.currency, ranked_products.c.currency_rank)
        ).mappings()
    ]

    corrections_by_currency = [
        dict(row)
        for row in session.execute(
            sa.select(
                models.order_corrections.c.currency,
                sa.func.count().label("correction_count"),
                sa.func.sum(models.order_corrections.c.settlement_delta_cents).label(
                    "net_delta_cents"
                ),
            )
            .where(
                models.order_corrections.c.organization_id == principal.organization_id,
                models.order_corrections.c.branch_id == authorized_branch,
                models.order_corrections.c.applied_at >= start,
                models.order_corrections.c.applied_at < end,
            )
            .group_by(models.order_corrections.c.currency)
            .order_by(models.order_corrections.c.currency)
        ).mappings()
    ]
    summary = (
        session.execute(
            sa.select(
                sa.func.count(sa.distinct(snapshots.c.order_id)).label("order_count"),
                sa.func.sum(
                    sa.case((snapshots.c.quality_status == "incomplete", 1), else_=0)
                ).label("incomplete_operation_count"),
            ).where(*snapshot_scope)
        )
        .mappings()
        .one()
    )
    return {
        "branch_id": authorized_branch,
        "from_utc": start,
        "to_utc": end,
        "order_count": int(summary["order_count"] or 0),
        "totals_by_currency": totals_by_currency,
        "services": services,
        "top_products": top_products,
        "corrections_by_currency": corrections_by_currency,
        "data_quality": {
            "incomplete_operation_count": int(summary["incomplete_operation_count"] or 0)
        },
    }


@router.get("/agent-tools/cash/cuts")
def list_agent_cash_cuts(
    branch_id: str,
    from_utc: datetime,
    to_utc: datetime,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 25,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    """Return finalized cash cuts without cashier identity or mutable workflow details."""
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.cash_cuts.read")
    if principal.profile != "administrator":
        _fail(403, "agent_capability_denied", "Cash cuts require the administrator profile")
    authorized_branch = _branch(session, principal, branch_id)
    _require_financial_audience(session, authorized_branch)
    if from_utc.tzinfo is None or to_utc.tzinfo is None:
        _fail(400, "agent_schema_invalid", "from_utc and to_utc must include a timezone")
    start = from_utc.astimezone(timezone.utc)
    end = to_utc.astimezone(timezone.utc)
    if start >= end or end - start > timedelta(days=31):
        _fail(
            400,
            "agent_schema_invalid",
            "Cash cut period must be positive and at most 31 days",
        )
    if not 1 <= limit <= 25:
        _fail(400, "agent_schema_invalid", "limit must be between 1 and 25")
    after = _cash_cut_cursor(
        cursor,
        branch_id=authorized_branch,
        start=start,
        end=end,
    )
    cuts = models.user_cash_cuts
    query = sa.select(
        cuts.c.id,
        cuts.c.branch_id,
        cuts.c.register_code_snapshot.label("register_code"),
        cuts.c.period_start,
        cuts.c.period_end,
        cuts.c.finalized_at,
        cuts.c.opening_cash_cents,
        cuts.c.cash_payment_cents,
        cuts.c.deposit_cents,
        cuts.c.withdrawal_cents,
        cuts.c.expected_cash_cents,
        cuts.c.counted_cash_cents,
        cuts.c.difference_cents,
    ).where(
        cuts.c.organization_id == principal.organization_id,
        cuts.c.branch_id == authorized_branch,
        cuts.c.status == "FINALIZED",
        cuts.c.period_start >= start,
        cuts.c.period_start < end,
    )
    if after:
        after_period_start, after_id = after
        query = query.where(
            sa.or_(
                cuts.c.period_start < after_period_start,
                sa.and_(cuts.c.period_start == after_period_start, cuts.c.id < after_id),
            )
        )
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(cuts.c.period_start.desc(), cuts.c.id.desc()).limit(limit + 1)
        ).mappings()
    ]
    visible_ids = [str(row["id"]) for row in rows[:limit]]
    latest_compensation: dict[str, dict[str, Any]] = {}
    if visible_ids:
        compensation_rows = session.execute(
            sa.select(
                models.user_cash_cut_compensations.c.id,
                models.user_cash_cut_compensations.c.cash_cut_id,
                models.user_cash_cut_compensations.c.corrected_counted_cash_cents,
                models.user_cash_cut_compensations.c.corrected_difference_cents,
                models.user_cash_cut_compensations.c.created_at,
            )
            .where(
                models.user_cash_cut_compensations.c.organization_id
                == principal.organization_id,
                models.user_cash_cut_compensations.c.cash_cut_id.in_(visible_ids),
            )
            .order_by(
                models.user_cash_cut_compensations.c.created_at.desc(),
                models.user_cash_cut_compensations.c.id.desc(),
            )
        ).mappings()
        ambiguous_compensations: set[str] = set()
        for compensation_row in compensation_rows:
            cut_id = str(compensation_row["cash_cut_id"])
            latest = latest_compensation.get(cut_id)
            if latest is None:
                latest_compensation[cut_id] = dict(compensation_row)
            elif latest["created_at"] == compensation_row["created_at"]:
                ambiguous_compensations.add(cut_id)
    else:
        ambiguous_compensations = set()
    required_amounts = (
        "cash_payment_cents",
        "deposit_cents",
        "withdrawal_cents",
        "expected_cash_cents",
        "counted_cash_cents",
        "difference_cents",
    )
    for row in rows[:limit]:
        if str(row["id"]) in ambiguous_compensations:
            _fail(
                503,
                "dependency_unavailable",
                "Cash cut compensation order is ambiguous",
            )
        if row["finalized_at"] is None or any(row[field] is None for field in required_amounts):
            _fail(503, "dependency_unavailable", "Finalized cash cut data is incomplete")
        effective_compensation = latest_compensation.get(str(row["id"]))
        row["compensated"] = effective_compensation is not None
        if effective_compensation:
            row["counted_cash_cents"] = effective_compensation["corrected_counted_cash_cents"]
            row["difference_cents"] = effective_compensation["corrected_difference_cents"]
    return _cash_cut_page(
        rows,
        limit,
        branch_id=authorized_branch,
        start=start,
        end=end,
    )


@router.get("/agent-tools/expenses/summary")
def get_agent_expense_summary(
    branch_id: str,
    from_utc: datetime,
    to_utc: datetime,
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    """Aggregate confirmed operating expenses by catalog concept. Read-only."""
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.operating_expenses.read")
    _administrator(principal)
    authorized_branch = _branch(session, principal, branch_id)
    _require_financial_audience(session, authorized_branch, ("expenses",))
    start, end = _utc_window(from_utc, to_utc, "Expense")
    documents = models.expense_documents
    concepts = models.expense_concepts
    concept_name = documents.c.concept_snapshot["name"].as_string()
    scope = (
        documents.c.organization_id == principal.organization_id,
        documents.c.branch_id == authorized_branch,
        documents.c.confirmed_at.is_not(None),
    )
    grouped: dict[tuple[str, str, str | None], dict[str, int]] = {}
    for stamp, sign in ((documents.c.confirmed_at, 1), (documents.c.cancelled_at, -1)):
        rows = session.execute(
            sa.select(
                documents.c.concept_id,
                concept_name.label("concept_name"),
                concepts.c.code.label("concept_code"),
                (sa.func.sum(documents.c.total_cents) * sign).label("net_cents"),
            )
            .select_from(
                documents.outerjoin(
                    concepts,
                    sa.and_(
                        concepts.c.id == documents.c.concept_id,
                        concepts.c.organization_id == principal.organization_id,
                    ),
                )
            )
            .where(*scope, stamp >= start, stamp < end)
            .group_by(documents.c.concept_id, concept_name, concepts.c.code)
        ).mappings()
        for row in rows:
            if not isinstance(row["concept_name"], str) or not row["concept_name"].strip():
                _fail(503, "dependency_unavailable", "Expense concept snapshot is incomplete")
            if row["net_cents"] is None:
                _fail(503, "dependency_unavailable", "Expense amount is incomplete")
            key = (str(row["concept_id"]), row["concept_name"], row["concept_code"])
            slot = grouped.setdefault(
                key, {"net_cents": 0, "confirmed_cents": 0, "reversed_cents": 0}
            )
            amount = int(row["net_cents"])
            slot["net_cents"] += amount
            if amount > 0:
                slot["confirmed_cents"] += amount
            elif amount < 0:
                slot["reversed_cents"] += -amount
    concepts_out = [
        {
            "concept_id": concept_id,
            "concept_code": concept_code,
            "concept_code_source": "current_catalog" if concept_code else None,
            "concept_name": name,
            "concept_name_source": "document_snapshot",
            "net_cents": amounts["net_cents"],
            "confirmed_cents": amounts["confirmed_cents"],
            "reversed_cents": amounts["reversed_cents"],
        }
        for (concept_id, name, concept_code), amounts in sorted(
            grouped.items(), key=lambda item: (item[0][2] or "", item[0][1], item[0][0])
        )
    ]
    return {
        "branch_id": authorized_branch,
        "from_utc": start,
        "to_utc": end,
        "currency": "MXN",
        "grouping": "concept",
        "concepts": concepts_out,
        "totals": {
            "confirmed_cents": sum(item["confirmed_cents"] for item in concepts_out),
            "reversed_cents": sum(item["reversed_cents"] for item in concepts_out),
            "net_cents": sum(item["net_cents"] for item in concepts_out),
        },
    }


@router.get("/agent-tools/payments/by-method")
def get_agent_payments_by_method(
    branch_id: str,
    from_utc: datetime,
    to_utc: datetime,
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    """Payment-method totals over the same confirmed-sale snapshots as sales/summary.

    `agent.sales.read` stays on by default and must not reveal method. This opt-in flag
    follows `agent.cash_cuts.read`: administrator only, absent from the default policy.
    """
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.payment_methods.read")
    _administrator(principal)
    authorized_branch = _branch(session, principal, branch_id)
    _require_financial_audience(session, authorized_branch, ("sales",))
    start, end = _utc_window(from_utc, to_utc, "Payment")
    snapshots = models.sales_operation_snapshots
    payments = models.payments
    orders = models.orders
    snapshot_scope = (
        snapshots.c.organization_id == principal.organization_id,
        snapshots.c.branch_id == authorized_branch,
        snapshots.c.confirmed_at >= start,
        snapshots.c.confirmed_at < end,
    )
    method_name = sa.func.lower(payments.c.method)
    linked_orders = sa.and_(
        orders.c.id == snapshots.c.order_id,
        orders.c.organization_id == principal.organization_id,
        orders.c.branch_id == authorized_branch,
    )
    incomplete = session.scalar(
        sa.select(sa.func.count())
        .select_from(
            snapshots.outerjoin(payments, payments.c.id == snapshots.c.payment_id).outerjoin(
                orders, linked_orders
            )
        )
        .where(*snapshot_scope, sa.or_(payments.c.id.is_(None), orders.c.id.is_(None)))
    )
    if int(incomplete or 0):
        _fail(503, "dependency_unavailable", "Confirmed sale is missing its payment or order")
    external_case = sa.case((orders.c.channel.in_(tuple(EXTERNAL_SALES_CHANNELS)), 1), else_=0)
    delivery_case = sa.case((snapshots.c.service_type_snapshot == "delivery", 1), else_=0)
    currency = sa.func.upper(snapshots.c.currency)
    method_rows = [
        dict(row)
        for row in session.execute(
            sa.select(
                currency.label("currency"),
                method_name.label("method"),
                sa.func.count().label("operation_count"),
                sa.func.sum(snapshots.c.net_cents).label("net_cents"),
                sa.func.sum(external_case).label("external_operation_count"),
                sa.func.sum(delivery_case).label("delivery_operation_count"),
            )
            .select_from(
                snapshots.join(payments, payments.c.id == snapshots.c.payment_id).join(
                    orders, linked_orders
                )
            )
            .where(*snapshot_scope)
            .group_by(currency, method_name)
            .order_by(currency, method_name)
        ).mappings()
    ]
    for row in method_rows:
        if row["method"] not in KNOWN_PAYMENT_METHODS or row["net_cents"] is None:
            _fail(503, "dependency_unavailable", "Confirmed sale payment method is unknown")
        row["operation_count"] = int(row["operation_count"])
        row["net_cents"] = int(row["net_cents"])
        row["external_operation_count"] = int(row["external_operation_count"] or 0)
        row["delivery_operation_count"] = int(row["delivery_operation_count"] or 0)
    totals: dict[str, dict[str, int]] = {}
    for row in method_rows:
        bucket = totals.setdefault(row["currency"], {"net_cents": 0, "operation_count": 0})
        bucket["net_cents"] += row["net_cents"]
        bucket["operation_count"] += row["operation_count"]
    summary = session.execute(
        sa.select(
            sa.func.count(sa.distinct(snapshots.c.order_id)).label("order_count"),
        ).where(*snapshot_scope)
    ).mappings().one()
    corrections = [
        {
            "currency": row["currency"],
            "correction_count": int(row["correction_count"]),
            "net_delta_cents": int(row["net_delta_cents"] or 0),
        }
        for row in session.execute(
            sa.select(
                models.order_corrections.c.currency,
                sa.func.count().label("correction_count"),
                sa.func.sum(models.order_corrections.c.settlement_delta_cents).label(
                    "net_delta_cents"
                ),
            )
            .where(
                models.order_corrections.c.organization_id == principal.organization_id,
                models.order_corrections.c.branch_id == authorized_branch,
                models.order_corrections.c.applied_at >= start,
                models.order_corrections.c.applied_at < end,
            )
            .group_by(models.order_corrections.c.currency)
            .order_by(models.order_corrections.c.currency)
        ).mappings()
    ]
    return {
        "branch_id": authorized_branch,
        "from_utc": start,
        "to_utc": end,
        "order_count": int(summary["order_count"] or 0),
        "external_order_count": sum(row["external_operation_count"] for row in method_rows),
        "external_orders_included": True,
        "net_includes_tax_and_delivery": True,
        "methods": method_rows,
        "totals_by_currency": [
            {"currency": code, **amounts} for code, amounts in sorted(totals.items())
        ],
        "corrections_by_currency": corrections,
    }


def _signed_amount_rows(
    rows: list[dict[str, Any]], source_key: str, output_key: str
) -> tuple[list[dict[str, Any]], int]:
    projected = [
        {output_key: row[source_key], "amount_cents": _exact_cents(Decimal(row["amount"]))}
        for row in rows
    ]
    return projected, sum(item["amount_cents"] for item in projected)


def _require_same_total(actual: int, expected: Any, label: str) -> None:
    if actual != _exact_cents(Decimal(expected)):
        _fail(503, "dependency_unavailable", f"{label} total does not match the ledger")


def _personal_amount_rows(
    rows: list[dict[str, Any]],
    *,
    ticket_key: str,
    name_key: str,
    phone_key: str | None,
    received_key: str | None,
) -> tuple[list[dict[str, Any]], int]:
    projected: list[dict[str, Any]] = []
    for row in rows:
        amount_cents = _exact_cents(Decimal(row["amount"]))
        item: dict[str, Any] = {"amount_cents": amount_cents}
        if ticket_key:
            item["ticket"] = row[ticket_key]
        if received_key:
            item["folio"] = row["folio"]
            item["received_by"] = row[received_key]
        else:
            item["name"] = row[name_key]
            item["phone"] = row[phone_key or "customer_phone"]
        projected.append(item)
    return projected, sum(item["amount_cents"] for item in projected)


def _cash_population(
    balance: dict[str, Any],
    suppliers: list[dict[str, Any]],
    fixed_expenses: list[dict[str, Any]],
    withdrawals: list[dict[str, Any]],
    credits: list[dict[str, Any]],
    transfers: list[dict[str, Any]],
    *,
    include_personal: bool,
    physical_count_status: str | None,
    surplus_shortage_cents: int | None,
) -> dict[str, Any]:
    supplier_rows, supplier_cents = _signed_amount_rows(suppliers, "provider_name", "supplier_name")
    fixed_rows, fixed_cents = _signed_amount_rows(fixed_expenses, "expense_type", "expense_type")
    _require_same_total(supplier_cents, balance["supplier_expenses"], "Supplier payment")
    _require_same_total(fixed_cents, balance["fixed_expenses"], "Fixed expense")
    withdrawal_cents = _exact_cents(Decimal(balance["cash_withdrawals"]))
    credit_cents = _exact_cents(Decimal(balance["credit_sales"]))
    transfer_cents = _exact_cents(Decimal(balance["transfer_payments"]))
    personal_withdrawals, withdrawal_line_cents = _personal_amount_rows(
        withdrawals,
        ticket_key="",
        name_key="",
        phone_key=None,
        received_key="recipient_name",
    )
    personal_credits, credit_line_cents = _personal_amount_rows(
        credits,
        ticket_key="ticket_folio",
        name_key="customer_name",
        phone_key="customer_phone",
        received_key=None,
    )
    personal_transfers, transfer_line_cents = _personal_amount_rows(
        transfers,
        ticket_key="ticket_folio",
        name_key="customer_name",
        phone_key="customer_phone",
        received_key=None,
    )
    _require_same_total(withdrawal_line_cents, balance["cash_withdrawals"], "Cash withdrawal")
    _require_same_total(credit_line_cents, balance["credit_sales"], "Credit client")
    _require_same_total(transfer_line_cents, balance["transfer_payments"], "Transfer")
    payload: dict[str, Any] = {
        "sales_cents": _exact_cents(Decimal(balance["total_sales_with_tax"])),
        "card_cents": _exact_cents(Decimal(balance["card_payments"])),
        "transfer_cents": transfer_cents,
        "deposit_cents": _exact_cents(Decimal(balance["cash_deposits"])),
        "supplier_payments_cents": supplier_cents,
        "supplier_payments": supplier_rows,
        "fixed_expenses_cents": fixed_cents,
        "fixed_expenses": fixed_rows,
        "cash_withdrawals_cents": withdrawal_cents,
        "cash_withdrawals_count": len(withdrawals),
        "credit_clients_cents": credit_cents,
        "credit_clients_count": len(credits),
    }
    if physical_count_status is not None:
        payload["physical_count_status"] = physical_count_status
        payload["surplus_shortage_cents"] = surplus_shortage_cents
    if include_personal:
        payload["cash_withdrawals"] = personal_withdrawals
        payload["credit_clients"] = personal_credits
        payload["transfers"] = personal_transfers
    return payload


def _identity_line(
    kind: str, ticket: str, snapshot: Any, owner_name: str | None, amount_cents: int
) -> dict[str, Any]:
    data = snapshot if isinstance(snapshot, dict) else {}
    name = data.get("name") or owner_name or ""
    phone = data.get("phone") or ""
    return {
        "kind": kind,
        "ticket": ticket,
        "name": str(name),
        "phone": str(phone),
        "amount_cents": amount_cents,
    }


def _day_refunds(
    session: Session,
    organization_id: str,
    branch_id: str,
    start: datetime,
    end: datetime,
    *,
    include_personal: bool,
) -> dict[str, Any]:
    corrections = models.order_corrections
    adjustments = models.order_payment_adjustments
    orders = models.orders
    events = models.order_events
    refund_rows = [
        dict(row)
        for row in session.execute(
            sa.select(
                orders.c.id.label("order_id"),
                orders.c.folio.label("ticket"),
                orders.c.owner_name,
                orders.c.customer_snapshot,
                orders.c.currency.label("order_currency"),
                adjustments.c.amount_cents,
                adjustments.c.currency,
            )
            .select_from(
                adjustments.join(corrections, corrections.c.id == adjustments.c.correction_id).join(
                    orders, orders.c.id == corrections.c.order_id
                )
            )
            .where(
                corrections.c.organization_id == organization_id,
                corrections.c.branch_id == branch_id,
                corrections.c.applied_at >= start,
                corrections.c.applied_at < end,
                adjustments.c.adjustment_type == "REFUND",
                adjustments.c.status == "CONFIRMED",
                orders.c.organization_id == organization_id,
                orders.c.branch_id == branch_id,
            )
            .order_by(corrections.c.applied_at, corrections.c.id)
        ).mappings()
    ]
    cancel_rows = [
        dict(row)
        for row in session.execute(
            sa.select(
                orders.c.id.label("order_id"),
                orders.c.folio.label("ticket"),
                orders.c.owner_name,
                orders.c.customer_snapshot,
                orders.c.total_cents,
                orders.c.currency,
            )
            .select_from(events.join(orders, orders.c.id == events.c.order_id))
            .where(
                orders.c.organization_id == organization_id,
                orders.c.branch_id == branch_id,
                orders.c.status == "CANCELLED",
                events.c.event_type == "ORDER_CANCELLED",
                events.c.created_at >= start,
                events.c.created_at < end,
            )
            .order_by(events.c.created_at, events.c.id)
        ).mappings()
    ]
    currencies: set[str] = set()
    refund_cents = 0
    refund_lines: list[dict[str, Any]] = []
    for row in refund_rows:
        if row["currency"] != row["order_currency"] or row["amount_cents"] is None:
            _fail(503, "dependency_unavailable", "Refund currency is inconsistent")
        currencies.add(str(row["currency"]))
        amount = int(row["amount_cents"])
        refund_cents += amount
        if include_personal:
            refund_lines.append(
                _identity_line(
                    "correction_refund",
                    str(row["ticket"]),
                    row["customer_snapshot"],
                    row["owner_name"],
                    amount,
                )
            )
    cancelled: dict[str, dict[str, Any]] = {}
    for row in cancel_rows:
        previous = cancelled.get(str(row["order_id"]))
        if previous is not None and previous["total_cents"] != row["total_cents"]:
            _fail(503, "dependency_unavailable", "Cancelled order amount is inconsistent")
        cancelled.setdefault(str(row["order_id"]), row)
    cancel_cents = 0
    for row in cancelled.values():
        if row["total_cents"] is None:
            _fail(503, "dependency_unavailable", "Cancelled order amount is incomplete")
        currencies.add(str(row["currency"]))
        amount = int(row["total_cents"])
        cancel_cents += amount
        if include_personal:
            refund_lines.append(
                _identity_line(
                    "cancellation",
                    str(row["ticket"]),
                    row["customer_snapshot"],
                    row["owner_name"],
                    amount,
                )
            )
    if len(currencies) > 1:
        _fail(503, "dependency_unavailable", "Refund currencies cannot be combined")
    payload: dict[str, Any] = {
        "currency": next(iter(currencies), None),
        "correction_refunds_cents": refund_cents,
        "correction_refund_count": len(refund_rows),
        "cancelled_orders_cents": cancel_cents,
        "cancelled_order_count": len(cancelled),
    }
    if include_personal:
        payload["lines"] = refund_lines
    return payload


def _bound(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _reconciliation_day(
    session: Session,
    principal: AgentPrincipal,
    report: dict[str, Any],
    *,
    include_personal: bool,
) -> dict[str, Any]:
    population = report["population"]
    activity = report["activity"]
    if (
        activity["from_utc"] != population["from_utc"]
        or activity["to_utc"] != population["to_utc"]
        or activity["timezone"] != population["timezone"]
    ):
        _fail(503, "dependency_unavailable", "Daily reconciliation populations disagree")
    status = report["physical_count"]["status"]
    if status not in {"COUNTED", "PENDING", "EMPTY"}:
        _fail(503, "dependency_unavailable", "Daily reconciliation count is unavailable")
    difference = report["balance"]["difference"]
    if status == "COUNTED":
        if difference is None:
            _fail(503, "dependency_unavailable", "Counted reconciliation has no difference")
        surplus: int | None = _exact_cents(Decimal(difference))
    elif difference is not None:
        _fail(503, "dependency_unavailable", "Open reconciliation reported a cash difference")
    else:
        surplus = None
    start = _bound(str(population["from_utc"]))
    end = _bound(str(population["to_utc"]))
    return {
        "date": report["date"],
        "timezone": population["timezone"],
        "from_utc": start,
        "to_utc": end,
        "shifts_opened": _cash_population(
            report["balance"],
            report["suppliers_breakdown"],
            report["fixed_expenses_breakdown"],
            report["withdrawals_breakdown"],
            report["credit_clients_breakdown"],
            report["transfers_breakdown"],
            include_personal=include_personal,
            physical_count_status=status,
            surplus_shortage_cents=surplus,
        ),
        "calendar_activity": _cash_population(
            activity["totals"],
            activity["suppliers_breakdown"],
            activity["fixed_expenses_breakdown"],
            activity["withdrawals_breakdown"],
            activity["credit_clients_breakdown"],
            activity["transfers_breakdown"],
            include_personal=include_personal,
            physical_count_status=None,
            surplus_shortage_cents=None,
        ),
        "refunds": _day_refunds(
            session,
            principal.organization_id,
            str(report["branch_id"]),
            start,
            end,
            include_personal=include_personal,
        ),
        "production_bakery": {
            "recorded": False,
            "amount_cents": None,
            "reason": "not_recorded",
        },
    }


@router.get("/agent-tools/cash/daily-reconciliation")
def get_agent_cash_daily_reconciliation(
    branch_id: str,
    from_date: str,
    to_date: str,
    session: SessionDep,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    """Minimized daily reconciliation v2. Names and phones require a second opt-in flag."""
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.cash_reconciliation.read")
    _administrator(principal)
    authorized_branch = _branch(session, principal, branch_id)
    include_personal = (
        "agent.cash_personal_data.read" in principal.capabilities
        and "agent.cash_personal_data.read" in BASELINE_CAPABILITIES[principal.profile]
    )
    _require_financial_audience(session, authorized_branch, RECONCILIATION_DATASETS)
    start_day = _calendar_date(from_date, "from_date")
    end_day = _calendar_date(to_date, "to_date")
    if start_day > end_day or (end_day - start_day).days >= 31:
        _fail(
            400,
            "agent_schema_invalid",
            "Reconciliation period must cover one to 31 local days",
        )
    days: list[dict[str, Any]] = []
    timezone_name: str | None = None
    current = start_day
    while current <= end_day:
        try:
            report = get_branch_daily_reconciliation(
                session, authorized_branch, current.isoformat(), None
            )
        except AuthorizationError:
            _fail(403, "financial_access_denied", "An authorized human audience is required")
        except BusinessError as exc:
            if exc.code in {"report_period_invalid", "report_timezone_invalid", "branch_not_found"}:
                _fail(
                    400,
                    "agent_schema_invalid",
                    "Reconciliation date or branch timezone is invalid",
                )
            _fail(503, "dependency_unavailable", "Daily reconciliation is unavailable")
        day = _reconciliation_day(
            session, principal, report, include_personal=include_personal
        )
        if timezone_name is None:
            timezone_name = str(day["timezone"])
        elif timezone_name != day["timezone"]:
            _fail(503, "dependency_unavailable", "Branch timezone changed during the period")
        days.append(day)
        current += timedelta(days=1)
    return {
        "branch_id": authorized_branch,
        "timezone": timezone_name,
        "from_date": start_day.isoformat(),
        "to_date": end_day.isoformat(),
        "contract_version": 2,
        "personal_data_included": include_personal,
        "days": days,
    }


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


class AgentStockSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_id: str
    unit_id: str = Field(description="Base unit shared by stock and both thresholds.")
    available_quantity: str
    min_quantity: str | None = Field(
        default=None, description="Exact configured minimum in unit_id, or null if unconfigured."
    )
    max_quantity: str | None = Field(
        default=None, description="Exact configured maximum in unit_id, or null if unconfigured."
    )
    as_of: datetime = Field(description="Stock timestamp; not the threshold update timestamp.")


class AgentStockPageMeta(BaseModel):
    model_config = ConfigDict(extra="forbid")

    next_cursor: str | None = None
    has_more: bool


class AgentStockPage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AgentStockSummary]
    page: AgentStockPageMeta


@router.get("/agent-tools/inventory/stock", response_model=AgentStockPage)
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
    thresholds = models.inventory_stock_thresholds.alias("agent_stock_thresholds")
    warehouse_id = session.scalar(
        sa.select(models.warehouses.c.id).where(
            models.warehouses.c.organization_id == principal.organization_id,
            models.warehouses.c.branch_id == authorized_branch,
            models.warehouses.c.status == "active",
        )
    )
    if warehouse_id is None:
        _fail(503, "dependency_unavailable", "Active branch warehouse is unavailable")
    query = (
        sa.select(
            models.inventory_items.c.id,
            models.inventory_items.c.id.label("item_id"),
            models.inventory_items.c.base_unit_id.label("unit_id"),
            sa.func.coalesce(state.c.quantity_on_hand, 0).label("available_quantity"),
            thresholds.c.minimum_quantity.label("min_quantity"),
            thresholds.c.maximum_quantity.label("max_quantity"),
            sa.func.coalesce(state.c.updated_at, _now()).label("as_of"),
        )
        .select_from(
            models.inventory_items.outerjoin(
                state,
                sa.and_(
                    state.c.item_id == models.inventory_items.c.id,
                    state.c.branch_id == authorized_branch,
                    state.c.warehouse_id == warehouse_id,
                ),
            ).outerjoin(
                thresholds,
                sa.and_(
                    thresholds.c.organization_id == principal.organization_id,
                    thresholds.c.branch_id == authorized_branch,
                    thresholds.c.warehouse_id == warehouse_id,
                    thresholds.c.item_id == models.inventory_items.c.id,
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
        for field in ("min_quantity", "max_quantity"):
            row[field] = str(row[field]) if row[field] is not None else None
    page = _page(rows, limit)
    for item in page["items"]:
        item.pop("id", None)
    return page


@router.get("/agent-tools/inventory/movements")
def list_agent_inventory_movements(
    branch_id: str,
    from_utc: datetime,
    to_utc: datetime,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.inventory.read")
    if principal.profile != "inventory":
        _fail(403, "agent_capability_denied", "Inventory movements require the inventory profile")
    authorized_branch = _branch(session, principal, branch_id)
    if from_utc.tzinfo is None or to_utc.tzinfo is None:
        _fail(400, "agent_schema_invalid", "from_utc and to_utc must include a timezone")
    start = from_utc.astimezone(timezone.utc)
    end = to_utc.astimezone(timezone.utc)
    if start >= end or end - start > timedelta(days=31):
        _fail(
            400,
            "agent_schema_invalid",
            "Inventory movement period must be positive and at most 31 days",
        )
    page_limit = _limit(limit)
    after = _inventory_movement_cursor(
        cursor,
        branch_id=authorized_branch,
        start=start,
        end=end,
    )
    movements = models.inventory_movements
    query = sa.select(
        movements.c.id,
        movements.c.item_id,
        movements.c.warehouse_id,
        movements.c.movement_type,
        movements.c.quantity_delta,
        movements.c.unit_id,
        movements.c.effective_at,
        movements.c.status,
    ).where(
        movements.c.organization_id == principal.organization_id,
        movements.c.branch_id == authorized_branch,
        movements.c.effective_at >= start,
        movements.c.effective_at < end,
    )
    if after:
        after_effective_at, after_id = after
        query = query.where(
            sa.or_(
                movements.c.effective_at < after_effective_at,
                sa.and_(
                    movements.c.effective_at == after_effective_at,
                    movements.c.id < after_id,
                ),
            )
        )
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(movements.c.effective_at.desc(), movements.c.id.desc()).limit(
                page_limit + 1
            )
        ).mappings()
    ]
    return _inventory_movement_page(
        rows,
        page_limit,
        branch_id=authorized_branch,
        start=start,
        end=end,
    )


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


@router.get("/agent-tools/purchase-presentations")
def list_agent_purchase_presentations(
    branch_id: str,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 50,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.purchases.read")
    if principal.profile != "purchasing":
        _fail(
            403,
            "agent_capability_denied",
            "Purchase costs require the purchasing profile",
        )
    authorized_branch = _branch(session, principal, branch_id)
    after = _cursor(cursor)
    disabled = sa.exists(
        sa.select(models.supplier_branch_terms.c.supplier_id).where(
            models.supplier_branch_terms.c.supplier_id
            == models.purchase_presentations.c.supplier_id,
            models.supplier_branch_terms.c.branch_id == authorized_branch,
            models.supplier_branch_terms.c.is_enabled.is_(False),
        )
    )
    query = (
        sa.select(
            models.purchase_presentations.c.id,
            models.purchase_presentations.c.supplier_id,
            models.suppliers.c.commercial_name.label("supplier_name"),
            models.purchase_presentations.c.item_id,
            models.inventory_items.c.name.label("item_name"),
            models.purchase_presentations.c.code,
            models.purchase_presentations.c.name,
            models.purchase_presentations.c.commercial_quantity,
            models.purchase_presentations.c.commercial_unit_id,
            models.purchase_presentations.c.base_unit_id,
            models.purchase_presentations.c.base_unit_yield,
            models.purchase_presentations.c.usable_content,
            models.purchase_presentations.c.yield_percent,
            models.purchase_presentations.c.tax_rate,
            models.purchase_presentations.c.last_net_price,
            models.purchase_presentations.c.cost_per_base_unit,
            sa.func.upper(models.suppliers.c.currency).label("currency"),
            models.purchase_presentations.c.is_preferred.label("preferred"),
            models.purchase_presentations.c.updated_at,
        )
        .join(
            models.suppliers,
            models.suppliers.c.id == models.purchase_presentations.c.supplier_id,
        )
        .join(
            models.inventory_items,
            models.inventory_items.c.id == models.purchase_presentations.c.item_id,
        )
        .where(
            models.purchase_presentations.c.organization_id == principal.organization_id,
            models.purchase_presentations.c.status == "active",
            models.suppliers.c.organization_id == principal.organization_id,
            models.suppliers.c.status == "active",
            models.inventory_items.c.organization_id == principal.organization_id,
            models.inventory_items.c.status == "active",
            ~disabled,
            _catalog_scope(models.inventory_items, authorized_branch),
        )
    )
    if after:
        query = query.where(models.purchase_presentations.c.id > after)
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(models.purchase_presentations.c.id).limit(_limit(limit) + 1)
        ).mappings()
    ]
    for row in rows:
        row["version"] = _resource_version(row.pop("updated_at"))
    return _page(rows, limit)


@router.get("/agent-tools/purchases/history")
def list_agent_purchase_history(
    branch_id: str,
    from_utc: datetime,
    to_utc: datetime,
    session: SessionDep,
    cursor: str | None = None,
    limit: int = 25,
    authorization: AuthorizationDep = None,
    actor_header: ActorHeaderDep = None,
) -> dict[str, Any]:
    principal = _agent(session, authorization, actor_header)
    _capability(principal, "agent.purchases.read")
    if principal.profile != "purchasing":
        _fail(
            403,
            "agent_capability_denied",
            "Purchase history requires the purchasing profile",
        )
    authorized_branch = _branch(session, principal, branch_id)
    if from_utc.tzinfo is None or to_utc.tzinfo is None:
        _fail(400, "agent_schema_invalid", "from_utc and to_utc must include a timezone")
    start = from_utc.astimezone(timezone.utc)
    end = to_utc.astimezone(timezone.utc)
    if start >= end or end - start > timedelta(days=31):
        _fail(
            400,
            "agent_schema_invalid",
            "Purchase history period must be positive and at most 31 days",
        )
    if not 1 <= limit <= 25:
        _fail(400, "agent_schema_invalid", "limit must be between 1 and 25")
    after = _purchase_history_cursor(
        cursor,
        branch_id=authorized_branch,
        start=start,
        end=end,
    )
    documents = models.purchase_documents
    query = (
        sa.select(
            documents.c.id,
            documents.c.supplier_id,
            models.suppliers.c.commercial_name.label("supplier_name"),
            sa.literal("current_supplier").label("supplier_name_source"),
            sa.func.upper(models.suppliers.c.currency).label("currency"),
            sa.literal("current_supplier").label("currency_source"),
            documents.c.document_type,
            documents.c.document_date,
            documents.c.confirmed_at,
            documents.c.cancelled_at,
            documents.c.status,
            documents.c.subtotal,
            documents.c.discount_total,
            documents.c.tax_total,
            documents.c.freight_total,
            documents.c.total,
        )
        .join(models.suppliers, models.suppliers.c.id == documents.c.supplier_id)
        .where(
            documents.c.organization_id == principal.organization_id,
            documents.c.branch_id == authorized_branch,
            documents.c.confirmed_at >= start,
            documents.c.confirmed_at < end,
            documents.c.status.in_(("confirmed", "cancelled")),
            models.suppliers.c.organization_id == principal.organization_id,
        )
    )
    if after:
        after_confirmed_at, after_id = after
        query = query.where(
            sa.or_(
                documents.c.confirmed_at < after_confirmed_at,
                sa.and_(
                    documents.c.confirmed_at == after_confirmed_at,
                    documents.c.id < after_id,
                ),
            )
        )
    rows = [
        dict(row)
        for row in session.execute(
            query.order_by(documents.c.confirmed_at.desc(), documents.c.id.desc()).limit(
                limit + 1
            )
        ).mappings()
    ]
    visible_ids = [row["id"] for row in rows[:limit]]
    lines_by_document: dict[str, list[dict[str, Any]]] = {
        document_id: [] for document_id in visible_ids
    }
    if visible_ids:
        line_rows = session.execute(
            sa.select(
                models.purchase_document_lines.c.purchase_document_id,
                models.purchase_document_lines.c.item_id,
                models.inventory_items.c.name.label("item_name"),
                sa.literal("current_catalog").label("item_name_source"),
                models.purchase_document_lines.c.presentation_id,
                models.purchase_presentations.c.name.label("presentation_name"),
                models.purchase_document_lines.c.presentation_snapshot,
                models.purchase_document_lines.c.presentation_quantity,
                models.purchase_document_lines.c.base_quantity,
                models.purchase_document_lines.c.unit_price,
                models.purchase_document_lines.c.discount,
                models.purchase_document_lines.c.tax,
                models.purchase_document_lines.c.line_total,
                models.purchase_document_lines.c.inventory_cost,
                models.purchase_document_lines.c.cost_per_base_unit,
            )
            .join(
                models.inventory_items,
                models.inventory_items.c.id == models.purchase_document_lines.c.item_id,
            )
            .join(
                models.purchase_presentations,
                models.purchase_presentations.c.id
                == models.purchase_document_lines.c.presentation_id,
            )
            .where(
                models.purchase_document_lines.c.purchase_document_id.in_(visible_ids),
                models.inventory_items.c.organization_id == principal.organization_id,
                models.purchase_presentations.c.organization_id == principal.organization_id,
            )
            .order_by(
                models.purchase_document_lines.c.purchase_document_id,
                models.purchase_document_lines.c.id,
            )
        ).mappings()
        for line_row in line_rows:
            line = dict(line_row)
            document_id = str(line.pop("purchase_document_id"))
            snapshot = line.pop("presentation_snapshot")
            snapshot_name = snapshot.get("name") if isinstance(snapshot, dict) else None
            if isinstance(snapshot_name, str) and snapshot_name.strip():
                line["presentation_name"] = snapshot_name
                line["presentation_name_source"] = "purchase_snapshot"
            else:
                line["presentation_name_source"] = "current_catalog"
            lines_by_document[document_id].append(line)
    for row in rows:
        row["lines"] = lines_by_document.get(str(row["id"]), [])
    return _purchase_history_page(
        rows,
        limit,
        branch_id=authorized_branch,
        start=start,
        end=end,
    )


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
    known_items: set[str] = set(
        session.scalars(
            sa.select(models.inventory_items.c.id).where(
                models.inventory_items.c.organization_id == principal.organization_id,
                models.inventory_items.c.id.in_(item_ids),
                _catalog_scope(models.inventory_items, branch_id),
            )
        ).all()
    )
    known_units: set[str] = set(
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
