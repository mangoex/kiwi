# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-pos-cashier-workflow-v1
from copy import deepcopy
from typing import Any

import pytest
from restaurant_os import models
from test_platform_api import BRANCH_ID, _admin_headers, _client_with_seeded_database, _open_shift

BURGER_ID = '018f6f73-2d0a-74f0-8f1c-000000000111'


def _pending_order(client: Any) -> dict[str, Any]:
    assert _open_shift(client, 10000).status_code == 200
    response = client.post('/api/v1/orders', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID, 'register_id': 'CAJA-01', 'order_type': 'takeout',
        'payment_method_intent': 'cash', 'lines': [{'product_id': BURGER_ID, 'quantity': 1}],
    })
    assert response.status_code == 200
    return dict(response.json())


def test_saved_order_payment_preview_and_cash_replay() -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    preview_body = {'method': 'cash', 'received_cash': '100'}
    assert client.post(path + '/payment-preview', json=preview_body).status_code == 401
    preview = client.post(path + '/payment-preview', headers=_admin_headers(), json=preview_body)
    assert preview.status_code == 200
    assert preview.json()['cash_tender']['change_cents'] == 500
    headers = {**_admin_headers(), 'Idempotency-Key': 'cashier-payment-replay-001'}
    body = {'amount_cents': 9500, 'method': 'cash', 'register_id': 'CAJA-01',
            'received_cash': '100.00'}
    payment = client.post(path + '/payments', headers=headers, json=body)
    assert payment.status_code == 200
    assert payment.json()['cash_tender'] == preview.json()['cash_tender']
    replay = client.post(path + '/payments', headers=headers, json={**body, 'received_cash': '100'})
    assert replay.json() == payment.json()
    conflict = client.post(path + '/payments', headers=headers,
                          json={**body, 'received_cash': '200'})
    assert conflict.status_code == 409
    assert conflict.json()['detail']['code'] == 'payment_idempotency_conflict'
    detail = client.get(path, headers=_admin_headers()).json()
    assert len(detail['payments']) == 1
    assert detail['payments'][0]['amount_cents'] == 9500
    assert detail['status'] == 'ACCEPTED'


def test_insufficient_received_cash_does_not_create_payment() -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    response = client.post(path + '/payments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-insufficient-001',
    }, json={'amount_cents': 9500, 'method': 'cash', 'register_id': 'CAJA-01',
             'received_cash': '94.99'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'cash_received_insufficient'
    assert client.get(path, headers=_admin_headers()).json()['payments'] == []


def test_competing_payment_can_be_reconciled_without_duplicate_payment() -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    body = {'amount_cents': 9500, 'method': 'cash', 'register_id': 'CAJA-01',
            'received_cash': '100'}
    first = client.post(path + '/payments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-first-payment-001',
    }, json=body)
    assert first.status_code == 200
    second = client.post(path + '/payments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-competing-payment-001',
    }, json=body)
    assert second.status_code == 409
    assert second.json()['detail']['code'] == 'payment_already_confirmed'
    detail = client.get(path, headers=_admin_headers()).json()
    assert detail['id'] == order['id']
    assert detail['payment_status'] == 'CONFIRMED'
    assert len(detail['payments']) == 1


def test_amendment_with_only_new_lines_does_not_claim_historical_sources() -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    response = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-all-new-lines-001',
    }, json={'expected_version': order['version'], 'lines': [
        {'product_id': BURGER_ID, 'quantity': 2, 'notes': 'Nueva línea', 'source_line_id': None},
    ]})
    assert response.status_code == 200
    after = client.get(path, headers=_admin_headers()).json()
    assert after['lines'][0]['supersedes_line_id'] is None
    assert after['lines'][0]['line_notes'] == 'Nueva línea'


@pytest.mark.parametrize('amount', [9500.5, '9500', True, None])
def test_cashier_payment_rejects_non_integer_amount(amount: object) -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    response = client.post(f"/api/v1/orders/{order['id']}/payments", headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-invalid-amount-001',
    }, json={'amount_cents': amount, 'method': 'cash', 'register_id': 'CAJA-01',
             'received_cash': '100.00'})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'invalid_payment_amount'


