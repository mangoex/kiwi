# SEC001-SYNTHETIC-FIXTURE provenance=restaurantos-grokbot-agent-tools-v1
from __future__ import annotations

import base64
from collections.abc import Generator
from datetime import datetime, timezone

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient
from pydantic import ValidationError
from restaurant_os import models
from restaurant_os.agent_tools import (
    AgentPrincipal,
    CatalogFields,
    InventoryProposal,
    PurchaseDraft,
    RecipeProposal,
    _persist_command,
)
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.database import get_session
from restaurant_os.main import create_app
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool
from test_platform_api import ADMIN_USER_ID, BRANCH_ID, _seed

UTC = timezone.utc
ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"
SECOND_BRANCH_ID = "018f6f73-2d0a-74f0-8f1c-000000000004"
UNIT_ID = "018f6f73-2d0a-74f0-8f1c-000000000301"
ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000311"
SUPPLIER_ID = "018f6f73-2d0a-74f0-8f1c-000000000701"
PRESENTATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000711"
FOREIGN_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000811"
FOREIGN_ITEM_ID = "018f6f73-2d0a-74f0-8f1c-000000000812"
LOCAL_PRODUCT_ID = "018f6f73-2d0a-74f0-8f1c-000000000813"
FOREIGN_COMPONENT_RECIPE_ID = "018f6f73-2d0a-74f0-8f1c-000000000814"


def _factory() -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    models.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    with factory() as session:
        _seed(session)
    return factory


def _client(factory: sessionmaker[Session]) -> TestClient:
    settings = get_settings()
    previous = settings.grokbot_agent_tools_enabled
    settings.grokbot_agent_tools_enabled = True
    try:
        app = create_app()
    finally:
        settings.grokbot_agent_tools_enabled = previous

    def override_session() -> Generator[Session, None, None]:
        with factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_session
    return TestClient(app)


def _admin_headers() -> dict[str, str]:
    token = create_session_token({"sub": ADMIN_USER_ID}, get_settings().secret_key)
    return {"Authorization": f"Bearer {token}"}


def _basic(client_id: str, client_secret: str) -> str:
    encoded = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    return f"Basic {encoded}"


def _configure(
    client: TestClient,
    profile: str,
    capabilities: list[str],
    *,
    corporate_scope: bool = False,
) -> tuple[str, str]:
    saved = client.put(
        "/api/v1/integrations/grokbot/config",
        headers=_admin_headers(),
        json={
            "display_name": "Administrador Kiwi",
            "base_url": "https://grokbot.example.com",
            "callback_url": "https://grokbot.example.com/callback",
            "is_enabled": True,
        },
    )
    assert saved.status_code == 200, saved.text
    rotated = client.post(
        f"/api/v1/integrations/grokbot/identities/{profile}/rotate-secret",
        headers=_admin_headers(),
    )
    assert rotated.status_code == 200, rotated.text
    credential = rotated.json()
    enabled = client.put(
        f"/api/v1/integrations/grokbot/identities/{profile}",
        headers=_admin_headers(),
        json={
            "is_enabled": True,
            "capabilities": capabilities,
            "branch_ids": [BRANCH_ID],
            "corporate_scope": corporate_scope,
            "expected_authorization_version": credential["authorization_version"],
        },
    )
    assert enabled.status_code == 200, enabled.text
    return credential["client_id"], credential["client_secret"]


