"""Isolated PostgreSQL recovery, copy races and actual migration evidence."""

from __future__ import annotations

import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Barrier, Event
from uuid import uuid4

import pytest
import sqlalchemy as sa
from restaurant_os import models, purchase_commands
from restaurant_os.modifier_configuration import (
    copy_modifier_configuration,
    save_modifier_configuration,
)
from restaurant_os.operations import (
    BusinessError,
    confirm_purchase_document,
    create_purchase_document,
    create_purchase_presentation,
    create_supplier,
    discard_purchase_document,
    update_purchase_document,
)
from restaurant_os.purchase_workspace import preview_purchase
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, ORGANIZATION_ID, _seed
from test_purchase_workspace import _presentation, _purchase_payload
from test_workspace_compound_copy import SOURCE, TARGET


@pytest.fixture
def pg_engine(request):
    url = os.environ.get("SR_WORKSPACE_TEST_POSTGRES_URL")
    if not url:
        pytest.skip("SR_WORKSPACE_TEST_POSTGRES_URL is required; configured in CI")
    parsed = make_url(url)
    if (
        not parsed.drivername.startswith("postgresql")
        or parsed.host not in {"localhost", "127.0.0.1"}
        or not (parsed.database or "").startswith("sr_workspace_")
        or parsed.query
    ):
        raise RuntimeError("Workspace tests require an isolated local sr_workspace_* database")
    engine = sa.create_engine(
        url, connect_args={"options": "-c statement_timeout=15000 -c lock_timeout=10000"}
    )
    with engine.begin() as connection:
        connection.execute(sa.text("DROP SCHEMA public CASCADE"))
        connection.execute(sa.text("CREATE SCHEMA public"))
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    revision = (
        "0073_pos_catalog_appearance"
        if request.node.name in {
            "test_pos_catalog_appearance_postgres_default_and_downgrade_guard",
            "test_postgres_migration_history_guard_and_empty_roundtrip",
        }
        else "head"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "upgrade",
            revision,
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    with engine.begin() as connection:
        names = [
            name for name in sa.inspect(connection).get_table_names() if name != "alembic_version"
        ]
        quoted = ", ".join(connection.dialect.identifier_preparer.quote(name) for name in names)
        connection.execute(sa.text("TRUNCATE TABLE " + quoted + " RESTART IDENTITY CASCADE"))
    with Session(engine) as session:
        _seed(session)
    try:
        yield engine
    finally:
        engine.dispose()


def _purchase_seed(engine):
    with Session(engine) as session:
        supplier = create_supplier(
            session, {"code": "SR-PG", "commercial_name": "SR fixture"}, ADMIN_USER_ID
        )
        presentation = create_purchase_presentation(
            session, _presentation(supplier["id"]), ADMIN_USER_ID
        )
        return _purchase_payload(supplier["id"], presentation["id"])


def test_pos_catalog_appearance_postgres_default_and_downgrade_guard(pg_engine):
    with Session(pg_engine) as session:
        assert session.scalar(
            sa.select(models.branches.c.pos_catalog_visuals_enabled).limit(1)
        ) is True
        session.execute(
            sa.update(models.branches).values(pos_catalog_visuals_enabled=False)
        )
        session.commit()
    url = os.environ["SR_WORKSPACE_TEST_POSTGRES_URL"]
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "downgrade",
            "0072_purchase_create_commands",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert blocked.returncode != 0
    assert (
        "Cannot downgrade 0073 while hidden catalog visuals are configured"
        in blocked.stdout + blocked.stderr
    )


@pytest.mark.parametrize("same_key", [True, False])
def test_concurrent_creation_has_one_document_and_no_duplicate_audit(pg_engine, same_key):
    payload = _purchase_seed(pg_engine)
    barrier = Barrier(2)

    def writer(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                result = create_purchase_document(
                    session,
                    payload,
                    ADMIN_USER_ID,
                    "sr-pg-create-" + ("same" if same_key else str(index)),
                )
                return result["id"]
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, range(2)))
    if same_key:
        assert outcomes[0] == outcomes[1]
    else:
        assert outcomes.count("purchase_document_identity_conflict") == 1
    with Session(pg_engine) as session:
        for table, count in (
            (models.purchase_documents, 1),
            (models.purchase_document_lines, 3),
            (models.purchase_create_commands, 1),
        ):
            assert session.scalar(sa.select(sa.func.count()).select_from(table)) == count
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "purchase.created")
            )
            == 1
        )


