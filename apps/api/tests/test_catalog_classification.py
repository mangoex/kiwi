"""CAT-CLASS-001 corporate category command regression tests."""

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.catalog_classification import category_command
from restaurant_os.operations import (
    AuthorizationError,
    BusinessError,
    create_category,
    update_category,
)
from test_admin_catalog import _seed_admin_catalog_scope
from test_cash_concepts import CASHIER_ID, OWNER_ID
from test_cash_ledger import _new_session


def test_branch_catalog_manager_cannot_create_corporate_category():
    engine, session = _new_session()
    _seed_admin_catalog_scope(session)
    session.commit()
    with pytest.raises(AuthorizationError):
        create_category(session, "FORBIDDEN", actor_user_id=CASHIER_ID)


def test_create_returns_explicit_pending_classification_and_version():
    engine, session = _new_session()
    _seed_admin_catalog_scope(session)
    session.commit()
    result = create_category(session, "PENDING", actor_user_id=OWNER_ID)
    assert result["classification_code"] is None
    assert result["configuration_version"] == 1
    assert session.scalar(sa.select(sa.func.count()).select_from(models.product_categories)) > 0


@pytest.fixture
def session():
    engine, value = _new_session()
    _seed_admin_catalog_scope(value)
    value.commit()
    yield value
    value.close()
    engine.dispose()


def test_replay_cas_legacy_and_hash_conflict(session):
    payload = {"name": "CER VEZA", "classification_code": "drinks", "expected_version": 0}
    created = category_command(session, OWNER_ID, payload, idempotency_key="create")
    assert category_command(session, OWNER_ID, payload, idempotency_key="create") == created
    with pytest.raises(BusinessError, match="Key used"):
        category_command(session, OWNER_ID, {**payload, "name": "OTHER"}, idempotency_key="create")
    updated = update_category(session, created["id"], name="CERVEZA", actor_user_id=OWNER_ID)
    assert updated["configuration_version"] == 2
    assert updated["classification_code"] == "drinks"
    with pytest.raises(BusinessError, match="Category has changed"):
        category_command(
            session,
            OWNER_ID,
            {"classification_code": "food", "expected_version": 1},
            category_id=created["id"],
            idempotency_key="stale",
        )
    assert (
        session.scalar(
            sa.select(sa.func.count()).select_from(models.category_configuration_commands)
        )
        == 2
    )


def test_failure_between_write_audit_and_command_rolls_back(session, monkeypatch):
    from restaurant_os import catalog_classification

    created = create_category(session, "ROLLBACK", actor_user_id=OWNER_ID)
    before = session.scalar(sa.select(sa.func.count()).select_from(models.audit_events))

    def fail(*args, **kwargs):
        raise RuntimeError("injected audit failure")

    monkeypatch.setattr(catalog_classification, "_audit", fail)
    with pytest.raises(RuntimeError, match="injected"):
        category_command(
            session,
            OWNER_ID,
            {"classification_code": "food", "expected_version": 1},
            category_id=created["id"],
            idempotency_key="failed",
        )
    row = (
        session.execute(
            sa.select(models.product_categories).where(
                models.product_categories.c.id == created["id"]
            )
        )
        .mappings()
        .one()
    )
    assert row["configuration_version"] == 1 and row["classification_code"] is None
    assert session.scalar(sa.select(sa.func.count()).select_from(models.audit_events)) == before
    assert (
        session.scalar(
            sa.select(sa.func.count()).select_from(models.category_configuration_commands)
        )
        == 1
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"classification_code": "unknown", "expected_version": 0},
        {"classification_code": [], "expected_version": 0},
        {"classification_code": "food", "expected_version": True},
        {"classification_code": "food", "expected_version": 0.5},
        {"classification_code": "food", "expected_version": -1},
        {"organization_id": "foreign"},
        {"station": "drinks"},
    ],
)
def test_hostile_payload_rejected_without_mutation(session, payload):
    before = session.scalar(sa.select(sa.func.count()).select_from(models.product_categories))
    with pytest.raises(BusinessError):
        category_command(session, OWNER_ID, {"name": "INVALID", **payload}, idempotency_key="bad")
    assert (
        session.scalar(sa.select(sa.func.count()).select_from(models.product_categories)) == before
    )


def test_replay_rechecks_revoked_authority(session):
    payload = {"name": "REPLAY", "expected_version": 0, "classification_code": "food"}
    category_command(session, OWNER_ID, payload, idempotency_key="revoked")
    session.execute(
        models.users.update().where(models.users.c.id == OWNER_ID).values(status="inactive")
    )
    session.commit()
    with pytest.raises(AuthorizationError):
        category_command(session, OWNER_ID, payload, idempotency_key="revoked")


