# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-mcp-readonly-contract-v1
from __future__ import annotations

import asyncio
import time
from collections.abc import Generator
from pathlib import Path

import httpx
import httpx2
import jwt
import pytest
import sqlalchemy as sa
import tomllib
import yaml
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import HTTPException
from fastapi.testclient import TestClient
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from pydantic import ValidationError
from restaurant_os import agent_tools, models
from restaurant_os.config import Settings, get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.mcp_server import (
    READ_TOOL_SPECS,
    KiwiOAuthTokenVerifier,
    create_mcp_server,
)
from sqlalchemy.orm import Session, sessionmaker
from test_agent_tools import _client, _configure, _factory

ROOT = Path(__file__).resolve().parents[3]
AGENT_OPENAPI = ROOT / "packages/contracts/openapi/kiwi-agent-tools-v1.openapi.yaml"
API_PYPROJECT = ROOT / "apps/api/pyproject.toml"
API_RUNTIME_LOCK = ROOT / "requirements/api-runtime-linux-py312.lock"


def _oauth_key_material() -> tuple[object, dict[str, object]]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwk = jwt.algorithms.RSAAlgorithm.to_jwk(private_key.public_key(), as_dict=True)
    jwk.update({"kid": "mcp-test-key", "alg": "RS256", "use": "sig"})
    return private_key, {"keys": [jwk]}


def _oauth_token(private_key: object, subject: str, **claims: object) -> str:
    now = int(time.time())
    payload = {
        "iss": "https://auth.example.com",
        "aud": "https://api.example.com/mcp",
        "sub": subject,
        "client_id": "mcp-test-client",
        "scope": "restaurantos:mcp.read",
        "iat": now,
        "exp": now + 300,
        **claims,
    }
    return jwt.encode(
        payload,
        private_key,
        algorithm="RS256",
        headers={"kid": "mcp-test-key"},
    )


def _bind_oauth_subject(
    factory: sessionmaker[Session],
    *,
    agent_client_id: str,
    subject: str,
    oauth_client_id: str = "mcp-test-client",
) -> str:
    with factory() as session:
        identity_id = session.scalar(
            sa.select(models.external_agent_identities.c.id).where(
                models.external_agent_identities.c.client_id == agent_client_id
            )
        )
        assert identity_id is not None
        session.execute(
            models.external_agent_oauth_bindings.insert().values(
                identity_id=identity_id,
                organization_id="018f6f73-2d0a-74f0-8f1c-000000000001",
                issuer="https://auth.example.com",
                subject=subject,
                oauth_client_id=oauth_client_id,
                created_by_user_id="018f6f73-2d0a-74f0-8f1c-000000000006",
                created_at=sa.func.now(),
                updated_at=sa.func.now(),
            )
        )
        session.commit()
    return str(identity_id)


def test_tdd_tc_481_read_manifest_matches_agent_tools_contract() -> None:
    contract = yaml.safe_load(AGENT_OPENAPI.read_text(encoding="utf-8"))
    operations = {
        operation["operationId"]: (method, path)
        for path, path_item in contract["paths"].items()
        for method, operation in path_item.items()
        if method in {"get", "post", "put", "patch", "delete"}
    }

    assert len(READ_TOOL_SPECS) == 16
    assert len({spec.name for spec in READ_TOOL_SPECS}) == len(READ_TOOL_SPECS)
    assert len({spec.operation_id for spec in READ_TOOL_SPECS}) == len(READ_TOOL_SPECS)
    assert all(spec.read_only for spec in READ_TOOL_SPECS)
    assert all(spec.operation_id in operations for spec in READ_TOOL_SPECS)
    assert {
        spec.operation_id: (spec.method, spec.path) for spec in READ_TOOL_SPECS
    } == {spec.operation_id: operations[spec.operation_id] for spec in READ_TOOL_SPECS}
    assert not {"call_api", "execute_sql", "http_request"} & {
        spec.name for spec in READ_TOOL_SPECS
    }


def test_tdd_tc_493_mcp_http_client_is_a_direct_frozen_runtime_dependency() -> None:
    manifest = tomllib.loads(API_PYPROJECT.read_text(encoding="utf-8"))
    runtime_dependencies = manifest["project"]["dependencies"]
    assert any(dependency.lower().startswith("httpx") for dependency in runtime_dependencies)

    locked_dependencies = API_RUNTIME_LOCK.read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("httpx==") for line in locked_dependencies)


