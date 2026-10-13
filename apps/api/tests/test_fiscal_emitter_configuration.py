# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-emitter-configuration-v1
"""Explicit issuer identity, versioned private configuration and legacy isolation."""

import base64
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
import test_fiscal_authority_remediation as authority
import test_fiscal_eligibility as eligibility
from restaurant_os import models
from restaurant_os.config import get_settings

test_db = authority.test_db
client = authority.client
auth_headers = authority.auth_headers
fiscal_data = authority.fiscal_data
EMITTER_B = "018f6f73-2d0a-74f0-8f1c-000000007002"
FOREIGN_EMITTER = "018f6f73-2d0a-74f0-8f1c-000000007003"


@pytest.fixture
def emitter_data(fiscal_data, monkeypatch):
    session, calls = fiscal_data
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        '{"qa":"' + base64.b64encode(bytes(range(32))).decode() + '"}',
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "qa")
    get_settings.cache_clear()
    emitter_a = session.scalar(
        sa.select(models.branches.c.legal_entity_id).where(
            models.branches.c.id == authority.legacy.BRANCH_ID
        )
    )
    session.execute(
        models.legal_entities.update()
        .where(models.legal_entities.c.id == emitter_a)
        .values(tax_id="SYN010101AAA")
    )
    now = datetime.now(timezone.utc)
    session.execute(
        models.organizations.insert().values(
            id="foreign-fiscal-org",
            name="Foreign synthetic",
            status="active",
            created_at=now,
            updated_at=now,
        )
    )
    for identifier, org, tax_id in (
        (EMITTER_B, authority.legacy.ORGANIZATION_ID, "SYN010101BBB"),
        (FOREIGN_EMITTER, "foreign-fiscal-org", "SYN010101CCC"),
    ):
        session.execute(
            models.legal_entities.insert().values(
                id=identifier,
                organization_id=org,
                name="Synthetic " + identifier,
                tax_id=tax_id,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
    session.commit()
    yield session, calls, emitter_a
    get_settings.cache_clear()


def _path(emitter, suffix="configuration"):
    return f"/api/v1/invoicing/emitters/{emitter}/{suffix}"


def _configuration(**changes):
    return {
        "expected_version": 0,
        "is_enabled": True,
        "environment": "sandbox",
        "api_key": "sk_test_synthetic_emitter_a",
        "organization_legal_name": "Synthetic A",
        "organization_rfc": "SYN010101AAA",
        "organization_tax_system": "601",
        "organization_zip": "80000",
        "default_product_sat_key": "90101501",
        "default_unit_sat_key": "E48",
        "series": "QA",
        "enable_self_invoicing": False,
        "self_invoicing_domain": "",
        "self_invoicing_days_valid": 30,
        "print_qr_on_ticket": False,
        **changes,
    }


def _grant(session):
    authority._grant(session, "invoicing.config.manage")


def test_explicit_emitter_listing_and_empty_configuration(client, auth_headers, emitter_data):
    session, calls, emitter = emitter_data
    _grant(session)
    listed = client.get("/api/v1/invoicing/emitters", headers=auth_headers)
    assert listed.status_code == 200, listed.text
    assert {row["id"] for row in listed.json()} == {emitter, EMITTER_B}
    response = client.get(_path(emitter), headers=auth_headers)
    assert response.status_code == 200, response.text
    value = response.json()
    assert value["version"] == 0 and value["is_enabled"] is False
    assert value["legal_entity_id"] == emitter and value["api_key_configured"] is False
    assert value["organization_rfc"] == "SYN010101AAA"
    for field in (
        "organization_tax_system",
        "organization_zip",
        "default_product_sat_key",
        "default_unit_sat_key",
    ):
        assert value[field] == ""
    assert calls == []


def test_private_revisions_are_isolated_and_blank_credential_preserves(
    client, auth_headers, emitter_data
):
    session, calls, emitter = emitter_data
    _grant(session)
    legacy_before = dict(session.execute(sa.select(models.facturapi_config)).mappings().one())
    first = client.put(_path(emitter), headers=auth_headers, json=_configuration())
    assert first.status_code == 200, first.text
    assert first.json()["version"] == 1 and first.json()["api_key_configured"] is True
    assert "api_key" not in first.json() and "sk_test_synthetic" not in first.text
    second = client.put(
        _path(emitter),
        headers=auth_headers,
        json=_configuration(expected_version=1, series="QB", api_key=""),
    )
    assert second.status_code == 200, second.text
    assert second.json()["version"] == 2 and second.json()["api_key_configured"] is True
    other = client.put(
        _path(EMITTER_B),
        headers=auth_headers,
        json=_configuration(organization_rfc="SYN010101BBB", api_key="sk_test_synthetic_emitter_b"),
    )
    assert other.status_code == 200, other.text
    assert other.json()["id"] != first.json()["id"] and other.json()["version"] == 1
    versions = list(
        session.execute(sa.select(models.fiscal_emitter_configuration_versions)).mappings()
    )
    assert len(versions) == 3
    assert all(
        "sk_test_synthetic" not in str(row) and "SYN010101" not in str(row) for row in versions
    )
    assert (
        dict(session.execute(sa.select(models.facturapi_config)).mappings().one()) == legacy_before
    )
    assert calls == []


@pytest.mark.parametrize(
    "method,suffix",
    [("get", "configuration"), ("put", "configuration"), ("post", "test-connection")],
)
@pytest.mark.parametrize("grant", ["none", "branch_only", "read_only"])
def test_configuration_authority_is_independent_and_corporate(
    client, auth_headers, emitter_data, method, suffix, grant
):
    session, calls, emitter = emitter_data
    if grant != "none":
        authority._grant(
            session,
            "invoicing.read" if grant == "read_only" else "invoicing.config.manage",
            branch_scoped=grant == "branch_only",
        )
    response = getattr(client, method)(
        _path(emitter, suffix),
        headers=auth_headers,
        **({"json": _configuration()} if method == "put" else {}),
    )
    assert response.status_code == 403, response.text
    assert calls == []


def test_foreign_emitter_does_not_expose_identity(client, auth_headers, emitter_data):
    session, calls, _ = emitter_data
    _grant(session)
    for method in ("get", "put"):
        response = getattr(client, method)(
            _path(FOREIGN_EMITTER),
            headers=auth_headers,
            **({"json": _configuration()} if method == "put" else {}),
        )
        assert response.status_code == 404, response.text
        assert "SYN010101CCC" not in response.text and "Foreign" not in response.text
    assert calls == []


@pytest.mark.parametrize(
    "changes",
    [
        {"expected_version": True},
        {"extra": "injected"},
        {"legal_entity_id": EMITTER_B},
        {"is_enabled": "true"},
        {"environment": "unknown"},
        {"organization_rfc": "SYN010101BBB"},
        {"organization_tax_system": ""},
        {"organization_zip": ""},
        {"default_product_sat_key": ""},
        {"default_unit_sat_key": ""},
        {"api_key": ""},
        {"api_key": "sk_live_synthetic_wrong_environment"},
    ],
)
def test_invalid_configuration_is_rejected_without_effects(
    client, auth_headers, emitter_data, changes
):
    session, calls, emitter = emitter_data
    _grant(session)
    response = client.put(_path(emitter), headers=auth_headers, json=_configuration(**changes))
    assert response.status_code == 409, response.text
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.fiscal_emitter_configurations))
        == 0
    )
    assert calls == []