@pytest.mark.parametrize("first_operation", ["create", "update"])
def test_creation_and_draft_edit_share_identity_lock_order(pg_engine, monkeypatch, first_operation):
    """Force both lock interleavings; no timing sleeps or probabilistic race starts."""
    payload = _purchase_seed(pg_engine)
    target_folio = "SR-PG-CREATE-EDIT"
    changed = {**payload, "folio": target_folio}
    creation = {
        **changed,
        "folio": f"  {target_folio}  ",
        "document_type": f" {payload['document_type'].upper()} ",
    }

    def financial_snapshot(session):
        return {
            table.name: sorted(
                [dict(row) for row in session.execute(sa.select(table)).mappings()],
                key=repr,
            )
            for table in (
                models.inventory_movements,
                models.inventory_cost_states,
                models.cash_movements,
                models.purchase_presentations,
                models.supplier_price_history,
            )
        }

    with Session(pg_engine) as session:
        draft = create_purchase_document(session, payload, ADMIN_USER_ID, "sr-pg-lock-order-seed")
        fingerprints = {
            "create": preview_purchase(session, creation, ADMIN_USER_ID)["context_fingerprint"],
            "update": preview_purchase(session, changed, ADMIN_USER_ID)["context_fingerprint"],
        }
        before_effects = financial_snapshot(session)

    first_locked = Event()
    second_requested = Event()
    original_lock = purchase_commands._acquire_idempotency_lock

    def interleaved_lock(session, namespace, key):
        if namespace != "purchase-document-identity":
            return original_lock(session, namespace, key)
        if session.info["race_operation"] == first_operation:
            original_lock(session, namespace, key)
            first_locked.set()
            assert second_requested.wait(timeout=10), "Second writer never requested identity"
        else:
            second_requested.set()
            original_lock(session, namespace, key)

    def write(operation):
        with Session(pg_engine) as session:
            session.info["race_operation"] = operation
            if operation != first_operation:
                assert first_locked.wait(timeout=10), "First writer never acquired identity"
            if operation == "create":
                return create_purchase_document(
                    session, creation, ADMIN_USER_ID, "sr-pg-lock-order-create",
                    fingerprints["create"],
                )
            return update_purchase_document(
                session, draft["id"], {**changed, "expected_version": 1}, ADMIN_USER_ID,
                "sr-pg-lock-order-update", fingerprints["update"],
            )

    def race(operation):
        try:
            return write(operation)
        except BusinessError as error:
            return error.code

    monkeypatch.setattr(purchase_commands, "_acquire_idempotency_lock", interleaved_lock)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {operation: pool.submit(race, operation) for operation in ("create", "update")}
        results = {operation: future.result(timeout=30) for operation, future in futures.items()}
    monkeypatch.setattr(purchase_commands, "_acquire_idempotency_lock", original_lock)
    second_operation = "update" if first_operation == "create" else "create"
    assert isinstance(results[first_operation], dict)
    assert results[second_operation] == "purchase_document_identity_conflict"

    def command_snapshot(session):
        return {
            table.name: sorted(
                [dict(row) for row in session.execute(sa.select(table)).mappings()], key=repr,
            )
            for table in (
                models.purchase_documents,
                models.purchase_document_lines,
                models.purchase_create_commands,
                models.purchase_update_commands,
                models.audit_events,
            )
        }

    with Session(pg_engine) as session:
        final = command_snapshot(session)
        assert financial_snapshot(session) == before_effects
        documents = final["purchase_documents"]
        assert len(documents) == (2 if first_operation == "create" else 1)
        target = [row for row in documents if row["folio"] == target_folio]
        assert len(target) == 1 and target[0]["status"] == "draft"
        assert target[0]["version"] == (1 if first_operation == "create" else 2)
        assert len(final["purchase_document_lines"]) == 3 * len(documents)
        assert len(final["purchase_create_commands"]) == len(documents)
        assert len(final["purchase_update_commands"]) == int(first_operation == "update")
        for action, count in (
            ("purchase.created", len(documents)),
            ("purchase.updated", int(first_operation == "update")),
        ):
            assert sum(row["action"] == action for row in final["audit_events"]) == count
        original = next(row for row in documents if row["id"] == draft["id"])
        assert original["version"] == (1 if first_operation == "create" else 2)
        expected_folio = payload["folio"] if first_operation == "create" else target_folio
        assert original["folio"] == expected_folio

    assert write(first_operation) == results[first_operation]
    with Session(pg_engine) as session:
        assert command_snapshot(session) == final
        assert financial_snapshot(session) == before_effects


