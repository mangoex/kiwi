import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.delivery_fee import calculate_charge, capture_charge, normalize_selection
from restaurant_os.operations import BusinessError, apply_order_reopen_request
from test_cash_concepts import OWNER_ID
from test_cash_ledger import _new_session
from test_delivery_fee_pricing import tariff
from test_order_corrections import _approved_production_request, _plan, _production_fixture
from test_order_reopen_workflow import _actors, _order


@pytest.mark.parametrize("discounted", [False, True])
def test_correction_preserves_original_payment_and_recalculates_threshold(discounted) -> None:
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        line_id, _ = _production_fixture(session, order_id, "PENDING")
        original = (
            session.execute(sa.select(models.orders).where(models.orders.c.id == order_id))
            .mappings()
            .one()
        )
        charge = calculate_charge(
            tariff(),
            {"free_threshold_cents": 500},
            normalize_selection(None),
            499 if discounted else 500,
        )
        capture_charge(session, dict(original), OWNER_ID, charge)
        session.commit()
        request = _approved_production_request(session, order_id, "fee-threshold")
        plan = _plan([{"source_line_id": line_id, "quantity": 1}])
        if discounted:
            with pytest.raises(BusinessError) as blocked:
                apply_order_reopen_request(
                    session, str(request["id"]), plan, "fee-correction-001", OWNER_ID
                )
            assert blocked.value.code == "order_adjustment_reauthorization_required"
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.order_corrections))
                == 0
            )
            return
        result = apply_order_reopen_request(
            session, str(request["id"]), plan, "fee-correction-001", OWNER_ID
        )
        assert result["status"] == "APPLIED"
        correction = (
            session.execute(
                sa.select(models.order_corrections).where(
                    models.order_corrections.c.order_id == order_id
                )
            )
            .mappings()
            .one()
        )
        assert correction["after_snapshot"]["delivery_charge"]["charged_cents"] == 2800
        assert correction["after_snapshot"]["total_cents"] == 3050
        assert (
            session.scalar(
                sa.select(models.payments.c.amount_cents).where(
                    models.payments.c.order_id == order_id
                )
            )
            == 500
        )
        assert (
            session.scalar(
                sa.select(models.orders.c.total_cents).where(models.orders.c.id == order_id)
            )
            == 500
        )
    finally:
        session.close()
        engine.dispose()


def test_second_paid_fee_correction_cannot_refund_original_fee_twice() -> None:
    engine, session = _new_session()
    try:
        _actors(session)
        order_id = _order(session)
        line_id, _ = _production_fixture(session, order_id, "PENDING")
        session.execute(
            models.orders.update().where(models.orders.c.id == order_id).values(total_cents=3300)
        )
        session.execute(
            models.payments.update()
            .where(models.payments.c.order_id == order_id)
            .values(amount_cents=3300)
        )
        session.execute(
            models.sales_operation_snapshots.update()
            .where(models.sales_operation_snapshots.c.order_id == order_id)
            .values(gross_cents=3300, net_cents=3300)
        )
        original = (
            session.execute(sa.select(models.orders).where(models.orders.c.id == order_id))
            .mappings()
            .one()
        )
        capture_charge(
            session,
            dict(original),
            OWNER_ID,
            calculate_charge(tariff(), {}, normalize_selection(None), 500),
        )
        session.commit()
        plan = {
            **_plan([{"source_line_id": line_id, "quantity": 2}]),
            "delivery_selection": {"mode": "REMOVED"},
        }
        request = _approved_production_request(session, order_id, "fee-first-refund")
        first = apply_order_reopen_request(
            session, str(request["id"]), plan, "fee-first-apply", OWNER_ID
        )
        assert first["status"] == "APPLIED"
        request2 = _approved_production_request(session, order_id, "fee-second-refund")
        with pytest.raises(BusinessError) as blocked:
            apply_order_reopen_request(
                session, str(request2["id"]), plan, "fee-second-apply", OWNER_ID
            )
        assert blocked.value.code == "delivery_correction_chain_pending"
        assert session.scalar(sa.select(sa.func.count()).select_from(models.order_corrections)) == 1
    finally:
        session.close()
        engine.dispose()
