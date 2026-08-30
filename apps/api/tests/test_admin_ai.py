# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-admin-ai-tests-v1
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from restaurant_os import models
from restaurant_os.admin_ai import (
    AdminAiError,
    AdminAiProviderOptions,
    create_admin_ai_response,
    request_openrouter_proposal,
    review_proposal,
)
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from restaurant_os.operations import AuthorizationError, BusinessError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _seed

UTC = timezone.utc

PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000111"
ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
OPTIONS = AdminAiProviderOptions(
    api_key="synthetic-admin-ai-key",
    model="test-model",
    base_url="https://openrouter.invalid/api/v1",
    timeout_seconds=3,
)


def _factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        _seed(session)
        session.commit()
    return factory


def _client(factory: sessionmaker[Session]) -> TestClient:
    app = create_app()

    def override_session():
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _result(
    kind: str,
    target_id: str | None,
    payload: dict[str, Any],
    evidence: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "answer": "Preparé una propuesta revisable.",
        "sources": ["PRD-FR-010", "SDD §43"],
        "questions": [],
        "warnings": [],
        "change_set": [
            {
                "kind": kind,
                "target_id": target_id,
                "payload_json": json.dumps(payload),
                "evidence": evidence,
            }
        ],
    }


def _fake(result: dict[str, Any], captured: dict[str, Any] | None = None):
    def provider(
        prompt: str, context: dict[str, Any], _options: AdminAiProviderOptions
    ) -> dict[str, Any]:
        if captured is not None:
            captured["prompt"] = prompt
            captured["context"] = context
        return result

    return provider


def test_tdd_tc_194_provider_context_is_allowlisted_and_transport_redacts_pii() -> None:
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            content = {
                "answer": "Regla",
                "sources": ["SDD §43"],
                "questions": [],
                "warnings": [],
                "change_set": [],
            }
            return json.dumps({"choices": [{"message": {"content": json.dumps(content)}}]}).encode()

    captured: dict[str, Any] = {}

    def opener(request: Any, timeout: float) -> FakeResponse:
        captured["body"] = json.loads(request.data.decode())
        captured["timeout"] = timeout
        return FakeResponse()

    context = {
        "rules": [],
        "products": [],
        "inventory_items": [],
        "units": [],
        "modifier_groups": [],
        "active_recipes": [],
        "branch_id": BRANCH_ID,
    }
    parsed = request_openrouter_proposal(
        "Ayuda a ana@example.com, 6672013019 con producto 1001", context, OPTIONS, opener
    )
    external = captured["body"]["messages"][1]["content"]
    assert "ana@example.com" not in external and "6672013019" not in external
    assert "[CORREO]" in external and "[TELEFONO]" in external
    assert captured["body"]["temperature"] == 0
    assert captured["body"]["response_format"]["json_schema"]["strict"] is True
    assert parsed["sources"] == ["SDD §43"]


