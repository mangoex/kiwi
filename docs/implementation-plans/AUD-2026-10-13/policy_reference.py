"""Executable D05/D06 design reference; no database, network or production effects.

Inputs are already-authorized snapshots. This is not an API, a tax eligibility decision,
CFDI validation, a live inventory projection, or implementation completion evidence.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction
from zoneinfo import ZoneInfo

Q = Decimal("0.000001")
MAX = Decimal("999999999999.999999")


def exact(value: object, *, signed: bool = False) -> Decimal:
    if not isinstance(value, (str, Decimal)):
        raise ValueError("decimal_required")
    number = Decimal(value)
    if not number.is_finite() or abs(number) > MAX or (not signed and number < 0):
        raise ValueError("decimal_out_of_range")
    if number != number.quantize(Q):
        raise ValueError("precision_exceeded")
    return number


def rounded(value: Decimal) -> Decimal:
    return exact(value.quantize(Q, rounding=ROUND_HALF_UP))


def forecast(
    as_of: date,
    history: list[tuple[date, bool, Decimal | None, bool]],
    future: list[tuple[date, bool]],
) -> Decimal:
    required = {as_of - timedelta(days=i) for i in range(1, 29)}
    rows = {}
    for day, opened, quantity, censored in history:
        if day not in required:
            continue
        if day in rows:
            raise ValueError("duplicate_history_day")
        rows[day] = (opened, quantity, censored)
    if set(rows) != required:
        raise ValueError("incomplete_history")
    samples: dict[int, list[int]] = {day: [] for day in range(7)}
    for day, (opened, quantity, censored) in rows.items():
        if type(opened) is not bool or type(censored) is not bool:
            raise ValueError("unknown_calendar")
        if not opened:
            if quantity is not None and exact(quantity) != 0:
                raise ValueError("calendar_conflict")
            continue
        if quantity is None or censored:
            raise ValueError("insufficient_data")
        samples[day.weekday()].append(int(exact(quantity) / Q))
    if not 1 <= len(future) <= 180:
        raise ValueError("invalid_horizon")
    total = Fraction(0)
    for index, (day, opened) in enumerate(future):
        if day != as_of + timedelta(days=index) or type(opened) is not bool:
            raise ValueError("incomplete_future_calendar")
        if not opened:
            continue
        values = samples[day.weekday()]
        if len(values) < 2:
            raise ValueError("insufficient_data")
        total += Fraction(sum(values), len(values))
    with localcontext() as ctx:
        ctx.prec = 60
        return rounded(Decimal(total.numerator) * Q / Decimal(total.denominator))


def remaining_demand(
    forecast_quantity: object, consumed_since_open: object, covered_reservations: object
) -> Decimal:
    """Same-day, same-item, disjoint quantities from one authorized snapshot."""
    demand, consumed, covered = map(
        exact, (forecast_quantity, consumed_since_open, covered_reservations)
    )
    return max(Decimal(0), demand - consumed - covered)


def need(
    demand: object,
    safety_fraction: object,
    physical: object,
    reserved: object,
    pending: object,
    *,
    minimum: object = Decimal(0),
    maximum: object | None = None,
) -> Decimal:
    demand, rate, physical, reserved, pending = map(
        exact, (demand, safety_fraction, physical, reserved, pending)
    )
    if rate > 1:
        raise ValueError("invalid_safety_fraction")
    floor = exact(minimum)
    ceiling = exact(maximum) if maximum is not None else None
    if ceiling is not None and floor > ceiling:
        raise ValueError("invalid_stock_limits")
    with localcontext() as ctx:
        ctx.prec = 60
        target = max(demand * (1 + rate), floor)
        if ceiling is not None and target > ceiling:
            raise ValueError("target_exceeds_maximum")
        return rounded(max(Decimal(0), target + reserved - physical - pending))


def packs(
    required: object,
    yield_per_pack: object,
    multiple: int,
    moq: int,
    capacity_at_arrival: object | None,
) -> dict[str, object]:
    """Capacity is residual physical capacity at ETA, not the absolute stock maximum."""
    required, yield_per_pack = map(exact, (required, yield_per_pack))
    if (
        yield_per_pack <= 0
        or type(multiple) is not int
        or type(moq) is not int
        or not 1 <= multiple <= 100000
        or not 0 <= moq <= 100000
    ):
        raise ValueError("invalid_presentation")
    maximum = exact(capacity_at_arrival) if capacity_at_arrival is not None else None
    if required == 0:
        return {"packs": 0, "base_quantity": Decimal(0), "review": False}
    numerator, denominator = int(required / Q), int(yield_per_pack / Q)
    count = (numerator + denominator - 1) // denominator
    count = max(count, moq)
    count = ((count + multiple - 1) // multiple) * multiple
    base = exact(yield_per_pack * count)
    return {"packs": count, "base_quantity": base, "review": maximum is not None and base > maximum}


def stockout_days(
    available: object, demands: list[Decimal], arrivals: list[tuple[int, Decimal]]
) -> list[int]:
    """Arrivals are available at bucket opening; intraday ETA belongs to the next bucket."""
    balance = exact(available)
    supply: dict[int, Decimal] = {}
    for day, quantity in arrivals:
        if type(day) is not int or not 0 <= day < len(demands):
            raise ValueError("invalid_arrival_bucket")
        supply[day] = supply.get(day, Decimal(0)) + exact(quantity)
    deficits = []
    for day, demand in enumerate(demands):
        balance += supply.get(day, Decimal(0)) - exact(demand)
        if balance < 0:
            deficits.append(day)
    return deficits


def arrival_bucket(eta: datetime, as_of: date, zone: ZoneInfo) -> int:
    """Conservative local-day bucketing; eligibility/horizon filtering belongs to the adapter."""
    if eta.tzinfo is None or eta.utcoffset() is None:
        raise ValueError("aware_eta_required")
    local = eta.astimezone(zone)
    day = (local.date() - as_of).days
    if day < 0:
        raise ValueError("overdue_eta")
    return day + int(bool(local.hour or local.minute or local.second or local.microsecond))


def cost(
    gross: object,
    discount: object,
    tax: object,
    recoverable_fraction: object,
    freight: object,
    withheld: object,
) -> dict[str, Decimal]:
    gross, discount, tax, rate, freight, withheld = map(
        exact, (gross, discount, tax, recoverable_fraction, freight, withheld)
    )
    if discount > gross or rate > 1:
        raise ValueError("invalid_cost_profile")
    with localcontext() as ctx:
        ctx.prec = 60
        inventory_tax = rounded(tax * (1 - rate))
        return {
            "inventory_cost": rounded(gross - discount + inventory_tax + freight),
            "inventory_tax": inventory_tax,
            "recoverable_tax": tax - inventory_tax,
            "supplier_payable": rounded(gross - discount + tax + freight - withheld),
        }


def allocate(
    total: object, weights: list[tuple[str, Decimal]], quantum: Decimal = Q
) -> dict[str, Decimal]:
    total = exact(total)
    if quantum not in (Q, Decimal("0.01")) or total % quantum:
        raise ValueError("invalid_quantum")
    if (
        not weights
        or any(not isinstance(key, str) or not key for key, _ in weights)
        or len({key for key, _ in weights}) != len(weights)
    ):
        raise ValueError("invalid_line_identity")
    normalized = sorted((key, int(exact(weight) / Q)) for key, weight in weights)
    denominator = sum(weight for _, weight in normalized)
    if denominator == 0:
        raise ValueError("weights_required")
    integer_total = int(total / quantum)
    cumulative = previous = 0
    result = {}
    for key, weight in normalized:
        cumulative += weight
        whole, remainder = divmod(integer_total * cumulative, denominator)
        target = whole + int(2 * remainder >= denominator)
        result[key] = Decimal(target - previous) * quantum
        previous = target
    return result


def compensate(
    delta: object, received: object, remaining: object, consumed: object
) -> dict[str, Decimal]:
    delta = exact(delta, signed=True)
    received, remaining, consumed = map(exact, (received, remaining, consumed))
    if received <= 0 or remaining + consumed != received:
        raise ValueError("attribution_required")
    pieces = allocate(abs(delta), [("inventory", remaining), ("consumed", consumed)])
    sign = 1 if delta >= 0 else -1
    return {key: value * sign for key, value in pieces.items()}
