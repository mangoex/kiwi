"""PCO-005A request/decision stays outside immutable operational history."""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    AuthorizationError,
    BusinessError,
    apply_order_reopen_request,
    count_pending_orders,
    create_order_reopen_request,
    decide_order_reopen_request,
    get_order_detail,
    list_order_accounts,
    list_order_reopen_requests,
)
from test_cash_concepts import BRANCH_B, OWNER_ID
from test_cash_ledger import (
    BRANCH_A,
    CASHIER_ID,
    CASHIER_ROLE_ID,
    NOW,
    ORG_ID,
    SHIFT_ID,
    _new_session,
)

CHIEF_ID = "018f6f73-2d0a-74f0-8f1c-000000009510"
CHIEF_ROLE_ID = "018f6f73-2d0a-74f0-8f1c-000000009511"


def _actors(session):
    session.execute(
        models.roles.insert().values(
            id=CHIEF_ROLE_ID,
            organization_id=ORG_ID,
            name="Cajero jefe",
            scope="branch",
            created_at=NOW,
        )
    )
    session.execute(
        models.users.insert().values(
            id=CHIEF_ID,
            organization_id=ORG_ID,
            email="chief@example.test",
            display_name="Cajero jefe",
            status="active",
            created_at=NOW,
            updated_at=NOW,
        )
    )
    session.execute(
        models.user_roles.insert().values(
            user_id=CHIEF_ID,
            role_id=CHIEF_ROLE_ID,
            branch_id=BRANCH_A,
        )
    )
    permission_ids = {
        "orders.read": "p-pco005-read",
        "orders.reopen.request": "p-pco005-request",
        "orders.reopen.authorize": "p-pco005-authorize",
    }
    session.execute(
        models.permissions.insert(),
        [
            {"id": permission_id, "code": code, "description": code, "created_at": NOW}
            for code, permission_id in permission_ids.items()
        ],
    )
    session.execute(
        models.role_permissions.insert(),
        [
            {"role_id": CASHIER_ROLE_ID, "permission_id": permission_ids["orders.read"]},
            {"role_id": CHIEF_ROLE_ID, "permission_id": permission_ids["orders.read"]},
            {
                "role_id": CHIEF_ROLE_ID,
                "permission_id": permission_ids["orders.reopen.request"],
            },
        ],
    )
    session.commit()


def _order(session, number: int = 1):
    order_id = f"018f6f73-2d0a-74f0-8f1c-{9500 + number:012d}"
    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            cash_shift_id=SHIFT_ID,
            customer_id=None,
            customer_snapshot={"name": f"Cliente privado {number}"},
            delivery_address_snapshot=None,
            folio=f"PCO005-{number}",
            channel="POS",
            status="CLOSED",
            total_cents=500,
            currency="MXN",
            owner_name=None,
            order_type="takeout",
            payment_method_intent=None,
            version=1,
            created_at=NOW,
            accepted_at=NOW,
        )
    )
    session.execute(
        models.payments.insert().values(
            id=f"018f6f73-2d0a-74f0-8f1c-{9600 + number:012d}",
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            order_id=order_id,
            cash_shift_id=SHIFT_ID,
            method="cash",
            status="CONFIRMED",
            amount_cents=500,
            currency="MXN",
            confirmed_at=NOW,
            created_at=NOW,
        )
    )
    session.commit()
    return order_id


def _pending_order(session, number: int, *, status: str = "PENDING") -> str:
    order_id = f"018f6f73-2d0a-74f0-8f1c-{9700 + number:012d}"
    session.execute(
        models.orders.insert().values(
            id=order_id,
            organization_id=ORG_ID,
            branch_id=BRANCH_A,
            cash_shift_id=SHIFT_ID,
            customer_id=None,
            customer_snapshot={"name": f"Pendiente {number}"},
            delivery_address_snapshot=None,
            folio=f"PENDING-{number}",
            channel="PUBLIC_INTENT",
            status=status,
            total_cents=500,
            currency="MXN",
            owner_name=None,
            order_type="takeout",
            payment_method_intent="cash",
            version=1,
            created_at=NOW,
            accepted_at=NOW if status != "PENDING" else None,
        )
    )
    session.commit()
    return order_id