def test_tdd_tc_481_mcp_is_default_off_and_absent_from_runtime() -> None:
    settings = get_settings()
    assert settings.mcp_enabled is False
    client = TestClient(create_app())
    assert client.post("/mcp", json={}).status_code == 404
    assert client.get("/.well-known/oauth-protected-resource/mcp").status_code == 404


def test_tdd_tc_483_enabled_mcp_requires_bound_authority_and_agent_tools() -> None:
    common = {
        "environment": "production",
        "secret_key": "s" * 32,
        "redis_url": "redis://redis.example:6379/0",
        "grokbot_agent_rate_limit_hmac_secret": "h" * 32,
        "mcp_enabled": True,
        "grokbot_agent_tools_enabled": True,
    }
    with pytest.raises(ValidationError, match="MCP_ISSUER_URL"):
        Settings(**common)
    with pytest.raises(ValidationError, match="MCP_JWKS_URL"):
        Settings(**common, mcp_issuer_url="https://auth.example.com")
    with pytest.raises(ValidationError, match="MCP_RESOURCE_SERVER_URL"):
        Settings(
            **common,
            mcp_issuer_url="https://auth.example.com",
            mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
        )
    with pytest.raises(ValidationError, match="GROKBOT_AGENT_TOOLS_ENABLED"):
        Settings(
            **{**common, "grokbot_agent_tools_enabled": False},
            mcp_issuer_url="https://auth.example.com",
            mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
            mcp_resource_server_url="https://api.example.com/mcp",
        )
    for unsafe_jwks_url in (
        "https://user:secret@auth.example.com/.well-known/jwks.json",
        "https://127.0.0.1/.well-known/jwks.json",
        "https://169.254.169.254/.well-known/jwks.json",
        "https://[::1]/.well-known/jwks.json",
        "https://[fe80::1]/.well-known/jwks.json",
        "https://[::ffff:127.0.0.1]/.well-known/jwks.json",
    ):
        with pytest.raises(ValidationError, match="MCP JWKS URL"):
            Settings(
                **common,
                mcp_issuer_url="https://auth.example.com",
                mcp_jwks_url=unsafe_jwks_url,
                mcp_resource_server_url="https://api.example.com/mcp",
            )


def test_tdd_tc_481_server_registers_only_the_read_allowlist() -> None:
    settings = Settings(
        mcp_enabled=True,
        grokbot_agent_tools_enabled=True,
        mcp_issuer_url="https://auth.example.com",
        mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
        mcp_resource_server_url="https://api.example.com/mcp",
    )
    server = create_mcp_server(settings)
    tools = asyncio.run(server.list_tools())
    assert [tool.name for tool in tools] == [spec.name for spec in READ_TOOL_SPECS]
    assert all(tool.annotations and tool.annotations.read_only_hint for tool in tools)
    assert all(tool.output_schema for tool in tools)


