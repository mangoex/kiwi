"""MCP-001 read-only transport over the governed Agent Tools boundary."""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, cast

import httpx
import jwt
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from mcp.server import MCPServer
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from mcp.server.context import CallNext, HandlerResult, ServerRequestContext
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations
from pydantic import AnyHttpUrl
from sqlalchemy.orm import Session

from restaurant_os import agent_tools
from restaurant_os.auth import create_session_token
from restaurant_os.config import Settings
from restaurant_os.database import get_session_factory


@dataclass(frozen=True)
class ReadToolSpec:
    name: str
    operation_id: str
    method: Literal["get"]
    path: str
    capability: str | None
    profiles: frozenset[str]
    read_only: bool = True


_ALL_PROFILES = frozenset(agent_tools.PROFILES)

READ_TOOL_SPECS: tuple[ReadToolSpec, ...] = (
    ReadToolSpec(
        "context",
        "getAgentContext",
        "get",
        "/api/v1/agent-tools/context",
        "agent.context.read",
        _ALL_PROFILES,
    ),
    ReadToolSpec(
        "catalog_items",
        "listAgentCatalogItems",
        "get",
        "/api/v1/agent-tools/catalog/items",
        "agent.catalog.read",
        frozenset({"administrator", "kitchen"}),
    ),
    ReadToolSpec(
        "sales_summary",
        "getAgentSalesSummary",
        "get",
        "/api/v1/agent-tools/sales/summary",
        "agent.sales.read",
        frozenset({"administrator"}),
    ),
    ReadToolSpec(
        "expenses_summary",
        "getAgentExpenseSummary",
        "get",
        "/api/v1/agent-tools/expenses/summary",
        "agent.operating_expenses.read",
        frozenset({"administrator"}),
    ),
    ReadToolSpec(
        "payments_by_method",
        "getAgentPaymentsByMethod",
        "get",
        "/api/v1/agent-tools/payments/by-method",
        "agent.payment_methods.read",
        frozenset({"administrator"}),
    ),
    ReadToolSpec(
        "cash_cuts",
        "listAgentCashCuts",
        "get",
        "/api/v1/agent-tools/cash/cuts",
        "agent.cash_cuts.read",
        frozenset({"administrator"}),
    ),
    ReadToolSpec(
        "cash_daily_reconciliation",
        "getAgentCashDailyReconciliation",
        "get",
        "/api/v1/agent-tools/cash/daily-reconciliation",
        "agent.cash_reconciliation.read",
        frozenset({"administrator"}),
    ),
    ReadToolSpec(
        "inventory_items",
        "listAgentInventoryItems",
        "get",
        "/api/v1/agent-tools/inventory/items",
        "agent.inventory.read",
        frozenset({"kitchen", "inventory", "purchasing"}),
    ),
    ReadToolSpec(
        "inventory_stock",
        "listAgentInventoryStock",
        "get",
        "/api/v1/agent-tools/inventory/stock",
        "agent.inventory.read",
        frozenset({"kitchen", "inventory", "purchasing"}),
    ),
    ReadToolSpec(
        "inventory_movements",
        "listAgentInventoryMovements",
        "get",
        "/api/v1/agent-tools/inventory/movements",
        "agent.inventory.read",
        frozenset({"inventory"}),
    ),
    ReadToolSpec(
        "recipes",
        "listAgentRecipes",
        "get",
        "/api/v1/agent-tools/recipes",
        "agent.recipes.read",
        frozenset({"kitchen", "inventory"}),
    ),
    ReadToolSpec(
        "suppliers",
        "listAgentSuppliers",
        "get",
        "/api/v1/agent-tools/suppliers",
        "agent.suppliers.read",
        frozenset({"purchasing"}),
    ),
    ReadToolSpec(
        "purchase_presentations",
        "listAgentPurchasePresentations",
        "get",
        "/api/v1/agent-tools/purchase-presentations",
        "agent.purchases.read",
        frozenset({"purchasing"}),
    ),
    ReadToolSpec(
        "purchase_history",
        "listAgentPurchaseHistory",
        "get",
        "/api/v1/agent-tools/purchases/history",
        "agent.purchases.read",
        frozenset({"purchasing"}),
    ),
    ReadToolSpec(
        "purchase_needs",
        "listAgentPurchaseNeeds",
        "get",
        "/api/v1/agent-tools/purchase-needs",
        "agent.purchase_needs.read",
        frozenset({"purchasing"}),
    ),
    ReadToolSpec(
        "operation_status",
        "getAgentOperation",
        "get",
        "/api/v1/agent-tools/operations/{operation_id}",
        None,
        _ALL_PROFILES,
    ),
)

