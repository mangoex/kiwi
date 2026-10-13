"""Executable design examples; no database, network or production side effects.

Proposed allocation policy for NEW documents, not a historical data repair.
Run with Python 3.12+: python calculos_referencia.py --output PATH
"""
from __future__ import annotations

import argparse
import itertools
import json
import random
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, localcontext
from pathlib import Path

Q = Decimal("0.000001")
CENT = Decimal("0.01")
MAX_NUMERIC = Decimal("999999999999.999999")


def exact(text: object) -> Decimal:
    if not isinstance(text, str):
        raise ValueError("Exact decimal strings required; floats are forbidden")
    value = Decimal(text)
    if not value.is_finite():
        raise ValueError("Finite decimal required")
    return value


def bounded(value: Decimal) -> Decimal:
    if not value.is_finite() or value < 0 or value > MAX_NUMERIC:
        raise ValueError("Outside nonnegative Numeric(18,6) domain")
    if value != value.quantize(Q):
        raise ValueError("Input exceeds six decimal places")
    return value


def units(value: Decimal) -> int:
    return int(bounded(value) / Q)


def rounded_ratio(numerator: int, denominator: int) -> int:
    """Exact ROUND_HALF_UP for a nonnegative rational, without float division."""
    if numerator < 0 or denominator <= 0:
        raise ValueError("Nonnegative numerator and positive denominator required")
    whole, remainder = divmod(numerator, denominator)
    return whole + int(2 * remainder >= denominator)


def apportion(total: Decimal, weights: list[Decimal], *, base: bool = False) -> list[Decimal]:
    if not weights or any(weight <= 0 for weight in weights):
        raise ValueError("Positive allocation weights required")
    integer_weights = [units(weight) for weight in weights]
    denominator = sum(integer_weights)
    total_units = units(total)
    cumulative_weight = previous_target = 0
    result = []
    for weight in integer_weights:
        cumulative_weight += weight
        target = rounded_ratio(total_units * cumulative_weight, denominator)
        result.append(Decimal(target - previous_target) * Q)
        previous_target = target
    if base and any(target <= 0 for target in result):
        raise ValueError("Positive destination below base precision; redesign allocation")
    return result


def partial_deltas(target: Decimal, assigned: Decimal, receipts: list[Decimal], *, base: bool) -> list[Decimal]:
    assigned_units = units(assigned)
    if assigned_units <= 0 or any(receipt <= 0 for receipt in receipts):
        raise ValueError("Positive assigned and received quantities required")
    target_units = units(target)
    cumulative = previous_target = 0
    result = []
    for receipt in receipts:
        cumulative += units(receipt)
        if cumulative > assigned_units:
            raise ValueError("Over-receipt")
        current = rounded_ratio(target_units * cumulative, assigned_units)
        delta = current - previous_target
        if base and (delta <= 0 or (cumulative < assigned_units and current >= target_units)):
            raise ValueError("Partial leaves an impossible base remainder")
        result.append(Decimal(delta) * Q)
        previous_target = current
    return result


def cents(text: str) -> int:
    value = exact(text)
    if value < 0:
        raise ValueError("Nonnegative amount required")
    with localcontext() as ctx:
        ctx.prec = 60
        return int(value.quantize(CENT, rounding=ROUND_HALF_UP) / CENT)


def average(old_quantity: Decimal, old_average: Decimal, incoming_quantity: Decimal, incoming_value: Decimal) -> Decimal:
    for value in (old_quantity, old_average, incoming_quantity, incoming_value):
        bounded(value)
    if incoming_quantity <= 0:
        raise ValueError("Positive incoming quantity required")
    bounded(old_quantity + incoming_quantity)
    with localcontext() as ctx:
        ctx.prec = 60
        result = ((old_quantity * old_average + incoming_value) / (old_quantity + incoming_quantity)).quantize(Q, rounding=ROUND_HALF_UP)
    return bounded(result)


