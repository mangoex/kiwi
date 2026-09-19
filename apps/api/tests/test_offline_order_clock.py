"""Reject future-dated acceptance without replacing the signed command."""

from datetime import timedelta

import pytest
import sqlalchemy as sa
from restaurant_os import models
from restaurant_os.offline_orders import reconcile_order_command
from restaurant_os.operations import BusinessError
from sqlalchemy.orm import Session
from test_domain_offline_orders import ACCEPTED_AT
from test_offline_order_reconcile_conflicts import _central_and_pending_envelopes


def test_future_command_waits_without_effect_and_same_envelope_can_retry(tmp_path):
    engine, envelope, _, keyring, _ = _central_and_pending_envelopes(tmp_path)
    try:
        with Session(engine) as session:
            with pytest.raises(BusinessError) as failure:
                reconcile_order_command(
                    session,
                    envelope,
                    keyring=keyring,
                    now=ACCEPTED_AT - timedelta(seconds=1),
                    commit=True,
                )
            assert failure.value.code == "offline_order_accepted_at_future"
            session.rollback()
        with Session(engine) as session:
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 0
            assert (
                session.scalar(sa.select(sa.func.count()).select_from(models.offline_order_inbox))
                == 0
            )
            receipt = reconcile_order_command(
                session,
                envelope,
                keyring=keyring,
                now=ACCEPTED_AT,
                commit=True,
            )
            assert receipt["status"] == "confirmed"
            assert session.scalar(sa.select(sa.func.count()).select_from(models.orders)) == 1
    finally:
        engine.dispose()
