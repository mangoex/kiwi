"""Financial authority is additional to fiscal authority, including downloads."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import BRANCH_B, ORG_ID, CashWorld, cash_world, grant_permission, ident
from restaurant_os import api, models
from sqlalchemy.orm import Session
from test_cash_ledger import NOW

__all__ = ["cash_world"]


@pytest.fixture
def fiscal_world(cash_world: CashWorld) -> CashWorld:
    with cash_world.sessions() as session:
        for role in ("cashier", "delegate"):
            grant_permission(session, cash_world.roles[role], "invoicing.read")
        session.execute(
            models.cfdi_invoices.insert().values(
                id=ident("invoice"),
                organization_id=ORG_ID,
                branch_id=BRANCH_B,
                order_id=ident("order-b"),
                facturapi_invoice_id="synthetic-remote",
                uuid_sat=ident("invoice-sat"),
                folio_number="F106",
                rfc_emisor="KIW210101ABC",
                rfc_receptor="XAXX010101000",
                nombre_receptor="Synthetic",
                codigo_postal_receptor="80000",
                regimen_fiscal_receptor="616",
                total_cents=5000,
                created_at=NOW,
                raw_sat_response={
                    "id": "synthetic-remote",
                    "uuid": ident("invoice-sat"),
                    "status": "valid",
                },
            )
        )
        session.execute(
            models.facturapi_config.insert().values(
                id=ident("fiscal-config"),
                organization_id=ORG_ID,
                is_enabled=True,
                api_key=ident("fiscal-credential-no-network"),
                organization_legal_name="Synthetic",
                organization_rfc="KIW210101ABC",
                organization_tax_system="601",
                organization_zip="80000",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.commit()
    return cash_world


@pytest.mark.parametrize("suffix", ["", "/pdf", "/xml"])
def test_fiscal_read_denies_before_loading_invoice_money(
    fiscal_world: CashWorld,
    suffix: str,
    monkeypatch: Any,
) -> None:
    statements: list[str] = []

    def observe(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if (
            statement.lstrip().upper().startswith("SELECT")
            and "cfdi_invoices.total_cents" in statement
        ):
            statements.append(statement)

    monkeypatch.setattr(
        api.invoicing_service, "get_client", lambda *_: pytest.fail("Provider reached")
    )
    sa.event.listen(fiscal_world.engine, "before_cursor_execute", observe)
    try:
        response = fiscal_world.client.get(
            f"/api/v1/invoicing/invoices/{ident('invoice')}{suffix}",
            headers=fiscal_world.headers("cashier"),
        )
    finally:
        sa.event.remove(fiscal_world.engine, "before_cursor_execute", observe)
    assert statements == [], "Invoice money loaded before financial authorization"
    assert response.status_code == 403, response.text


def test_fiscal_download_revalidates_financial_grant_after_transport(
    fiscal_world: CashWorld,
    monkeypatch: Any,
) -> None:
    calls: list[str] = []

    class Provider:
        def download_invoice(self, *_: Any) -> bytes:
            calls.append("download")
            fiscal_world.revoke("delegate", "sales-b")
            return b"PRIVATE-SYNTHETIC-INVOICE"

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_: Provider())
    response = fiscal_world.client.get(
        f"/api/v1/invoicing/invoices/{ident('invoice')}/pdf",
        headers=fiscal_world.headers("delegate"),
    )
    assert calls == ["download"]
    assert response.status_code == 403, response.text
    assert b"PRIVATE-SYNTHETIC-INVOICE" not in response.content


def test_fiscal_list_cannot_silently_shrink_requested_financial_scope(
    fiscal_world: CashWorld,
) -> None:
    response = fiscal_world.client.get(
        "/api/v1/invoicing/invoices", headers=fiscal_world.headers("delegate")
    )
    assert response.status_code == 403, response.text


def test_fiscal_download_rechecks_after_audit_commit(
    fiscal_world: CashWorld, monkeypatch: Any
) -> None:
    class Provider:
        def download_invoice(self, *_: Any) -> bytes:
            return b"PRIVATE-SYNTHETIC-INVOICE"

    monkeypatch.setattr(api.invoicing_service, "get_client", lambda *_: Provider())
    commit = Session.commit
    revoked = False

    def revoke(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            fiscal_world.revoke("delegate", "sales-b")

    monkeypatch.setattr(Session, "commit", revoke)
    response = fiscal_world.client.get(
        f"/api/v1/invoicing/invoices/{ident('invoice')}/pdf",
        headers=fiscal_world.headers("delegate"),
    )
    assert revoked and response.status_code == 403
    assert b"PRIVATE-SYNTHETIC-INVOICE" not in response.content
