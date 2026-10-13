# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-audit-test-fiscal-downloads-v1
"""Authenticated fiscal artifacts; all transport and data are synthetic."""

from io import BytesIO
from urllib.error import HTTPError
from uuid import uuid4

import pytest
import sqlalchemy as sa
import test_facturapi_integration as legacy
import test_fiscal_authority_remediation as authority
from restaurant_os import api, models
from restaurant_os.invoicing.facturapi_client import FacturapiClient

test_db = legacy.test_db
client = legacy.client
auth_headers = legacy.auth_headers


@pytest.fixture
def fiscal_data(test_db, monkeypatch):
    session, calls = authority.fiscal_data.__wrapped__(test_db, monkeypatch)
    for row in session.execute(sa.select(models.cfdi_invoices)).mappings().all():
        session.execute(
            models.cfdi_invoices.update()
            .where(models.cfdi_invoices.c.id == row["id"])
            .values(
                raw_sat_response={
                    "id": row["facturapi_invoice_id"],
                    "uuid": row["uuid_sat"],
                    "status": "valid",
                }
            )
        )
    session.commit()
    return session, calls


def _path(format="pdf", invoice=authority.INVOICE_A):
    return f"/api/v1/invoicing/invoices/{invoice}/{format}"


@pytest.fixture
def download_provider(fiscal_data, monkeypatch):
    session, _ = fiscal_data
    calls = []

    class ArtifactPAC:
        def download_invoice(self, remote_id, format):
            assert not session.in_transaction(), "Provider I/O must not retain a DB transaction"
            calls.append((remote_id, format))
            return b"%PDF-synthetic" if format == "pdf" else b"<synthetic/>"

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_: ArtifactPAC())
    return calls


@pytest.mark.parametrize("format", ["pdf", "xml"])
def test_download_is_authenticated_scoped_audited_and_uncached(
    client, auth_headers, fiscal_data, download_provider, format
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read", branch_scoped=True)
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        .values(pdf_url="https://attacker.invalid/private?key=legacy-secret")
    )
    session.commit()
    response = client.get(_path(format), headers=auth_headers)
    assert response.status_code == 200, response.text
    assert response.content == (b"%PDF-synthetic" if format == "pdf" else b"<synthetic/>")
    assert response.headers["content-type"].startswith(
        "application/pdf" if format == "pdf" else "application/xml"
    )
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["content-disposition"] == (
        f'attachment; filename="factura-{authority.INVOICE_A}.{format}"'
    )
    assert download_provider == [("remote-" + authority.INVOICE_A, format)]
    audit = (
        session.execute(
            sa.select(models.audit_events).where(
                models.audit_events.c.action == "invoicing.document.downloaded"
            )
        )
        .mappings()
        .one()
    )
    assert audit["payload"] == {"format": format}
    assert audit["actor_user_id"] == legacy.USER_ID
    assert audit["branch_id"] == legacy.BRANCH_ID
    assert (
        session.scalar(
            sa.select(models.cfdi_invoices.c.pdf_url).where(
                models.cfdi_invoices.c.id == authority.INVOICE_A
            )
        )
        == "https://attacker.invalid/private?key=legacy-secret"
    )


@pytest.mark.parametrize(
    "condition", ["unauthenticated", "no_permission", "cross_branch", "missing"]
)
def test_download_denial_precedes_transport(
    client, auth_headers, fiscal_data, download_provider, condition
):
    session, _ = fiscal_data
    if condition in {"cross_branch", "missing"}:
        authority._grant(session, "invoicing.read", branch_scoped=True)
    invoice = (
        authority.INVOICE_B
        if condition == "cross_branch"
        else (str(uuid4()) if condition == "missing" else authority.INVOICE_A)
    )
    response = client.get(
        _path(invoice=invoice), headers={} if condition == "unauthenticated" else auth_headers
    )
    assert (
        response.status_code
        == {
            "unauthenticated": 401,
            "no_permission": 403,
            "cross_branch": 403,
            "missing": 404,
        }[condition]
    ), response.text
    assert download_provider == []


