# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-emitter-refutations-v1
"""Independent F02 disproofs; all credentials and transport are synthetic."""

import base64
import json
import urllib.request
from datetime import datetime, timezone
from io import BytesIO
from types import MethodType
from urllib.error import HTTPError

import pytest
import sqlalchemy as sa
import test_fiscal_authority_remediation as authority
import test_fiscal_emitter_configuration as directed
from restaurant_os import api, models
from restaurant_os.config import get_settings
from restaurant_os.invoicing import crypto, emitters, service
from restaurant_os.invoicing.facturapi_client import FacturapiClient

test_db = directed.test_db
client = directed.client
auth_headers = directed.auth_headers
fiscal_data = directed.fiscal_data
emitter_data = directed.emitter_data


def _save(session, emitter, **changes):
    return emitters.save_configuration(
        session, authority.legacy.USER_ID, emitter, directed._configuration(**changes)
    )


@pytest.mark.parametrize("expected", [None, False, 0.0, -1, 2147483648, "0"])
def test_expected_version_is_strict_and_has_no_partial_write(
    client, auth_headers, emitter_data, expected
):
    session, calls, emitter = emitter_data
    directed._grant(session)
    payload = directed._configuration(expected_version=expected)
    if expected is None:
        del payload["expected_version"]
    response = client.put(directed._path(emitter), headers=auth_headers, json=payload)
    assert response.status_code == 409, response.text
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.fiscal_emitter_configurations))
        == 0
    )
    assert calls == []


@pytest.mark.parametrize("condition", ["inactive_actor", "inactive_emitter", "missing_emitter"])
def test_current_actor_and_emitter_are_required(client, auth_headers, emitter_data, condition):
    session, calls, emitter = emitter_data
    directed._grant(session)
    if condition == "inactive_actor":
        session.execute(
            models.users.update()
            .where(models.users.c.id == authority.legacy.USER_ID)
            .values(status="suspended")
        )
    elif condition == "inactive_emitter":
        session.execute(
            models.legal_entities.update()
            .where(models.legal_entities.c.id == emitter)
            .values(status="inactive")
        )
    else:
        emitter = "unknown-synthetic-emitter"
    session.commit()
    response = client.put(
        directed._path(emitter), headers=auth_headers, json=directed._configuration()
    )
    assert response.status_code == (403 if condition == "inactive_actor" else 404)
    assert calls == []


def test_mixed_grants_do_not_borrow_corporate_authority(client, auth_headers, emitter_data):
    session, calls, emitter = emitter_data
    authority._grant(session, "invoicing.config.manage", branch_scoped=True)
    session.execute(
        models.roles.insert().values(
            id="synthetic-unrelated-org-role",
            organization_id=authority.legacy.ORGANIZATION_ID,
            name="Unrelated corporate role",
            scope="organization",
            created_at=datetime.now(timezone.utc),
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=authority.legacy.USER_ID, role_id="synthetic-unrelated-org-role"
        )
    )
    session.commit()
    assert client.get(directed._path(emitter), headers=auth_headers).status_code == 403
    assert calls == []


