from decimal import Decimal

import pytest
from restaurant_os import delivery_fee_fiscal
from restaurant_os.delivery_fee import calculate_charge, normalize_selection
from restaurant_os.operations import BusinessError
from test_delivery_fee_commands import quote, setup_delivery
from test_delivery_fee_pricing import tariff
from test_platform_api import _admin_headers, _test_session_factory


def test_fiscal_delivery_is_exact_separate_and_requires_issuer_mapping() -> None:
    charge = calculate_charge(tariff(), {}, normalize_selection(None), 9500)
    with pytest.raises(BusinessError) as missing:
        delivery_fee_fiscal.service_item(charge, "issuer-test")
    assert missing.value.code == "delivery_fiscal_mapping_required"
    charge["tariff"]["fiscal_mapping"] = {
        "emitter_id": "issuer-test",
        "product_key": "TEST-ONLY",
        "unit_key": "TEST-UNIT",
    }
    item = delivery_fee_fiscal.service_item(charge, "issuer-test")
    assert item is not None
    assert item["product"]["price"] == Decimal("28.00")
    assert item["product"]["taxes"][0]["rate"] == Decimal("0.16")
    with pytest.raises(BusinessError):
        delivery_fee_fiscal.service_item(charge, "different-issuer")
    charge["charged_cents"] = 0
    assert delivery_fee_fiscal.service_item(charge, "issuer-test") is None


def test_paid_delivery_blocks_legacy_aggregate_before_any_provider_call() -> None:
    client, payload, _ = setup_delivery()
    payload["delivery_quote_reference"] = quote(client, payload)["delivery_quote_reference"]
    order = client.post("/api/v1/orders", headers=_admin_headers(), json=payload).json()
    response = client.post(
        f"/api/v1/orders/{order['id']}/payments",
        headers=_admin_headers(),
        json={"amount_cents": 12300, "method": "cash", "register_id": "CAJA-01"},
    )
    assert response.status_code == 200
    with _test_session_factory(client)() as session:
        with pytest.raises(BusinessError) as blocked:
            delivery_fee_fiscal.reject_aggregate_receipt(session, [order["id"]])
        assert blocked.value.code == "fiscal_concept_snapshot_required"
        assert delivery_fee_fiscal.payment_charge(session, order["id"])["charged_cents"] == 2800
