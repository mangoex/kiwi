"""D02: only fully paid, non-cancelled orders may reach the synthetic provider."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
import sqlalchemy as sa
import test_facturapi_integration as legacy
import test_fiscal_authority_remediation as authority
from fiscal_test_support import configure_issuer, encryption_environment
from restaurant_os import models
from restaurant_os.config import get_settings

test_db = legacy.test_db
client = legacy.client
auth_headers = legacy.auth_headers


@pytest.fixture
def fiscal_data(test_db, monkeypatch):
    session, calls = authority.fiscal_data.__wrapped__(test_db, monkeypatch)
    authority._grant(session, "invoicing.config.manage")
    encryption_environment(monkeypatch)
    configure_issuer(session, legacy.USER_ID, legacy.BRANCH_ID)
    yield session, calls
    get_settings.cache_clear()


def _payment(session, *, amount=1999, status="CONFIRMED", currency="MXN", branch=None):
    now, shift, payment = datetime.now(timezone.utc), str(uuid4()), str(uuid4())
    branch = branch or legacy.BRANCH_ID
    session.execute(
        models.cash_shifts.insert().values(
            id=shift,
            organization_id=legacy.ORGANIZATION_ID,
            branch_id=branch,
            register_code="FISCAL-QA",
            status="CLOSED",
            opening_cash_cents=0,
            opened_at=now,
            closed_at=now,
            created_at=now,
        )
    )
    session.execute(
        models.payments.insert().values(
            id=payment,
            organization_id=legacy.ORGANIZATION_ID,
            branch_id=branch,
            order_id=authority.ORDER_A,
            cash_shift_id=shift,
            method="cash",
            status=status,
            amount_cents=amount,
            currency=currency,
            confirmed_at=now,
            created_at=now,
        )
    )
    session.commit()
    return payment


def _request(client, headers, kind):
    if kind == "receipt":
        return client.post(
            "/api/v1/invoicing/orders/" + authority.ORDER_A + "/receipt", headers=headers
        )
    return client.post(
        "/api/v1/invoicing/invoices/issue",
        headers=headers,
        json={"order_ids": [authority.ORDER_A], "receptor": {}},
    )


@pytest.mark.parametrize("kind", ["issue", "receipt"])
@pytest.mark.parametrize(
    "condition",
    ["no_payment", "intent_only", "partial", "pending", "cancelled", "currency", "branch"],
)
def test_ineligible_order_never_reaches_provider(
    client, auth_headers, fiscal_data, kind, condition
):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue" if kind == "issue" else "invoicing.receipt.create")
    if condition == "intent_only":
        session.execute(
            models.orders.update()
            .where(models.orders.c.id == authority.ORDER_A)
            .values(payment_method_intent="cash")
        )
        session.commit()
    elif condition != "no_payment":
        _payment(
            session,
            amount=1998 if condition == "partial" else 1999,
            status="PENDING" if condition == "pending" else "CONFIRMED",
            currency="USD" if condition == "currency" else "MXN",
            branch=authority.BRANCH_B if condition == "branch" else None,
        )
    if condition == "cancelled":
        session.execute(
            models.orders.update()
            .where(models.orders.c.id == authority.ORDER_A)
            .values(status="CANCELLED")
        )
        session.commit()
    response = _request(client, auth_headers, kind)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == (
        "fiscal_order_cancelled" if condition == "cancelled" else "fiscal_order_not_fully_paid"
    )
    assert calls == []


@pytest.mark.parametrize("kind", ["issue", "receipt"])
def test_fully_paid_order_is_eligible(client, auth_headers, fiscal_data, kind):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue" if kind == "issue" else "invoicing.receipt.create")
    _payment(session)
    response = _request(client, auth_headers, kind)
    assert response.status_code == 200, response.text
    assert calls == [kind]
    if kind == "issue":
        assert response.json()["total_cents"] == 1999


def _correction(session, payment, *, currency="MXN", include_adjustment=True):
    now, request, correction = datetime.now(timezone.utc), str(uuid4()), str(uuid4())
    session.execute(
        models.order_reopen_requests.insert().values(
            id=request,
            organization_id=legacy.ORGANIZATION_ID,
            branch_id=legacy.BRANCH_ID,
            order_id=authority.ORDER_A,
            status="APPLIED",
            order_version_snapshot=1,
            order_status_snapshot="COMPLETED",
            before_snapshot={"total_cents": 1999},
            reason="Synthetic correction",
            evidence_refs=["synthetic-evidence"],
            requested_by_user_id=legacy.USER_ID,
            requested_at=now,
            decided_by_user_id=legacy.USER_ID,
            decided_at=now,
            decision_reason="Authorized fixture",
            applied_by_user_id=legacy.USER_ID,
            applied_at=now,
            created_at=now,
            updated_at=now,
        )
    )
    session.execute(
        models.order_corrections.insert().values(
            id=correction,
            organization_id=legacy.ORGANIZATION_ID,
            branch_id=legacy.BRANCH_ID,
            order_id=authority.ORDER_A,
            request_id=request,
            folio="COR-FISCAL-QA",
            captured_order_version=1,
            resulting_order_version=1,
            before_snapshot={"total_cents": 1999},
            after_snapshot={"total_cents": 499},
            currency="MXN",
            corrected_total_cents=499,
            settlement_delta_cents=-1500,
            status="APPLIED",
            actor_user_id=legacy.USER_ID,
            applied_at=now,
        )
    )
    if include_adjustment:
        session.execute(
            models.order_payment_adjustments.insert().values(
                id=str(uuid4()),
                correction_id=correction,
                original_payment_id=payment,
                adjustment_type="REFUND",
                amount_cents=1500,
                method="transfer",
                currency=currency,
                status="CONFIRMED",
                evidence_refs=["synthetic-evidence"],
                created_at=now,
            )
        )
    session.commit()


def test_invoice_uses_corrected_total_and_confirmed_compensation(client, auth_headers, fiscal_data):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue")
    payment = _payment(session)
    _correction(session, payment)
    session.execute(sa.text("PRAGMA foreign_keys=ON"))
    assert session.scalar(sa.text("PRAGMA foreign_keys")) == 1
    response = _request(client, auth_headers, "issue")
    assert response.status_code == 200, response.text
    assert response.json()["total_cents"] == 499
    assert calls == ["issue"]
    assert (
        session.scalar(
            sa.select(models.orders.c.total_cents).where(
                models.orders.c.id == authority.ORDER_A,
            )
        )
        == 1999
    )
    assert session.scalar(sa.select(models.payments.c.amount_cents)) == 1999


@pytest.mark.parametrize("condition", ["missing_adjustment", "wrong_currency"])
def test_incomplete_correction_evidence_fails_before_provider(
    client, auth_headers, fiscal_data, condition
):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue")
    payment = _payment(session)
    _correction(
        session,
        payment,
        currency="USD" if condition == "wrong_currency" else "MXN",
        include_adjustment=condition != "missing_adjustment",
    )
    response = _request(client, auth_headers, "issue")
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_payment_evidence_invalid"
    assert calls == []