def test_tdd_tc_202_http_boundary_keeps_disabled_provider_in_draft() -> None:
    client = _client(_factory())
    headers = {"X-Actor-User-Id": ADMIN_USER_ID}

    created = client.post(
        "/api/v1/admin-ai/proposals",
        headers=headers,
        json={"prompt": "¿Cómo configuro un producto?", "branch_id": BRANCH_ID},
    )

    assert created.status_code == 200, created.text
    proposal = created.json()
    assert proposal["status"] == "DRAFT"
    assert proposal["payload"]["change_set"] == []

    fetched = client.get(f"/api/v1/admin-ai/proposals/{proposal['id']}", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == proposal["id"]

    accepted = client.post(
        f"/api/v1/admin-ai/proposals/{proposal['id']}/review",
        headers={**headers, "Idempotency-Key": "draft-cannot-apply"},
        json={"accept": True},
    )
    assert accepted.status_code == 409
    assert accepted.json()["detail"]["code"] == "admin_ai_proposal_not_ready"

    rejected = client.post(
        f"/api/v1/admin-ai/proposals/{proposal['id']}/review",
        headers=headers,
        json={"accept": False},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"


def test_tdd_tc_205_observability_uses_ids_and_codes_without_prompt_or_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _client(_factory())
    headers = {"X-Actor-User-Id": ADMIN_USER_ID}
    secret_prompt_marker = "PROMPT-PRIVADO-AIA-205"
    secret_key_marker = "KEY-PRIVADA-AIA-205"

    with caplog.at_level(logging.INFO, logger="restaurant_os.api"):
        created = client.post(
            "/api/v1/admin-ai/proposals",
            headers=headers,
            json={"prompt": secret_prompt_marker, "branch_id": BRANCH_ID},
        )
        proposal = created.json()
        failed = client.post(
            f"/api/v1/admin-ai/proposals/{proposal['id']}/review",
            headers={**headers, "Idempotency-Key": secret_key_marker},
            json={"accept": True},
        )

    assert created.status_code == 200
    assert failed.status_code == 409
    assert "admin_ai_proposal result=success" in caplog.text
    assert "admin_ai_review result=error" in caplog.text
    assert "admin_ai_proposal_not_ready" in caplog.text
    assert proposal["id"] in caplog.text
    assert secret_prompt_marker not in caplog.text
    assert secret_key_marker not in caplog.text


def test_tdd_tc_205_http_permission_denial_is_redacted_and_fail_closed(
    caplog: pytest.LogCaptureFixture,
) -> None:
    client = _client(_factory())
    unauthorized_actor = "018f6f73-2d0a-74f0-8f1c-000000009999"
    prompt_marker = "PROMPT-NO-AUTORIZADO-AIA-205"

    with caplog.at_level(logging.INFO, logger="restaurant_os.api"):
        response = client.post(
            "/api/v1/admin-ai/proposals",
            headers={"X-Actor-User-Id": unauthorized_actor},
            json={"prompt": prompt_marker, "branch_id": BRANCH_ID},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "actor_not_authorized"
    assert "admin_ai_proposal result=error" in caplog.text
    assert "actor_not_authorized" in caplog.text
    assert unauthorized_actor in caplog.text
    assert prompt_marker not in caplog.text


def test_tdd_tc_196_and_198_product_proposal_is_reviewed_applied_and_replayed() -> None:
    factory = _factory()
    prompt = "Actualiza Hamburguesa Kiwi a HAMBURGUESA PREMIUM con precio 9900"
    result = _result(
        "product.update",
        PRODUCT_ID,
        {"name": "HAMBURGUESA PREMIUM", "price_cents": 9900},
        [
            {"field": "target_id", "quote": "Hamburguesa Kiwi"},
            {"field": "name", "quote": "HAMBURGUESA PREMIUM"},
            {"field": "price_cents", "quote": "9900"},
        ],
    )
    with factory() as session:
        proposal = create_admin_ai_response(
            session, ADMIN_USER_ID, prompt, BRANCH_ID, OPTIONS, _fake(result)
        )
        assert proposal["status"] == "READY_FOR_REVIEW"
        assert proposal["payload"]["change_set"][0]["current"]["name"] == "Hamburguesa Kiwi"
        assert (
            session.execute(
                sa.select(models.products.c.name).where(models.products.c.id == PRODUCT_ID)
            ).scalar_one()
            == "Hamburguesa Kiwi"
        )
        applied = review_proposal(session, proposal["id"], ADMIN_USER_ID, True, "apply-product-1")
        assert applied["status"] == "APPLIED" and applied["result"]["id"] == PRODUCT_ID
        replay = review_proposal(session, proposal["id"], ADMIN_USER_ID, True, "apply-product-1")
        assert replay["result"] == applied["result"]
        assert (
            session.execute(
                sa.select(models.products.c.name).where(models.products.c.id == PRODUCT_ID)
            ).scalar_one()
            == "HAMBURGUESA PREMIUM"
        )
        with pytest.raises(BusinessError) as conflict:
            review_proposal(session, proposal["id"], ADMIN_USER_ID, True, "another-key")
        assert conflict.value.code == "idempotency_conflict"


def test_tdd_tc_195_unknown_source_missing_evidence_and_unknown_reference_fail_closed() -> None:
    factory = _factory()
    with factory() as session:
        unknown_source = _result(
            "product.update",
            PRODUCT_ID,
            {"name": "NUEVO NOMBRE"},
            [{"field": "name", "quote": "NUEVO NOMBRE"}],
        )
        unknown_source["sources"] = ["manual inventado"]
        with pytest.raises(AdminAiError) as source_error:
            create_admin_ai_response(
                session, ADMIN_USER_ID, "NUEVO NOMBRE", BRANCH_ID, OPTIONS, _fake(unknown_source)
            )
        assert source_error.value.code == "admin_ai_source_unknown"

        missing = _result(
            "product.update",
            PRODUCT_ID,
            {"price_cents": 1234},
            [
                {"field": "target_id", "quote": "Hamburguesa Kiwi"},
                {"field": "price_cents", "quote": "precio 4321"},
            ],
        )
        with pytest.raises(AdminAiError) as evidence_error:
            create_admin_ai_response(
                session,
                ADMIN_USER_ID,
                "Hamburguesa Kiwi precio 4321",
                BRANCH_ID,
                OPTIONS,
                _fake(missing),
            )
        assert evidence_error.value.code == "admin_ai_evidence_missing"

        bad_reference = _result(
            "modifier_group.create",
            "missing",
            {
                "name": "TAMAÑO",
                "is_required": False,
                "minimum_selections": 0,
                "maximum_selections": 1,
            },
            [
                {"field": "name", "quote": "TAMAÑO"},
                {"field": "is_required", "quote": "opcional"},
                {"field": "minimum_selections", "quote": "mínimo 0"},
                {"field": "maximum_selections", "quote": "máximo 1"},
            ],
        )
        with pytest.raises(AdminAiError) as reference_error:
            create_admin_ai_response(
                session,
                ADMIN_USER_ID,
                "TAMAÑO opcional mínimo 0 máximo 1",
                BRANCH_ID,
                OPTIONS,
                _fake(bad_reference),
            )
        assert reference_error.value.code == "admin_ai_reference_invalid"
        assert (
            session.execute(
                sa.select(sa.func.count()).select_from(models.admin_ai_proposals)
            ).scalar_one()
            == 0
        )


def test_tdd_tc_197_vertical_actions_use_canonical_services() -> None:
    factory = _factory()
    with factory() as session:
        product_prompt = (
            "Crea producto PANINI VERDE SKU 9100 categoría COMIDA estación cocina precio 8800"
        )
        product_raw = _result(
            "product.create",
            None,
            {
                "name": "PANINI VERDE",
                "sku": "9100",
                "category_name": "COMIDA",
                "station": "kitchen",
                "price_cents": 8800,
            },
            [
                {"field": "name", "quote": "PANINI VERDE"},
                {"field": "sku", "quote": "9100"},
                {"field": "category_name", "quote": "COMIDA"},
                {"field": "station", "quote": "cocina"},
                {"field": "price_cents", "quote": "8800"},
            ],
        )
        product_proposal = create_admin_ai_response(
            session,
            ADMIN_USER_ID,
            product_prompt,
            BRANCH_ID,
            OPTIONS,
            _fake(product_raw),
        )
        product_applied = review_proposal(
            session, product_proposal["id"], ADMIN_USER_ID, True, "apply-product-create"
        )
        assert product_applied["result"]["sku"] == "9100"

        item_prompt = "Crea insumo QUESO NUEVO SKU 9001 tipo ingredient unidad Gramo"
        item_raw = _result(
            "inventory_item.create",
            None,
            {
                "name": "QUESO NUEVO",
                "sku": "9001",
                "base_unit_id": UNIT_ID,
                "item_type": "ingredient",
            },
            [
                {"field": "name", "quote": "QUESO NUEVO"},
                {"field": "sku", "quote": "9001"},
                {"field": "item_type", "quote": "ingredient"},
                {"field": "base_unit_id", "quote": "unidad Gramo"},
            ],
        )
        item_proposal = create_admin_ai_response(
            session, ADMIN_USER_ID, item_prompt, BRANCH_ID, OPTIONS, _fake(item_raw)
        )
        item_applied = review_proposal(
            session, item_proposal["id"], ADMIN_USER_ID, True, "apply-item"
        )
        assert item_applied["result"]["sku"] == "9001"

        group_prompt = "Para Hamburguesa Kiwi crea grupo TAMAÑO opcional mínimo 0 máximo 1"
        group_raw = _result(
            "modifier_group.create",
            PRODUCT_ID,
            {
                "name": "TAMAÑO",
                "is_required": False,
                "minimum_selections": 0,
                "maximum_selections": 1,
            },
            [
                {"field": "target_id", "quote": "Hamburguesa Kiwi"},
                {"field": "name", "quote": "TAMAÑO"},
                {"field": "is_required", "quote": "opcional"},
                {"field": "minimum_selections", "quote": "mínimo 0"},
                {"field": "maximum_selections", "quote": "máximo 1"},
            ],
        )
        group_proposal = create_admin_ai_response(
            session, ADMIN_USER_ID, group_prompt, BRANCH_ID, OPTIONS, _fake(group_raw)
        )
        group_applied = review_proposal(
            session, group_proposal["id"], ADMIN_USER_ID, True, "apply-group"
        )

        option_prompt = "En grupo TAMAÑO crea opción SIN CORTAR efecto instruction precio 0"
        option_raw = _result(
            "modifier_option.create",
            group_applied["result"]["id"],
            {"name": "SIN CORTAR", "effect_type": "instruction", "price_delta_cents": 0},
            [
                {"field": "target_id", "quote": "grupo TAMAÑO"},
                {"field": "name", "quote": "SIN CORTAR"},
                {"field": "effect_type", "quote": "instruction"},
                {"field": "price_delta_cents", "quote": "precio 0"},
            ],
        )
        option_proposal = create_admin_ai_response(
            session, ADMIN_USER_ID, option_prompt, BRANCH_ID, OPTIONS, _fake(option_raw)
        )
        option_applied = review_proposal(
            session, option_proposal["id"], ADMIN_USER_ID, True, "apply-option"
        )
        assert option_applied["result"]["group_id"] == group_applied["result"]["id"]

        recipe_prompt = (
            "Versiona receta de Hamburguesa Kiwi con rendimiento 1 Gramo, "
            "Carne molida 100 Gramo y merma 0"
        )
        recipe_raw = _result(
            "recipe.version",
            PRODUCT_ID,
            {
                "yield_quantity": "1",
                "yield_unit_id": UNIT_ID,
                "components": [
                    {
                        "item_id": ITEM_ID,
                        "unit_id": UNIT_ID,
                        "net_quantity": "100",
                        "waste_rate": "0",
                    }
                ],
            },
            [
                {"field": "target_id", "quote": "Hamburguesa Kiwi"},
                {"field": "yield_quantity", "quote": "rendimiento 1"},
                {"field": "yield_unit_id", "quote": "1 Gramo"},
                {"field": "components.0.item_id", "quote": "Carne molida"},
                {"field": "components.0.unit_id", "quote": "100 Gramo"},
                {"field": "components.0.net_quantity", "quote": "100"},
                {"field": "components.0.waste_rate", "quote": "merma 0"},
            ],
        )
        recipe_proposal = create_admin_ai_response(
            session, ADMIN_USER_ID, recipe_prompt, BRANCH_ID, OPTIONS, _fake(recipe_raw)
        )
        recipe_applied = review_proposal(
            session, recipe_proposal["id"], ADMIN_USER_ID, True, "apply-recipe"
        )
        assert recipe_applied["result"]["product_id"] == PRODUCT_ID
        assert recipe_applied["result"]["components"][0]["item_id"] == ITEM_ID


def test_tdd_tc_198_stale_and_tdd_tc_199_reject_are_fail_closed() -> None:
    factory = _factory()
    prompt = "Actualiza Hamburguesa Kiwi a HAMBURGUESA STALE"
    raw = _result(
        "product.update",
        PRODUCT_ID,
        {"name": "HAMBURGUESA STALE"},
        [
            {"field": "target_id", "quote": "Hamburguesa Kiwi"},
            {"field": "name", "quote": "HAMBURGUESA STALE"},
        ],
    )
    with factory() as session:
        stale = create_admin_ai_response(
            session, ADMIN_USER_ID, prompt, BRANCH_ID, OPTIONS, _fake(raw)
        )
        session.execute(
            sa.update(models.products)
            .where(models.products.c.id == PRODUCT_ID)
            .values(updated_at=datetime(2030, 1, 1, tzinfo=UTC))
        )
        session.commit()
        with pytest.raises(BusinessError) as stale_error:
            review_proposal(session, stale["id"], ADMIN_USER_ID, True, "stale-key")
        assert stale_error.value.code == "admin_ai_proposal_stale"
        assert (
            session.execute(
                sa.select(models.products.c.name).where(models.products.c.id == PRODUCT_ID)
            ).scalar_one()
            == "Hamburguesa Kiwi"
        )

    factory = _factory()
    with factory() as session:
        unauthorized = create_admin_ai_response(
            session, ADMIN_USER_ID, prompt, BRANCH_ID, OPTIONS, _fake(raw)
        )
        with pytest.raises(AuthorizationError):
            review_proposal(
                session, unauthorized["id"], "actor-without-role", True, "unauthorized-key"
            )
        assert (
            session.execute(
                sa.select(models.products.c.name).where(models.products.c.id == PRODUCT_ID)
            ).scalar_one()
            == "Hamburguesa Kiwi"
        )

    factory = _factory()
    with factory() as session:
        expired = create_admin_ai_response(
            session, ADMIN_USER_ID, prompt, BRANCH_ID, OPTIONS, _fake(raw)
        )
        session.execute(
            sa.update(models.admin_ai_proposals)
            .where(models.admin_ai_proposals.c.id == expired["id"])
            .values(expires_at=datetime(2000, 1, 1, tzinfo=UTC))
        )
        session.commit()
        with pytest.raises(BusinessError) as expired_error:
            review_proposal(session, expired["id"], ADMIN_USER_ID, True, "expired-key")
        assert expired_error.value.code == "admin_ai_proposal_expired"
        assert (
            session.execute(
                sa.select(models.admin_ai_proposals.c.status).where(
                    models.admin_ai_proposals.c.id == expired["id"]
                )
            ).scalar_one()
            == "EXPIRED"
        )

    factory = _factory()
    with factory() as session:
        rejected = create_admin_ai_response(
            session, ADMIN_USER_ID, prompt, BRANCH_ID, OPTIONS, _fake(raw)
        )
        decision = review_proposal(session, rejected["id"], ADMIN_USER_ID, False)
        assert decision["status"] == "REJECTED"
        assert (
            session.execute(
                sa.select(models.products.c.name).where(models.products.c.id == PRODUCT_ID)
            ).scalar_one()
            == "Hamburguesa Kiwi"
        )


def test_tdd_tc_194_disabled_provider_returns_non_applicable_local_guidance() -> None:
    factory = _factory()
    with factory() as session:
        response = create_admin_ai_response(
            session, ADMIN_USER_ID, "¿Cómo funcionan los modificadores?", BRANCH_ID
        )
        assert response["status"] == "DRAFT"
        assert response["payload"]["change_set"] == []
        assert "deshabilitado" in response["payload"]["warnings"][0]
        with pytest.raises(BusinessError) as not_ready:
            review_proposal(session, response["id"], ADMIN_USER_ID, True, "must-not-apply")
        assert not_ready.value.code == "admin_ai_proposal_not_ready"
