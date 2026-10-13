"""Independent synthetic refutations; no real provider or production data."""

import pytest
import sqlalchemy as sa
import test_facturapi_integration as legacy
import test_fiscal_authority_remediation as authority
import test_fiscal_eligibility as existing
from restaurant_os import models
from restaurant_os.invoicing.eligibility import payment_snapshot

test_db = legacy.test_db
client = legacy.client
auth_headers = legacy.auth_headers
fiscal_data = existing.fiscal_data


@pytest.mark.parametrize("kind", ["issue", "receipt"])
@pytest.mark.parametrize(
    "condition", ["json_list", "json_null", "json_bool", "json_float", "delta_inconsistent"]
)
def test_inconsistent_evidence_returns_stable_review_before_provider(
    client, auth_headers, fiscal_data, kind, condition
):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue" if kind == "issue" else "invoicing.receipt.create")
    payment = existing._payment(session)
    existing._correction(session, payment)
    correction = dict(session.execute(sa.select(models.order_corrections)).mappings().one())
    if condition == "json_list":
        change = {"after_snapshot": [499]}
    elif condition == "json_null":
        change = {"after_snapshot": None}
    elif condition == "json_bool":
        change = {
            "corrected_total_cents": 1,
            "after_snapshot": {"total_cents": True},
            "settlement_delta_cents": -1998,
        }
        session.execute(models.order_payment_adjustments.update().values(amount_cents=1998))
    elif condition == "json_float":
        change = {"after_snapshot": {"total_cents": 499.0}}
    else:
        # Both stored delta and its compensation agree, but the corrected amount does not.
        change = {"settlement_delta_cents": 0}
        session.execute(models.order_payment_adjustments.delete())
    session.execute(
        models.order_corrections.update()
        .where(models.order_corrections.c.id == correction["id"])
        .values(**change)
    )
    session.commit()
    response = existing._request(client, auth_headers, kind)
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_payment_evidence_invalid"
    assert calls == []


@pytest.mark.parametrize(
    "condition",
    ["foreign_payment", "foreign_branch", "wrong_delta", "wrong_sign", "future_version"],
)
def test_wrong_links_fail_closed_without_source_writes(
    client, auth_headers, fiscal_data, condition
):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue")
    payment = existing._payment(session)
    existing._correction(session, payment)
    if condition == "foreign_payment":
        session.execute(
            models.payments.update()
            .where(models.payments.c.id == payment)
            .values(order_id=authority.ORDER_B)
        )
    elif condition == "foreign_branch":
        session.execute(models.order_corrections.update().values(branch_id=authority.BRANCH_B))
    elif condition == "wrong_delta":
        session.execute(models.order_payment_adjustments.update().values(amount_cents=1499))
    elif condition == "wrong_sign":
        session.execute(models.order_payment_adjustments.update().values(adjustment_type="CHARGE"))
    else:
        session.execute(models.order_corrections.update().values(resulting_order_version=999))
    session.commit()
    tables = (
        models.orders,
        models.payments,
        models.order_corrections,
        models.order_payment_adjustments,
    )
    before = [list(session.execute(sa.select(table)).mappings()) for table in tables]
    response = existing._request(client, auth_headers, "issue")
    assert response.status_code == 409, response.text
    assert calls == []
    assert [list(session.execute(sa.select(table)).mappings()) for table in tables] == before


def test_entire_set_is_rejected_if_later_order_is_unpaid(client, auth_headers, fiscal_data):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue")
    existing._payment(session)
    session.execute(
        models.orders.update()
        .where(models.orders.c.id == authority.ORDER_B)
        .values(branch_id=legacy.BRANCH_ID)
    )
    session.commit()
    response = client.post(
        "/api/v1/invoicing/invoices/issue",
        headers=auth_headers,
        json={"order_ids": [authority.ORDER_A, authority.ORDER_B], "receptor": {}},
    )
    assert response.status_code == 409, response.text
    assert response.json()["detail"]["code"] == "fiscal_order_not_fully_paid"
    assert calls == []
    assert session.scalar(sa.select(sa.func.count()).select_from(models.cfdi_invoices)) == 2


def test_snapshot_is_frozen_and_preserves_exact_sources(fiscal_data):
    from dataclasses import FrozenInstanceError

    session, calls = fiscal_data
    payment = existing._payment(session)
    existing._correction(session, payment)
    before = list(session.execute(sa.select(models.order_corrections)).mappings())
    snapshot = payment_snapshot(
        session, legacy.ORGANIZATION_ID, legacy.BRANCH_ID, authority.ORDER_A
    )
    assert snapshot.total_cents == snapshot.paid_cents == 499
    assert snapshot.payment_ids == (payment,)
    assert len(snapshot.correction_ids) == len(snapshot.adjustment_ids) == 1
    with pytest.raises(FrozenInstanceError):
        snapshot.total_cents = 500
    assert list(session.execute(sa.select(models.order_corrections)).mappings()) == before
    assert calls == []
