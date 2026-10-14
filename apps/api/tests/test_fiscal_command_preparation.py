"""TDD-TC-384: durable payment evidence precedes provider dispatch."""

import json
from contextlib import contextmanager
from uuid import uuid4

import pytest
import sqlalchemy as sa
import test_facturapi_integration as legacy
import test_fiscal_authority_remediation as authority
import test_fiscal_eligibility as eligibility
from restaurant_os import models
from restaurant_os.invoicing.service import InvoicingService
from restaurant_os.operations import BusinessError

test_db = legacy.test_db


@pytest.fixture
def fiscal_data(test_db, monkeypatch):
    with contextmanager(eligibility.fiscal_data.__wrapped__)(test_db, monkeypatch) as value:
        session, _ = value
        session.execute(sa.text("PRAGMA foreign_keys=ON"))
        assert session.scalar(sa.text("PRAGMA foreign_keys")) == 1
        session.commit()
        yield value


RECEIVER = {
    "rfc": "XAXX010101000",
    "legal_name": "PUBLICO EN GENERAL",
    "zip": "80000",
    "tax_system": "616",
    "use": "S01",
    "payment_form": "01",
    "payment_method": "PUE",
}


def _prepare(session, *, key="fiscal-prepare-qa-1", orders=None, receiver=None):
    method = getattr(InvoicingService(), "prepare_invoice", None)
    assert callable(method), "Durable fiscal preparation is missing"
    return method(
        session,
        legacy.ORGANIZATION_ID,
        legacy.BRANCH_ID,
        orders if orders is not None else [authority.ORDER_A],
        receiver if receiver is not None else RECEIVER,
        actor_user_id=legacy.USER_ID,
        idempotency_key=key,
    )


def _ready(fiscal_data):
    session, calls = fiscal_data
    authority._grant(session, "invoicing.issue")
    payment = eligibility._payment(session)
    return session, calls, payment


def _counts(session):
    return [
        session.scalar(sa.select(sa.func.count()).select_from(table))
        for table in (
            models.fiscal_commands,
            models.fiscal_command_orders,
            models.fiscal_order_reservations,
            models.fiscal_command_outbox,
        )
    ]


def test_prepare_is_committed_encrypted_and_has_no_provider_effect(fiscal_data):
    session, calls, payment = _ready(fiscal_data)
    result = _prepare(session)
    assert result["state"] == "pending"
    assert result["dispatch_ready"] is False
    assert result["order_ids"] == [authority.ORDER_A]
    assert result["total_cents"] == 1999
    assert _counts(session) == [1, 1, 1, 1]
    assert calls == []
    from restaurant_os.invoicing.commands import read_private_snapshot

    row = dict(session.execute(sa.select(models.fiscal_commands)).mappings().one())
    assert "XAXX010101000" not in row["snapshot_ciphertext"]
    assert "PUBLICO EN GENERAL" not in json.dumps(row, default=str)
    assert "ciphertext" not in json.dumps(result)
    assert "request_hash" not in result and "external_key" not in result
    snapshot = read_private_snapshot(row)
    assert snapshot["payments"][0]["payment_ids"] == [payment]
    assert snapshot["payments"][0]["total_cents"] == 1999
    assert snapshot["request"]["receiver"] == RECEIVER
    audit = session.execute(
        sa.select(models.audit_events.c.payload).where(
            models.audit_events.c.action == "invoicing.command.prepared"
        )
    ).scalar_one()
    assert "XAXX010101000" not in json.dumps(audit)
    session.rollback()
    assert _counts(session) == [1, 1, 1, 1]


def test_response_loss_replay_keeps_original_payment_and_configuration(fiscal_data):
    session, calls, _ = _ready(fiscal_data)
    first = _prepare(session)
    original = dict(session.execute(sa.select(models.fiscal_commands)).mappings().one())
    session.execute(
        models.orders.update()
        .where(models.orders.c.id == authority.ORDER_A)
        .values(total_cents=2200, version=2)
    )
    session.commit()
    second = _prepare(session)
    assert second == first
    current = dict(session.execute(sa.select(models.fiscal_commands)).mappings().one())
    assert current == original
    assert _counts(session) == [1, 1, 1, 1] and calls == []


def test_same_key_different_receiver_conflicts_without_writes(fiscal_data):
    session, calls, _ = _ready(fiscal_data)
    _prepare(session)
    with pytest.raises(BusinessError) as denied:
        _prepare(session, receiver={**RECEIVER, "use": "G03"})
    assert denied.value.code == "fiscal_idempotency_conflict"
    session.commit()
    assert _counts(session) == [1, 1, 1, 1] and calls == []


def test_new_key_cannot_bypass_unresolved_order_reservation(fiscal_data):
    session, calls, _ = _ready(fiscal_data)
    _prepare(session)
    with pytest.raises(BusinessError) as denied:
        _prepare(session, key="different-intent-qa")
    assert denied.value.code == "fiscal_order_reserved"
    session.commit()
    assert _counts(session) == [1, 1, 1, 1] and calls == []


@pytest.mark.parametrize("condition", ["inactive", "revoked"])
def test_replay_rechecks_current_authority(fiscal_data, condition):
    from restaurant_os.operations import AuthorizationError

    session, calls, _ = _ready(fiscal_data)
    _prepare(session)
    if condition == "inactive":
        session.execute(
            models.users.update()
            .where(models.users.c.id == legacy.USER_ID)
            .values(status="inactive")
        )
    else:
        permission = session.scalar(
            sa.select(models.permissions.c.id).where(models.permissions.c.code == "invoicing.issue")
        )
        session.execute(
            models.role_permissions.delete().where(
                models.role_permissions.c.permission_id == permission
            )
        )
    session.commit()
    with pytest.raises(AuthorizationError):
        _prepare(session)
    assert _counts(session) == [1, 1, 1, 1] and calls == []


