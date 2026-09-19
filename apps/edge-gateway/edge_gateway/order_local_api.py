"""Small, explicit POS/KDS surface: never forward arbitrary routes to cloud."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa
from fastapi import FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from restaurant_os import operations as domain
from restaurant_os.platform_data import list_catalog_products, list_categories
from sqlalchemy.orm import Session

from edge_gateway.order_outbox import commands
from edge_gateway.order_service import LocalOrderService

PREFIX = "/api/v1/local/order-api"


def attach_order_routes(app: FastAPI, service: LocalOrderService) -> None:
    def authenticated(request: Request) -> tuple[str, dict[str, Any]]:
        authorization = request.headers.get("authorization", "")
        if not authorization.startswith("Offline "):
            raise HTTPException(401, detail={"code": "offline_order_grant_required"})
        token = authorization[8:]
        grant = service.authorize(token, datetime.now(UTC))
        branch = request.query_params.get("branch_id")
        if branch and branch != grant["branch_id"]:
            raise HTTPException(403, detail={"code": "offline_order_branch_mismatch"})
        return token, grant

    @app.get("/api/v1/local/orders/status")
    def status() -> dict[str, Any]:
        lifecycle = service.outbox.lifecycle_status()
        return {
            "ready": lifecycle == "ACTIVE"
            and service.outbox.active_bundle_matches(
                str(service.bundle["hash"]), int(service.manifest["lease_epoch"])
            )
            and service.manifest.get("issued_at", 0)
            <= datetime.now(UTC).timestamp()
            < service.manifest.get("expires_at", 0),
            "lifecycle": lifecycle.lower(),
            **{
                key: service.manifest[key]
                for key in ("organization_id", "branch_id", "device_id", "bundle_id", "lease_epoch")
            },
            "bundle_hash": service.bundle["hash"],
        }

    @app.get("/api/v1/local/orders/commands/{command_id}")
    def command_status(command_id: str, request: Request) -> dict[str, Any]:
        try:
            _, grant = authenticated(request)
            row = service.outbox.get(command_id)
            if row["envelope"]["branch_id"] != grant["branch_id"] or (
                row["actor_id"] != grant["actor_id"] and "orders.read" not in grant["capabilities"]
            ):
                raise KeyError(command_id)
            return {
                "_offline": {
                    "command_id": command_id,
                    "status": row["status"],
                    "checkpoint": row["checkpoint"],
                    "code": row["detail"],
                }
            }
        except KeyError as exc:
            raise HTTPException(404, detail={"code": "offline_order_command_not_found"}) from exc
        except domain.BusinessError as exc:
            raise HTTPException(403, detail={"code": exc.code}) from exc

    @app.api_route(PREFIX + "/{path:path}", methods=["GET", "POST"])
    async def order_api(path: str, request: Request) -> Any:
        try:
            token, grant = authenticated(request)
            if request.method == "GET":
                return jsonable_encoder(read(path, dict(request.query_params), grant))
            try:
                payload = await request.json()
            except ValueError as exc:
                raise HTTPException(422, detail={"code": "offline_order_payload_invalid"}) from exc
            if not isinstance(payload, dict):
                raise HTTPException(422, detail={"code": "offline_order_payload_invalid"})
            if payload.get("branch_id", grant["branch_id"]) != grant["branch_id"]:
                raise HTTPException(403, detail={"code": "offline_order_branch_mismatch"})
            payload = {key: value for key, value in payload.items() if key != "branch_id"}
            if path == "orders/recover":
                require(grant, "orders.create")
                if payload:
                    raise HTTPException(422, detail={"code": "offline_order_payload_invalid"})
                key = request.headers.get("Idempotency-Key", "")
                with Session(service.outbox.engine) as session:
                    row = (
                        session.execute(
                            sa.select(commands).where(
                                commands.c.actor_id == grant["actor_id"],
                                commands.c.idempotency_key == key,
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if (
                        row is None
                        or row["envelope"]["command_type"] != "create"
                        or row["envelope"]["branch_id"] != grant["branch_id"]
                    ):
                        raise HTTPException(404, detail={"code": "order_create_not_found"})
                    if row["status"] == "CONFLICT":
                        raise HTTPException(409, detail={"code": "offline_order_stream_conflict"})
                    result = domain.get_order_detail(
                        session, row["aggregate_id"], grant["actor_id"]
                    )
                    return jsonable_encoder(
                        {
                            **result,
                            "_offline": {
                                "command_id": row["command_id"],
                                "status": row["status"],
                                "checkpoint": row["checkpoint"],
                                "code": row["detail"],
                            },
                        }
                    )
            if path == "orders/quote":
                require(grant, "orders.create")
                with Session(service.outbox.engine) as session:
                    # The operational database was bootstrapped with the same immutable catalog.
                    return jsonable_encoder(
                        domain.quote_local_order(
                            session,
                            payload.get("lines", []),
                            grant["branch_id"],
                            grant["actor_id"],
                            payload.get("adjustment_authorization_id"),
                        )
                    )
            command_type, aggregate_id, payload = command(path, payload, grant)
            key = request.headers.get("Idempotency-Key", "")
            if not 12 <= len(key) <= 160:
                raise HTTPException(422, detail={"code": "idempotency_key_required"})
            return jsonable_encoder(
                service.execute(token, command_type, payload, key, aggregate_id=aggregate_id)
            )
        except domain.BusinessError as exc:
            raise HTTPException(409, detail={"code": exc.code, "message": str(exc)}) from exc
        except ValueError as exc:
            if str(exc) == "gateway_orders_frozen":
                raise HTTPException(
                    409,
                    detail={
                        "code": "gateway_orders_frozen",
                        "message": "El gateway está congelado; espere la devolución de autoridad.",
                    },
                ) from exc
            raise HTTPException(409, detail={"code": "offline_order_request_rejected"}) from exc

    def require(grant: dict[str, Any], capability: str) -> None:
        if capability not in grant["capabilities"]:
            raise HTTPException(403, detail={"code": "offline_order_permission_denied"})

    def command(
        path: str, payload: dict[str, Any], grant: dict[str, Any]
    ) -> tuple[str, str | None, dict[str, Any]]:
        if path == "orders":
            return "create", None, payload
        match = re.fullmatch(r"orders/([^/]+)/(payments|amendments|cancel)", path)
        if match:
            return (
                {"payments": "pay", "amendments": "amend", "cancel": "cancel"}[match[2]],
                match[1],
                payload,
            )
        match = re.fullmatch(r"orders/([^/]+)/fulfillment/([^/]+)", path)
        if match:
            return "fulfill", match[1], {**payload, "command": match[2]}
        match = re.fullmatch(r"kds/tasks/([^/]+)/transition", path)
        if match:
            return (
                "kds_transition",
                service.order_for_task(match[1], grant),
                {**payload, "task_id": match[1]},
            )
        raise HTTPException(404, detail={"code": "offline_order_route_unavailable"})

    def read(path: str, query: dict[str, str], grant: dict[str, Any]) -> Any:
        with Session(service.outbox.engine) as session:
            actor, branch = grant["actor_id"], grant["branch_id"]
            if path == "auth/session":
                profile = domain.build_session_profile(session, actor, branch)
                profile["permissions"] = sorted(
                    set(profile["permissions"]) & set(grant["capabilities"])
                )
                profile["scope"]["allowed_branch_ids"] = [branch]
                return profile
            if path == "categories":
                require(grant, "pos.operate")
                return list_categories(session, branch)
            if path == "catalog/products":
                require(grant, "pos.operate")
                return list_catalog_products(session, branch)
            if path == "catalog/ingredient-extras/available":
                require(grant, "pos.operate")
                return domain.list_available_ingredient_extras(session, actor, branch)
            if path == "kds/tasks":
                require(grant, "kds.tasks.operate")
                return domain.list_kds_tasks(session, branch)
            if path == "cash/shifts/current":
                require(grant, "cash.shift.read")
                if not query.get("register_id"):
                    raise HTTPException(422, detail={"code": "register_id_required"})
                return {
                    "cash_shift": domain.get_open_cash_shift(session, query["register_id"], branch),
                    "closure": None,
                }
            match = re.fullmatch(r"orders/([^/]+)", path)
            if match:
                require(grant, "orders.read")
                result = domain.get_order_detail(session, match[1], actor)
                if result.get("branch_id") != branch:
                    raise HTTPException(404, detail={"code": "order_not_found"})
                return result
            match = re.fullmatch(r"products/([^/]+)/modifiers", path)
            if match:
                require(grant, "pos.operate")
                return domain.list_product_modifiers(session, match[1], branch)
        raise HTTPException(404, detail={"code": "offline_order_route_unavailable"})