@pytest.mark.parametrize("creation", [True, False])
def test_audit_sink_failure_rolls_back_identity_revision_and_pointer(
    emitter_data, monkeypatch, creation
):
    session, calls, emitter = emitter_data
    directed._grant(session)
    if not creation:
        _save(session, emitter)
    before = [
        dict(row)
        for row in session.execute(
            sa.select(models.fiscal_emitter_configuration_versions)
        ).mappings()
    ]
    audits = session.scalar(sa.select(sa.func.count()).select_from(models.audit_events))

    def failure(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(emitters, "_audit", failure)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        _save(session, emitter, expected_version=0 if creation else 1, series="NEXT")
    session.commit()
    after = [
        dict(row)
        for row in session.execute(
            sa.select(models.fiscal_emitter_configuration_versions)
        ).mappings()
    ]
    assert before == after
    assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == audits
    assert session.scalar(sa.select(models.fiscal_emitter_configurations.c.current_version)) == (
        None if creation else 1
    )
    assert calls == []


@pytest.mark.parametrize("context", ["wrong-org", "wrong-identity", "wrong-version"])
def test_ciphertext_cannot_be_reused_in_another_context(emitter_data, context):
    envelope = crypto.seal({"api_key": "sk_test_private_synthetic"}, "org/config/1")
    with pytest.raises(RuntimeError, match="^fiscal_crypto_unavailable$"):
        crypto.unseal(envelope, context)


def test_ciphertext_tamper_is_sanitized(client, auth_headers, emitter_data, caplog):
    session, calls, emitter = emitter_data
    directed._grant(session)
    saved = _save(session, emitter)
    envelope = json.loads(
        session.scalar(sa.select(models.fiscal_emitter_configuration_versions.c.payload_ciphertext))
    )
    damaged = bytearray(base64.b64decode(envelope["ciphertext"]))
    damaged[0] ^= 1
    envelope["ciphertext"] = base64.b64encode(damaged).decode()
    session.execute(
        models.fiscal_emitter_configuration_versions.update().values(
            payload_ciphertext=json.dumps(envelope)
        )
    )
    session.commit()
    response = client.get(directed._path(emitter), headers=auth_headers)
    assert response.status_code == 503
    assert "sk_test_synthetic_emitter_a" not in response.text + caplog.text
    assert saved["version"] == 1 and calls == []


def test_rotation_retains_old_revision_and_removed_key_fails_closed(emitter_data, monkeypatch):
    session, _, emitter = emitter_data
    directed._grant(session)
    first = _save(session, emitter)
    key = base64.b64encode(bytes(reversed(range(32)))).decode()
    monkeypatch.setenv(
        "RESTAURANTOS_FISCAL_ENCRYPTION_KEYS",
        json.dumps({"qa": base64.b64encode(bytes(range(32))).decode(), "next": key}),
    )
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ACTIVE_ENCRYPTION_KEY_ID", "next")
    get_settings.cache_clear()
    _save(session, emitter, expected_version=1, series="NEXT")
    identity = emitters._identity(session, authority.legacy.ORGANIZATION_ID, emitter)
    assert emitters._revision(session, identity, 1)["series"] == "QA"
    assert emitters._revision(session, identity, 2)["series"] == "NEXT"
    assert first["version"] == 1
    monkeypatch.setenv("RESTAURANTOS_FISCAL_ENCRYPTION_KEYS", json.dumps({"next": key}))
    get_settings.cache_clear()
    with pytest.raises(RuntimeError, match="^fiscal_crypto_unavailable$"):
        emitters._revision(session, identity, 1)
    assert emitters._revision(session, identity, 2)["series"] == "NEXT"


def test_whitespace_key_preserves_secret_and_audit_replacement_is_false(emitter_data):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)
    _save(session, emitter, expected_version=1, api_key="   ")
    identity = emitters._identity(session, authority.legacy.ORGANIZATION_ID, emitter)
    assert emitters._revision(session, identity, 2)["api_key"] == "sk_test_synthetic_emitter_a"
    audit = (
        session.execute(
            sa.select(models.audit_events.c.payload)
            .where(models.audit_events.c.action == "invoicing.emitter_configuration.updated")
            .order_by(models.audit_events.c.created_at.desc())
        )
        .scalars()
        .first()
    )
    assert audit["credential_replaced"] is False


@pytest.mark.parametrize("key", [None, "", "sk_test_mock_synthetic"])
def test_no_implicit_provider_mock_or_ambient_credential(emitter_data, key):
    with pytest.raises(Exception, match="credential|mock"):
        emitters.client_for_configuration({"api_key": key})


def test_valid_provider_connection_result_is_normalized(
    client, auth_headers, emitter_data, monkeypatch
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)
    monkeypatch.setattr(
        FacturapiClient,
        "validate_api_key",
        lambda self: {
            "id": "65fe9cd6030ea750855e6126",
            "legal": {"name": "Synthetic A"},
            "is_production_ready": False,
        },
    )
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


def test_legacy_mock_connection_result_cannot_certify_real_provider(
    client, auth_headers, emitter_data, monkeypatch
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)
    monkeypatch.setattr(
        FacturapiClient,
        "validate_api_key",
        lambda self: {
            "status": "ok",
            "is_active": True,
            "legal_name": "Synthetic A",
            "rfc": "SYN010101AAA",
        },
    )
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.json()["success"] is False