def test_draft_edit_and_confirmation_have_one_reviewed_version_winner(pg_engine):
    payload = _purchase_seed(pg_engine)
    with Session(pg_engine) as session:
        created = create_purchase_document(
            session, payload, ADMIN_USER_ID, "sr-pg-draft-race-create"
        )
        changed = {**payload, "folio": "SR-PG-EDITED", "lines": [payload["lines"][0]]}
        fingerprint = preview_purchase(session, changed, ADMIN_USER_ID)["context_fingerprint"]
    barrier = Barrier(2)

    def edit():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return "updated", update_purchase_document(
                    session,
                    created["id"],
                    {**changed, "expected_version": 1},
                    ADMIN_USER_ID,
                    "sr-pg-draft-race-edit",
                    fingerprint,
                )
            except BusinessError as error:
                return error.code, None

    def confirm():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return "confirmed", confirm_purchase_document(
                    session,
                    created["id"],
                    "sr-pg-draft-race-confirm",
                    actor_user_id=ADMIN_USER_ID,
                    confirmation_context={"branch_id": BRANCH_ID, "expected_version": 1},
                )
            except BusinessError as error:
                return error.code, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(edit), pool.submit(confirm)]
        results = [future.result() for future in outcomes]
    codes = {result[0] for result in results}
    assert len(codes & {"updated", "confirmed"}) == 1
    assert codes <= {"updated", "confirmed", "purchase_version_conflict", "purchase_not_editable"}
    with Session(pg_engine) as session:
        document = session.execute(
            sa.select(models.purchase_documents).where(
                models.purchase_documents.c.id == created["id"]
            )
        ).mappings().one()
        effects = session.scalar(
            sa.select(sa.func.count()).select_from(models.inventory_movements).where(
                models.inventory_movements.c.source_id == created["id"]
            )
        )
        updates = session.scalar(
            sa.select(sa.func.count()).select_from(models.purchase_update_commands).where(
                models.purchase_update_commands.c.purchase_id == created["id"]
            )
        )
        if document["status"] == "confirmed":
            assert document["version"] == 1 and effects == 3 and updates == 0
        else:
            assert document["status"] == "draft"
            assert document["version"] == 2 and effects == 0 and updates == 1


def test_draft_edit_and_discard_have_one_reviewed_version_winner(pg_engine):
    payload = _purchase_seed(pg_engine)
    with Session(pg_engine) as session:
        created = create_purchase_document(
            session, payload, ADMIN_USER_ID, "sr-pg-draft-discard-race-create"
        )
        changed = {**payload, "folio": "SR-PG-DISCARD-EDITED"}
        fingerprint = preview_purchase(session, changed, ADMIN_USER_ID)["context_fingerprint"]
    barrier = Barrier(2)

    def edit():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return "updated", update_purchase_document(
                    session,
                    created["id"],
                    {**changed, "expected_version": 1},
                    ADMIN_USER_ID,
                    "sr-pg-draft-discard-race-edit",
                    fingerprint,
                )
            except BusinessError as error:
                return error.code, None

    def discard():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return "cancelled", discard_purchase_document(
                    session,
                    created["id"],
                    "Concurrent discard",
                    ADMIN_USER_ID,
                    1,
                )
            except BusinessError as error:
                return error.code, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(edit), pool.submit(discard)]
        results = [future.result() for future in outcomes]
    codes = {result[0] for result in results}
    assert len(codes & {"updated", "cancelled"}) == 1
    assert codes <= {"updated", "cancelled", "purchase_version_conflict", "purchase_not_editable"}
    with Session(pg_engine) as session:
        document = session.execute(
            sa.select(models.purchase_documents).where(
                models.purchase_documents.c.id == created["id"]
            )
        ).mappings().one()
        effects = session.scalar(
            sa.select(sa.func.count()).select_from(models.inventory_movements).where(
                models.inventory_movements.c.source_id == created["id"]
            )
        )
        updates = session.scalar(
            sa.select(sa.func.count()).select_from(models.purchase_update_commands).where(
                models.purchase_update_commands.c.purchase_id == created["id"]
            )
        )
        assert effects == 0
        if document["status"] == "cancelled":
            assert document["version"] == 1 and updates == 0
        else:
            assert document["status"] == "draft"
            assert document["version"] == 2 and updates == 1