@pytest.mark.parametrize("field", ["snapshot_ciphertext", "external_key"])
def test_snapshot_or_external_identity_changes_fail_closed(fiscal_data, field):
    session, calls, _ = _ready(fiscal_data)
    _prepare(session)
    session.execute(models.fiscal_commands.update().values(**{field: "tampered-synthetic"}))
    session.commit()
    with pytest.raises(BusinessError) as denied:
        _prepare(session)
    assert denied.value.code == "fiscal_snapshot_unavailable"
    assert _counts(session) == [1, 1, 1, 1] and calls == []


@pytest.mark.parametrize("missing", ["reservation", "outbox"])
def test_replay_with_incomplete_durable_evidence_requires_review(fiscal_data, missing):
    session, calls, _ = _ready(fiscal_data)
    _prepare(session)
    table = (
        models.fiscal_order_reservations
        if missing == "reservation"
        else models.fiscal_command_outbox
    )
    session.execute(table.delete())
    session.commit()
    with pytest.raises(BusinessError) as denied:
        _prepare(session)
    assert denied.value.code == "fiscal_snapshot_unavailable" and calls == []


def test_new_key_does_not_escape_a_damaged_reservation(fiscal_data):
    session, calls, _ = _ready(fiscal_data)
    _prepare(session)
    session.execute(models.fiscal_order_reservations.delete())
    session.commit()
    with pytest.raises(BusinessError) as denied:
        _prepare(session, key="different-with-damaged-reservation")
    assert denied.value.code == "fiscal_order_reserved" and calls == []
    assert _counts(session) == [1, 1, 0, 1]


def test_payment_snapshot_cannot_claim_dispatch_or_success(fiscal_data):
    session, _, _ = _ready(fiscal_data)
    _prepare(session)
    with pytest.raises(sa.exc.IntegrityError), session.begin_nested():
        session.execute(models.fiscal_commands.update().values(dispatch_ready=True))
    session.execute(models.fiscal_commands.update().values(state="succeeded"))
    session.commit()
    with pytest.raises(BusinessError) as denied:
        _prepare(session)
    assert denied.value.code == "fiscal_snapshot_unavailable"


@pytest.mark.parametrize("bad", [{}, {**RECEIVER, "zip": ""}, {**RECEIVER, "use": 1}])
def test_receiver_without_explicit_fields_is_not_defaulted(fiscal_data, bad):
    session, calls, _ = _ready(fiscal_data)
    with pytest.raises(BusinessError) as denied:
        _prepare(session, receiver=bad)
    assert denied.value.code == "fiscal_receiver_invalid"
    assert _counts(session) == [0, 0, 0, 0] and calls == []


@pytest.mark.parametrize("key", [None, "", "a" * 129, "control\nkey"])
def test_invalid_key_creates_no_intention(fiscal_data, key):
    session, calls, _ = _ready(fiscal_data)
    with pytest.raises(BusinessError) as denied:
        _prepare(session, key=key)
    assert denied.value.code == "fiscal_idempotency_key_invalid"
    assert _counts(session) == [0, 0, 0, 0] and calls == []


def test_audit_failure_rolls_back_every_fiscal_row(fiscal_data, monkeypatch):
    session, calls, _ = _ready(fiscal_data)
    from restaurant_os.invoicing import commands

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic audit failure")

    monkeypatch.setattr(commands, "_audit", fail)
    with pytest.raises(RuntimeError, match="synthetic audit failure"):
        _prepare(session)
    session.commit()
    assert _counts(session) == [0, 0, 0, 0] and calls == []


def test_database_errors_do_not_expose_intention_key_or_ciphertext(fiscal_data, monkeypatch):
    session, calls, _ = _ready(fiscal_data)
    from restaurant_os.invoicing import commands

    def fail(*args, **kwargs):
        raise sa.exc.IntegrityError("synthetic", {"key": "private-protocol-marker"},
                                    Exception("private-protocol-marker"))

    monkeypatch.setattr(commands, "_audit", fail)
    with pytest.raises(BusinessError) as denied:
        _prepare(session)
    assert denied.value.code == "fiscal_persistence_unavailable"
    assert "private-protocol-marker" not in str(denied.value)
    assert denied.value.__suppress_context__
    session.commit()
    assert _counts(session) == [0, 0, 0, 0] and calls == []


def test_complete_order_set_and_canonical_ordering_are_preserved(fiscal_data):
    session, calls, payment = _ready(fiscal_data)
    order = dict(
        session.execute(sa.select(models.orders).where(models.orders.c.id == authority.ORDER_A))
        .mappings()
        .one()
    )
    second = str(uuid4())
    session.execute(models.orders.insert().values(**{**order, "id": second, "folio": "FISCAL-2"}))
    paid = dict(
        session.execute(sa.select(models.payments).where(models.payments.c.id == payment))
        .mappings()
        .one()
    )
    session.execute(
        models.payments.insert().values(**{**paid, "id": str(uuid4()), "order_id": second})
    )
    session.commit()
    first = _prepare(session, orders=[second, authority.ORDER_A])
    assert first["order_ids"] == sorted([second, authority.ORDER_A])
    assert first["total_cents"] == 3998
    assert _prepare(session, orders=[authority.ORDER_A, second]) == first
    assert _counts(session) == [1, 2, 2, 1] and calls == []
