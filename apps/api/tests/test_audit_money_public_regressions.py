from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.integrations.rappi import RappiAdapter
from restaurant_os.operations import list_public_branches
from test_platform_api import BRANCH_ID, _client_with_seeded_database, _test_session_factory


@pytest.mark.parametrize("amount, cents", [(19.99, 1999), (0.29, 29), (1.005, 101)])
def test_rappi_major_units_are_converted_exactly(amount: float, cents: int) -> None:
    order = RappiAdapter().normalize_order(
        {"id": "money-regression", "items": [{"id": "sku", "price": amount}], "total": amount},
        {"sku": "product"},
    )
    assert order.items[0].unit_price_cents == cents
    assert order.total_cents == cents


def test_public_branch_read_never_creates_or_commits_keys() -> None:
    client = _client_with_seeded_database()
    with _test_session_factory(client)() as session:
        session.execute(models.public_order_keys.delete())
        session.commit()
        with patch.object(session, "commit", side_effect=AssertionError("GET must not commit")):
            rows = list_public_branches(session, include_public_key=True)
        assert rows
        assert all(row.get("public_key") is None for row in rows)
        assert session.scalar(sa.select(sa.func.count()).select_from(models.public_order_keys)) == 0


@pytest.mark.parametrize("total, expected", [("19.99", "19.99"), ("1.005", "1.01")])
def test_reconciliation_purchase_conversion_is_exact(total: str, expected: str) -> None:
    from restaurant_os.reconciliation_reports import (
        get_branch_daily_reconciliation,
        get_multi_branch_consolidated_report,
    )

    client = _client_with_seeded_database()
    now = datetime(2026, 9, 25, 18, tzinfo=timezone.utc)
    with _test_session_factory(client)() as session:
        branch = (
            session.execute(models.branches.select().where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        actor = session.scalar(sa.select(models.users.c.id).limit(1))
        session.execute(
            models.suppliers.insert().values(
                id="audit-supplier",
                organization_id=branch["organization_id"],
                code="AUDIT",
                commercial_name="Audit supplier",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.purchase_documents.insert().values(
                id="audit-purchase",
                organization_id=branch["organization_id"],
                branch_id=BRANCH_ID,
                supplier_id="audit-supplier",
                document_type="ticket",
                folio="AUDIT",
                document_date=now,
                subtotal=Decimal(total),
                discount_total=0,
                tax_total=0,
                total=Decimal(total),
                payment_method="cash",
                paid_from_cash=True,
                status="confirmed",
                created_by=actor,
                created_at=now,
            )
        )
        session.commit()
        report = get_branch_daily_reconciliation(session, BRANCH_ID, "2026-09-25")
        assert report["balance"]["supplier_expenses"] == Decimal(expected)
        assert report["balance"]["expected_cash_in_register"] == -Decimal(expected)
        consolidated = get_multi_branch_consolidated_report(
            session, "2026-09-25", "2026-09-25", BRANCH_ID
        )
        assert consolidated["summary"]["total_suppliers"] == Decimal(expected)


def test_rappi_cents_are_not_scaled_again() -> None:
    order = RappiAdapter().normalize_order(
        {
            "id": "cents",
            "items": [{"id": "sku", "price": {"amount": 1999}}],
            "payment": {"charges": {"total": {"amount": 1999}}},
        },
        {"sku": "product"},
    )
    assert order.items[0].unit_price_cents == 1999
    assert order.total_cents == 1999


def test_new_branch_key_is_random_and_persisted_atomically() -> None:
    from test_platform_api import ADMIN_ROLE_ID, _admin_headers

    client = _client_with_seeded_database()
    with _test_session_factory(client)() as session:
        session.execute(
            models.role_authority_grants.insert().values(
                role_id=ADMIN_ROLE_ID,
                authority_kind="organization_all_permissions",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    response = client.post(
        "/api/v1/branches", headers=_admin_headers(), json={"name": "Audit branch", "code": "AUDIT"}
    )
    assert response.status_code == 200
    branch = response.json()
    key = branch["public_key"]
    assert key.startswith("pk_") and len(key) >= 43
    assert branch["id"].replace("-", "")[:24] not in key
    with _test_session_factory(client)() as session:
        stored = (
            session.execute(
                models.public_order_keys.select().where(
                    models.public_order_keys.c.branch_id == branch["id"]
                )
            )
            .mappings()
            .one()
        )
        assert stored["public_key"] == key
        assert stored["status"] == "active"
    duplicate = client.post(
        "/api/v1/branches",
        headers=_admin_headers(),
        json={"name": "Audit duplicate", "code": "AUDIT"},
    )
    assert duplicate.status_code == 409
    with _test_session_factory(client)() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.public_order_keys)
                .where(models.public_order_keys.c.branch_id == branch["id"])
            )
            == 1
        )