def test_confirmation_and_draft_discard_cannot_cross_intents(pg_engine):
    payload = _purchase_seed(pg_engine)
    with Session(pg_engine) as session:
        created = create_purchase_document(
            session, payload, ADMIN_USER_ID, "sr-pg-confirm-discard-create"
        )
    barrier = Barrier(2)

    def confirm():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return "confirmed", confirm_purchase_document(
                    session,
                    created["id"],
                    "sr-pg-confirm-discard-confirm",
                    actor_user_id=ADMIN_USER_ID,
                    confirmation_context={"branch_id": BRANCH_ID, "expected_version": 1},
                )
            except BusinessError as error:
                return error.code, None

    def discard():
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return "cancelled", discard_purchase_document(
                    session,
                    created["id"],
                    "Concurrent stale row discard",
                    ADMIN_USER_ID,
                    1,
                )
            except BusinessError as error:
                return error.code, None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = [pool.submit(confirm), pool.submit(discard)]
        results = [future.result() for future in outcomes]
    codes = {result[0] for result in results}
    assert len(codes & {"confirmed", "cancelled"}) == 1
    assert codes <= {
        "confirmed",
        "cancelled",
        "purchase_state_conflict",
        "purchase_not_confirmable",
    }
    with Session(pg_engine) as session:
        document = session.execute(
            sa.select(models.purchase_documents).where(
                models.purchase_documents.c.id == created["id"]
            )
        ).mappings().one()
        effects = session.scalar(
            sa.select(sa.func.count()).select_from(models.inventory_movements).where(
                models.inventory_movements.c.source_id == created["id"]
            )
        )
        if document["status"] == "confirmed":
            assert effects == 3
        else:
            assert document["status"] == "cancelled"
            assert effects == 0


@pytest.mark.parametrize("guard", ["receipt", "version"])
def test_purchase_draft_edit_postgres_downgrade_guards_history(pg_engine, guard):
    payload = _purchase_seed(pg_engine)
    with Session(pg_engine) as session:
        created = create_purchase_document(
            session, payload, ADMIN_USER_ID, f"sr-pg-draft-migration-{guard}"
        )
        if guard == "receipt":
            changed = {**payload, "folio": "SR-PG-MIGRATION-EDITED"}
            fingerprint = preview_purchase(session, changed, ADMIN_USER_ID)[
                "context_fingerprint"
            ]
            update_purchase_document(
                session,
                created["id"],
                {**changed, "expected_version": 1},
                ADMIN_USER_ID,
                "sr-pg-draft-migration-update",
                fingerprint,
            )
        else:
            session.execute(
                sa.update(models.purchase_documents)
                .where(models.purchase_documents.c.id == created["id"])
                .values(version=2)
            )
            session.commit()
    url = os.environ["SR_WORKSPACE_TEST_POSTGRES_URL"]
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "downgrade",
            "0103_blind_cash_phases_2_6",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert blocked.returncode != 0
    expected = (
        "purchase edit receipts exist"
        if guard == "receipt"
        else "edited purchase drafts exist"
    )
    assert expected in blocked.stdout + blocked.stderr


