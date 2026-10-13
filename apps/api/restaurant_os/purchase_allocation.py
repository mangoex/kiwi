"""Exact cumulative apportionment of frozen purchase quantities and costs."""

from decimal import Decimal

QUANTUM = Decimal("0.000001")


def apportion(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Distribute integer micro-units with monotone HALF_UP cumulative targets.

    Inputs are already validated boundary values. Every target is nonnegative,
    and telescoping cumulative differences preserve the complete frozen total.
    """
    if total < 0 or total % QUANTUM or not weights:
        raise ValueError("Apportionment requires a nonnegative micro-unit total")
    if any(weight <= 0 or weight % QUANTUM for weight in weights):
        raise ValueError("Apportionment requires positive micro-unit weights")
    units = int(total / QUANTUM)
    integer_weights = [int(weight / QUANTUM) for weight in weights]
    denominator = sum(integer_weights)
    cumulative = previous = 0
    targets = []
    for weight in integer_weights:
        cumulative += weight
        quotient, remainder = divmod(units * cumulative, denominator)
        rounded = quotient + int(2 * remainder >= denominator)
        targets.append(Decimal(rounded - previous) * QUANTUM)
        previous = rounded
    return targets