def test_connection_cannot_succeed_after_emitter_deactivation(
    client, auth_headers, emitter_data, monkeypatch
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)

    def provider(self):
        assert not session.in_transaction()
        session.execute(
            models.legal_entities.update()
            .where(models.legal_entities.c.id == emitter)
            .values(status="inactive")
        )
        session.commit()
        return {"success": True}

    monkeypatch.setattr(FacturapiClient, "validate_api_key", provider)
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == 404, response.text


@pytest.mark.parametrize("change", ["actor", "configuration"])
def test_connection_reauthorizes_actor_and_configuration_after_network(
    client, auth_headers, emitter_data, monkeypatch, change
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)

    def provider(self):
        assert not session.in_transaction()
        if change == "actor":
            session.execute(
                models.users.update()
                .where(models.users.c.id == authority.legacy.USER_ID)
                .values(status="suspended")
            )
            session.commit()
        else:
            _save(session, emitter, expected_version=1, series="CHANGED")
        return {"success": True}

    monkeypatch.setattr(FacturapiClient, "validate_api_key", provider)
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == (403 if change == "actor" else 409), response.text


@pytest.mark.parametrize("failure", ["http_body", "transport_exception"])
def test_provider_error_body_never_reaches_logs(
    client, auth_headers, emitter_data, monkeypatch, caplog, failure
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)
    marker = "synthetic-private-provider-error-marker"

    def provider(*args, **kwargs):
        if failure == "transport_exception":
            raise OSError(marker)
        raise HTTPError(
            "https://www.facturapi.io/v2/organizations/me",
            401,
            "Unauthorized",
            {},
            BytesIO(json.dumps({"message": marker}).encode()),
        )

    monkeypatch.setattr("urllib.request.OpenerDirector.open", provider)
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == 503
    assert marker not in response.text + caplog.text


def test_provider_redirect_cannot_forward_issuer_authorization(
    client, auth_headers, emitter_data, monkeypatch
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)
    visited = []

    def provider(opener, request, *args, **kwargs):
        visited.append(request.full_url)
        if len(visited) > 1:
            return BytesIO(json.dumps({"id": "redirected", "legal": {}}).encode())
        handler = next(
            h for h in opener.handlers if isinstance(h, urllib.request.HTTPRedirectHandler)
        )
        return handler.http_error_302(
            request,
            BytesIO(),
            302,
            "Moved",
            {"location": "https://synthetic-attacker.invalid/credential-sink"},
        )

    monkeypatch.setattr("urllib.request.OpenerDirector.open", provider)
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == 503, response.text
    assert visited == ["https://www.facturapi.io/v2/organizations/me"]


@pytest.mark.parametrize(
    "body",
    [b"[]", b"true", b"null", b"x" * (1024 * 1024 + 2)],
    ids=["array", "boolean", "null", "oversized"],
)
def test_provider_response_is_bounded_and_requires_object(
    client, auth_headers, emitter_data, monkeypatch, body
):
    session, _, emitter = emitter_data
    directed._grant(session)
    _save(session, emitter)
    reads = []

    class Response(BytesIO):
        def read(self, size=-1):
            reads.append(size)
            return super().read(size)

        def read1(self, size=-1):
            return self.read(size)

    monkeypatch.setattr("urllib.request.OpenerDirector.open", lambda *a, **k: Response(body))
    response = client.post(directed._path(emitter, "test-connection"), headers=auth_headers)
    assert response.status_code == 503, response.text
    assert reads and 0 < reads[0] <= 1024 * 1024 + 1