def test_pending_order_count_is_exact_and_branch_scoped() -> None:
    engine, session = _new_session()
    try:
        _actors(session)
        first = _pending_order(session, 1)
        _pending_order(session, 2)
        _pending_order(session, 3, status="ACCEPTED")

        assert count_pending_orders(session, BRANCH_A, CASHIER_ID) == {"count": 2}

        session.execute(
            models.orders.update().where(models.orders.c.id == first).values(status="ACCEPTED")
        )
        session.commit()
        assert count_pending_orders(session, BRANCH_A, CASHIER_ID) == {"count": 1}

        with pytest.raises(AuthorizationError):
            count_pending_orders(session, BRANCH_B, CASHIER_ID)
    finally:
        session.close()
        engine.dispose()


def test_request_replay_decision_and_apply_do_not_mutate_order_or_payment():
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        before = dict(
            session.execute(models.orders.select().where(models.orders.c.id == order_id))
            .mappings()
            .one()
        )
        request = create_order_reopen_request(
            session,
            order_id,
            {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]},
            "request-key-0001",
            CHIEF_ID,
        )
        replay = create_order_reopen_request(
            session,
            order_id,
            {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]},
            "request-key-0001",
            CHIEF_ID,
        )
        assert replay["id"] == request["id"]
        approved = decide_order_reopen_request(
            session,
            request["id"],
            "APPROVED",
            {"decision_reason": "Autoriza revisión documentada"},
            "approve-key-0001",
            OWNER_ID,
        )
        assert approved["status"] == "APPROVED"
        with pytest.raises(BusinessError, match="Compensating"):
            apply_order_reopen_request(session, request["id"], OWNER_ID)
        assert (
            dict(
                session.execute(models.orders.select().where(models.orders.c.id == order_id))
                .mappings()
                .one()
            )
            == before
        )
    finally:
        session.close()
        engine.dispose()


def test_accounts_cursor_is_bound_to_filters_and_authority_precedes_replay():
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        page = list_order_accounts(session, {"branch_id": BRANCH_A, "limit": 1}, CASHIER_ID)
        assert page["items"][0]["id"] == order_id
        with pytest.raises(BusinessError) as invalid:
            list_order_accounts(
                session, {"branch_id": BRANCH_A, "limit": 1, "cursor": "not-a-cursor"}, CASHIER_ID
            )
        assert invalid.value.code == "order_accounts_cursor_invalid"
        create_order_reopen_request(
            session,
            order_id,
            {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]},
            "request-key-0001",
            CHIEF_ID,
        )
        with pytest.raises(AuthorizationError):
            create_order_reopen_request(
                session,
                order_id,
                {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]},
                "request-key-0001",
                "unknown",
            )
    finally:
        session.close()
        engine.dispose()


def test_accounts_filters_snapshot_search_and_cursor_are_authoritative():
    engine, session = _new_session()
    try:
        _actors(session)
        first = _order(session, 1)
        second = _order(session, 2)
        page = list_order_accounts(
            session,
            {
                "branch_id": BRANCH_A,
                "from_utc": "2026-08-11T00:00:00+00:00",
                "to_utc": "2026-08-13T00:00:00+00:00",
                "cash_shift_id": SHIFT_ID,
                "register_code": "CAJA-01",
                "service_type": "takeout",
                "q": "cliente privado",
                "limit": 1,
            },
            CASHIER_ID,
        )
        assert len(page["items"]) == 1
        assert page["next_cursor"]
        assert {first, second} >= {page["items"][0]["id"]}
        with pytest.raises(BusinessError) as changed_filter:
            list_order_accounts(
                session,
                {"branch_id": BRANCH_A, "limit": 1, "q": "PCO", "cursor": page["next_cursor"]},
                CASHIER_ID,
            )
        assert changed_filter.value.code == "order_accounts_cursor_invalid"
        for cursor in ("%%", "eyJoIjoiYSIsImMiOiIyMDI2LTA4LTEyVDAwOjAwOjAwIiwiaSI6IngifQ=="):
            with pytest.raises(BusinessError) as malformed:
                list_order_accounts(
                    session,
                    {"branch_id": BRANCH_A, "limit": 1, "cursor": cursor},
                    CASHIER_ID,
                )
            assert malformed.value.code == "order_accounts_cursor_invalid"
    finally:
        session.close()
        engine.dispose()


