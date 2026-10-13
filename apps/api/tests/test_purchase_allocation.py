"""Conservation and monotonicity across exact micro-unit allocation plans."""

from decimal import Decimal
from random import Random

import pytest
from restaurant_os.purchase_allocation import QUANTUM, apportion


def test_rounding_golden_examples() -> None:
    assert apportion(Decimal("0.333333"), [Decimal("0.5")] * 2) == [
        Decimal("0.166667"),
        Decimal("0.166666"),
    ]
    assert apportion(Decimal("0.000002"), [Decimal("1")] * 4) == [
        QUANTUM,
        Decimal("0"),
        QUANTUM,
        Decimal("0"),
    ]


def test_conservation_nonnegative_and_cumulative_error_bound() -> None:
    random = Random(20261013)
    for _ in range(5000):
        weights = [
            Decimal(random.randrange(1, 1000000)) * QUANTUM for _ in range(random.randrange(1, 30))
        ]
        total = Decimal(random.randrange(0, 10**18)) * QUANTUM
        targets = apportion(total, weights)
        assert sum(targets) == total
        assert all(target >= 0 and target % QUANTUM == 0 for target in targets)
        for index in range(len(weights)):
            exact = total * sum(weights[: index + 1]) / sum(weights)
            assert abs(sum(targets[: index + 1]) - exact) <= QUANTUM / 2


@pytest.mark.parametrize(
    "total,weights",
    [
        ("-1", ["1"]),
        ("0.0000001", ["1"]),
        ("1", []),
        ("1", ["0"]),
        ("1", ["-1"]),
        ("1", ["0.0000001"]),
    ],
)
def test_invalid_allocation_inputs(total: str, weights: list[str]) -> None:
    with pytest.raises(ValueError):
        apportion(Decimal(total), [Decimal(weight) for weight in weights])