_READ_ONLY_ANNOTATIONS = ToolAnnotations(
    read_only_hint=True,
    destructive_hint=False,
    idempotent_hint=True,
    open_world_hint=False,
)


JwksLoader = Callable[[], Awaitable[dict[str, Any]]]
_ALLOWED_JWT_ALGORITHMS = frozenset({"RS256", "ES256"})
_MAX_JWKS_BYTES = 262_144


class KiwiOAuthTokenVerifier(TokenVerifier):
    """Validate access-token JWTs issued by the configured external authority."""

    def __init__(self, settings: Settings, jwks_loader: JwksLoader | None = None) -> None:
        self._settings = settings
        self._jwks_loader = jwks_loader or self._fetch_jwks
        self._jwks_cache: dict[str, Any] | None = None
        self._jwks_cache_until = 0.0
        self._jwks_lock = asyncio.Lock()

    async def _fetch_jwks(self) -> dict[str, Any]:
        if self._settings.mcp_jwks_url is None:
            raise ValueError("MCP JWKS URL is required")
        timeout = httpx.Timeout(self._settings.mcp_jwks_timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream(
                "GET",
                str(self._settings.mcp_jwks_url),
                headers={"Accept": "application/json"},
                follow_redirects=False,
            ) as response:
                if response.is_redirect:
                    raise ValueError("MCP JWKS redirects are not allowed")
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_JWKS_BYTES:
                        raise ValueError("MCP JWKS response is too large")
        payload = json.loads(body)
        if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
            raise ValueError("MCP JWKS response is invalid")
        return payload

    async def _load_jwks(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._jwks_cache is not None and now < self._jwks_cache_until:
            return self._jwks_cache
        async with self._jwks_lock:
            now = time.monotonic()
            if self._jwks_cache is not None and now < self._jwks_cache_until:
                return self._jwks_cache
            jwks = await self._jwks_loader()
            self._jwks_cache = jwks
            self._jwks_cache_until = now + self._settings.mcp_jwks_cache_ttl_seconds
            return jwks

    async def verify_token(self, token: str) -> AccessToken | None:
        if self._settings.mcp_issuer_url is None or self._settings.mcp_resource_server_url is None:
            return None
        issuer = str(self._settings.mcp_issuer_url).rstrip("/")
        resource = str(self._settings.mcp_resource_server_url)
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            key_id = header.get("kid")
            if algorithm not in _ALLOWED_JWT_ALGORITHMS or not isinstance(key_id, str):
                return None
            key_set = jwt.PyJWKSet.from_dict(await self._load_jwks())
            matching_keys = [key for key in key_set.keys if key.key_id == key_id]
            if len(matching_keys) != 1:
                return None
            signing_key = matching_keys[0]
            if signing_key.algorithm_name != algorithm:
                return None
            payload = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                audience=resource,
                issuer=issuer,
                leeway=5,
                options={"require": ["aud", "exp", "iat", "iss", "sub"]},
            )
            subject = payload["sub"]
            client_id = payload["client_id"]
            expires_at = int(payload["exp"])
        except (httpx.HTTPError, jwt.PyJWTError, KeyError, TypeError, ValueError):
            return None
        if (
            not isinstance(subject, str)
            or not subject
            or not isinstance(client_id, str)
            or not client_id
        ):
            return None
        scopes = _scopes(payload.get("scope"))
        if self._settings.mcp_required_scope not in scopes:
            return None
        return AccessToken(
            token=token,
            client_id=client_id,
            subject=subject,
            scopes=scopes,
            expires_at=expires_at,
            resource=resource,
            claims=payload,
        )


def _scopes(value: object) -> list[str]:
    if isinstance(value, str):
        return sorted({part for part in value.split() if part})
    if isinstance(value, list) and all(isinstance(part, str) for part in value):
        return sorted({part for part in value if part})
    return []


def _external_principal(session: Session) -> agent_tools.AgentPrincipal:
    access_token = get_access_token()
    if access_token is None or not access_token.subject or not access_token.client_id:
        raise ToolError("agent_unauthorized")
    issuer = (access_token.claims or {}).get("iss")
    if not isinstance(issuer, str) or not issuer:
        raise ToolError("agent_unauthorized")
    try:
        return agent_tools._agent_for_external_oauth(
            session,
            issuer=issuer,
            subject=access_token.subject,
            client_id=access_token.client_id,
        )
    except HTTPException as exc:
        raise _safe_tool_error(exc) from exc


def _internal_authorization(settings: Settings, session: Session) -> str:
    principal = _external_principal(session)
    token = create_session_token(
        {
            "typ": "agent",
            "aud": "kiwi-agent-tools-v1",
            "sub": principal.identity_id,
            "org": principal.organization_id,
            "integration": principal.integration_id,
            "profile": principal.profile,
            "authorization_version": principal.authorization_version,
        },
        settings.secret_key,
        ttl_seconds=60,
    )
    return f"Bearer {token}"


def _safe_tool_error(exc: HTTPException) -> ToolError:
    detail = exc.detail if isinstance(exc.detail, dict) else {"code": "agent_request_failed"}
    safe = {
        "code": str(detail.get("code", "agent_request_failed")),
        "message": str(detail.get("message", "Agent request failed")),
        "correlation_id": detail.get("correlation_id"),
    }
    return ToolError(json.dumps(safe, sort_keys=True, separators=(",", ":")))


def _run_read(settings: Settings, handler: Any, /, **arguments: Any) -> dict[str, Any]:
    session_factory = get_session_factory()
    with session_factory() as session:
        try:
            result = handler(
                session=session,
                authorization=_internal_authorization(settings, session),
                actor_header=None,
                **arguments,
            )
        except HTTPException as exc:
            raise _safe_tool_error(exc) from exc
    encoded = jsonable_encoder(result)
    if not isinstance(encoded, dict):
        raise ToolError("agent_response_invalid")
    return encoded


def _is_authorized(spec: ReadToolSpec, principal: agent_tools.AgentPrincipal) -> bool:
    if principal.profile not in spec.profiles:
        return False
    if spec.capability is None:
        return True
    return (
        spec.capability in principal.capabilities
        and spec.capability in agent_tools.BASELINE_CAPABILITIES[principal.profile]
    )


class AuthorizedToolCatalog:
    """Filter tools/list with the same persisted Agent Tools authority used by calls."""

    async def __call__(
        self,
        ctx: ServerRequestContext[Any, Any],
        call_next: CallNext,
    ) -> HandlerResult:
        result = await call_next(ctx)
        tools = result.get("tools") if isinstance(result, dict) else getattr(result, "tools", None)
        if ctx.method != "tools/list" or not isinstance(tools, list):
            return result
        session_factory = get_session_factory()
        with session_factory() as session:
            try:
                principal = _external_principal(session)
            except ToolError:
                allowed: set[str] = set()
            else:
                allowed = {
                    spec.name for spec in READ_TOOL_SPECS if _is_authorized(spec, principal)
                }
        filtered = [
            tool
            for tool in tools
            if (
                tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", None)
            )
            in allowed
        ]
        if isinstance(result, dict):
            return {
                **result,
                "tools": filtered,
                "ttlMs": 0,
                "cacheScope": "private",
            }
        if result is None:
            return None
        return result.model_copy(
            update={
                "tools": filtered,
                "ttl_ms": 0,
                "cache_scope": "private",
            }
        )


def create_mcp_server(
    settings: Settings,
    token_verifier: TokenVerifier | None = None,
) -> MCPServer[None]:
    if settings.mcp_issuer_url is None or settings.mcp_resource_server_url is None:
        raise ValueError("MCP issuer and resource URL are required")
    server: MCPServer[None] = MCPServer(
        "RestaurantOS",
        version=settings.app_version,
        description="Governed read-only RestaurantOS Agent Tools",
        token_verifier=token_verifier or KiwiOAuthTokenVerifier(settings),
        auth=AuthSettings(
            # AuthSettings preserves an empty path only when it receives the
            # canonical string. Passing Pydantic's AnyHttpUrl would reintroduce
            # a trailing slash and publish a different OAuth issuer.
            issuer_url=cast(AnyHttpUrl, str(settings.mcp_issuer_url).rstrip("/")),
            resource_server_url=settings.mcp_resource_server_url,
            required_scopes=[settings.mcp_required_scope],
            validate_token_resource=True,
        ),
        middleware=[AuthorizedToolCatalog()],
    )

    @server.tool(
        name="context",
        description="Return the caller's effective Agent Tools context.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def context() -> dict[str, Any]:
        return _run_read(settings, agent_tools.agent_context)

    @server.tool(
        name="catalog_items",
        description="List minimized catalog items within the authorized scope.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def catalog_items(
        branch_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_catalog,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="sales_summary",
        description="Read the minimized confirmed-sales summary for an authorized branch.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def sales_summary(
        branch_id: str,
        from_utc: datetime,
        to_utc: datetime,
        top_limit: int = 10,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.get_agent_sales_summary,
            branch_id=branch_id,
            from_utc=from_utc,
            to_utc=to_utc,
            top_limit=top_limit,
        )

    @server.tool(
        name="expenses_summary",
        description="Read confirmed operating-expense totals by concept.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def expenses_summary(
        branch_id: str,
        from_utc: datetime,
        to_utc: datetime,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.get_agent_expense_summary,
            branch_id=branch_id,
            from_utc=from_utc,
            to_utc=to_utc,
        )

    @server.tool(
        name="payments_by_method",
        description="Read confirmed sales grouped by payment method.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def payments_by_method(
        branch_id: str,
        from_utc: datetime,
        to_utc: datetime,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.get_agent_payments_by_method,
            branch_id=branch_id,
            from_utc=from_utc,
            to_utc=to_utc,
        )

    @server.tool(
        name="cash_cuts",
        description="List finalized, minimized cash cuts for an authorized branch.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def cash_cuts(
        branch_id: str,
        from_utc: datetime,
        to_utc: datetime,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_cash_cuts,
            branch_id=branch_id,
            from_utc=from_utc,
            to_utc=to_utc,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="cash_daily_reconciliation",
        description="Read minimized daily cash reconciliation for local branch dates.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def cash_daily_reconciliation(
        branch_id: str,
        from_date: str,
        to_date: str,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.get_agent_cash_daily_reconciliation,
            branch_id=branch_id,
            from_date=from_date,
            to_date=to_date,
        )

    @server.tool(
        name="inventory_items",
        description="List minimized inventory items within the authorized scope.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def inventory_items(
        branch_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_inventory_items,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="inventory_stock",
        description="List stock and configured thresholds for an authorized branch.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def inventory_stock(
        branch_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_stock,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="inventory_movements",
        description="List minimized inventory movements for an authorized branch and UTC window.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def inventory_movements(
        branch_id: str,
        from_utc: datetime,
        to_utc: datetime,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_inventory_movements,
            branch_id=branch_id,
            from_utc=from_utc,
            to_utc=to_utc,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="recipes",
        description="List active recipes and minimized components within the authorized scope.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def recipes(
        branch_id: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_recipes,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="suppliers",
        description="List active suppliers available to an authorized branch.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def suppliers(
        branch_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_suppliers,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="purchase_presentations",
        description="List current purchase presentations and costs for an authorized branch.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purchase_presentations(
        branch_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_purchase_presentations,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="purchase_history",
        description="List confirmed purchase history for an authorized branch and UTC window.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purchase_history(
        branch_id: str,
        from_utc: datetime,
        to_utc: datetime,
        cursor: str | None = None,
        limit: int = 25,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_purchase_history,
            branch_id=branch_id,
            from_utc=from_utc,
            to_utc=to_utc,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="purchase_needs",
        description="List governed purchase needs for an authorized branch.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def purchase_needs(
        branch_id: str,
        cursor: str | None = None,
        limit: int = 50,
    ) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.list_agent_purchase_needs,
            branch_id=branch_id,
            cursor=cursor,
            limit=limit,
        )

    @server.tool(
        name="operation_status",
        description="Recover the caller's own pre-existing Agent Tools operation status.",
        annotations=_READ_ONLY_ANNOTATIONS,
        structured_output=True,
    )
    def operation_status(operation_id: str) -> dict[str, Any]:
        return _run_read(
            settings,
            agent_tools.get_agent_operation,
            operation_id=operation_id,
        )

    return server