@pytest.mark.parametrize("action", ["download", "cancel"])
def test_document_uses_its_retained_revision_not_legacy_or_current(
    client, auth_headers, emitter_data, monkeypatch, action
):
    session, _, emitter = emitter_data
    directed._grant(session)
    authority._grant(session, "invoicing.read" if action == "download" else "invoicing.cancel")
    first = _save(session, emitter)
    _save(session, emitter, expected_version=1, api_key="sk_test_synthetic_rotated")
    invoice = dict(
        session.execute(
            sa.select(models.cfdi_invoices).where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        )
        .mappings()
        .one()
    )
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == invoice["id"])
        .values(
            emitter_configuration_id=first["id"],
            emitter_configuration_version=1,
            rfc_emisor="SYN010101AAA",
            raw_sat_response={
                "id": invoice["facturapi_invoice_id"],
                "uuid": invoice["uuid_sat"],
                "status": "valid",
            },
        )
    )
    session.commit()
    captured = []
    monkeypatch.setattr(
        api.invoicing_service,
        "get_client",
        MethodType(service.InvoicingService.get_client, api.invoicing_service),
    )

    def download(self, *args):
        captured.append(self.api_key)
        return b"%PDF-synthetic"

    def cancel(self, *args):
        captured.append(self.api_key)
        return {"status": "canceled", "cancellation_status": "accepted"}

    monkeypatch.setattr(FacturapiClient, "download_invoice", download)
    monkeypatch.setattr(FacturapiClient, "cancel_invoice", cancel)
    path = f"/api/v1/invoicing/invoices/{invoice['id']}/" + (
        "pdf" if action == "download" else "cancel"
    )
    response = (
        client.get(path, headers=auth_headers)
        if action == "download"
        else client.post(path, headers=auth_headers, json={"motive": "02"})
    )
    assert response.status_code == 200, response.text
    assert captured == ["sk_test_synthetic_emitter_a"]


@pytest.mark.parametrize("action", ["download_mismatched_issuer", "cancel_unbound"])
def test_legacy_origin_must_be_known_and_cancellation_must_be_bound(
    client, auth_headers, emitter_data, monkeypatch, action
):
    session, _, _ = emitter_data
    authority._grant(
        session, "invoicing.read" if action.startswith("download") else "invoicing.cancel"
    )
    invoice = dict(
        session.execute(
            sa.select(models.cfdi_invoices).where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        )
        .mappings()
        .one()
    )
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == invoice["id"])
        .values(
            rfc_emisor="SYN010101BBB" if action.startswith("download") else invoice["rfc_emisor"],
            raw_sat_response={
                "id": invoice["facturapi_invoice_id"],
                "uuid": invoice["uuid_sat"],
                "status": "valid",
            },
        )
    )
    session.commit()
    captured = []
    monkeypatch.setattr(
        api.invoicing_service,
        "get_client",
        MethodType(service.InvoicingService.get_client, api.invoicing_service),
    )

    def download(self, *args):
        captured.append("download")
        return b"%PDF-synthetic"

    def cancel(self, *args):
        captured.append("cancel")
        return {"status": "canceled", "cancellation_status": "accepted"}

    monkeypatch.setattr(FacturapiClient, "download_invoice", download)
    monkeypatch.setattr(FacturapiClient, "cancel_invoice", cancel)
    path = f"/api/v1/invoicing/invoices/{invoice['id']}/" + (
        "pdf" if action.startswith("download") else "cancel"
    )
    response = (
        client.get(path, headers=auth_headers)
        if action.startswith("download")
        else client.post(path, headers=auth_headers, json={"motive": "02"})
    )
    assert response.status_code == 409, response.text
    assert captured == []


def test_download_does_not_return_bytes_if_origin_revision_changed_during_network(
    client, auth_headers, emitter_data, monkeypatch
):
    session, _, emitter = emitter_data
    directed._grant(session)
    authority._grant(session, "invoicing.read")
    first = _save(session, emitter)
    _save(session, emitter, expected_version=1, api_key="sk_test_synthetic_rotated")
    invoice = dict(
        session.execute(
            sa.select(models.cfdi_invoices).where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        )
        .mappings()
        .one()
    )
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == invoice["id"])
        .values(
            emitter_configuration_id=first["id"],
            emitter_configuration_version=1,
            rfc_emisor="SYN010101AAA",
            raw_sat_response={
                "id": invoice["facturapi_invoice_id"],
                "uuid": invoice["uuid_sat"],
                "status": "valid",
            },
        )
    )
    session.commit()
    monkeypatch.setattr(
        api.invoicing_service,
        "get_client",
        MethodType(service.InvoicingService.get_client, api.invoicing_service),
    )

    def provider(self, *args):
        assert not session.in_transaction()
        session.execute(
            models.cfdi_invoices.update()
            .where(models.cfdi_invoices.c.id == invoice["id"])
            .values(emitter_configuration_version=2)
        )
        session.commit()
        return b"%PDF-synthetic-private-body"

    monkeypatch.setattr(FacturapiClient, "download_invoice", provider)
    response = client.get(f"/api/v1/invoicing/invoices/{invoice['id']}/pdf", headers=auth_headers)
    assert response.status_code == 409, response.text
    assert b"synthetic-private-body" not in response.content
    assert (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "invoicing.document.downloaded")
        )
        == 0
    )


