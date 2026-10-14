"""Executable policy specifications, not proof of live procurement integration."""

import importlib.util
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal as D
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "docs/implementation-plans/AUD-2026-10-13/policy_reference.py"


@pytest.fixture(scope="module")
def policy():
    spec = importlib.util.spec_from_file_location("procurement_policy_reference", SOURCE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def history():
    today = date(2026, 10, 14)
    rows = [
        (today - timedelta(days=i), True, D((today - timedelta(days=i)).weekday() + 1), False)
        for i in range(1, 29)
    ]
    future = [(today + timedelta(days=i), True) for i in range(7)]
    return today, rows, future


def test_weekly_forecast_is_real_and_current_day_excluded(policy):
    today, rows, future = history()
    assert policy.forecast(today, rows + [(today, True, D("999"), False)], future) == D("28")


@pytest.mark.parametrize("bad", ["missing", "unknown", "censored", "duplicate"])
def test_incomplete_history_does_not_become_zero_or_constant(policy, bad):
    today, rows, future = history()
    if bad == "missing":
        rows.pop()
    if bad == "unknown":
        rows[0] = (rows[0][0], True, None, False)
    if bad == "censored":
        rows[0] = (rows[0][0], True, D(0), True)
    if bad == "duplicate":
        rows.append(rows[0])
    with pytest.raises(ValueError):
        policy.forecast(today, rows, future)


def test_closed_day_is_excluded_and_observed_zero_is_zero(policy):
    today, rows, future = history()
    zero = [(day, True, D(0), False) for day, *_ in rows]
    assert policy.forecast(today, zero, future) == 0
    closed = [
        (day, False, None, False) if day.weekday() == 2 else (day, True, value, False)
        for day, _, value, _ in rows
    ]
    assert policy.forecast(today, closed, [(today, False)]) == 0
    with pytest.raises(ValueError):
        policy.forecast(today, closed, [(today, True)])


def test_fractional_forecasts_round_once_at_aggregate(policy):
    today, rows, _ = history()
    rows = [(day, True, D(0), False) for day, *_ in rows]
    indices = [index for index, (day, *_) in enumerate(rows) if day.weekday() == 2]
    rows[indices[0]] = (rows[indices[0]][0], True, D("0.000001"), False)
    rows[indices[3]] = (rows[indices[3]][0], False, None, False)
    future = [(today + timedelta(days=i), i % 7 == 0) for i in range(15)]
    assert policy.forecast(today, rows, future) == D("0.000001")


def test_need_reserves_and_pending_once_and_zero_does_not_trigger_moq(policy):
    assert policy.need(D("28"), D("0.2"), D("10"), D("2"), D("4")) == D("21.600000")
    assert policy.need(D(0), D("0.2"), D(0), D(0), D(0)) == 0
    assert policy.packs(D(0), D("6"), 2, 5, None) == {
        "packs": 0,
        "base_quantity": D(0),
        "review": False,
    }


def test_pack_multiple_moq_and_overstock_review(policy):
    value = policy.packs(D("21.6"), D("6"), 2, 5, D("25"))
    assert value == {"packs": 6, "base_quantity": D("36"), "review": True}


def test_future_receipt_cannot_hide_earlier_gap(policy):
    assert policy.stockout_days(D(2), [D(3), D(3)], [(1, D(10))]) == [0]
    assert policy.stockout_days(D(2), [D(3), D(3)], [(0, D(10))]) == []


def test_current_day_consumption_and_covered_reservations_are_counted_once(policy):
    demand = policy.remaining_demand(D(10), D(8), D(1))
    assert demand == 1
    assert policy.need(demand, D(0), D(2), D(1), D(0)) == 0
    assert policy.remaining_demand(D(10), D(12), D(1)) == 0


def test_minimum_is_floor_and_incompatible_target_requires_review(policy):
    assert policy.need(D(0), D(0), D(2), D(0), D(0), minimum=D(5)) == 3
    with pytest.raises(ValueError, match="target_exceeds_maximum"):
        policy.need(D(10), D("0.2"), D(9), D(0), D(0), maximum=D(10))
    with pytest.raises(ValueError, match="invalid_stock_limits"):
        policy.need(D(0), D(0), D(0), D(0), D(0), minimum=D(11), maximum=D(10))


def test_pack_capacity_is_residual_after_projected_stock(policy):
    assert policy.packs(D(3), D(6), 1, 0, D(10) - D(9))["review"] is True


def test_intraday_eta_moves_to_next_local_bucket(policy):
    day = date(2026, 10, 14)
    zone = ZoneInfo("America/Chihuahua")
    midnight = datetime(2026, 10, 14, 6, tzinfo=timezone.utc)
    late = datetime(2026, 10, 15, 5, tzinfo=timezone.utc)
    assert policy.arrival_bucket(midnight, day, zone) == 0
    assert policy.arrival_bucket(late, day, zone) == 1
    assert policy.stockout_days(
        D(2), [D(3), D(3)], [(policy.arrival_bucket(late, day, zone), D(10))]
    ) == [0]
    with pytest.raises(ValueError, match="aware_eta_required"):
        policy.arrival_bucket(datetime(2026, 10, 14), day, zone)
    with pytest.raises(ValueError, match="overdue_eta"):
        policy.arrival_bucket(midnight - timedelta(days=1), day, zone)


def test_forecast_horizon_limit_is_explicit(policy):
    today, rows, _ = history()
    future = [(today + timedelta(days=i), True) for i in range(180)]
    assert policy.forecast(today, rows, future) > 0
    with pytest.raises(ValueError, match="invalid_horizon"):
        policy.forecast(today, rows, future + [(today + timedelta(days=180), True)])


@pytest.mark.parametrize("fraction,expected", [("1", "110"), ("0", "126"), ("0.5", "118")])
def test_inventory_cost_excludes_only_explicitly_recoverable_fraction(policy, fraction, expected):
    result = policy.cost(D(100), D(0), D(16), D(fraction), D(10), D(0))
    assert result["inventory_cost"] == D(expected)
    assert result["supplier_payable"] == D(126)
    assert result["recoverable_tax"] + result["inventory_tax"] == D(16)


@pytest.mark.parametrize("bad", [None, D("1.1"), D("-0.1"), 0.5, D("NaN")])
def test_unknown_invalid_fraction_is_never_guessed(policy, bad):
    with pytest.raises(ValueError):
        policy.cost(D(100), D(0), D(16), bad, D(0), D(0))


def test_discounts_and_withholding_do_not_duplicate_cost_reduction(policy):
    value = policy.cost(D(100), D(10), D(16), D(1), D(10), D(5))
    assert value["inventory_cost"] == D(100)
    assert value["supplier_payable"] == D(111)


def test_global_allocation_conserves_cent_and_ignores_zero_weight(policy):
    parts = policy.allocate(
        D("0.01"), [("c", D(1)), ("a", D(1)), ("b", D(1)), ("z", D(0))], D("0.01")
    )
    assert sum(parts.values()) == D("0.01") and parts["z"] == 0
    assert parts == policy.allocate(
        D("0.01"), [("b", D(1)), ("a", D(1)), ("z", D(0)), ("c", D(1))], D("0.01")
    )


@pytest.mark.parametrize("sign", [1, -1])
def test_attributed_compensation_preserves_signed_delta(policy, sign):
    value = policy.compensate(D(10 * sign), D(10), D(3), D(7))
    assert value == {"inventory": D(3 * sign), "consumed": D(7 * sign)}
    assert sum(value.values()) == D(10 * sign)


@pytest.mark.parametrize("remaining,consumed", [(None, D(10)), (D(4), D(7)), (D(-1), D(11))])
def test_unknown_or_inconsistent_attribution_requires_review(policy, remaining, consumed):
    with pytest.raises(ValueError):
        policy.compensate(D(10), D(10), remaining, consumed)


@pytest.mark.parametrize("bad", [1.1, "NaN", "Infinity", "0.0000001", "-1"])
def test_exact_bounded_quantities_reject_float_and_invalid_input(policy, bad):
    with pytest.raises(ValueError):
        policy.need(bad, D(0), D(0), D(0), D(0))