@pytest.mark.parametrize(
    "changes",
    [
        {"status": "pending"},
        {"status": "needs_review"},
        {"uuid_sat": None},
        {"uuid_sat": "fabricated"},
        {"facturapi_invoice_id": None},
        {"facturapi_invoice_id": "../organizations/me?key=private"},
    ],
)
def test_unconfirmed_or_ambiguous_document_has_no_download(
    client, auth_headers, fiscal_data, download_provider, changes
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        .values(**changes)
    )
    session.commit()
    response = client.get(_path(), headers=auth_headers)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_document_not_available"
    assert download_provider == []
    detail = client.get(f"/api/v1/invoicing/invoices/{authority.INVOICE_A}", headers=auth_headers)
    assert detail.json()["pdf_url"] is None and detail.json()["xml_url"] is None


def test_public_artifact_links_are_local_not_remote_credentials(client, auth_headers, fiscal_data):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    session.execute(
        models.cfdi_invoices.update().values(
            pdf_url="https://provider.invalid/signed?secret=private",
            xml_url="https://attacker.invalid/x",
        )
    )
    session.commit()
    response = client.get("/api/v1/invoicing/invoices", headers=auth_headers)
    assert response.status_code == 200
    assert "private" not in response.text and "attacker.invalid" not in response.text
    for row in response.json():
        assert row["pdf_url"] == _path(invoice=row["id"])
        assert row["xml_url"] == _path("xml", row["id"])


@pytest.mark.parametrize("field", ["verification_url", "self_invoice_url"])
def test_invoice_projection_does_not_publish_unvalidated_provider_urls(
    client, auth_headers, fiscal_data, field
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    private_url = "https://provider.invalid/private?token=synthetic-secret"
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        .values({field: private_url})
    )
    session.commit()
    for path in (
        "/api/v1/invoicing/invoices",
        f"/api/v1/invoicing/invoices/{authority.INVOICE_A}",
    ):
        response = client.get(path, headers=auth_headers)
        assert response.status_code == 200, response.text
        assert "synthetic-secret" not in response.text
    original = session.scalar(
        sa.select(models.cfdi_invoices.c[field]).where(
            models.cfdi_invoices.c.id == authority.INVOICE_A
        )
    )
    assert original == private_url


@pytest.mark.parametrize("failure", ["revocation", "audit", "transport"])
def test_private_bytes_are_not_delivered_after_failure(
    client, auth_headers, fiscal_data, monkeypatch, failure, caplog
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")

    class FailingPAC:
        def download_invoice(self, *_):
            assert not session.in_transaction()
            if failure == "transport":
                raise RuntimeError("private-provider-body-and-key")
            if failure == "revocation":
                session.execute(
                    models.role_permissions.delete().where(
                        models.role_permissions.c.permission_id.in_(
                            sa.select(models.permissions.c.id).where(
                                models.permissions.c.code == "invoicing.read"
                            )
                        )
                    )
                )
                session.commit()
            return b"private-file-content"

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_: FailingPAC())
    if failure == "audit":
        monkeypatch.setattr(
            "restaurant_os.invoicing.service._audit",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("private-audit-content")),
        )
    response = client.get(_path(), headers=auth_headers)
    assert response.status_code == (403 if failure == "revocation" else 503), response.text
    assert "private" not in response.text + caplog.text
    session.commit()
    assert (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "invoicing.document.downloaded")
        )
        == 0
    )


class _ArtifactResponse(BytesIO):
    headers = {}
    status = 200

    def isclosed(self):
        return self.tell() == len(self.getvalue())