def test_legacy_projection_requires_binding_and_absence_has_no_fiscal_defaults(
    client, auth_headers, emitter_data
):
    session, calls, _ = emitter_data
    directed._grant(session)
    path = "/api/v1/integrations/facturapi/config"
    existing = client.get(path, headers=auth_headers)
    assert existing.status_code == 200, existing.text
    assert existing.json()["emitter_binding_required"] is True
    assert existing.json()["api_key_configured"] is True
    assert "api_key" not in existing.json() and "synthetic-sensitive-key" not in existing.text
    session.execute(models.facturapi_config.delete())
    session.commit()
    missing = client.get(path, headers=auth_headers)
    assert missing.status_code == 200, missing.text
    assert missing.json() == {"api_key_configured": False, "emitter_binding_required": True}
    disabled_missing = client.post(path, headers=auth_headers, json={"is_enabled": False})
    assert disabled_missing.status_code == 404, disabled_missing.text
    assert session.scalar(sa.select(sa.func.count()).select_from(models.facturapi_config)) == 0
    assert calls == []


def test_legacy_disable_preserves_credential_identity_and_audits_only_disable(
    client, auth_headers, emitter_data
):
    session, calls, _ = emitter_data
    directed._grant(session)
    before = dict(session.execute(sa.select(models.facturapi_config)).mappings().one())
    response = client.post(
        "/api/v1/integrations/facturapi/config", headers=auth_headers, json={"is_enabled": False}
    )
    assert response.status_code == 200, response.text
    after = dict(session.execute(sa.select(models.facturapi_config)).mappings().one())
    assert after["is_enabled"] is False
    assert {k: v for k, v in before.items() if k not in {"is_enabled", "updated_at"}} == {
        k: v for k, v in after.items() if k not in {"is_enabled", "updated_at"}
    }
    audit = session.execute(
        sa.select(models.audit_events.c.payload).where(
            models.audit_events.c.action == "invoicing.config.updated"
        )
    ).scalar_one()
    assert audit == {
        "is_enabled": False,
        "environment": before["environment"],
        "credential_replaced": False,
    }
    assert "synthetic-sensitive-key" not in str(audit) + response.text
    assert calls == []


def test_legacy_reconfiguration_and_connection_reject_before_provider(
    client, auth_headers, emitter_data
):
    session, calls, _ = emitter_data
    directed._grant(session)
    before = dict(session.execute(sa.select(models.facturapi_config)).mappings().one())
    for payload in (
        {},
        {"is_enabled": True},
        {"is_enabled": 0},
        {"is_enabled": "false"},
        {"is_enabled": False, "api_key": "sk_test_synthetic_replacement"},
        {"is_enabled": False, "organization_rfc": "SYN010101BBB"},
    ):
        response = client.post(
            "/api/v1/integrations/facturapi/config", headers=auth_headers, json=payload
        )
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "fiscal_emitter_configuration_required"
    connection = client.post("/api/v1/integrations/facturapi/test-connection", headers=auth_headers)
    assert connection.status_code == 409, connection.text
    assert connection.json()["detail"]["code"] == "fiscal_emitter_configuration_required"
    assert dict(session.execute(sa.select(models.facturapi_config)).mappings().one()) == before
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.fiscal_emitter_configurations))
        == 0
    )
    assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == 0
    assert calls == []
