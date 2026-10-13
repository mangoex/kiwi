"""Independent synthetic negatives at the post-transport trust boundary."""

from copy import deepcopy
from uuid import uuid4

import pytest
import sqlalchemy as sa
import test_fiscal_authority_remediation as authority
import test_fiscal_downloads as downloads
from restaurant_os import api, models
from restaurant_os.invoicing.authority import public_invoice

test_db = downloads.test_db
client = downloads.client
auth_headers = downloads.auth_headers
fiscal_data = downloads.fiscal_data


@pytest.mark.parametrize(
    "mutation", ["actor_suspended", "branch_crossed", "remote_changed", "status_pending"]
)
def test_resource_or_actor_changed_during_transport_blocks_delivery(
    client, auth_headers, fiscal_data, monkeypatch, mutation
):
    session, _ = fiscal_data
    authority._grant(session, "invoicing.read", branch_scoped=True)
    transported = []

    class SyntheticPAC:
        def download_invoice(self, *_):
            assert not session.in_transaction()
            transported.append(True)
            if mutation == "actor_suspended":
                session.execute(
                    models.users.update()
                    .where(models.users.c.id == downloads.legacy.USER_ID)
                    .values(status="suspended")
                )
            else:
                value = {
                    "branch_crossed": {"branch_id": authority.BRANCH_B},
                    "remote_changed": {"facturapi_invoice_id": "another-remote-safe"},
                    "status_pending": {"status": "pending"},
                }[mutation]
                session.execute(
                    models.cfdi_invoices.update()
                    .where(models.cfdi_invoices.c.id == authority.INVOICE_A)
                    .values(**value)
                )
            session.commit()
            return b"private-synthetic-document"

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_: SyntheticPAC())
    response = client.get(downloads._path(), headers=auth_headers)
    assert transported == [True], "The adversary must run after actual synthetic transport"
    assert response.status_code in {403, 409}, response.text
    assert "private" not in response.text
    assert (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(models.audit_events.c.action == "invoicing.document.downloaded")
        )
        == 0
    )


def test_projection_drops_both_remote_url_fields_without_mutating_original():
    invoice_id, sat_uuid = str(uuid4()), str(uuid4())
    invoice = {
        "id": invoice_id,
        "uuid_sat": sat_uuid,
        "facturapi_invoice_id": "remote-safe",
        "status": "issued",
        "verification_url": "https://provider.invalid/verify?credential=synthetic-verification",
        "self_invoice_url": "https://provider.invalid/self?credential=synthetic-self",
        "pdf_url": "https://provider.invalid/pdf?credential=synthetic-pdf",
        "xml_url": "https://provider.invalid/xml?credential=synthetic-xml",
        "raw_sat_response": {"id": "remote-safe", "uuid": sat_uuid, "status": "valid"},
    }
    original = deepcopy(invoice)
    dto = public_invoice(invoice)
    assert {"verification_url", "self_invoice_url", "raw_sat_response"}.isdisjoint(dto)
    assert dto["pdf_url"] == f"/api/v1/invoicing/invoices/{invoice_id}/pdf"
    assert dto["xml_url"] == f"/api/v1/invoicing/invoices/{invoice_id}/xml"
    assert "synthetic-" not in str(dto)
    assert invoice == original