def test_tdd_tc_483_token_verifier_requires_signature_issuer_resource_and_scope(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        mcp_enabled=True,
        grokbot_agent_tools_enabled=True,
        mcp_issuer_url="https://auth.example.com",
        mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
        mcp_resource_server_url="https://api.example.com/mcp",
    )
    private_key, jwks = _oauth_key_material()

    async def load_jwks() -> dict[str, object]:
        return jwks

    verifier = KiwiOAuthTokenVerifier(settings, load_jwks)
    subject = "018f6f73-2d0a-74f0-8f1c-000000000901"
    valid = _oauth_token(private_key, subject)
    accepted = asyncio.run(verifier.verify_token(valid))
    assert accepted is not None
    assert accepted.client_id == "mcp-test-client"
    assert accepted.subject == subject
    assert accepted.resource == "https://api.example.com/mcp"

    missing_client = _oauth_token(private_key, subject, client_id=None)
    assert asyncio.run(verifier.verify_token(missing_client)) is None
    trailing_slash_issuer = _oauth_token(
        private_key, subject, iss="https://auth.example.com/"
    )
    assert asyncio.run(verifier.verify_token(trailing_slash_issuer)) is None

    for claim, replacement in (
        ("iss", "https://other.example.com/"),
        ("aud", "https://api.example.com/other"),
        ("scope", "restaurantos:mcp.write"),
    ):
        rejected = _oauth_token(private_key, subject, **{claim: replacement})
        assert asyncio.run(verifier.verify_token(rejected)) is None

    other_private_key, _ = _oauth_key_material()
    assert asyncio.run(verifier.verify_token(_oauth_token(other_private_key, subject))) is None
    expired = _oauth_token(
        private_key,
        subject,
        iat=int(time.time()) - 600,
        exp=int(time.time()) - 300,
    )
    assert asyncio.run(verifier.verify_token(expired)) is None

    original_async_client = httpx.AsyncClient

    def install_transport(handler: httpx.MockTransport) -> None:
        monkeypatch.setattr(
            httpx,
            "AsyncClient",
            lambda **kwargs: original_async_client(transport=handler, **kwargs),
        )

    redirect_requests: list[str] = []

    def redirect_handler(request: httpx.Request) -> httpx.Response:
        redirect_requests.append(str(request.url))
        return httpx.Response(
            302,
            headers={"Location": "https://internal.example/jwks"},
            request=request,
        )

    install_transport(httpx.MockTransport(redirect_handler))
    with pytest.raises(ValueError, match="redirects are not allowed"):
        asyncio.run(KiwiOAuthTokenVerifier(settings)._fetch_jwks())
    assert redirect_requests == ["https://auth.example.com/.well-known/jwks.json"]

    def oversized_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"x" * 262_145, request=request)

    install_transport(httpx.MockTransport(oversized_handler))
    with pytest.raises(ValueError, match="too large"):
        asyncio.run(KiwiOAuthTokenVerifier(settings)._fetch_jwks())

    async def unavailable_jwks() -> dict[str, object]:
        raise httpx.ConnectError("synthetic authority outage")

    unavailable = KiwiOAuthTokenVerifier(settings, unavailable_jwks)
    assert asyncio.run(unavailable.verify_token(valid)) is None


def test_tdd_tc_494_external_authority_requires_exact_persisted_tuple() -> None:
    factory = _factory()
    client = _client(factory)
    agent_client_id, _ = _configure(
        client,
        "administrator",
        ["agent.context.read", "agent.catalog.read"],
    )
    subject = "user_01JWORKOSADMIN0494"
    identity_id = _bind_oauth_subject(
        factory,
        agent_client_id=agent_client_id,
        subject=subject,
        oauth_client_id="client_grokbot_mcp",
    )

    with factory() as session:
        principal = agent_tools._agent_for_external_oauth(
            session,
            issuer="https://auth.example.com",
            subject=subject,
            client_id="client_grokbot_mcp",
        )
        assert principal.identity_id == identity_id
        for issuer, external_subject, oauth_client_id in (
            ("https://other.example.com", subject, "client_grokbot_mcp"),
            ("https://auth.example.com", "user_other", "client_grokbot_mcp"),
            ("https://auth.example.com", subject, "client_rakazo_mcp"),
            ("https://auth.example.com", identity_id, "client_grokbot_mcp"),
        ):
            with pytest.raises(HTTPException) as denied:
                agent_tools._agent_for_external_oauth(
                    session,
                    issuer=issuer,
                    subject=external_subject,
                    client_id=oauth_client_id,
                )
            assert denied.value.status_code == 403
            assert denied.value.detail["code"] == "agent_disabled"


