"""Human integration diagnostics cannot export unscoped original payloads."""

from typing import Any

import pytest
import sqlalchemy as sa
from corte_ciego_fixtures import ORG_ID, CashWorld, cash_world
from restaurant_os import models
from restaurant_os import operations as ops
from restaurant_os.auth import create_session_token
from restaurant_os.config import get_settings
from restaurant_os.integrations.service import ChannelIntegrationService
from sqlalchemy.orm import Session

__all__ = ["cash_world"]
PROVIDERS = ("UBER_EATS", "DIDI_FOOD", "RAPPI", "WHATSAPP")
PATHS = ("uber-eats", "didi-food", "rappi", "whatsapp")
PRIVATE = "PRIVATE-LOG-950123-customer-phone"


def seed_logs(world: CashWorld) -> None:
    with world.sessions() as session:
        for provider in PROVIDERS:
            ChannelIntegrationService().log_webhook(
                session,
                ORG_ID,
                provider,
                PRIVATE,
                PRIVATE,
                PRIVATE,
                {"amount_cents": 950123, "nested": {"phone": PRIVATE}},
                "failed",
                PRIVATE,
            )


@pytest.mark.parametrize("actor", ["administrator", "owner"])
@pytest.mark.parametrize("path", PATHS)
def test_human_logs_are_metadata_only(cash_world: CashWorld, path: str, actor: str) -> None:
    world = cash_world
    seed_logs(world)
    result = world.client.get(f"/api/v1/integrations/{path}/logs", headers=world.headers(actor))
    assert result.status_code == 200, result.text
    assert PRIVATE not in result.text and "amount_cents" not in result.text
    assert result.headers["cache-control"] == "no-store"
    assert len(result.json()) == 1
    assert set(result.json()[0]) == {
        "schema_version",
        "projection",
        "id",
        "provider",
        "status",
        "created_at",
        "processed_at",
    }
    assert result.json()[0]["status"] == "failed"


def test_metadata_query_does_not_load_original_columns(cash_world: CashWorld) -> None:
    world = cash_world
    seed_logs(world)
    statements: list[str] = []

    def observe(_conn: Any, _cursor: Any, sql: str, *_args: Any) -> None:
        if sql.lstrip().upper().startswith("SELECT") and "integration_webhook_logs" in sql:
            statements.append(sql)

    sa.event.listen(world.engine, "before_cursor_execute", observe)
    try:
        result = world.client.get(
            "/api/v1/integrations/rappi/logs", headers=world.headers("administrator")
        )
    finally:
        sa.event.remove(world.engine, "before_cursor_execute", observe)
    assert result.status_code == 200 and statements
    for column in ("payload_raw", "signature", "error_message", "event_type", "event_id"):
        assert not any(column in sql for sql in statements)
    with world.sessions() as session:
        assert all(
            row["signature"] == PRIVATE and row["payload_raw"]["amount_cents"] == 950123
            for row in session.execute(sa.select(models.integration_webhook_logs)).mappings()
        )


@pytest.mark.parametrize("typ", ["agent", "device"])
def test_technical_identity_cannot_use_human_logs(cash_world: CashWorld, typ: str) -> None:
    world = cash_world
    seed_logs(world)
    token = create_session_token(
        {"sub": world.actors["administrator"], "typ": typ}, get_settings().secret_key
    )
    for path in PATHS:
        result = world.client.get(
            f"/api/v1/integrations/{path}/logs", headers={"Authorization": f"Bearer {token}"}
        )
        assert result.status_code == 403 and PRIVATE not in result.text


def test_query_parameters_and_suspension_do_not_reopen_originals(cash_world: CashWorld) -> None:
    world = cash_world
    seed_logs(world)
    with world.sessions() as session:
        session.execute(
            models.integration_webhook_logs.update().values(status="private-money-950123")
        )
        branches = (
            session.execute(
                sa.select(models.blind_cash_policy_revisions).where(
                    models.blind_cash_policy_revisions.c.organization_id == ORG_ID,
                )
            )
            .mappings()
            .all()
        )
        for row in branches:
            session.execute(
                models.blind_cash_policy_revisions.insert().values(
                    {
                        **dict(row),
                        "revision": row["revision"] + 1,
                        "event": "suspended",
                    }
                )
            )
        session.commit()
    result = world.client.get(
        "/api/v1/integrations/whatsapp/logs",
        headers=world.headers("owner"),
        params={"branch_id": "unresolved", "include_payload": "true"},
    )
    assert result.status_code == 200 and PRIVATE not in result.text
    assert result.json()[0]["status"] == "unknown" and "950123" not in result.text


@pytest.mark.parametrize("actor", ["foreign", "inactive", "no_permission"])
def test_current_authority_is_required_before_loading_logs(
    cash_world: CashWorld, actor: str
) -> None:
    world = cash_world
    seed_logs(world)
    selected = "foreign" if actor == "foreign" else "administrator"
    with world.sessions() as session:
        if actor == "inactive":
            session.execute(
                models.users.update()
                .where(models.users.c.id == world.actors[selected])
                .values(status="inactive")
            )
        if actor == "no_permission":
            permission = session.scalar(
                sa.select(models.permissions.c.id).where(
                    models.permissions.c.code == "admin.manage"
                )
            )
            session.execute(
                models.role_permissions.delete().where(
                    models.role_permissions.c.role_id == world.roles[selected],
                    models.role_permissions.c.permission_id == permission,
                )
            )
        session.commit()
    result = world.client.get("/api/v1/integrations/rappi/logs", headers=world.headers(selected))
    assert result.status_code == 403 and PRIVATE not in result.text