def test_purchase_delivery_name_persists_and_blocks_postgres_data_loss(pg_engine):
    payload = {**_purchase_seed(pg_engine), "delivered_by_name": "  Ana López  "}
    with Session(pg_engine) as session:
        created = create_purchase_document(
            session, payload, ADMIN_USER_ID, "sr-pg-delivery-name"
        )
        assert created["delivered_by_name"] == "Ana López"
        assert session.scalar(
            sa.select(models.purchase_documents.c.delivered_by_name).where(
                models.purchase_documents.c.id == created["id"]
            )
        ) == "Ana López"

    url = os.environ["SR_WORKSPACE_TEST_POSTGRES_URL"]
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)
    blocked = subprocess.run(
        [
            sys.executable,
            "-m",
            "alembic",
            "-c",
            "alembic.ini",
            "downgrade",
            "0093_whatsapp_order_channel",
        ],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert blocked.returncode != 0
    assert "0094 downgrade blocked: purchase delivery names exist" in (
        blocked.stdout + blocked.stderr
    )


def _copy_seed(engine):
    with Session(engine) as session:
        source = dict(
            session.execute(sa.select(models.products).where(models.products.c.id == SOURCE))
            .mappings()
            .one()
        )
        session.execute(
            models.products.insert().values(**{**source, "id": TARGET, "sku": "SR-PG-TARGET"})
        )
        session.commit()
        return save_modifier_configuration(
            session,
            ADMIN_USER_ID,
            SOURCE,
            {
                "expected_version": 0,
                "groups": [
                    {
                        "name": "Preparación",
                        "minimum_selections": 0,
                        "maximum_selections": 1,
                        "options": [
                            {
                                "name": "Sin sal",
                                "effect_type": "instruction",
                                "price_delta_cents": 0,
                            }
                        ],
                    }
                ],
            },
            "sr-pg-source",
        )


def test_concurrent_copy_and_target_writer_have_one_version_winner(pg_engine):
    _copy_seed(pg_engine)
    barrier = Barrier(2)

    def writer(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                if index == 0:
                    copy_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        TARGET,
                        {
                            "source_product_id": SOURCE,
                            "expected_source_version": 1,
                            "expected_target_version": 0,
                        },
                        "sr-pg-copy",
                    )
                else:
                    save_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        TARGET,
                        {"expected_version": 0, "groups": []},
                        "sr-pg-target",
                    )
                return "applied"
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(writer, range(2))) == [
            "applied",
            "modifier_configuration_version_conflict",
        ]
    with Session(pg_engine) as session:
        assert (
            session.scalar(
                sa.select(models.product_modifier_configurations.c.version).where(
                    models.product_modifier_configurations.c.product_id == TARGET
                )
            )
            == 1
        )


def test_copy_source_change_is_serialized_or_rejected_without_mixture(pg_engine):
    _copy_seed(pg_engine)
    barrier = Barrier(2)

    def writer(index):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                if index == 0:
                    return copy_modifier_configuration(
                        session,
                        ADMIN_USER_ID,
                        TARGET,
                        {
                            "source_product_id": SOURCE,
                            "expected_source_version": 1,
                            "expected_target_version": 0,
                        },
                        "sr-pg-copy-source-race",
                    )["groups"]
                save_modifier_configuration(
                    session,
                    ADMIN_USER_ID,
                    SOURCE,
                    {"expected_version": 1, "groups": []},
                    "sr-pg-change-source",
                )
                return "source-applied"
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, range(2)))
    assert outcomes[1] == "source-applied"
    if isinstance(outcomes[0], list):
        assert [group["name"] for group in outcomes[0]] == ["Preparación"]
    else:
        assert outcomes[0] == "modifier_copy_source_version_conflict"
        with Session(pg_engine) as session:
            assert (
                session.scalar(
                    sa.select(sa.func.count())
                    .select_from(models.modifier_groups)
                    .where(models.modifier_groups.c.product_id == TARGET)
                )
                == 0
            )