def test_tdd_tc_483_http_boundary_challenges_before_tool_execution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = Settings(
        secret_key="s" * 32,
        mcp_enabled=True,
        grokbot_agent_tools_enabled=True,
        mcp_issuer_url="https://auth.example.com",
        mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
        mcp_resource_server_url="https://api.example.com/mcp",
    )
    monkeypatch.setattr("restaurant_os.main.get_settings", lambda: settings)
    with TestClient(create_app()) as client:
        metadata = client.get("/.well-known/oauth-protected-resource/mcp")
        assert metadata.status_code == 200
        assert metadata.json() == {
            "resource": "https://api.example.com/mcp",
            "authorization_servers": ["https://auth.example.com"],
            "scopes_supported": ["restaurantos:mcp.read"],
            "bearer_methods_supported": ["header"],
        }
        denied = client.post(
            "/mcp",
            headers={
                "MCP-Protocol-Version": "2026-07-28",
                "Mcp-Method": "tools/list",
            },
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert denied.status_code == 401
    assert "oauth-protected-resource/mcp" in denied.headers["WWW-Authenticate"]


def test_tdd_tc_482_484_modern_http_exchange_filters_calls_and_reauthorizes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    private_key, jwks = _oauth_key_material()
    settings = Settings(
        secret_key=get_settings().secret_key,
        mcp_enabled=True,
        grokbot_agent_tools_enabled=True,
        mcp_issuer_url="https://auth.example.com",
        mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
        mcp_resource_server_url="https://api.example.com/mcp",
    )

    async def fake_fetch_jwks(_: KiwiOAuthTokenVerifier) -> dict[str, object]:
        return jwks

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    monkeypatch.setattr("restaurant_os.main.get_settings", lambda: settings)
    monkeypatch.setattr("restaurant_os.agent_tools.get_settings", lambda: settings)
    monkeypatch.setattr("restaurant_os.mcp_server.get_session_factory", lambda: factory)
    monkeypatch.setattr(KiwiOAuthTokenVerifier, "_fetch_jwks", fake_fetch_jwks)
    app = create_app()
    app.dependency_overrides[get_session] = override_session
    meta = {
        "io.modelcontextprotocol/protocolVersion": "2026-07-28",
        "io.modelcontextprotocol/clientCapabilities": {},
    }

    with TestClient(app, base_url="https://api.example.com") as client:
        client_id, _ = _configure(
            client,
            "administrator",
            ["agent.context.read", "agent.catalog.read", "agent.sales.read"],
        )
        subject = "user_01JWORKOSADMIN0001"
        identity_id = _bind_oauth_subject(factory, agent_client_id=client_id, subject=subject)
        bearer = _oauth_token(private_key, subject, org_id="external-untrusted-org")
        limited: list[tuple[str, str]] = []

        class CaptureLimiter:
            def allow(self, namespace: str, client_signal: str) -> bool:
                limited.append((namespace, client_signal))
                return True

        client.app.state.grokbot_agent_rate_limiter = CaptureLimiter()
        common_headers = {
            "Authorization": f"Bearer {bearer}",
            "MCP-Protocol-Version": "2026-07-28",
        }
        forged_key_one, _ = _oauth_key_material()
        forged_key_two, _ = _oauth_key_material()
        forged_responses = [
            client.post(
                "/mcp",
                headers={
                    "Authorization": f"Bearer {_oauth_token(key, subject)}",
                    "MCP-Protocol-Version": "2026-07-28",
                    "Mcp-Method": "tools/list",
                },
                json={
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "method": "tools/list",
                    "params": {"_meta": meta},
                },
            )
            for request_id, key in enumerate((forged_key_one, forged_key_two), start=90)
        ]
        assert [response.status_code for response in forged_responses] == [401, 401]
        forged_buckets = [
            signal for namespace, signal in limited if namespace == "restaurantos-mcp"
        ]
        assert len(forged_buckets) == 2
        assert forged_buckets[0] != forged_buckets[1]
        assert all(str(subject) not in signal for signal in forged_buckets)

        listed = client.post(
            "/mcp",
            headers={**common_headers, "Mcp-Method": "tools/list"},
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {"_meta": meta},
            },
        )
        assert listed.status_code == 200, listed.text
        listing = listed.json()["result"]
        assert [tool["name"] for tool in listing["tools"]] == [
            "context",
            "catalog_items",
            "sales_summary",
            "operation_status",
        ]
        assert listing["ttlMs"] == 0
        assert listing["cacheScope"] == "private"

        called = client.post(
            "/mcp",
            headers={
                **common_headers,
                "Mcp-Method": "tools/call",
                "Mcp-Name": "context",
            },
            json={
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {"name": "context", "arguments": {}, "_meta": meta},
            },
        )
        assert called.status_code == 200, called.text
        result = called.json()["result"]
        assert result["isError"] is False
        assert result["structuredContent"]["identity_id"] == identity_id

        with factory() as session:
            session.execute(
                sa.update(models.external_agent_identities)
                .where(models.external_agent_identities.c.id == identity_id)
                .values(is_enabled=False)
            )
            session.commit()
        relisted = client.post(
            "/mcp",
            headers={**common_headers, "Mcp-Method": "tools/list"},
            json={
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/list",
                "params": {"_meta": meta},
            },
        )
        assert relisted.status_code == 200, relisted.text
        assert relisted.json()["result"]["tools"] == []

        revoked_call = client.post(
            "/mcp",
            headers={
                **common_headers,
                "Mcp-Method": "tools/call",
                "Mcp-Name": "context",
            },
            json={
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "context", "arguments": {}, "_meta": meta},
            },
        )
        assert revoked_call.status_code == 200, revoked_call.text
        assert revoked_call.json()["result"]["isError"] is True
        assert "agent_disabled" in revoked_call.json()["result"]["content"][0]["text"]
        valid_buckets = [
            signal
            for namespace, signal in limited
            if namespace == "restaurantos-mcp" and signal not in forged_buckets
        ]
        assert valid_buckets
        assert all(signal.startswith("oauth-token:") for signal in valid_buckets)
        assert all(str(subject) not in signal for signal in valid_buckets)