def test_direct_service_requires_actor_and_tenant(cash_world: CashWorld) -> None:
    world = cash_world
    seed_logs(world)
    service = ChannelIntegrationService()
    with world.sessions() as session:
        with pytest.raises(ops.AuthorizationError):
            service.list_webhook_logs(session, ORG_ID, "RAPPI")
        with pytest.raises(ops.AuthorizationError):
            service.list_webhook_logs(
                session, "foreign", "RAPPI", actor_user_id=world.actors["owner"]
            )


def test_audit_failure_is_closed_and_does_not_expose_sql(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    seed_logs(world)
    audit = ops._audit

    def fail(session: Session, action: str, *args: Any, **kwargs: Any) -> Any:
        if action == "integration.logs.read":
            raise sa.exc.SQLAlchemyError(PRIVATE)
        return audit(session, action, *args, **kwargs)

    monkeypatch.setattr(ops, "_audit", fail)
    result = world.client.get(
        "/api/v1/integrations/rappi/logs", headers=world.headers("administrator")
    )
    assert result.status_code == 503 and PRIVATE not in result.text
    with world.sessions() as session:
        assert (
            session.scalar(sa.select(sa.func.count()).select_from(models.integration_webhook_logs))
            == 4
        )
        assert (
            session.scalar(
                sa.select(sa.func.count())
                .select_from(models.audit_events)
                .where(models.audit_events.c.action == "integration.logs.read")
            )
            == 0
        )


def test_revocation_after_commit_denies_delivery(
    cash_world: CashWorld, monkeypatch: pytest.MonkeyPatch
) -> None:
    world = cash_world
    seed_logs(world)
    commit = Session.commit
    revoked = False

    def revoke(session: Session) -> None:
        nonlocal revoked
        commit(session)
        if not revoked:
            revoked = True
            with world.sessions() as other:
                other.execute(
                    models.users.update()
                    .where(models.users.c.id == world.actors["administrator"])
                    .values(status="inactive")
                )
                commit(other)

    monkeypatch.setattr(Session, "commit", revoke)
    result = world.client.get(
        "/api/v1/integrations/rappi/logs", headers=world.headers("administrator")
    )
    assert revoked and result.status_code == 403 and PRIVATE not in result.text


@pytest.mark.parametrize("limit", [0, -1, 201])
def test_log_limit_is_bounded(cash_world: CashWorld, limit: int) -> None:
    response = cash_world.client.get(
        "/api/v1/integrations/rappi/logs",
        headers=cash_world.headers("owner"),
        params={"limit": limit},
    )
    assert (
        response.status_code == 409
        and response.json()["detail"]["code"] == "integration_logs_query_invalid"
    )


def test_legacy_contract_is_kept_but_activation_during_delivery_blocks_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from test_corte_ciego_f105_intents import activate
    from test_platform_api import (
        _admin_headers,
        _client_with_seeded_database,
        _test_session_factory,
    )

    with _client_with_seeded_database() as client:
        factory = _test_session_factory(client)
        with factory() as session:
            ChannelIntegrationService().log_webhook(
                session, ORG_ID, "RAPPI", "order.new", None, PRIVATE, {"money": 950123}, "received"
            )
        assert client.get("/api/v1/integrations/rappi/logs", headers=_admin_headers()).json()[0][
            "payload_raw"
        ] == {"money": 950123}
        commit = Session.commit
        activated = False

        def enable(session: Session) -> None:
            nonlocal activated
            commit(session)
            if not activated:
                activated = True
                activate(factory)

        monkeypatch.setattr(Session, "commit", enable)
        result = client.get("/api/v1/integrations/rappi/logs", headers=_admin_headers())
        assert activated and result.status_code == 409 and PRIVATE not in result.text
        assert result.json()["detail"]["code"] == "cash_authorization_changed"


def test_metadata_schema_matches_published_contract() -> None:
    import json
    from pathlib import Path

    from restaurant_os.integration_log_views import IntegrationLogMetadataV2

    schema = json.loads(
        (
            Path(__file__).resolve().parents[3]
            / "packages/contracts/schemas/integration-log-metadata-v2.schema.json"
        ).read_text()
    )
    assert schema == IntegrationLogMetadataV2.model_json_schema()
    assert schema["additionalProperties"] is False


def test_server_error_status_remains_useful_without_error_text(cash_world: CashWorld) -> None:
    world = cash_world
    with world.sessions() as session:
        ChannelIntegrationService().log_webhook(
            session,
            ORG_ID,
            "RAPPI",
            "order.new",
            None,
            None,
            {"amount_cents": 950123},
            "error",
            PRIVATE,
        )
    result = world.client.get(
        "/api/v1/integrations/rappi/logs", headers=world.headers("administrator")
    )
    assert result.status_code == 200 and result.json()[0]["status"] == "error"
    assert PRIVATE not in result.text and "amount_cents" not in result.text