def test_order_detail_keeps_legacy_fields_and_exposes_canonical_history_aliases():
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        detail = get_order_detail(session, order_id, CASHIER_ID)
        assert detail["owner_name"] is None
        assert detail["order_type"] == "takeout"
        assert detail["customer_label"] == "Cliente privado 1"
        assert detail["service_type"] == "takeout"
    finally:
        session.close()
        engine.dispose()


def test_roles_transitions_and_reopen_list_cursor():
    engine, session = _new_session()
    try:
        _actors(session)
        first, second = _order(session, 1), _order(session, 2)
        payload = {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]}
        with pytest.raises(AuthorizationError):
            create_order_reopen_request(session, first, payload, "cashier-key-001", CASHIER_ID)
        request = create_order_reopen_request(session, first, payload, "chief-key-0001", CHIEF_ID)
        with pytest.raises(BusinessError) as key_conflict:
            create_order_reopen_request(
                session,
                first,
                {"reason": "Motivo distinto documentado", "evidence_refs": ["ticket:002"]},
                "chief-key-0001",
                CHIEF_ID,
            )
        assert key_conflict.value.code == "idempotency_conflict"
        with pytest.raises(BusinessError) as active:
            create_order_reopen_request(session, first, payload, "chief-key-0003", CHIEF_ID)
        assert active.value.code == "order_reopen_request_active"
        with pytest.raises(AuthorizationError):
            list_order_reopen_requests(session, {"limit": 1}, CHIEF_ID)
        with pytest.raises(AuthorizationError):
            decide_order_reopen_request(
                session,
                request["id"],
                "APPROVED",
                {"decision_reason": "Autoriza revisión documentada"},
                "decision-key-001",
                CHIEF_ID,
            )
        other = create_order_reopen_request(session, second, payload, "chief-key-0002", CHIEF_ID)
        listing = list_order_reopen_requests(session, {"limit": 1}, OWNER_ID)
        assert len(listing["items"]) == 1 and listing["next_cursor"]
        approved = decide_order_reopen_request(
            session,
            request["id"],
            "APPROVED",
            {"decision_reason": "Autoriza revisión documentada"},
            "decision-key-001",
            OWNER_ID,
        )
        assert approved["status"] == "APPROVED"
        approval_replay = decide_order_reopen_request(
            session,
            request["id"],
            "APPROVED",
            {"decision_reason": "Autoriza revisión documentada"},
            "decision-key-001",
            OWNER_ID,
        )
        assert approval_replay["id"] == approved["id"]
        assert approval_replay["status"] == approved["status"]
        with pytest.raises(BusinessError) as terminal:
            decide_order_reopen_request(
                session,
                request["id"],
                "REJECTED",
                {"decision_reason": "No aplica por política vigente"},
                "decision-key-002",
                OWNER_ID,
            )
        assert terminal.value.code == "order_reopen_transition_invalid"
        assert other["status"] == "REQUESTED"
    finally:
        session.close()
        engine.dispose()


def _protected_fingerprint(session, order_id):
    tables = (
        models.orders,
        models.order_lines,
        models.payments,
        models.production_tasks,
        models.sales_operation_snapshots,
        models.cash_shift_closures,
        models.cash_shift_cuts,
    )
    result = {}
    for table in tables:
        column = table.c.order_id if "order_id" in table.c else None
        rows = (
            session.execute(sa.select(table).where(column == order_id)).mappings()
            if column is not None
            else []
        )
        result[table.name] = [dict(row) for row in rows]
    return result


