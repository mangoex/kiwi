"""F1-03 synthetic inputs, never a replacement authorization implementation.

The real F1-04 relations hold synthetic inputs in isolated tests.
Legacy handlers remain RED until F1-05/06; this fixture proves no rollout.
No monkeypatch of permissions, projections, commands or route registration is used.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import UserCashCutService
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from test_cash_concepts import (
    BRANCH_A,
    BRANCH_B,
    BUSINESS_UNIT_ID,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    LEGAL_ID,
    ORG_ID,
    OWNER_ID,
    OWNER_ROLE_ID,
    _seed_cash_concept_scope,
)
from test_cash_ledger import NOW, SHIFT_ID, _insert_movement, _insert_shift
from test_user_cash_cuts import _closed_shift

__all__ = ["BRANCH_A", "BRANCH_B", "ORG_ID", "SHIFT_ID", "CashWorld", "cash_world"]


def ident(label: str) -> str:
    return str(uuid5(NAMESPACE_URL, f"restaurantos.test/corte-ciego-001/{label}"))


OTHER_ORG = ident("organization-b")
OTHER_BRANCH = ident("branch-foreign")
LEGACY_READ = (
    "cash.shift.read", "cash.user_cut.read", "dashboard.read", "reports.sales.read",
    "payments.read", "cash.movement.read", "orders.read", "admin.manage",
)
NEW_READ = ("cash.user_cut.operational.read", "financial.data.read")

# Real F1-04 schema; synthetic data stays confined to the disposable fixture.
policy_revisions = models.blind_cash_policy_revisions
grants = models.financial_access_grants
grant_scopes = models.financial_access_grant_scopes
revocations = models.financial_access_grant_revocations


def grant_permission(session: Session, role_id: str, code: str) -> None:
    permission_id = session.scalar(sa.select(models.permissions.c.id).where(
        models.permissions.c.code == code
    ))
    if permission_id is None:
        permission_id = ident(f"permission:{code}")
        session.execute(models.permissions.insert().values(
            id=permission_id, code=code, description="Synthetic F1-03", created_at=NOW,
        ))
    exists = session.scalar(sa.select(models.role_permissions.c.role_id).where(
        models.role_permissions.c.role_id == role_id,
        models.role_permissions.c.permission_id == permission_id,
    ))
    if exists is None:
        session.execute(models.role_permissions.insert().values(
            role_id=role_id, permission_id=permission_id,
        ))


def _clone(session: Session, table: sa.Table, source: str, **changes: Any) -> None:
    row = dict(session.execute(sa.select(table).where(table.c.id == source)).mappings().one())
    session.execute(table.insert().values(**{**row, **changes}))


def _actor(session: Session, name: str, *, organization: str = ORG_ID) -> tuple[str, str]:
    user_id, role_id = ident(f"user:{name}"), ident(f"role:{name}")
    session.execute(models.users.insert().values(
        id=user_id, organization_id=organization, email=f"{name}@fixture.invalid",
        display_name=name, status="active", created_at=NOW, updated_at=NOW,
    ))
    session.execute(models.roles.insert().values(
        id=role_id, organization_id=organization, name=name, scope="organization", created_at=NOW,
    ))
    session.execute(models.user_roles.insert().values(
        user_id=user_id, role_id=role_id, branch_id=None,
    ))
    return user_id, role_id


@dataclass
class CashWorld:
    engine: sa.Engine
    sessions: sessionmaker[Session]
    client: TestClient
    actors: dict[str, str]
    roles: dict[str, str]
    cut_id: str
    payload: dict[str, str]

    def headers(self, actor: str, *, key: str | None = None) -> dict[str, str]:
        result = {"X-Actor-User-Id": self.actors[actor]}
        if key is not None:
            result["Idempotency-Key"] = key
        return result

    def revoke(self, subject: str, label: str) -> None:
        """Exercise the real F1-04 revocation command (subject retained for callers)."""
        from restaurant_os.financial_access import FinancialAccessService

        with self.sessions() as session:
            FinancialAccessService(session, ORG_ID).revoke(
                OWNER_ID, ident(f"grant:{label}"), f"fixture-revoke:{label}",
                {"reason": "Synthetic fixture revocation"},
            )

    def snapshot(self) -> str:
        """Compare business rows, excluding denial audit records by design."""
        with self.sessions() as session:
            rows = {
                table.name: sorted(
                    (dict(row) for row in session.execute(sa.select(table)).mappings()),
                    key=lambda row: str(row.get("id", "")),
                )
                for table in (
                    models.cash_shifts, models.cash_movements, models.payments,
                    models.user_cash_cuts, models.user_cash_cut_operations,
                    models.user_cash_cut_commands,
                )
            }
        return hashlib.sha256(json.dumps(rows, sort_keys=True, default=str).encode()).hexdigest()


@pytest.fixture
def cash_world() -> Iterator[CashWorld]:
    engine = sa.create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    actors, roles = {"owner": OWNER_ID, "cashier": CASHIER_ID}, {
        "owner": OWNER_ROLE_ID, "cashier": CASHIER_ROLE_ID,
    }
    with sessions() as session:
        _seed_cash_concept_scope(session)
        _clone(session, models.organizations, ORG_ID, id=OTHER_ORG, name="Other synthetic org")
        _clone(session, models.legal_entities, LEGAL_ID,
               id=ident("legal-b"), organization_id=OTHER_ORG)
        _clone(session, models.business_units, BUSINESS_UNIT_ID, id=ident("unit-b"),
               organization_id=OTHER_ORG, legal_entity_id=ident("legal-b"))
        _clone(session, models.branches, BRANCH_A, id=OTHER_BRANCH, organization_id=OTHER_ORG,
               legal_entity_id=ident("legal-b"), business_unit_id=ident("unit-b"))
        for name in ("leader", "chief_cashier", "administrator", "supervisor",
                     "delegate", "revoked", "accumulated", "foreign"):
            actors[name], roles[name] = _actor(
                session, name, organization=OTHER_ORG if name == "foreign" else ORG_ID,
            )
        for role in roles.values():
            for code in (*LEGACY_READ, *NEW_READ):
                grant_permission(session, role, code)
        for actor in ("cashier", "leader", "chief_cashier"):
            grant_permission(session, roles[actor], "cash.user_cut.capture")
        for actor in ("owner", "leader"):
            grant_permission(session, roles[actor], "cash.user_cut.finalize")
            grant_permission(session, roles[actor], "reports.operational.read")
        # Accumulated profiles are an adversarial fixture, NOT a migration recommendation.
        session.execute(models.user_roles.insert().values(
            user_id=actors["accumulated"], role_id=roles["administrator"], branch_id=BRANCH_A,
        ))
        session.execute(models.role_authority_grants.insert().values(
            role_id=roles["accumulated"], authority_kind="organization_all_permissions",
            created_at=NOW,
        ))
        _insert_shift(session)
        session.execute(models.customers.insert().values(
            id=ident("customer"), organization_id=ORG_ID, name="Synthetic customer",
            origin_branch_id=BRANCH_A, created_at=NOW, updated_at=NOW,
        ))
        for index, amount in enumerate((5_000, 7_000), start=1):
            session.execute(models.orders.insert().values(
                id=ident(f"order:{index}"), organization_id=ORG_ID, branch_id=BRANCH_A,
                cash_shift_id=SHIFT_ID, customer_id=ident("customer"),
                folio=f"F103-{index}", channel="POS", status="PAID", total_cents=amount,
                currency="MXN", order_type="takeout", created_at=NOW,
            ))
        session.execute(models.payments.insert().values(
            id=ident("payment"), organization_id=ORG_ID, branch_id=BRANCH_A,
            order_id=ident("order:1"), cash_shift_id=SHIFT_ID, method="cash",
            status="CONFIRMED", amount_cents=5_000, currency="MXN",
            confirmed_at=NOW + timedelta(minutes=10), created_at=NOW,
        ))
        session.execute(models.sales_operation_snapshots.insert().values(
            id=ident("sale"), organization_id=ORG_ID, branch_id=BRANCH_A,
            order_id=ident("order:1"), payment_id=ident("payment"), cash_shift_id=SHIFT_ID,
            register_code_snapshot="CAJA-01", folio_snapshot="F103-1",
            service_type_snapshot="takeout", currency="MXN", gross_cents=5_000,
            net_cents=5_000, discount_cents=0, courtesy_cents=0, tax_cents=0,
            quality_status="captured", confirmed_at=NOW + timedelta(minutes=10), created_at=NOW,
        ))
        _insert_movement(session, ident("movement"), "deposit", 1_500,
                         created_at=NOW + timedelta(minutes=15))
        payload = _closed_shift(session)
        for role in roles.values():
            grant_permission(session, role, "cash.user_cut.create")
        session.commit()
        # Establish historical DRAFT/COUNTED through real baseline commands BEFORE activation.
        service = UserCashCutService(session)
        cut = service.create(payload, "f103-setup-create", OWNER_ID)["cash_cut"]
        service.counted_cash(cut["id"], {"counted_cash_cents": 10_001, "version": 1},
                             "f103-setup-count", CASHIER_ID)
        for branch, org, cashier in (
            (BRANCH_B, ORG_ID, actors["leader"]),
            (OTHER_BRANCH, OTHER_ORG, actors["foreign"]),
        ):
            shift_id = ident(f"shift:{branch}")
            _clone(session, models.cash_shifts, SHIFT_ID, id=shift_id,
                   organization_id=org, branch_id=branch, cashier_user_id=cashier)
            _clone(session, models.user_cash_cuts, cut["id"], id=ident(f"cut:{branch}"),
                   organization_id=org, branch_id=branch, cash_shift_id=shift_id,
                   cashier_user_id=cashier)
        _clone(session, models.orders, ident("order:1"), id=ident("order-b"),
               branch_id=BRANCH_B, cash_shift_id=ident(f"shift:{BRANCH_B}"), folio="F103-B")
        _clone(session, models.payments, ident("payment"), id=ident("payment-b"),
               branch_id=BRANCH_B, order_id=ident("order-b"),
               cash_shift_id=ident(f"shift:{BRANCH_B}"))
        _clone(session, models.sales_operation_snapshots, ident("sale"), id=ident("sale-b"),
               branch_id=BRANCH_B, order_id=ident("order-b"), payment_id=ident("payment-b"),
               cash_shift_id=ident(f"shift:{BRANCH_B}"), folio_snapshot="F103-B")
        for branch in (BRANCH_A, BRANCH_B):
            session.execute(policy_revisions.insert().values(
                organization_id=ORG_ID, branch_id=branch, revision=1,
                manifest_digest=hashlib.sha256(b"synthetic-reviewed-actors").hexdigest(),
                minimum_api_version=2, minimum_client_version=2, minimum_gateway_version=2,
                event="activated", created_at=NOW,
            ))
        for subject, label, branch, dataset in (
            ("delegate", "cuts-a", BRANCH_A, "cash.cuts"),
            ("delegate", "sales-b", BRANCH_B, "sales"),
            ("revoked", "revoked-sales-a", BRANCH_A, "sales"),
            ("cashier", "cashier-prior-cuts-a", BRANCH_A, "cash.cuts"),
        ):
            grant_id = ident(f"grant:{label}")
            session.execute(grants.insert().values(
                id=grant_id, organization_id=ORG_ID, subject_user_id=actors[subject],
                issuer_user_id=OWNER_ID, issued_at=NOW, reason="F1-03 explicit fixture",
                authorization_version_at_issue=1,
            ))
            session.execute(grant_scopes.insert().values(
                organization_id=ORG_ID, grant_id=grant_id, branch_id=branch, dataset=dataset,
            ))
        session.execute(models.financial_owner_reviews.insert().values(
            organization_id=ORG_ID, user_id=OWNER_ID, authorization_version=1,
            manifest_digest=hashlib.sha256(b"synthetic-reviewed-owner").hexdigest(),
            approval_reference="Synthetic CC-D01/02 review only", reviewed_at=NOW,
        ))
        session.commit()

    app = create_app()

    def session_override() -> Iterator[Session]:
        with sessions() as session:
            yield session

    app.dependency_overrides[get_session] = session_override
    client = TestClient(app)
    world = CashWorld(engine, sessions, client, actors, roles, str(cut["id"]), payload)
    world.revoke("revoked", "revoked-sales-a")
    try:
        yield world
    finally:
        client.close()
        app.dependency_overrides.clear()
        engine.dispose()