@pytest.mark.parametrize(
    "proof",
    [
        None,
        {},
        {"status": "pending"},
        {"status": "valid", "id": "different-document", "uuid": str(uuid4())},
        {"status": "valid", "id": "remote-" + authority.INVOICE_A, "uuid": str(uuid4())},
    ],
)
def test_final_looking_legacy_identity_needs_coherent_timbre_evidence(
    client, auth_headers, fiscal_data, download_provider, proof
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read")
    session.execute(
        models.cfdi_invoices.update()
        .where(models.cfdi_invoices.c.id == authority.INVOICE_A)
        .values(raw_sat_response=proof)
    )
    session.commit()
    response = client.get(_path(), headers=auth_headers)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_document_not_available"
    assert download_provider == []
    detail = client.get(f"/api/v1/invoicing/invoices/{authority.INVOICE_A}", headers=auth_headers)
    assert detail.json()["pdf_url"] is None
    assert (
        session.scalar(
            sa.select(models.cfdi_invoices.c.raw_sat_response).where(
                models.cfdi_invoices.c.id == authority.INVOICE_A
            )
        )
        == proof
    )


class _Socket:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        self.timeouts.append(value)


@pytest.mark.parametrize("format", ["pdf", "xml"])
def test_transport_fixed_origin_bearer_and_bounded_binary(monkeypatch, format):
    seen, opened, closed = [], [], []
    response = _ArtifactResponse(b"%PDF-synthetic" if format == "pdf" else b"<synthetic/>")
    response.headers = {"Content-Type": "application/pdf" if format == "pdf" else "application/xml"}

    class Connection:
        def __init__(self, host, timeout):
            opened.append((host, timeout))
            self.sock = _Socket()

        def request(self, method, endpoint, headers):
            seen.append((method, endpoint, headers))

        def getresponse(self):
            return response

        def close(self):
            closed.append(True)
            assert all(0 < value <= 20 for value in self.sock.timeouts)

    monkeypatch.setattr("http.client.HTTPSConnection", Connection)
    result = FacturapiClient(api_key="synthetic-private-key").download_invoice(
        "remote-safe", format
    )
    assert result == (b"%PDF-synthetic" if format == "pdf" else b"<synthetic/>")
    assert opened == [("www.facturapi.io", 20)]
    method, endpoint, headers = seen[0]
    assert (method, endpoint) == ("GET", f"/v2/invoices/remote-safe/{format}")
    assert headers["Authorization"] == "Bearer synthetic-private-key"
    assert len(closed) == 1


@pytest.mark.parametrize(
    "condition", ["empty", "oversize", "mime", "error", "mock", "bad_id", "bad_format", "redirect"]
)
def test_transport_rejects_invalid_or_unsafe_artifacts(monkeypatch, condition, caplog):
    seen, closed = [], []

    class Connection:
        def __init__(self, *_, **kwargs):
            self.sock = _Socket()

        def request(self, method, endpoint, headers):
            seen.append((method, endpoint))

        def getresponse(self):
            if condition == "error":
                raise HTTPError(
                    "https://private-url.invalid",
                    403,
                    "private-http-error",
                    {},
                    BytesIO(b"private-error-body"),
                )
            response = _ArtifactResponse(
                b""
                if condition == "empty"
                else (b"x" * (10 * 1024 * 1024 + 1) if condition == "oversize" else b"synthetic")
            )
            response.headers = {
                "Content-Type": "text/html" if condition == "mime" else "application/pdf",
                "Location": "https://attacker.invalid/signed-private",
            }
            response.status = 302 if condition == "redirect" else 200
            return response

        def close(self):
            closed.append(True)

    monkeypatch.setattr("http.client.HTTPSConnection", Connection)
    provider = FacturapiClient(api_key="synthetic-private-key", is_mock=condition == "mock")
    with pytest.raises((RuntimeError, ValueError)) as raised:
        provider.download_invoice(
            "../private" if condition == "bad_id" else "remote-safe",
            "html" if condition == "bad_format" else "pdf",
        )
    assert "private" not in str(raised.value) + caplog.text
    if condition in {"mock", "bad_id", "bad_format"}:
        assert seen == [] and closed == []
    else:
        assert seen == [("GET", "/v2/invoices/remote-safe/pdf")]
        assert len(closed) == 1