def test_delivery_detail_projects_structured_historical_contact() -> None:
    client = _client_with_seeded_database()
    customer = client.post('/api/v1/customers', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID, 'name': 'Cliente sintético',
        'phones': [{'number': '6690001234', 'is_primary': True}],
    }).json()
    address_response = client.post(
        f"/api/v1/customers/{customer['id']}/addresses", headers=_admin_headers(), json={
            'branch_id': BRANCH_ID, 'alias': 'Casa QA', 'street': 'Calle QA',
            'exterior_number': '123', 'interior_number': 'B', 'neighborhood': 'Colonia QA',
            'postal_code': '82000', 'city': 'Mazatlán', 'municipality': 'Mazatlán',
            'state': 'Sinaloa', 'references': 'Puerta verde',
            'delivery_instructions': 'Llamar al llegar',
        },
    )
    assert address_response.status_code == 200
    address = address_response.json()
    assert _open_shift(client, 10000).status_code == 200
    response = client.post('/api/v1/orders', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID, 'register_id': 'CAJA-01', 'order_type': 'delivery',
        'payment_method_intent': 'cash', 'customer_id': customer['id'],
        'delivery_address_id': address['id'], 'lines': [{'product_id': BURGER_ID, 'quantity': 1}],
    })
    assert response.status_code == 200
    order = response.json()
    snapshot = deepcopy(order['delivery_address_snapshot'])
    update = client.put(f"/api/v1/customers/{customer['id']}/addresses/{address['id']}",
                        headers=_admin_headers(), json={'branch_id': BRANCH_ID,
                                                        'street': 'Calle posterior'})
    assert update.status_code == 200
    detail = client.get(f"/api/v1/orders/{order['id']}", headers=_admin_headers()).json()
    assert detail['customer_phone'] == '+526690001234'
    assert 'Calle QA 123' in detail['delivery_address']
    assert 'B' in detail['delivery_address']
    assert 'Colonia QA' in detail['delivery_address']
    assert 'Puerta verde' in detail['delivery_notes']
    assert 'Llamar al llegar' in detail['delivery_notes']
    assert detail['delivery_address_snapshot'] == snapshot
    assert detail['display_status'] == 'PENDING_PAYMENT'
    assert detail['payments'] == []


def test_order_quote_calculates_cash_tender_without_order_or_payment() -> None:
    client = _client_with_seeded_database()
    headers = _admin_headers()
    response = client.post('/api/v1/orders/quote', headers=headers, json={
        'branch_id': BRANCH_ID, 'lines': [{'product_id': BURGER_ID, 'quantity': 2}],
        'received_cash': '200.00',
    })
    assert response.status_code == 200
    quote = response.json()
    assert quote['total_cents'] == 19000
    assert quote['cash_tender'] == {
        'received_cents': 20000, 'change_cents': 1000, 'shortfall_cents': 0, 'can_confirm': True,
    }
    assert client.get('/api/v1/orders', headers=headers).json() == []
    assert client.get('/api/v1/payments', headers=headers).json() == []


@pytest.mark.parametrize('value', [True, 200.0, '-1', '1e3', '2.001', '$200', 'NaN', ''])
def test_quote_rejects_invalid_cash_received(value: Any) -> None:
    client = _client_with_seeded_database()
    response = client.post('/api/v1/orders/quote', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID, 'lines': [{'product_id': BURGER_ID, 'quantity': 1}],
        'received_cash': value,
    })
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'cash_received_invalid'


@pytest.mark.parametrize('notes', [{'text': 'no es texto'}])
def test_quote_rejects_invalid_line_notes(notes: Any) -> None:
    client = _client_with_seeded_database()
    response = client.post('/api/v1/orders/quote', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID,
        'lines': [{'product_id': BURGER_ID, 'quantity': 1, 'notes': notes}],
    })
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'invalid_line_notes'


@pytest.mark.parametrize('notes', ['x' * 501, {'text': 'no es texto'}])
def test_amendment_rejects_new_invalid_notes_atomically(notes: Any) -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    before = client.get(path, headers=_admin_headers()).json()
    response = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-amend-note-001',
    }, json={'expected_version': before['version'],
             'lines': [{'product_id': BURGER_ID, 'quantity': 2, 'notes': notes}]})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == 'invalid_line_notes'
    after = client.get(path, headers=_admin_headers()).json()
    assert after['version'] == before['version']
    assert after['lines'] == before['lines']
    assert after['production_tasks'] == before['production_tasks']


