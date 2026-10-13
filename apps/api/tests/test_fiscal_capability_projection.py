"""Fiscal UI uses explicit current capabilities; config requires its own corporate scope."""

import pytest
import test_facturapi_integration as legacy
import test_fiscal_authority_remediation as authority

test_db = legacy.test_db
client = legacy.client
auth_headers = legacy.auth_headers
fiscal_data = authority.fiscal_data


@pytest.mark.parametrize(
    "capability,branch_scoped,allowed",
    [
        ("invoicing.read", True, True),
        ("invoicing.issue", True, True),
        ("invoicing.config.manage", True, False),
        ("invoicing.config.manage", False, True),
    ],
)
def test_fiscal_capabilities_follow_current_persisted_scope(
    client, auth_headers, fiscal_data, capability, branch_scoped, allowed
):
    session, _ = fiscal_data
    authority._grant(session, capability, branch_scoped=branch_scoped)
    response = client.get("/api/v1/auth/session", headers=auth_headers)
    assert response.status_code == 200, response.text
    capabilities = response.json()["admin_capabilities"]
    assert capabilities[capability] is allowed
    for code in [
        "invoicing.read",
        "invoicing.issue",
        "invoicing.cancel",
        "invoicing.receipt.create",
        "invoicing.config.manage",
    ]:
        if code != capability:
            assert capabilities[code] is False
