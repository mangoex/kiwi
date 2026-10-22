"""GREEN fixture/contract controls; these do not certify the new runtime policy."""

from __future__ import annotations

import importlib
from copy import deepcopy
from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_contracts import RECEIPT_SCHEMA, REPORT_SCHEMA
from corte_ciego_fixtures import (
    BRANCH_A,
    BRANCH_B,
    ORG_ID,
    OTHER_ORG,
    CashWorld,
    cash_world,
    grant_scopes,
    grants,
    policy_revisions,
    revocations,
)
from restaurant_os import models
from restaurant_os.operations import UserCashCutService

__all__ = ["cash_world"]
# Same required-dependency loading convention as test_user_cash_cut_contracts.py.
# Import errors fail collection; this is not importorskip or a typing exclusion.
jsonschema = importlib.import_module("jsonschema")


def test_fixture_has_two_orgs_scoped_grants_revocation_and_nonzero_ledger(
    cash_world: CashWorld,
) -> None:
    with cash_world.sessions() as session:
        assert set(session.scalars(sa.select(models.organizations.c.id))) == {ORG_ID, OTHER_ORG}
        assert session.scalar(sa.select(sa.func.count()).select_from(policy_revisions)) == 2
        pairs = set(session.execute(sa.select(grant_scopes.c.branch_id, grant_scopes.c.dataset)
                    .join(grants, grants.c.id == grant_scopes.c.grant_id)
                    .where(grants.c.subject_user_id == cash_world.actors["delegate"])).all())
        assert pairs == {(BRANCH_A, "cash.cuts"), (BRANCH_B, "sales")}
        assert session.scalar(sa.select(sa.func.count()).select_from(revocations)) == 1
        assert session.scalar(sa.select(models.users.c.authorization_version).where(
            models.users.c.id == cash_world.actors["revoked"]
        )) == 2
        cut = session.execute(sa.select(models.user_cash_cuts).where(
            models.user_cash_cuts.c.id == cash_world.cut_id
        )).mappings().one()
        assert cut["status"] == "COUNTED"
        assert cut["counted_cash_cents"] == 10_001
        assert session.scalar(sa.select(sa.func.sum(models.payments.c.amount_cents)).where(
            models.payments.c.branch_id == BRANCH_A
        )) == 5_000


def test_owner_baseline_reads_real_financial_data_and_receipt_is_idempotent(
    cash_world: CashWorld,
) -> None:
    # Control runs the existing financial domain, not a pretend v2 endpoint.
    with cash_world.sessions() as session:
        service = UserCashCutService(session)
        service.finalize(cash_world.cut_id, {"version": 2}, "f103-owner-finalize",
                         cash_world.actors["owner"])
        result = service.detail(cash_world.cut_id, cash_world.actors["owner"])
        assert result["cash_cut"]["expected_cash_cents"] == 16_500
    before = cash_world.snapshot()
    with cash_world.sessions() as session:
        UserCashCutService(session).counted_cash(
            cash_world.cut_id, {"counted_cash_cents": 10_001, "version": 1},
            "f103-setup-count", cash_world.actors["cashier"],
        )
    assert cash_world.snapshot() == before


def test_foreign_actor_cannot_read_real_cut(cash_world: CashWorld) -> None:
    response = cash_world.client.get(
        f"/api/v1/cash/user-cuts/{cash_world.cut_id}", headers=cash_world.headers("foreign"),
    )
    assert response.status_code == 403, response.text
    assert response.json()["detail"]["code"] == "actor_not_authorized"


@pytest.fixture
def receipt() -> dict[str, Any]:
    return {
        "command_id": "command", "resource_id": "cut", "action": "count", "status": "COUNTED",
        "version": 2, "accepted_at": "2026-10-21T12:00:00Z", "replay": False,
        "correlation_id": "correlation", "projection": "operational", "schema_version": 2,
        "policy_version": 1,
    }


def test_receipt_allowlist_accepts_ack_without_financial_result(receipt: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator.check_schema(RECEIPT_SCHEMA)
    jsonschema.Draft202012Validator(RECEIPT_SCHEMA,
                                   format_checker=jsonschema.FormatChecker()).validate(receipt)


@pytest.mark.parametrize("field,value", [
    ("expected_cash_cents", 0), ("difference_cents", None), ("has_financial_alert", False),
    ("snapshot", {"difference_cents": 1}), ("balanced", True), ("version", True),
])
def test_receipt_rejects_hidden_zero_null_derived_and_nested_result(
    receipt: dict[str, Any], field: str, value: Any,
) -> None:
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**receipt, field: value}, RECEIPT_SCHEMA)


@pytest.fixture
def report() -> dict[str, Any]:
    return {
        "branch_id": BRANCH_A, "period": "day", "start": "2026-10-21T06:00:00Z",
        "end": "2026-10-22T06:00:00Z", "timezone": "America/Chihuahua", "ticket_count": 2,
        "top_products": [{"position": 1, "name": "Producto de prueba"}],
        "projection": "operational", "schema_version": 2, "policy_version": 1,
    }


def test_report_allowlist_accepts_only_names_positions_and_tickets(report: dict[str, Any]) -> None:
    jsonschema.Draft202012Validator.check_schema(REPORT_SCHEMA)
    jsonschema.Draft202012Validator(REPORT_SCHEMA,
                                   format_checker=jsonschema.FormatChecker()).validate(report)


@pytest.mark.parametrize("field", ["quantity", "price_cents", "revenue_cents", "margin", "id"])
def test_report_rejects_product_reconstruction_fields(report: dict[str, Any], field: str) -> None:
    invalid = deepcopy(report)
    invalid["top_products"][0][field] = 1
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, REPORT_SCHEMA)