def test_reopen_preserves_complete_protected_fingerprint_and_request_on_apply():
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        before = _protected_fingerprint(session, order_id)
        payload = {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]}
        request = create_order_reopen_request(
            session, order_id, payload, "fingerprint-key", CHIEF_ID
        )
        assert _protected_fingerprint(session, order_id) == before
        approved = decide_order_reopen_request(
            session,
            request["id"],
            "APPROVED",
            {"decision_reason": "Autoriza revisión documentada"},
            "fingerprint-approve",
            OWNER_ID,
        )
        assert _protected_fingerprint(session, order_id) == before
        request_before_apply = dict(
            session.execute(
                sa.select(models.order_reopen_requests).where(
                    models.order_reopen_requests.c.id == request["id"]
                )
            )
            .mappings()
            .one()
        )
        with pytest.raises(BusinessError) as denied:
            apply_order_reopen_request(session, request["id"], OWNER_ID)
        assert denied.value.code == "order_reopen_policy_pending"
        assert _protected_fingerprint(session, order_id) == before
        assert (
            dict(
                session.execute(
                    sa.select(models.order_reopen_requests).where(
                        models.order_reopen_requests.c.id == request["id"]
                    )
                )
                .mappings()
                .one()
            )
            == request_before_apply
        )
        assert approved["status"] == "APPROVED"
    finally:
        session.close()
        engine.dispose()


def test_request_constraints_and_version_conflict_preserve_requested_state():
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        request = create_order_reopen_request(
            session,
            order_id,
            {"reason": "Corrección solicitada por cliente", "evidence_refs": ["ticket:001"]},
            "constraints-key",
            CHIEF_ID,
        )
        with pytest.raises(sa.exc.IntegrityError):
            session.execute(
                models.order_reopen_requests.update()
                .where(models.order_reopen_requests.c.id == request["id"])
                .values(evidence_refs=[])
            )
            session.commit()
        session.rollback()
        with pytest.raises(sa.exc.IntegrityError):
            session.execute(
                models.order_reopen_requests.update()
                .where(models.order_reopen_requests.c.id == request["id"])
                .values(status="APPROVED")
            )
            session.commit()
        session.rollback()
        session.execute(
            models.orders.update().where(models.orders.c.id == order_id).values(version=2)
        )
        session.commit()
        with pytest.raises(BusinessError) as version_conflict:
            decide_order_reopen_request(
                session,
                request["id"],
                "APPROVED",
                {"decision_reason": "Autoriza revisión documentada"},
                "constraints-decision",
                OWNER_ID,
            )
        assert version_conflict.value.code == "order_version_conflict"
        assert (
            session.execute(
                sa.select(models.order_reopen_requests.c.status).where(
                    models.order_reopen_requests.c.id == request["id"]
                )
            ).scalar_one()
            == "REQUESTED"
        )
    finally:
        session.close()
        engine.dispose()


def test_audit_and_logs_are_redacted_for_request_replay_and_denial(caplog):
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        reason = "Motivo privado que no debe aparecer en registros"
        evidence = "evidence://private-ticket"
        payload = {"reason": reason, "evidence_refs": [evidence]}
        caplog.set_level("INFO", logger="restaurant_os.operations")
        request = create_order_reopen_request(
            session, order_id, payload, "redacted-key-001", CHIEF_ID
        )
        create_order_reopen_request(session, order_id, payload, "redacted-key-001", CHIEF_ID)
        with pytest.raises(BusinessError):
            apply_order_reopen_request(session, request["id"], OWNER_ID)
        audit_payloads = [
            row[0]
            for row in session.execute(
                sa.select(models.audit_events.c.payload).where(
                    models.audit_events.c.entity_id == request["id"]
                )
            )
        ]
        serialized = " ".join(str(record.__dict__) for record in caplog.records)
        assert reason not in serialized and evidence not in serialized
        assert "redacted-key-001" not in serialized
        assert all(reason not in str(item) and evidence not in str(item) for item in audit_payloads)
        assert any(
            getattr(record, "request_id", None) == request["id"] for record in caplog.records
        )
    finally:
        session.close()
        engine.dispose()