def test_quote_preserves_historical_long_note_without_writing() -> None:
    client = _client_with_seeded_database()
    assert _open_shift(client, 10000).status_code == 200
    response = client.post('/api/v1/orders/quote', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID,
        'lines': [{'product_id': BURGER_ID, 'quantity': 1, 'notes': 'x' * 501}],
    })
    assert response.status_code == 200
    created = client.post('/api/v1/orders', headers=_admin_headers(), json={
        'branch_id': BRANCH_ID, 'register_id': 'CAJA-01', 'order_type': 'takeout',
        'payment_method_intent': 'cash',
        'lines': [{'product_id': BURGER_ID, 'quantity': 1, 'notes': 'x' * 501}],
    })
    assert created.status_code == 409
    assert created.json()['detail']['code'] == 'invalid_line_notes'


def test_amendment_preserves_unchanged_historical_long_note() -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    # Historical synthetic fixture predates the 500-character write boundary.
    factory = client.app.state.test_session_factory
    with factory() as session:
        session.execute(models.order_lines.update().where(
            models.order_lines.c.order_id == order['id'],
        ).values(line_notes='x' * 501))
        session.commit()
    path = f"/api/v1/orders/{order['id']}"
    before = client.get(path, headers=_admin_headers()).json()
    response = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-legacy-note-001',
    }, json={'expected_version': before['version'],
             'lines': [{'product_id': BURGER_ID, 'quantity': 2, 'notes': 'x' * 501,
                        'source_line_id': before['lines'][0]['id']}]})
    assert response.status_code == 200
    after = client.get(path, headers=_admin_headers()).json()
    assert after['lines'][0]['line_notes'] == 'x' * 501
    assert after['lines'][0]['quantity'] == 2


def test_amended_order_becomes_ready_only_after_all_active_tasks_complete() -> None:
    _assert_amended_order_ready(_client_with_seeded_database())


@pytest.mark.parametrize('target_index', [1, 2])
def test_amendment_cannot_copy_oversized_historical_note(target_index: int) -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    response = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-two-lines-001',
    }, json={'expected_version': order['version'], 'lines': [
        {'product_id': BURGER_ID, 'quantity': 1},
        {'product_id': BURGER_ID, 'quantity': 1, 'notes': 'Normal'},
    ]})
    assert response.status_code == 200
    before = client.get(path, headers=_admin_headers()).json()
    source_id = before['lines'][0]['id']
    with client.app.state.test_session_factory() as session:
        session.execute(models.order_lines.update().where(
            models.order_lines.c.id == source_id,
        ).values(line_notes='x' * 501))
        session.commit()
    before = client.get(path, headers=_admin_headers()).json()
    lines = [{'product_id': BURGER_ID, 'quantity': 1, 'notes': line['line_notes'],
              'source_line_id': line['id']}
             for line in before['lines']]
    if target_index == 2:
        lines.append({'product_id': BURGER_ID, 'quantity': 1, 'notes': None})
    lines[target_index]['notes'] = 'x' * 501
    rejected = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-copy-note-001',
    }, json={'expected_version': before['version'], 'lines': lines})
    assert rejected.status_code == 409
    assert rejected.json()['detail']['code'] == 'invalid_line_notes'
    after = client.get(path, headers=_admin_headers()).json()
    assert after['version'] == before['version']
    assert after['lines'] == before['lines']
    assert after['production_tasks'] == before['production_tasks']


@pytest.mark.parametrize('mode', ['delete_previous', 'reorder'])
def test_amendment_preserves_source_after_deletion_or_reorder(mode: str) -> None:
    client = _client_with_seeded_database()
    _assert_historical_source_reordered(client, mode)


def _assert_historical_source_reordered(client: Any, mode: str, *, note_length: int = 501) -> None:
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    response = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-source-setup-001',
    }, json={'expected_version': order['version'], 'lines': [
        {'product_id': BURGER_ID, 'quantity': 1, 'notes': 'Anterior'},
        {'product_id': BURGER_ID, 'quantity': 2, 'notes': 'Normal'},
    ]})
    assert response.status_code == 200
    before = client.get(path, headers=_admin_headers()).json()
    source_id = next(line['id'] for line in before['lines'] if line['line_notes'] == 'Normal')
    with client.app.state.test_session_factory() as session:
        session.execute(models.order_lines.update().where(
            models.order_lines.c.id == source_id,
        ).values(line_notes='x' * note_length))
        session.commit()
    before = client.get(path, headers=_admin_headers()).json()
    lines = [{'source_line_id': line['id'], 'product_id': line['product_id'],
              'quantity': line['quantity'], 'notes': line['line_notes']}
             for line in sorted(before['lines'], key=lambda line: line['id'] != source_id)]
    if mode == 'delete_previous':
        lines = lines[:1]
    applied = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-source-apply-001',
    }, json={'expected_version': before['version'], 'lines': lines})
    assert applied.status_code == 200
    after = client.get(path, headers=_admin_headers()).json()
    historical = next(line for line in after['lines'] if line['line_notes'] == 'x' * note_length)
    assert historical['supersedes_line_id'] == source_id
    assert historical['quantity'] == 2
    assert len(after['lines']) == len(lines)


