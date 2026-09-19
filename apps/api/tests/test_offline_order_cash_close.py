"""Cash cannot close before the local writer proves its drain and releases authority."""

from datetime import timedelta

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.operations import (
    BusinessError,
    close_cash_shift_operationally,
    close_cash_shift_operationally_for_register,
)
from test_cash_ledger import BRANCH_A, CASHIER_ID, NOW, SHIFT_ID, _new_session
from test_offline_order_fencing import _active_lease


@pytest.mark.parametrize("alias", [False, True])
@pytest.mark.parametrize("expired", [False, True])
def test_close_requires_handoff_even_if_lease_expired(alias, expired):
    engine, session = _new_session()
    try:
        _active_lease(session)
        session.execute(
            models.offline_order_gateway_leases.update().values(
                expires_at=NOW + timedelta(days=-1 if expired else 365),
            )
        )
        session.commit()
        register = session.scalar(
            sa.select(models.cash_shifts.c.register_code).where(
                models.cash_shifts.c.id == SHIFT_ID,
            )
        )

        def close():
            if alias:
                return close_cash_shift_operationally_for_register(
                    session,
                    BRANCH_A,
                    register,
                    "offline-close-test",
                    CASHIER_ID,
                )
            return close_cash_shift_operationally(
                session,
                SHIFT_ID,
                "offline-close-test",
                CASHIER_ID,
            )

        with pytest.raises(BusinessError) as failure:
            close()
        assert failure.value.code == "offline_orders_close_requires_handoff"
        assert (
            session.scalar(
                sa.select(models.cash_shifts.c.status).where(
                    models.cash_shifts.c.id == SHIFT_ID,
                )
            )
            == "OPEN"
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_shift_closures)) == 0
        )
        # The lifecycle protocol owns this transition. This domain test isolates
        # the close guard; signed handoff has its own integration coverage.
        session.execute(models.offline_order_gateway_leases.update().values(status="RELEASED"))
        session.commit()
        result = close()
        assert result["cash_shift"]["status"] == "OPERATIVELY_CLOSED"
        session.execute(models.offline_order_gateway_leases.update().values(status="ACTIVE"))
        session.commit()
        # An already committed close response may be recovered after another
        # lease was acquired; this is a read replay, not a new close.
        assert close() == result
    finally:
        session.close()
        engine.dispose()