def _token(client: TestClient, client_id: str, client_secret: str) -> str:
    response = client.post(
        "/api/v1/agent-auth/token",
        headers={"Authorization": _basic(client_id, client_secret)},
        data={"grant_type": "client_credentials"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["expires_in"] <= 600
    return response.json()["access_token"]


def test_tdd_tc_358_global_feature_flag_is_default_off() -> None:
    settings = get_settings()
    previous = settings.grokbot_agent_tools_enabled
    settings.grokbot_agent_tools_enabled = False
    try:
        client = TestClient(create_app())
    finally:
        settings.grokbot_agent_tools_enabled = previous
    assert client.get("/api/v1/agent-tools/context").status_code == 404


def test_tdd_tc_365_config_is_default_off_and_secrets_are_one_time() -> None:
    factory = _factory()
    client = _client(factory)

    denied = client.get("/api/v1/integrations/grokbot/config")
    assert denied.status_code == 403

    initial = client.get("/api/v1/integrations/grokbot/config", headers=_admin_headers())
    assert initial.status_code == 200, initial.text
    assert initial.json()["is_enabled"] is False
    assert initial.json()["state"] == "DISCONNECTED"
    assert initial.json()["orchestrator_label"] == "Administrador Kiwi"
    assert {row["profile"] for row in initial.json()["identities"]} == {
        "administrator",
        "kitchen",
        "inventory",
        "purchasing",
    }
    assert all(row["is_enabled"] is False for row in initial.json()["identities"])

    for invalid_payload in (
        {"base_url": "https://example.com/" + ("a" * 590)},
        {"callback_url": 123},
        {"callback_secret_ref": 123},
        {"callback_secret_ref": "s" * 241},
    ):
        invalid = client.put(
            "/api/v1/integrations/grokbot/config",
            headers=_admin_headers(),
            json={"display_name": "Administrador Kiwi", **invalid_payload},
        )
        assert invalid.status_code == 400, invalid.text
        assert invalid.json()["detail"]["code"] == "agent_schema_invalid"

    malformed = client.put(
        "/api/v1/integrations/grokbot/config",
        headers={**_admin_headers(), "Content-Type": "application/json"},
        content="{",
    )
    assert malformed.status_code == 400, malformed.text
    assert malformed.json()["detail"]["code"] == "agent_schema_invalid"

    client_id, secret = _configure(
        client,
        "administrator",
        ["agent.context.read", "agent.catalog.read", "agent.catalog.propose"],
        corporate_scope=True,
    )
    assert len(secret) >= 32
    stored = client.get("/api/v1/integrations/grokbot/config", headers=_admin_headers()).json()
    administrator = next(row for row in stored["identities"] if row["profile"] == "administrator")
    assert administrator["client_id"] == client_id
    assert "client_secret" not in administrator


def test_tdd_tc_359_service_auth_revalidates_rotation_and_rejects_human_tokens() -> None:
    client = _client(_factory())
    client_id, secret = _configure(
        client,
        "inventory",
        ["agent.context.read", "agent.inventory.read", "agent.inventory_item.propose"],
    )
    token = _token(client, client_id, secret)

    context = client.get(
        "/api/v1/agent-tools/context", headers={"Authorization": f"Bearer {token}"}
    )
    assert context.status_code == 200, context.text
    assert context.json()["profile"] == "inventory"
    assert context.json()["branches"] == [
        {"id": BRANCH_ID, "code": "PILOTO", "name": "Sucursal Piloto"}
    ]

    human = create_session_token({"sub": ADMIN_USER_ID}, get_settings().secret_key)
    rejected = client.get(
        "/api/v1/agent-tools/context", headers={"Authorization": f"Bearer {human}"}
    )
    assert rejected.status_code == 401
    assert rejected.json()["detail"]["code"] == "agent_unauthorized"

    rotated = client.post(
        "/api/v1/integrations/grokbot/identities/inventory/rotate-secret",
        headers=_admin_headers(),
    )
    assert rotated.status_code == 200
    revoked = client.get(
        "/api/v1/agent-tools/context", headers={"Authorization": f"Bearer {token}"}
    )
    assert revoked.status_code == 403
    assert revoked.json()["detail"]["code"] == "agent_disabled"


def test_tdd_tc_359_identity_policy_rejects_stale_concurrent_updates() -> None:
    client = _client(_factory())
    client_id, secret = _configure(
        client,
        "inventory",
        ["agent.context.read", "agent.inventory.read", "agent.inventory_item.propose"],
    )
    assert client_id and secret
    config = client.get("/api/v1/integrations/grokbot/config", headers=_admin_headers()).json()
    identity = next(row for row in config["identities"] if row["profile"] == "inventory")
    payload = {
        "is_enabled": identity["is_enabled"],
        "corporate_scope": identity["corporate_scope"],
        "capabilities": identity["capabilities"],
        "branch_ids": identity["branch_ids"],
        "expected_authorization_version": identity["authorization_version"],
    }
    first = client.put(
        "/api/v1/integrations/grokbot/identities/inventory",
        headers=_admin_headers(),
        json={**payload, "corporate_scope": True},
    )
    assert first.status_code == 200, first.text
    stale = client.put(
        "/api/v1/integrations/grokbot/identities/inventory",
        headers=_admin_headers(),
        json={**payload, "is_enabled": False},
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "stale_reference"


def test_tdd_tc_360_branch_reads_exclude_another_branch_catalog() -> None:
    factory = _factory()
    with factory() as session:
        pilot = (
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        category_id = session.scalar(sa.select(models.product_categories.c.id).limit(1))
        now = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)
        session.execute(
            models.branches.insert().values(
                id=SECOND_BRANCH_ID,
                organization_id=pilot["organization_id"],
                legal_entity_id=pilot["legal_entity_id"],
                business_unit_id=pilot["business_unit_id"],
                name="Sucursal Ajena",
                code="AJENA",
                timezone="America/Chihuahua",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.products.insert().values(
                id=FOREIGN_PRODUCT_ID,
                organization_id=ORGANIZATION_ID,
                category_id=category_id,
                name="PRODUCTO DE OTRA SUCURSAL",
                sku="900090",
                station="kitchen",
                status="active",
                catalog_scope="branch",
                source_branch_id=SECOND_BRANCH_ID,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.products.insert().values(
                id=LOCAL_PRODUCT_ID,
                organization_id=ORGANIZATION_ID,
                category_id=category_id,
                name="PRODUCTO CORPORATIVO PARA RECETA",
                sku="900092",
                station="kitchen",
                status="active",
                catalog_scope="organization",
                source_branch_id=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.inventory_items.insert().values(
                id=FOREIGN_ITEM_ID,
                organization_id=ORGANIZATION_ID,
                name="INSUMO DE OTRA SUCURSAL",
                sku="900091",
                base_unit_id=UNIT_ID,
                item_type="ingredient",
                catalog_scope="branch",
                source_branch_id=SECOND_BRANCH_ID,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.recipes.insert().values(
                id=FOREIGN_COMPONENT_RECIPE_ID,
                organization_id=ORGANIZATION_ID,
                product_id=LOCAL_PRODUCT_ID,
                output_item_id=None,
                branch_id=None,
                recipe_type="sale",
                version=1,
                status="active",
                yield_quantity=1,
                yield_unit_id=UNIT_ID,
                valid_from=now,
                valid_to=None,
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.recipe_components.insert().values(
                recipe_id=FOREIGN_COMPONENT_RECIPE_ID,
                item_id=FOREIGN_ITEM_ID,
                quantity_base_units=1,
                unit_id=UNIT_ID,
                net_quantity=1,
                waste_rate=0,
                gross_quantity=1,
                sort_order=0,
                notes=None,
            )
        )
        session.commit()

    client = _client(factory)
    client_id, secret = _configure(
        client,
        "kitchen",
        [
            "agent.context.read",
            "agent.catalog.read",
            "agent.inventory.read",
            "agent.recipes.read",
            "agent.recipe.propose",
        ],
    )
    token = _token(client, client_id, secret)
    headers = {"Authorization": f"Bearer {token}"}
    catalog = client.get(
        "/api/v1/agent-tools/catalog/items",
        params={"branch_id": BRANCH_ID},
        headers=headers,
    )
    inventory = client.get(
        "/api/v1/agent-tools/inventory/items",
        params={"branch_id": BRANCH_ID},
        headers=headers,
    )
    stock = client.get(
        "/api/v1/agent-tools/inventory/stock",
        params={"branch_id": BRANCH_ID},
        headers=headers,
    )
    recipes = client.get(
        "/api/v1/agent-tools/recipes",
        params={"branch_id": BRANCH_ID},
        headers=headers,
    )
    assert (
        catalog.status_code
        == inventory.status_code
        == stock.status_code
        == recipes.status_code
        == 200
    )
    assert FOREIGN_PRODUCT_ID not in {item["id"] for item in catalog.json()["items"]}
    assert FOREIGN_ITEM_ID not in {item["id"] for item in inventory.json()["items"]}
    assert FOREIGN_ITEM_ID not in {item["item_id"] for item in stock.json()["items"]}
    assert FOREIGN_COMPONENT_RECIPE_ID not in {item["id"] for item in recipes.json()["items"]}

    invalid_recipe = client.post(
        "/api/v1/agent-tools/proposals/recipes",
        headers={
            **headers,
            "Idempotency-Key": "cross-branch-recipe-component-001",
        },
        json={
            "scope": {"kind": "branch", "branch_id": BRANCH_ID},
            "target_id": LOCAL_PRODUCT_ID,
            "expected_active_recipe_id": None,
            "yield_quantity": "1",
            "yield_unit_id": UNIT_ID,
            "components": [
                {
                    "item_id": FOREIGN_ITEM_ID,
                    "unit_id": UNIT_ID,
                    "net_quantity": "1",
                    "waste_rate": "0",
                }
            ],
        },
    )
    assert invalid_recipe.status_code == 409
    assert invalid_recipe.json()["detail"]["code"] == "stale_reference"

    admin_client_id, admin_secret = _configure(
        client,
        "administrator",
        ["agent.context.read", "agent.catalog.read", "agent.catalog.propose"],
        corporate_scope=True,
    )
    admin_token = _token(client, admin_client_id, admin_secret)
    invalid_corporate_update = client.post(
        "/api/v1/agent-tools/proposals/catalog",
        headers={
            "Authorization": f"Bearer {admin_token}",
            "Idempotency-Key": "cross-scope-product-update-001",
        },
        json={
            "scope": {"kind": "corporate"},
            "action": "product.update",
            "target_id": FOREIGN_PRODUCT_ID,
            "expected_version": 1,
            "fields": {"name": "NO DEBE CAMBIAR"},
        },
    )
    assert invalid_corporate_update.status_code == 409
    assert invalid_corporate_update.json()["detail"]["code"] == "stale_reference"


def test_tdd_tc_368_decimal_strings_and_storage_boundaries_are_strict() -> None:
    assert CatalogFields.model_validate(
        {"sku": "9" * 64, "name": "A" * 160, "image_url": "x" * 512}
    )
    with pytest.raises(ValidationError):
        CatalogFields.model_validate({"sku": "9" * 65})
    with pytest.raises(ValidationError):
        CatalogFields.model_validate({"name": "A" * 161})
    with pytest.raises(ValidationError):
        CatalogFields.model_validate({"image_url": "x" * 513})
    assert InventoryProposal.model_validate(
        {
            "scope": {"kind": "corporate"},
            "sku": "9" * 64,
            "name": "A" * 160,
            "base_unit_id": UNIT_ID,
        }
    )

    valid_recipe = {
        "scope": {"kind": "branch", "branch_id": BRANCH_ID},
        "target_id": LOCAL_PRODUCT_ID,
        "expected_active_recipe_id": None,
        "yield_quantity": "1.000001",
        "yield_unit_id": UNIT_ID,
        "components": [
            {
                "item_id": ITEM_ID,
                "unit_id": UNIT_ID,
                "net_quantity": "0.000001",
                "waste_rate": "0.999999",
            }
        ],
    }
    assert RecipeProposal.model_validate(valid_recipe).yield_quantity == "1.000001"
    with pytest.raises(ValidationError):
        RecipeProposal.model_validate({**valid_recipe, "yield_quantity": 1})
    with pytest.raises(ValidationError):
        RecipeProposal.model_validate({**valid_recipe, "yield_quantity": "1e1"})
    with pytest.raises(ValidationError):
        RecipeProposal.model_validate({**valid_recipe, "yield_quantity": "0"})

    valid_purchase = {
        "branch_id": BRANCH_ID,
        "supplier_id": SUPPLIER_ID,
        "document_type": "receipt",
        "folio": "BOUNDARY-1",
        "document_date": "2026-10-10",
        "payment_method": "other",
        "paid_from_cash": False,
        "freight_total": "0",
        "lines": [
            {
                "presentation_id": PRESENTATION_ID,
                "quantity": "1",
                "unit_price": "999999999999.999999",
                "discount": "0",
                "tax": "0",
            }
        ],
    }
    assert PurchaseDraft.model_validate(valid_purchase).lines[0].quantity == "1"
    invalid_numeric = {
        **valid_purchase,
        "lines": [{**valid_purchase["lines"][0], "quantity": 1}],
    }
    with pytest.raises(ValidationError):
        PurchaseDraft.model_validate(invalid_numeric)


def test_tdd_tc_361_363_catalog_proposal_is_scoped_and_idempotent() -> None:
    factory = _factory()
    with factory() as session:
        pilot = (
            session.execute(sa.select(models.branches).where(models.branches.c.id == BRANCH_ID))
            .mappings()
            .one()
        )
        now = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)
        session.execute(
            models.branches.insert().values(
                id=SECOND_BRANCH_ID,
                organization_id=pilot["organization_id"],
                legal_entity_id=pilot["legal_entity_id"],
                business_unit_id=pilot["business_unit_id"],
                name="Sucursal Secundaria",
                code="SECUNDARIA",
                timezone="America/Chihuahua",
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        role_id = session.scalar(
            sa.select(models.user_roles.c.role_id).where(
                models.user_roles.c.user_id == ADMIN_USER_ID
            )
        )
        session.execute(
            models.role_authority_grants.insert().values(
                role_id=role_id,
                authority_kind="organization_all_permissions",
                created_at=now,
            )
        )
        session.commit()
    client = _client(factory)
    client_id, secret = _configure(
        client,
        "administrator",
        ["agent.context.read", "agent.catalog.read", "agent.catalog.propose"],
        corporate_scope=True,
    )
    token = _token(client, client_id, secret)
    headers = {
        "Authorization": f"Bearer {token}",
        "Idempotency-Key": "grokbot-product-create-001",
        "X-Correlation-Id": "pilot-correlation-001",
    }
    catalog_snapshot = client.get(
        "/api/v1/agent-tools/catalog/items",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert catalog_snapshot.status_code == 200, catalog_snapshot.text
    stale_target = catalog_snapshot.json()["items"][0]
    with factory() as session:
        session.execute(
            sa.update(models.products)
            .where(models.products.c.id == stale_target["id"])
            .values(updated_at=datetime(2026, 10, 11, 18, 0, tzinfo=UTC))
        )
        session.commit()
    stale_update = client.post(
        "/api/v1/agent-tools/proposals/catalog",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "grokbot-product-stale-update-001",
        },
        json={
            "scope": {"kind": "corporate"},
            "action": "product.update",
            "target_id": stale_target["id"],
            "expected_version": stale_target["version"],
            "fields": {"name": "PRODUCTO CAMBIADO"},
        },
    )
    assert stale_update.status_code == 409, stale_update.text
    assert stale_update.json()["detail"]["code"] == "stale_reference"

    command = {
        "scope": {"kind": "corporate"},
        "action": "product.create",
        "target_id": None,
        "expected_version": None,
        "fields": {
            "sku": "900001",
            "name": "PRODUCTO PROPUESTO POR GROKBOT",
            "category_name": "PRUEBAS",
            "station": "kitchen",
            "price_cents": 12500,
        },
    }

    created = client.post("/api/v1/agent-tools/proposals/catalog", headers=headers, json=command)
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "READY_FOR_REVIEW"
    replay = client.post("/api/v1/agent-tools/proposals/catalog", headers=headers, json=command)
    assert replay.status_code == 202
    assert replay.json() == created.json()
    conflict = client.post(
        "/api/v1/agent-tools/proposals/catalog",
        headers=headers,
        json={**command, "fields": {**command["fields"], "name": "OTRO NOMBRE"}},
    )
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "idempotency_conflict"

    denied = client.post(
        "/api/v1/agent-tools/proposals/inventory-items",
        headers={**headers, "Idempotency-Key": "wrong-specialist-001"},
        json={
            "scope": {"kind": "corporate"},
            "sku": "INS-BOT-001",
            "name": "Insumo inválido para administrador",
            "base_unit_id": UNIT_ID,
            "item_type": "ingredient",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["detail"]["code"] == "agent_capability_denied"

    with factory() as session:
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.products)
                .where(models.products.c.sku == "900001")
            )
            == 0
        )
        proposal = (
            session.execute(
                sa.select(models.admin_ai_proposals).where(
                    models.admin_ai_proposals.c.id == created.json()["resource_id"]
                )
            )
            .mappings()
            .one()
        )
        assert proposal["origin"] == "GROKBOT"
        assert proposal["actor_user_id"] is None
        assert proposal["actor_agent_identity_id"] is not None
        operation = (
            session.execute(
                sa.select(models.external_agent_commands).where(
                    models.external_agent_commands.c.id == created.json()["operation_id"]
                )
            )
            .mappings()
            .one()
        )
        assert operation["request_hash"]
        callback = (
            session.execute(
                sa.select(models.external_agent_callback_outbox).where(
                    models.external_agent_callback_outbox.c.operation_id == operation["id"]
                )
            )
            .mappings()
            .one()
        )
        serialized = str(callback["payload"])
        assert "PRODUCTO PROPUESTO" not in serialized
        assert "price_cents" not in serialized
        identity = (
            session.execute(
                sa.select(models.external_agent_identities).where(
                    models.external_agent_identities.c.id == operation["identity_id"]
                )
            )
            .mappings()
            .one()
        )
        integration = (
            session.execute(
                sa.select(models.external_agent_integrations).where(
                    models.external_agent_integrations.c.id == operation["integration_id"]
                )
            )
            .mappings()
            .one()
        )
        recovered_insert_race = _persist_command(
            session,
            AgentPrincipal(
                identity_id=str(identity["id"]),
                integration_id=str(integration["id"]),
                organization_id=ORGANIZATION_ID,
                profile=str(identity["profile"]),
                authorization_version=int(identity["authorization_version"]),
                capabilities=frozenset(identity["capabilities"]),
                branch_ids=frozenset(),
                corporate_scope=bool(identity["corporate_scope"]),
                callback_url=integration["callback_url"],
                callback_key_id=integration["callback_key_id"],
            ),
            operation_type="catalog_proposal",
            branch_id=None,
            key=str(operation["idempotency_key"]),
            digest=str(operation["request_hash"]),
            status="READY_FOR_REVIEW",
            resource_id="loser-must-be-rolled-back",
            correlation_id=None,
        )
        assert recovered_insert_race["id"] == operation["id"]

    reviewed = client.post(
        f"/api/v1/admin-ai/proposals/{created.json()['resource_id']}/review",
        headers={**_admin_headers(), "Idempotency-Key": "human-accept-grokbot-product-001"},
        json={"accept": True},
    )
    assert reviewed.status_code == 200, reviewed.text
    assert reviewed.json()["status"] == "APPLIED"
    recovered = client.get(
        f"/api/v1/agent-tools/operations/{created.json()['operation_id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["status"] == "APPLIED"
    with factory() as session:
        product_id = session.scalar(
            sa.select(models.products.c.id).where(models.products.c.sku == "900001")
        )
        assert product_id is not None
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.branch_product_availability)
                .where(models.branch_product_availability.c.product_id == product_id)
            )
            == 0
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.external_agent_callback_outbox)
                .where(
                    models.external_agent_callback_outbox.c.operation_id
                    == created.json()["operation_id"]
                )
            )
            == 2
        )


def test_tdd_tc_362_purchase_agent_creates_draft_without_inventory_or_cash_effects() -> None:
    factory = _factory()
    with factory() as session:
        now = datetime(2026, 10, 10, 18, 0, tzinfo=UTC)
        session.execute(
            models.suppliers.insert().values(
                id=SUPPLIER_ID,
                organization_id=ORGANIZATION_ID,
                code="SUP-BOT",
                commercial_name="Proveedor Bot",
                supplier_type="insumos",
                credit_days=0,
                currency="MXN",
                delivery_days=[],
                payment_methods=[],
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.execute(
            models.purchase_presentations.insert().values(
                id=PRESENTATION_ID,
                organization_id=ORGANIZATION_ID,
                supplier_id=SUPPLIER_ID,
                item_id=ITEM_ID,
                code="PRES-BOT",
                name="Presentación Bot",
                package_type="box",
                commercial_quantity=1,
                commercial_unit_id=UNIT_ID,
                base_unit_id=UNIT_ID,
                base_unit_yield=1,
                usable_content=1,
                yield_percent=1,
                last_net_price=10,
                cost_per_base_unit=10,
                status="active",
                created_at=now,
                updated_at=now,
            )
        )
        session.commit()
        movement_count = session.scalar(
            sa.select(sa.func.count()).select_from(models.inventory_movements)
        )
        cash_count = session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements))

    client = _client(factory)
    client_id, secret = _configure(
        client,
        "purchasing",
        [
            "agent.context.read",
            "agent.inventory.read",
            "agent.suppliers.read",
            "agent.purchase_needs.read",
            "agent.purchase_draft.create",
        ],
    )
    token = _token(client, client_id, secret)
    created = client.post(
        "/api/v1/agent-tools/purchase-drafts",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "grokbot-purchase-draft-001",
        },
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": SUPPLIER_ID,
            "document_type": "receipt",
            "folio": "BOT-REC-001",
            "document_date": "2026-10-10",
            "payment_method": "other",
            "paid_from_cash": False,
            "freight_total": "0",
            "lines": [
                {
                    "presentation_id": PRESENTATION_ID,
                    "quantity": "2",
                    "unit_price": "10",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
    )
    assert created.status_code == 202, created.text
    assert created.json()["status"] == "DRAFT_CREATED"

    duplicate_document = client.post(
        "/api/v1/agent-tools/purchase-drafts",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "grokbot-purchase-draft-duplicate-002",
        },
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": SUPPLIER_ID,
            "document_type": "receipt",
            "folio": "BOT-REC-001",
            "document_date": "2026-10-10",
            "payment_method": "other",
            "paid_from_cash": False,
            "freight_total": "0",
            "lines": [
                {
                    "presentation_id": PRESENTATION_ID,
                    "quantity": "2",
                    "unit_price": "10",
                    "discount": "0",
                    "tax": "0",
                }
            ],
        },
    )
    assert duplicate_document.status_code == 409, duplicate_document.text
    assert duplicate_document.json()["detail"]["code"] == "stale_reference"

    invalid_discount = client.post(
        "/api/v1/agent-tools/purchase-drafts",
        headers={
            "Authorization": f"Bearer {token}",
            "Idempotency-Key": "grokbot-purchase-draft-invalid-discount-001",
        },
        json={
            "branch_id": BRANCH_ID,
            "supplier_id": SUPPLIER_ID,
            "document_type": "receipt",
            "folio": "BOT-REC-INVALID",
            "document_date": "2026-10-10",
            "payment_method": "other",
            "paid_from_cash": False,
            "freight_total": "0",
            "lines": [
                {
                    "presentation_id": PRESENTATION_ID,
                    "quantity": "1",
                    "unit_price": "10",
                    "discount": "11",
                    "tax": "0",
                }
            ],
        },
    )
    assert invalid_discount.status_code == 400, invalid_discount.text
    assert invalid_discount.json() == {
        "detail": {
            "code": "agent_schema_invalid",
            "message": "Purchase draft input is invalid",
            "correlation_id": None,
        }
    }

    with factory() as session:
        purchase = (
            session.execute(
                sa.select(models.purchase_documents).where(
                    models.purchase_documents.c.id == created.json()["resource_id"]
                )
            )
            .mappings()
            .one()
        )
        assert purchase["status"] == "draft"
        assert purchase["origin"] == "GROKBOT"
        assert purchase["created_by"] is None
        assert purchase["created_by_agent_identity_id"] is not None
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.inventory_movements))
            == movement_count
        )
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.cash_movements))
            == cash_count
        )