@pytest.mark.parametrize('mode', ['duplicate', 'foreign', 'inactive', 'product', 'changed'])
def test_amendment_source_guards_are_atomic(mode: str) -> None:
    client = _client_with_seeded_database()
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    first = client.get(path, headers=_admin_headers()).json()['lines'][0]['id']
    applied = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-guard-setup-001',
    }, json={'expected_version': order['version'],
             'lines': [{'source_line_id': first, 'product_id': BURGER_ID, 'quantity': 1}]})
    assert applied.status_code == 200
    before = client.get(path, headers=_admin_headers()).json()
    source_id = before['lines'][0]['id']
    line: dict[str, Any] = {'source_line_id': source_id, 'product_id': BURGER_ID, 'quantity': 1}
    if mode == 'foreign':
        line['source_line_id'] = '11111111-1111-4111-8111-111111111111'
    elif mode == 'inactive':
        line['source_line_id'] = first
    elif mode == 'product':
        line['product_id'] = 'other-product'
    elif mode == 'changed':
        line['notes'] = 'x' * 501
    lines = [line, dict(line)] if mode == 'duplicate' else [line]
    response = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-guard-reject-001',
    }, json={'expected_version': before['version'], 'lines': lines})
    assert response.status_code == 409
    assert response.json()['detail']['code'] == (
        'invalid_line_notes' if mode == 'changed' else 'invalid_source_line'
    )
    after = client.get(path, headers=_admin_headers()).json()
    assert after['version'] == before['version']
    assert after['lines'] == before['lines']
    assert after['production_tasks'] == before['production_tasks']


def _assert_amended_order_ready(client: Any) -> None:
    order = _pending_order(client)
    path = f"/api/v1/orders/{order['id']}"
    amended = client.post(path + '/amendments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-amend-kds-001',
    }, json={'expected_version': order['version'], 'lines': [
        {'product_id': BURGER_ID, 'quantity': 2, 'notes': 'Nota conservada'},
        {'product_id': BURGER_ID, 'quantity': 1, 'notes': 'Otra personalización'},
    ]})
    assert amended.status_code == 200
    detail = client.get(path, headers=_admin_headers()).json()
    cancelled_ids = {t['id'] for t in detail['production_tasks'] if t['status'] == 'CANCELLED'}
    active = [t for t in detail['production_tasks'] if t['status'] == 'PENDING']
    assert len(cancelled_ids) == 1 and len(active) == 2
    for index, task in enumerate(active):
        task_path = f"/api/v1/kds/tasks/{task['id']}/transition"
        for status in ('IN_PROGRESS', 'COMPLETED'):
            result = client.post(task_path, headers=_admin_headers(), json={'status': status})
            assert result.status_code == 200
        detail = client.get(path, headers=_admin_headers()).json()
        assert detail['status'] == ('READY' if index == len(active) - 1 else 'IN_PRODUCTION')
        remaining_cancelled = {
            t['id'] for t in detail['production_tasks'] if t['status'] == 'CANCELLED'
        }
        assert remaining_cancelled == cancelled_ids
        assert detail['payments'] == []
    paid = client.post(path + '/payments', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-amend-kds-payment-001',
    }, json={'amount_cents': 28500, 'method': 'cash', 'register_id': 'CAJA-01',
             'received_cash': '300.00'})
    assert paid.status_code == 200
    assert paid.json()['cash_tender']['change_cents'] == 1500
    assert client.get(path, headers=_admin_headers()).json()['status'] == 'READY'
    delivered = client.post(path + '/fulfillment/deliver', headers={
        **_admin_headers(), 'Idempotency-Key': 'cashier-amend-kds-deliver-001',
    }, json={})
    assert delivered.status_code == 200
    assert client.get(path, headers=_admin_headers()).json()['status'] == 'DELIVERED'
    assert len(client.get(path, headers=_admin_headers()).json()['payments']) == 1
