# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-assisted-order-tests-v1
from __future__ import annotations

import json
from typing import Any

import pytest
from restaurant_os.assisted_order import (
    AssistedOrderError,
    OpenRouterOptions,
    build_assisted_draft,
    extract_and_redact_customer,
)

OPTIONS = OpenRouterOptions(
    api_key="synthetic-test-key-not-secret",
    model="google/gemini-3.1-flash-lite",
    base_url="https://openrouter.invalid/api/v1",
    timeout_seconds=3,
)


class FakeResponse:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def model_opener(proposal: dict[str, Any], captured: dict[str, Any] | None = None):
    def open_request(request: Any, timeout: float) -> FakeResponse:
        if captured is not None:
            captured["timeout"] = timeout
            captured["body"] = json.loads(request.data.decode("utf-8"))
        return FakeResponse({"choices": [{"message": {"content": json.dumps(proposal)}}]})

    return open_request


def catalog() -> list[dict[str, Any]]:
    return [
        {"id": "baguette-bbq", "name": "Baguette BBQ", "status": "active", "is_available": True}
    ]


def groups(_product_id: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "bread",
            "name": "Pan",
            "minimum_selections": 1,
            "maximum_selections": 1,
            "options": [
                {"id": "white", "name": "Pan blanco", "price_delta_cents": 0},
                {"id": "whole", "name": "Pan integral", "price_delta_cents": 500},
            ],
        },
        {
            "id": "comments",
            "name": "Comentarios del pedido",
            "minimum_selections": 0,
            "maximum_selections": 3,
            "options": [
                {
                    "id": "no-onion",
                    "name": "Sin cebolla",
                    "price_delta_cents": 0,
                    "variation_kind": "order_comment",
                }
            ],
        },
    ]


def test_redacts_name_and_phone_before_openrouter_and_asks_required_group() -> None:
    captured: dict[str, Any] = {}
    text = (
        "Pedido para Miguel Ángel González con teléfono 6672013019, "
        "un baguette BBQ sin cebolla para recoger"
    )
    draft = build_assisted_draft(
        text,
        catalog(),
        groups,
        OPTIONS,
        model_opener(
            {"order_type": "takeout", "lines": [{"product_id": "baguette-bbq", "quantity": 1}]},
            captured,
        ),
    )

    external_request = captured["body"]["messages"][1]["content"]
    assert "Miguel Ángel González" not in external_request
    assert "6672013019" not in external_request
    assert "[CLIENTE]" in external_request and "[TELEFONO]" in external_request
    assert draft["customer_name"] == "Miguel Ángel González"
    assert draft["phone"] == "6672013019"
    assert draft["status"] == "needs_input"
    assert draft["questions"][0]["group_id"] == "bread"
    assert draft["lines"][0]["selected_options"][0]["option_id"] == "no-onion"


def test_explicit_required_option_makes_draft_ready() -> None:
    draft = build_assisted_draft(
        "Un baguette BBQ con pan integral sin cebolla para llevar",
        catalog(),
        groups,
        OPTIONS,
        model_opener(
            {"order_type": "takeout", "lines": [{"product_id": "baguette-bbq", "quantity": 1}]}
        ),
    )

    assert draft["status"] == "ready"
    assert draft["questions"] == []
    assert {option["option_id"] for option in draft["lines"][0]["selected_options"]} == {
        "whole",
        "no-onion",
    }


def test_unknown_product_id_fails_closed() -> None:
    with pytest.raises(AssistedOrderError, match="catálogo") as error:
        build_assisted_draft(
            "Un producto",
            catalog(),
            groups,
            OPTIONS,
            model_opener(
                {"order_type": None, "lines": [{"product_id": "invented", "quantity": 1}]}
            ),
        )

    assert error.value.code == "assisted_order_catalog_mismatch"


def test_extract_customer_without_explicit_phone_label() -> None:
    name, phone, redacted = extract_and_redact_customer(
        "Una ensalada grande para Miguel Gonzalez 6672013019 para recoger"
    )

    assert name == "Miguel Gonzalez"
    assert phone == "6672013019"
    assert name not in redacted and phone not in redacted


def test_takeout_phrase_is_not_mistaken_for_customer_name() -> None:
    name, phone, _redacted = extract_and_redact_customer("Un baguette BBQ para recoger")

    assert name == ""
    assert phone == ""
