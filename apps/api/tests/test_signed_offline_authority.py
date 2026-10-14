"""Signed W04 authority versions, strict wire pairs and real issuer regressions."""

import base64
import json
from datetime import UTC, datetime

import pytest
import sqlalchemy as sa
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from edge_gateway import grants as edge_grants
from restaurant_os import models, offline_grants
from restaurant_os.offline_orders import verify_order_grant
from restaurant_os.operations import BusinessError
from test_branch_workspace_authority import workspace as workspace
from test_offline_authorization_registry import _cash_grant, _order_fixture


def _encoded(value):
    return (
        base64.urlsafe_b64encode(json.dumps(value, sort_keys=True, separators=(",", ":")).encode())
        .decode()
        .rstrip("=")
    )


def _token(header, claims, key):
    signed = f"{_encoded(header)}.{_encoded(claims)}".encode()
    return f"{signed.decode()}.{base64.urlsafe_b64encode(key.sign(signed)).decode().rstrip('=')}"


def _claims(domain, version):
    header = {"alg": "EdDSA", "kid": "qa", "version": version}
    claims = {
        "organization_id": "org",
        "branch_id": "branch",
        "iat": 100,
        "exp": 200,
    }
    if domain == "cash":
        header["typ"] = f"offline_grant.v{version}"
        claims.update(
            actor_user_id="actor",
            source_device_id="device",
            capabilities=["cash.movement.create.v1"],
            kind=header["typ"],
            version=version,
        )
    else:
        header["typ"] = f"order_grant.v{version}"
        claims.update(
            actor_id="actor",
            device_id="device",
            bundle_id="bundle",
            bundle_hash="a" * 64,
            lease_epoch=1,
            capabilities=["orders.create"],
            schema_version=f"ord-off-grant/v{version}",
        )
    if version == (3 if domain == "cash" else 4):
        claims["authorization_version"] = 7
    return header, claims


def _verify(domain, token, key):
    keyring = {"qa": key.public_key()}
    if domain == "cash":
        result = offline_grants.verify_offline_grant(token, keyring, now=150)
        assert result == edge_grants.verify_offline_grant(token, keyring, now=150)
        return result
    try:
        return verify_order_grant(token, keyring, datetime.fromtimestamp(150, UTC))
    except BusinessError:
        return None


@pytest.mark.parametrize("domain", ["cash", "orders"])
@pytest.mark.parametrize("version", [1, 7, 2147483647])
def test_signed_authority_preserves_exact_positive_version(domain, version):
    key = Ed25519PrivateKey.generate()
    header, claims = _claims(domain, 3 if domain == "cash" else 4)
    claims["authorization_version"] = version
    result = _verify(domain, _token(header, claims, key), key)
    assert result is not None
    assert result["authorization_version"] == version
    assert type(result["authorization_version"]) is int


@pytest.mark.parametrize("domain", ["cash", "orders"])
@pytest.mark.parametrize("version", [True, False, 1.0, "1", 0, -1, 2147483648, None])
def test_signed_invalid_authority_is_rejected(domain, version):
    key = Ed25519PrivateKey.generate()
    header, claims = _claims(domain, 3 if domain == "cash" else 4)
    claims["authorization_version"] = version
    assert _verify(domain, _token(header, claims, key), key) is None


@pytest.mark.parametrize("domain", ["cash", "orders"])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "legacy_extra",
        "old_header",
        "old_body",
        "header_float",
        "extra_claim",
    ],
)
def test_authority_wire_formats_cannot_be_mixed(domain, mutation):
    key = Ed25519PrivateKey.generate()
    version = 3 if domain == "cash" else 4
    header, claims = _claims(domain, version)
    old_header, old_claims = _claims(domain, version - 1)
    if mutation == "missing":
        claims.pop("authorization_version")
    elif mutation == "legacy_extra":
        header, claims = old_header, old_claims
        claims["authorization_version"] = 7
    elif mutation == "old_header":
        header = old_header
    elif mutation == "old_body":
        claims = old_claims
    elif mutation == "header_float":
        header["version"] = float(version)
    else:
        claims["unknown"] = True
    assert _verify(domain, _token(header, claims, key), key) is None


@pytest.mark.parametrize("domain", ["cash", "orders"])
def test_legacy_grant_never_infers_authority_version(domain):
    key = Ed25519PrivateKey.generate()
    header, claims = _claims(domain, 2 if domain == "cash" else 3)
    result = _verify(domain, _token(header, claims, key), key)
    assert result is not None
    assert "authorization_version" not in result


def test_cash_legacy_only_verifiers_do_not_accept_the_new_format():
    key = Ed25519PrivateKey.generate()
    header, claims = _claims("cash", 3)
    token = _token(header, claims, key)
    keyring = {"qa": key.public_key()}
    assert offline_grants.verify_offline_grant_v2(token, keyring, now=150) is None
    assert edge_grants.verify_offline_grant_v2(token, keyring, now=150) is None


@pytest.mark.parametrize("domain", ["cash", "orders"])
def test_new_grant_cannot_be_accepted_with_a_different_signing_key(domain):
    key = Ed25519PrivateKey.generate()
    header, claims = _claims(domain, 3 if domain == "cash" else 4)
    assert _verify(domain, _token(header, claims, key), Ed25519PrivateKey.generate()) is None


def test_real_cash_issuer_signs_its_registered_version(workspace, monkeypatch):
    _, _, factory, _ = workspace
    _, grant = _cash_grant(workspace, monkeypatch)
    header, claims = [
        json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        for part in grant["offline_grant"].split(".")[:2]
    ]
    assert header["typ"] == "offline_grant.v3"
    with factory() as session:
        assert claims["authorization_version"] == session.scalar(
            sa.select(models.offline_authorization_leases.c.authorization_version)
        )


def test_real_order_issuer_signs_its_registered_version(workspace, monkeypatch):
    client, _, factory, headers, payload = _order_fixture(workspace, monkeypatch)
    response = client.post("/api/v1/offline-orders/grants", headers=headers, json=payload)
    assert response.status_code == 200, response.text
    header, claims = [
        json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
        for part in response.json()["grant"].split(".")[:2]
    ]
    assert header["typ"] == "order_grant.v4"
    with factory() as session:
        assert claims["authorization_version"] == session.scalar(
            sa.select(models.offline_authorization_leases.c.authorization_version)
        )
