from decimal import Decimal

import pytest
from restaurant_os.delivery_fee import allocate_adjustment, calculate_charge, normalize_selection
from restaurant_os.operations import BusinessError


def tariff(amount: int = 2800) -> dict:
    return {
        "id": "tariff",
        "version": 1,
        "name": "Estándar",
        "amount_cents": amount,
        "currency": "MXN",
        "tax_rate": "0.160000",
        "tax_included": True,
    }


@pytest.mark.parametrize("subtotal,expected", [(49999, 2800), (50000, 0), (50001, 0)])
def test_inclusive_threshold_uses_only_discounted_products(subtotal: int, expected: int) -> None:
    result = calculate_charge(
        tariff(), {"free_threshold_cents": 50000}, normalize_selection(None), subtotal
    )
    assert result["charged_cents"] == expected
    assert result["eligible_subtotal_cents"] == subtotal
    assert result["tariff"]["id"] == "tariff"


def test_removed_is_sticky_and_distinct_from_threshold() -> None:
    for subtotal in (49000, 50000, 60000):
        result = calculate_charge(
            tariff(),
            {"free_threshold_cents": 50000},
            normalize_selection({"mode": "REMOVED"}),
            subtotal,
        )
        assert result["state"] == "REMOVED"
        assert result["charged_cents"] == 0


def test_product_adjustment_allocation_conserves_cents() -> None:
    assert allocate_adjustment([333, 333, 334], 101) == [34, 33, 34]
    assert allocate_adjustment([100, 200], 300) == [100, 200]
    assert allocate_adjustment([0, 0], 0) == [0, 0]


def test_exact_included_tax_and_alternative_tariff_replaces_default() -> None:
    first = calculate_charge(tariff(), {}, normalize_selection(None), 20000)
    assert Decimal(first["net_amount"]) + Decimal(first["tax_amount"]) == Decimal("28")
    assert Decimal(first["tax_amount"]).quantize(Decimal("0.01")) == Decimal("3.86")
    other = calculate_charge(
        tariff(4200), {}, normalize_selection({"mode": "SELECTED", "tariff_id": "tariff"}), 20000
    )
    assert other["charged_cents"] == 4200


@pytest.mark.parametrize(
    "value",
    [
        [],
        ["a", "b"],
        {"mode": "AUTO", "amount_cents": 0},
        {"mode": "SELECTED"},
        {"mode": "REMOVED", "tariff_id": "a"},
    ],
)
def test_untrusted_selection_cannot_set_price_or_stack_tariffs(value: object) -> None:
    with pytest.raises(BusinessError, match="selection"):
        normalize_selection(value)