def test_mapping_preserves_historical_name_when_omitted(session):
    from test_admin_catalog import CATEGORY_A

    before = session.scalar(
        sa.select(models.product_categories.c.name).where(
            models.product_categories.c.id == CATEGORY_A
        )
    )
    result = category_command(
        session,
        OWNER_ID,
        {"classification_code": "drinks", "expected_version": 1},
        category_id=CATEGORY_A,
        idempotency_key="historical",
    )
    assert result["name"] == before
    assert result["classification_code"] == "drinks"


def test_foreign_organization_actor_and_category_cannot_cross_scope(session):
    from restaurant_os.operations import NotFoundError
    from test_cash_ledger import NOW

    session.execute(
        models.organizations.insert().values(
            id="foreign-org", name="Foreign", status="active", created_at=NOW, updated_at=NOW
        )
    )
    session.execute(
        models.users.insert().values(
            id="foreign-actor",
            organization_id="foreign-org",
            email="foreign@example.test",
            display_name="Foreign",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.roles.insert().values(
            id="foreign-role",
            organization_id="foreign-org",
            name="Owner",
            scope="organization",
            created_at=NOW,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id="foreign-actor", role_id="foreign-role", branch_id=None
        )
    )
    session.execute(
        models.role_authority_grants.insert().values(
            role_id="foreign-role", authority_kind="organization_all_permissions", created_at=NOW
        )
    )
    session.execute(
        models.product_categories.insert().values(
            id="foreign-category",
            organization_id="foreign-org",
            name="FOREIGN",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.commit()
    payload = {"classification_code": "food", "expected_version": 1}
    with pytest.raises(AuthorizationError):
        category_command(
            session,
            "foreign-actor",
            payload,
            category_id="foreign-category",
            idempotency_key="foreign",
        )
    with pytest.raises(NotFoundError):
        category_command(
            session, OWNER_ID, payload, category_id="foreign-category", idempotency_key="foreign"
        )
    assert (
        session.scalar(
            sa.select(models.product_categories.c.configuration_version).where(
                models.product_categories.c.id == "foreign-category"
            )
        )
        == 1
    )


@pytest.mark.parametrize("writer", ["product", "legacy_import", "excel"])
def test_legacy_category_writers_are_audited_and_cannot_bypass_preparation(
    session, tmp_path, monkeypatch, writer
):
    from test_cash_ledger import BRANCH_A, NOW
    from test_catalog_classification_rollout import _classify, _prepare

    def write(name):
        if writer == "product":
            from restaurant_os.operations import _get_or_create_category

            return _get_or_create_category(session, name, NOW, OWNER_ID)
        if writer == "legacy_import":
            from restaurant_os.legacy_import import _ensure_category

            return _ensure_category(session, name, OWNER_ID)
        import pandas as pd
        from restaurant_os.real_catalog_loader import load_real_catalog_from_excels

        (tmp_path / "PRODUCTOS.XLS").touch()
        monkeypatch.setattr(
            pd,
            "read_excel",
            lambda *args, **kwargs: pd.DataFrame(
                [
                    {
                        "CLAVE": "99999",
                        "DESCRIPCION": "SYNTHETIC",
                        "GRUPODEPRODUCTOS": name,
                        "PRECIO": 10,
                    }
                ]
            ),
        )
        return load_real_catalog_from_excels(
            session,
            str(tmp_path),
            branch_id=BRANCH_A,
            import_customers=False,
            actor_user_id=OWNER_ID,
        )

    write("WRITER LEGACY")
    session.commit()
    row = (
        session.execute(
            sa.select(models.product_categories).where(
                models.product_categories.c.name == "WRITER LEGACY"
            )
        )
        .mappings()
        .one()
    )
    assert row["configuration_version"] == 1 and row["classification_code"] is None
    assert (
        session.scalar(
            sa.select(sa.func.count())
            .select_from(models.audit_events)
            .where(
                models.audit_events.c.entity_id == row["id"],
                models.audit_events.c.action == "category.created",
            )
        )
        == 1
    )
    _classify(session)
    _prepare(session)
    with pytest.raises(BusinessError, match="requires classification"):
        write("WRITER PREPARING")
    assert (
        session.scalar(
            sa.select(models.product_categories.c.id).where(
                models.product_categories.c.name == "WRITER PREPARING"
            )
        )
        is None
    )