def demand_example() -> dict[str, str | int]:
    """Illustrative D05 parameters; NOT operational defaults or approved policy."""
    daily, coverage, safety = exact("7"), exact("7"), exact("5")
    physical, reserved, pending, yield_per_pack = map(exact, ["30", "4", "10", "6"])
    available = physical - reserved
    forecast = daily * coverage
    need = max(Decimal(0), forecast + safety - available - pending)
    packs = int((need / yield_per_pack).to_integral_value(rounding=ROUND_CEILING))
    return {"forecast": str(forecast), "available": str(available), "pending": str(pending), "need": str(need), "packs": packs, "policy": "illustrative_requires_D05"}


def verify_reference() -> dict[str, object]:
    examples: dict[str, object] = {}
    targets = apportion(exact("0.333333"), [exact("0.5"), exact("0.5")], base=True)
    assert targets == [exact("0.166667"), exact("0.166666")]
    examples["H09_base_targets"] = list(map(str, targets))
    costs = apportion(exact("0.000002"), [exact("1")] * 4)
    assert costs == [Q, Decimal(0), Q, Decimal(0)]
    examples["H10_cost_targets"] = list(map(str, costs))
    partial = partial_deltas(exact("0.333333"), exact("3"), [exact("1")] * 3, base=True)
    assert partial == [exact("0.111111")] * 3
    examples["partial_base_deltas"] = list(map(str, partial))
    assert cents("19.99") == 1999 and cents("0.29") == 29
    assert cents("0.005") == 1
    examples["H18_cents"] = {"19.99": cents("19.99"), "0.29": cents("0.29")}
    avg = average(exact("10"), exact("20"), exact("5"), exact("150"))
    assert avg == exact("23.333333")
    examples["stock_positive_average"] = str(avg)
    ap_entries = [10000, -3000, -2000]
    assert sum(ap_entries) == 5000
    assert sum(ap_entries + [3000]) == 8000
    examples["AP_balance_and_reversal_cents"] = [5000, 8000]
    forecast = demand_example()
    assert forecast["need"] == "18" and forecast["packs"] == 3
    examples["demand_illustration"] = forecast

    invalid = [lambda: bounded(exact("1200000000000")), lambda: exact("NaN"), lambda: exact("Infinity"), lambda: exact(19.99), lambda: bounded(exact("0.0000001")), lambda: apportion(Q, [exact("1")] * 2, base=True), lambda: partial_deltas(Q, exact("1"), [exact("0.5")], base=True), lambda: partial_deltas(exact("1"), exact("1"), [exact("2")], base=True)]
    for operation in invalid:
        try:
            operation()
        except ValueError:
            pass
        else:
            raise AssertionError("An invalid boundary was accepted")
    assert bounded(MAX_NUMERIC) == MAX_NUMERIC
    examples["H13_max_and_overflow"] = {"max": str(MAX_NUMERIC), "overflow_rejected": "1200000000000"}

    # Independent invariants, not comparison against the same formula.
    allocation_checks = 0
    for count in (2, 3, 4):
        for weights in itertools.product(range(1, 5), repeat=count):
            for total in range(0, 21):
                amounts = apportion(Decimal(total) * Q, [Decimal(w) for w in weights])
                assert sum(amounts) == Decimal(total) * Q
                assert all(amount >= 0 and amount % Q == 0 for amount in amounts)
                allocation_checks += 1
    rng = random.Random(20261013)
    partial_checks = 0
    for _ in range(5000):
        count = rng.randint(1, 12)
        weights = [rng.randint(1, 10000) for _ in range(count)]
        quantity = sum(weights)
        target = rng.randint(quantity, quantity * 500)
        receipts = [Decimal(w) * Q for w in weights]
        amounts = partial_deltas(Decimal(target) * Q, Decimal(quantity) * Q, receipts, base=True)
        assert sum(amounts) == Decimal(target) * Q
        assert all(amount > 0 and amount % Q == 0 for amount in amounts)
        # Splitting cannot change the final frozen quantity.
        merged = partial_deltas(Decimal(target) * Q, Decimal(quantity) * Q, [Decimal(quantity) * Q], base=True)
        assert sum(merged) == sum(amounts)
        partial_checks += 1
    return {"status": "reference_verified_not_runtime", "examples": examples, "allocation_property_cases": allocation_checks, "partial_property_cases": partial_checks, "invalid_boundary_cases": len(invalid)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = verify_reference()
    serialized = json.dumps(result, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