def test_postgres_migration_history_guard_and_empty_roundtrip(pg_engine):
    url = os.environ["SR_WORKSPACE_TEST_POSTGRES_URL"]
    env = {**os.environ, "RESTAURANTOS_DATABASE_URL": url}
    env.pop("DATABASE_URL", None)

    def migrate(command, revision):
        return subprocess.run(
            [sys.executable, "-m", "alembic", "-c", "alembic.ini", command, revision],
            cwd=Path(__file__).resolve().parents[1],
            env=env,
            capture_output=True,
            text=True,
            timeout=90,
        )

    assert migrate("downgrade", "0071_classification_rollout").returncode == 0
    assert migrate("upgrade", "0072_purchase_create_commands").returncode == 0
    payload = _purchase_seed(pg_engine)
    # Exercise the 0072 guard with records valid for that revision, rather than a newer service
    # that writes columns introduced after 0072 (for example delivered_by_name in 0094).
    historical = sa.MetaData()
    document = sa.Table("purchase_documents", historical, autoload_with=pg_engine)
    command = sa.Table("purchase_create_commands", historical, autoload_with=pg_engine)
    purchase_id, command_id, now = str(uuid4()), str(uuid4()), datetime.now(timezone.utc)
    with pg_engine.begin() as connection:
        connection.execute(document.insert().values(
            id=purchase_id, organization_id=ORGANIZATION_ID, branch_id=BRANCH_ID,
            supplier_id=payload["supplier_id"], document_type="note", folio="SR-HISTORY-0072",
            document_date=now, subtotal=100, discount_total=0, tax_total=0, freight_total=0,
            total=100, payment_method="other", paid_from_cash=False, status="draft",
            created_by=ADMIN_USER_ID, created_at=now,
        ))
        connection.execute(command.insert().values(
            id=command_id, organization_id=ORGANIZATION_ID, branch_id=BRANCH_ID,
            actor_user_id=ADMIN_USER_ID, idempotency_key="sr-pg-migration-history",
            request_hash="7" * 64, purchase_id=purchase_id,
            result={"id": purchase_id}, created_at=now,
        ))
        before = {
            table.name: list(connection.execute(sa.select(table)).mappings())
            for table in (document, command)
        }
    blocked = migrate("downgrade", "0071_classification_rollout")
    assert blocked.returncode != 0
    assert (
        "Cannot downgrade 0072 while purchase creation history exists"
        in blocked.stdout + blocked.stderr
    )
    with pg_engine.connect() as connection:
        assert connection.scalar(sa.text("SELECT version_num FROM alembic_version")) == (
            "0072_purchase_create_commands"
        )
        for table in (document, command):
            assert list(connection.execute(sa.select(table)).mappings()) == before[table.name]


def test_reviewed_creation_serializes_with_catalog_writer(pg_engine):
    from restaurant_os.operations import update_purchase_presentation
    from restaurant_os.purchase_workspace import preview_purchase

    payload = _purchase_seed(pg_engine)
    presentation_id = payload["lines"][0]["presentation_id"]
    with Session(pg_engine) as session:
        fingerprint = preview_purchase(session, payload, ADMIN_USER_ID)["context_fingerprint"]
    barrier = Barrier(2)

    def writer(kind):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            if kind == "catalog":
                update_purchase_presentation(
                    session, presentation_id, {"base_unit_yield": "10"}, ADMIN_USER_ID
                )
                return "catalog-updated"
            try:
                purchase = create_purchase_document(
                    session, payload, ADMIN_USER_ID, "sr-reviewed-pg-race", fingerprint
                )
                assert str(purchase["lines"][0]["base_quantity"]) == "10.000000"
                return "created-reviewed"
            except BusinessError as error:
                assert error.code == "purchase_preview_changed"
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, ["catalog", "purchase"]))
    assert outcomes[0] == "catalog-updated"
    with Session(pg_engine) as session:
        expected = 1 if outcomes[1] == "created-reviewed" else 0
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.purchase_documents))
            == expected
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.purchase_create_commands))
            == expected
        )


def test_keyed_creator_races_legacy_identity_without_500(pg_engine):
    payload = _purchase_seed(pg_engine)
    barrier = Barrier(2)

    def writer(key):
        with Session(pg_engine) as session:
            barrier.wait(timeout=10)
            try:
                return create_purchase_document(session, payload, ADMIN_USER_ID, key)["id"]
            except BusinessError as error:
                return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(writer, ["sr-keyed-vs-legacy", None]))
    assert outcomes.count("purchase_document_identity_conflict") == 1
    with Session(pg_engine) as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.purchase_documents)) == 1
        )
