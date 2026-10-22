"""Operational browsing must never hydrate historical financial detail."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import (
    BRANCH_A,
    BRANCH_B,
    ORG_ID,
    OTHER_BRANCH,
    CashWorld,
    cash_world,
    ident,
)
from restaurant_os import models
from restaurant_os import operations as ops
from sqlalchemy.orm import Session
from test_cash_ledger import NOW

__all__ = ["cash_world"]


def seed_contact_details(session: Session, actor_id: str) -> str:
    """Real, nonempty nested contacts and an import containing forbidden historical data."""
    customer = ident("contact-detail")
    session.execute(
        models.customers.insert().values(
            id=customer,
            organization_id=ORG_ID,
            origin_branch_id=BRANCH_A,
            name="Contact detail",
            customer_segment="VIP",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.customer_addresses.insert().values(
            id=ident("contact-address"),
            customer_id=customer,
            alias="Casa",
            street="Calle",
            exterior_number="1",
            neighborhood="Centro",
            postal_code="82000",
            city="Mazatlan",
            municipality="Mazatlan",
            state="Sinaloa",
            latitude="23.2494149",
            longitude="-106.4111425",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.customer_tax_profiles.insert().values(
            customer_id=customer,
            legal_name="Contact detail",
            tax_id="XAXX010101000",
            tax_regime="616",
            fiscal_postal_code="82000",
            updated_at=NOW,
        )
    )
    batch = ident("contact-import")
    session.execute(
        models.legacy_import_batches.insert().values(
            id=batch,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            source_system="fixture",
            manifest_checksum="a" * 64,
            manifest={},
            created_by=actor_id,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.legacy_import_records.insert().values(
            id=ident("contact-record"),
            batch_id=batch,
            entity_type="customer",
            source_key="contact",
            source_row=1,
            raw_payload={"total_cents": 999999},
            normalized_payload={"legacy_address": "Referencia", "average_ticket_cents": 555555},
            status="applied",
            target_entity_type="customer",
            target_entity_id=customer,
            created_at=NOW,
            updated_at=NOW,
        )
    )
    return customer


def test_operational_customer_nested_contact_contract_preserves_precision(
    cash_world: CashWorld,
) -> None:
    import json
    from pathlib import Path

    import jsonschema

    with cash_world.sessions() as session:
        customer_id = seed_contact_details(session, cash_world.actors["owner"])
        session.commit()
    response = cash_world.client.get(
        "/api/v2/customers",
        params={"branch_id": BRANCH_A, "q": "Contact detail"},
        headers=cash_world.headers("cashier"),
    )
    assert response.status_code == 200, response.text
    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/operational-customers-page-v2.schema.json"
        ).read_text()
    )
    jsonschema.validate(response.json(), schema)
    customer = response.json()["items"][0]
    assert customer["id"] == customer_id
    assert customer["legacy_address_reference"] == "Referencia"
    assert customer["addresses"][0]["latitude"] == "23.2494149"
    assert customer["addresses"][0]["longitude"] == "-106.4111425"
    assert customer["tax_profile"]["tax_id"] == "XAXX010101000"
    assert "555555" not in response.text and "999999" not in response.text
    assert "customer_segment" not in response.text
    customer["addresses"][0]["total_cents"] = 999999
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**response.json(), "items": [customer]}, schema)


def seed_pending_web(session: Session) -> str:
    session.execute(
        models.public_order_keys.insert().values(
            public_key="f106-operational-web",
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            created_at=NOW,
        )
    )
    intent = ident("f106-operational-intent")
    session.execute(
        models.public_order_intents.insert().values(
            id=intent,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            public_key="f106-operational-web",
            public_reference="reference-123456",
            correlation_id="f106-web-correlation",
            status="PENDING_REVIEW",
            order_type="takeout",
            total_cents=123456,
            customer_snapshot={"name": "F103 Web", "historical_total_cents": 555555},
            created_at=NOW,
        )
    )
    return intent


@pytest.mark.parametrize("include_web", [False, True])
def test_operational_account_pages_never_load_or_return_money(
    cash_world: CashWorld,
    include_web: bool,
) -> None:
    if include_web:
        with cash_world.sessions() as session:
            seed_pending_web(session)
            session.commit()
    money_queries: list[str] = []

    def observe(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT") and "_cents" in statement:
            money_queries.append(statement)

    sa.event.listen(cash_world.engine, "before_cursor_execute", observe)
    try:
        seen: list[str] = []
        cursor = None
        for _ in range(3):
            params = {"branch_id": BRANCH_A, "limit": 1, "q": "F103"}
            if cursor:
                params["cursor"] = cursor
            response = cash_world.client.get(
                "/api/v2/orders/accounts", params=params, headers=cash_world.headers("cashier")
            )
            assert response.status_code == 200, response.text
            assert response.headers["cache-control"] == "no-store"
            page = response.json()
            for item in page["items"]:
                assert item["projection"] == "operational"
                assert item["schema_version"] == 2
                assert not any(
                    key in response.text
                    for key in (
                        "total_cents",
                        "amount_cents",
                        "currency",
                        "settlement_eligible",
                        "payments",
                        "555555",
                    )
                )
                seen.append(item["id"])
            cursor = page["next_cursor"]
            if not cursor:
                break
        assert len(set(seen)) == len(seen) == (3 if include_web else 2)
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe)
    assert money_queries == []


def test_operational_accounts_reject_foreign_scope_and_cursor_filter_changes(
    cash_world: CashWorld,
) -> None:
    route, headers = "/api/v2/orders/accounts", cash_world.headers("cashier")
    first = cash_world.client.get(
        route, params={"branch_id": BRANCH_A, "limit": 1}, headers=headers
    )
    assert first.status_code == 200, first.text
    cursor = first.json()["next_cursor"]
    assert cursor
    changed = cash_world.client.get(
        route, params={"branch_id": BRANCH_A, "q": "other", "cursor": cursor}, headers=headers
    )
    assert changed.status_code == 409, changed.text
    foreign = cash_world.client.get(route, params={"branch_id": OTHER_BRANCH}, headers=headers)
    assert foreign.status_code == 403, foreign.text


def test_operational_customer_search_preserves_contact_without_spend(cash_world: CashWorld) -> None:
    from test_cash_ledger import NOW

    with cash_world.sessions() as session:
        session.execute(
            models.customer_phones.insert().values(
                id=ident("phone"),
                customer_id=ident("customer"),
                captured_number="5551234567",
                normalized_number="+525551234567",
                is_primary=True,
                created_at=NOW,
                updated_at=NOW,
            )
        )
        session.execute(
            models.customers.update()
            .where(models.customers.c.id == ident("customer"))
            .values(customer_segment="VIP")
        )
        session.commit()
    statements: list[str] = []

    def observe(conn: Any, cursor: Any, statement: str, *args: Any) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    sa.event.listen(cash_world.engine, "before_cursor_execute", observe)
    try:
        response = cash_world.client.get(
            "/api/v2/customers",
            params={"branch_id": BRANCH_A, "q": "5551234567", "limit": 1},
            headers=cash_world.headers("cashier"),
        )
    finally:
        sa.event.remove(cash_world.engine, "before_cursor_execute", observe)
    assert response.status_code == 200, response.text
    customer = response.json()["items"][0]
    assert customer["name"] == "Synthetic customer"
    assert customer["phones"][0]["normalized_number"] == "+525551234567"
    assert customer["projection"] == "operational"
    assert "order_summary" not in customer and "customer_segment" not in customer
    assert not any(
        "_cents" in query or "customers.customer_segment" in query for query in statements
    )
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("reader", ["unpaged", "summary"])
def test_legacy_customer_domain_reads_require_financial_authority(
    cash_world: CashWorld,
    reader: str,
) -> None:
    with cash_world.sessions() as session:
        with pytest.raises(ops.AuthorizationError, match="not authorized"):
            if reader == "unpaged":
                ops.list_customers(session, branch_id=BRANCH_A)
            else:
                ops.get_customer_order_summary(session, ident("customer"))


def test_operational_customer_scope_and_revoked_operating_permission(cash_world: CashWorld) -> None:
    route, headers = "/api/v2/customers", cash_world.headers("cashier")
    for params in ({"branch_id": OTHER_BRANCH}, {"branch_id": OTHER_BRANCH, "q": "missing"}):
        response = cash_world.client.get(route, params=params, headers=headers)
        assert response.status_code == 403, response.text
    # The customer's origin A does not appear in branch B, including in the count.
    unauthorized_branch = cash_world.client.get(
        route, params={"branch_id": BRANCH_B}, headers=headers
    )
    assert unauthorized_branch.status_code == 403, unauthorized_branch.text
    other_branch = cash_world.client.get(
        route, params={"branch_id": BRANCH_B}, headers=cash_world.headers("owner")
    )
    assert other_branch.status_code == 200, other_branch.text
    assert other_branch.json()["items"] == [] and other_branch.json()["total"] == 0
    with cash_world.sessions() as session:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(
                models.permissions.c.code == "orders.read",
            )
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.role_id == cash_world.roles["cashier"],
                models.role_permissions.c.permission_id == permission,
            )
        )
        session.commit()
    denied = cash_world.client.get(route, params={"branch_id": BRANCH_A}, headers=headers)
    assert denied.status_code == 403, denied.text


def test_customer_financial_history_remains_owner_only(cash_world: CashWorld) -> None:
    params = {"branch_id": BRANCH_A, "limit": 1}
    denied = cash_world.client.get(
        "/api/v1/customers",
        params=params,
        headers=cash_world.headers("cashier"),
    )
    assert denied.status_code == 403, denied.text
    for query in (params, {"branch_id": BRANCH_A}):
        allowed = cash_world.client.get(
            "/api/v1/customers",
            params=query,
            headers=cash_world.headers("owner"),
        )
        assert allowed.status_code == 200, allowed.text
        items = allowed.json()["items"] if "limit" in query else allowed.json()
        assert items[0]["order_summary"]["average_ticket_cents"] == 17000 // 3
        assert items[0]["order_summary"]["order_count"] == 3