def test_stale_version_and_environment_change_cannot_reuse_a_credential(
    client, auth_headers, emitter_data
):
    session, calls, emitter = emitter_data
    _grant(session)
    assert (
        client.put(_path(emitter), headers=auth_headers, json=_configuration()).status_code == 200
    )
    stale = client.put(
        _path(emitter), headers=auth_headers, json=_configuration(series="DIFFERENT")
    )
    assert (
        stale.status_code == 409
        and stale.json()["detail"]["code"] == "fiscal_configuration_version_conflict"
    )
    change = _configuration(expected_version=1, environment="live")
    del change["api_key"]
    rejected = client.put(_path(emitter), headers=auth_headers, json=change)
    assert rejected.status_code == 409, rejected.text
    assert (
        session.scalar(
            sa.select(sa.func.count()).select_from(models.fiscal_emitter_configuration_versions)
        )
        == 1
    )
    assert calls == []


@pytest.mark.parametrize("kind", ["issue", "receipt"])
def test_unbound_legacy_configuration_never_enables_new_effects(
    client, auth_headers, emitter_data, kind
):
    session, calls, _ = emitter_data
    authority._grant(session, "invoicing.issue" if kind == "issue" else "invoicing.receipt.create")
    eligibility._payment(session)
    response = eligibility._request(client, auth_headers, kind)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_emitter_configuration_required"
    assert calls == []


def test_missing_encryption_key_does_not_store_configuration(
    client, auth_headers, emitter_data, monkeypatch
):
    session, calls, emitter = emitter_data
    _grant(session)
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ENCRYPTION_KEYS", "{}")
    get_settings.cache_clear()
    response = client.put(_path(emitter), headers=auth_headers, json=_configuration())
    assert response.status_code == 503, response.text
    assert "sk_test" not in response.text
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.fiscal_emitter_configurations))
        == 0
    )
    assert calls == []