def test_tdd_tc_492_official_client_lists_and_calls_read_only_tools(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory = _factory()
    private_key, jwks = _oauth_key_material()
    common_settings = {
        "secret_key": get_settings().secret_key,
        "grokbot_agent_tools_enabled": True,
    }
    rest_settings = Settings(**common_settings)

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    monkeypatch.setattr("restaurant_os.main.get_settings", lambda: rest_settings)
    monkeypatch.setattr("restaurant_os.agent_tools.get_settings", lambda: rest_settings)
    rest_app = create_app()
    rest_app.dependency_overrides[get_session] = override_session
    with TestClient(rest_app, base_url="https://api.example.com") as rest_client:
        client_id, _ = _configure(
            rest_client,
            "administrator",
            ["agent.context.read", "agent.catalog.read"],
        )
    subject = "user_01JWORKOSADMIN0002"
    identity_id = _bind_oauth_subject(factory, agent_client_id=client_id, subject=subject)

    mcp_settings = Settings(
        **common_settings,
        mcp_enabled=True,
        mcp_issuer_url="https://auth.example.com",
        mcp_jwks_url="https://auth.example.com/.well-known/jwks.json",
        mcp_resource_server_url="https://api.example.com/mcp",
    )

    async def fake_fetch_jwks(_: KiwiOAuthTokenVerifier) -> dict[str, object]:
        return jwks

    monkeypatch.setattr("restaurant_os.main.get_settings", lambda: mcp_settings)
    monkeypatch.setattr("restaurant_os.agent_tools.get_settings", lambda: mcp_settings)
    monkeypatch.setattr("restaurant_os.mcp_server.get_session_factory", lambda: factory)
    monkeypatch.setattr(KiwiOAuthTokenVerifier, "_fetch_jwks", fake_fetch_jwks)
    app = create_app()
    app.dependency_overrides[get_session] = override_session
    bearer = _oauth_token(private_key, subject)

    async def exercise_client() -> None:
        transport = httpx2.ASGITransport(app=app)
        async with app.router.lifespan_context(app):
            async with httpx2.AsyncClient(
                transport=transport,
                base_url="https://api.example.com",
                headers={"Authorization": f"Bearer {bearer}"},
            ) as http_client:
                mcp_transport = streamable_http_client(
                    "https://api.example.com/mcp",
                    http_client=http_client,
                    terminate_on_close=False,
                )
                async with Client(mcp_transport, mode="2026-07-28") as client:
                    listing = await client.list_tools(cache_mode="refresh")
                    assert [tool.name for tool in listing.tools] == [
                        "context",
                        "catalog_items",
                        "operation_status",
                    ]
                    called = await client.call_tool("context", {})
                    assert called.is_error is False
                    assert called.structured_content is not None
                    assert called.structured_content["identity_id"] == identity_id

    asyncio.run(exercise_client())
