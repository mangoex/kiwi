"""TC-451/464: real migration, strict FK, append-only and guarded rollback."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import sqlalchemy as sa
from corte_ciego_storage import isolated_database, migrate, relation_names, seed_authority
from restaurant_os import models
from restaurant_os.financial_access import FinancialAccessService
from restaurant_os.financial_access_schema import CAPABILITIES
from sqlalchemy.orm import Session
from test_cash_concepts import BRANCH_A, CASHIER_ID, ORG_ID, OWNER_ID
from test_cash_ledger import NOW


@pytest.fixture(params=["sqlite", "postgresql"])
def authority_db(request: pytest.FixtureRequest) -> Iterator[sa.Engine]:
    yield from isolated_database(str(request.param))


def test_migration_adds_no_assignments_owner_or_policy_and_roundtrips(
    authority_db: sa.Engine,
) -> None:
    with authority_db.begin() as connection:
        assert connection.scalar(
            sa.select(sa.func.count())
            .select_from(models.permissions)
            .where(
                models.permissions.c.code.in_(CAPABILITIES),
            )
        ) == len(CAPABILITIES)
        assert (
            connection.scalar(sa.select(sa.func.count()).select_from(models.role_permissions)) == 0
        )
        for name in relation_names():
            assert (
                connection.scalar(
                    sa.select(sa.func.count()).select_from(models.metadata.tables[name])
                )
                == 0
            )
        migrate(connection, "downgrade")
        assert not set(relation_names()) & set(sa.inspect(connection).get_table_names())
        migrate(connection, "upgrade")


def test_all_authority_evidence_is_append_only_and_downgrade_preserves_it(
    authority_db: sa.Engine,
) -> None:
    grant = seed_authority(authority_db)
    with Session(authority_db) as session:
        FinancialAccessService(session, ORG_ID).revoke(
            OWNER_ID, grant, "revoke", {"reason": "Stop"}
        )
        session.execute(
            models.blind_cash_policy_revisions.insert().values(
                organization_id=ORG_ID,
                branch_id=BRANCH_A,
                revision=1,
                manifest_digest="a" * 64,
                minimum_api_version=2,
                minimum_client_version=2,
                minimum_gateway_version=2,
                event="prepared",
                created_at=NOW,
            )
        )
        session.commit()
    for name in relation_names():
        table = models.metadata.tables[name]
        column = next(iter(table.primary_key.columns))
        for statement in (table.update().values({column.name: column}), table.delete()):
            with authority_db.connect() as connection:
                with pytest.raises(sa.exc.DBAPIError, match="append-only"):
                    connection.execute(statement)
                connection.rollback()
    with authority_db.begin() as connection:
        with pytest.raises(RuntimeError, match="evidence exists"):
            migrate(connection, "downgrade")
        assert (
            connection.scalar(
                sa.select(sa.func.count()).select_from(models.financial_access_grants)
            )
            == 1
        )


def test_database_rejects_cross_organization_unknown_dataset_and_revocation_fk(
    authority_db: sa.Engine,
) -> None:
    grant = seed_authority(authority_db)
    with authority_db.begin() as connection:
        connection.execute(
            models.organizations.insert().values(
                id="other-org",
                name="Other",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
        connection.execute(
            models.users.insert().values(
                id="foreign-user",
                organization_id="other-org",
                email="foreign@fixture.invalid",
                display_name="Foreign",
                status="active",
                created_at=NOW,
                updated_at=NOW,
            )
        )
    invalid = [
        models.financial_access_grants.insert().values(
            id="cross-org",
            organization_id=ORG_ID,
            subject_user_id="foreign-user",
            issuer_user_id=OWNER_ID,
            issued_at=NOW,
            reason="invalid",
            authorization_version_at_issue=1,
        ),
        models.financial_access_grant_scopes.insert().values(
            organization_id="other-org",
            grant_id=grant,
            branch_id=BRANCH_A,
            dataset="sales",
        ),
        models.financial_access_grant_scopes.insert().values(
            organization_id=ORG_ID,
            grant_id=grant,
            branch_id=BRANCH_A,
            dataset="*",
        ),
        models.financial_access_grant_revocations.insert().values(
            organization_id=ORG_ID,
            grant_id=grant,
            revoked_by=CASHIER_ID,
            revoked_at=NOW,
            reason="invalid",
            command_id="no-command",
        ),
    ]
    for statement in invalid:
        with authority_db.connect() as connection:
            with pytest.raises(sa.exc.IntegrityError):
                connection.execute(statement)
            connection.rollback()
