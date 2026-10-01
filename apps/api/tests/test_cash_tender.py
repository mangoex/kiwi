from copy import deepcopy

import pytest
from restaurant_os.cash_tender import MAX_SAFE_CENTS, preview_cash_tender
from restaurant_os.cashier_projection import project_cashier_contact


@pytest.mark.parametrize(('total', 'received', 'change', 'shortfall', 'valid'), [
    (19000, '200.00', 1000, 0, True), (19000, '190', 0, 0, True),
    (19000, '189.99', 0, 1, False), (1, '0.01', 0, 0, True),
    (0, '0', 0, 0, True), (1, '0,02', 1, 0, True),
    (MAX_SAFE_CENTS, '90071992547409.91', 0, 0, True),
])
def test_cash_preview_exact_boundaries(
    total: int, received: str, change: int, shortfall: int, valid: bool,
) -> None:
    result = preview_cash_tender(total, received)
    assert result['change_cents'] == change
    assert result['shortfall_cents'] == shortfall
    assert result['can_confirm'] is valid
    assert result['received_cents'] == total + change - shortfall


@pytest.mark.parametrize('received', [True, 200, 200.0, None, '1e2', '-1', '1.001',
                                     '1,000.00', '90071992547409.92'])
def test_cash_preview_rejects_invalid_received(received: object) -> None:
    with pytest.raises(ValueError, match='cash_received_invalid'):
        preview_cash_tender(1, received)


@pytest.mark.parametrize('total', [True, 1.0, -1, MAX_SAFE_CENTS + 1])
def test_cash_preview_rejects_invalid_total(total: int) -> None:
    with pytest.raises(ValueError, match='cash_received_invalid'):
        preview_cash_tender(total, '200')


def test_contact_uses_primary_active_snapshot_and_does_not_mutate() -> None:
    customer = {'phones': [
        {'captured_number': 'inactive', 'is_primary': True, 'status': 'inactive'},
        {'captured_number': 'secondary', 'is_primary': False},
        {'normalized_number': 'primary', 'is_primary': True},
    ]}
    address = {'street': 'Calle QA', 'exterior_number': '1', 'references': 'Puerta QA'}
    original = deepcopy((customer, address))
    result = project_cashier_contact(customer, address)
    assert result['customer_phone'] == 'primary'
    assert result['delivery_address'] == 'Calle QA 1'
    assert result['delivery_notes'] == 'Puerta QA'
    assert (customer, address) == original


def test_contact_legacy_and_missing_snapshots() -> None:
    assert project_cashier_contact({'phone': 'legacy'}, {
        'address_text': 'Domicilio anterior', 'notes': 'Referencia anterior',
    }) == {'customer_phone': 'legacy', 'delivery_address': 'Domicilio anterior',
           'delivery_notes': 'Referencia anterior'}
    assert project_cashier_contact(None, None) == {
        'customer_phone': '', 'delivery_address': '', 'delivery_notes': '',
    }
