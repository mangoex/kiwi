from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import models
from .base import NormalizedOrder
from .didi_food import DiDiFoodAdapter
from .uber_eats import UberEatsAdapter

ORGANIZATION_ID = "018f6f73-2d0a-74f0-8f1c-000000000001"


class ChannelIntegrationService:
    def __init__(self) -> None:
        self.uber_adapter = UberEatsAdapter()
        self.didi_adapter = DiDiFoodAdapter()

    def get_adapter(self, provider: str):
        if provider == "UBER_EATS":
            return self.uber_adapter
        if provider == "DIDI_FOOD":
            return self.didi_adapter
        raise ValueError(f"Proveedor no soportado: {provider}")

    def get_config(
        self, session: Session, organization_id: str, provider: str
    ) -> dict[str, Any] | None:
        query = sa.select(models.channel_integrations).where(
            models.channel_integrations.c.organization_id == organization_id,
            models.channel_integrations.c.provider == provider,
        )
        row = session.execute(query).mappings().first()
        if not row:
            return None
        return dict(row)

    def save_config(
        self,
        session: Session,
        organization_id: str,
        provider: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self.get_config(session, organization_id, provider)
        now = datetime.now(timezone.utc)

        payload = {
            "is_enabled": bool(data.get("is_enabled", False)),
            "environment": str(data.get("environment", "sandbox")),
            "client_id": str(data.get("client_id", "")).strip() or None,
            "client_secret": str(data.get("client_secret", "")).strip() or None,
            "webhook_secret": str(data.get("webhook_secret", "")).strip() or None,
            "auto_accept": bool(data.get("auto_accept", True)),
            "default_prep_time_minutes": int(data.get("default_prep_time_minutes", 20)),
            "updated_at": now,
        }

        if existing:
            session.execute(
                sa.update(models.channel_integrations)
                .where(
                    models.channel_integrations.c.organization_id == organization_id,
                    models.channel_integrations.c.provider == provider,
                )
                .values(**payload)
            )
            config_id = existing["id"]
        else:
            config_id = str(uuid.uuid4())
            session.execute(
                models.channel_integrations.insert().values(
                    id=config_id,
                    organization_id=organization_id,
                    provider=provider,
                    created_at=now,
                    **payload,
                )
            )

        session.commit()
        return self.get_config(session, organization_id, provider) or {}

    def list_store_mappings(
        self, session: Session, organization_id: str, provider: str
    ) -> list[dict[str, Any]]:
        query = (
            sa.select(
                models.channel_store_mappings.c.id,
                models.channel_store_mappings.c.branch_id,
                models.channel_store_mappings.c.provider,
                models.channel_store_mappings.c.external_store_id,
                models.channel_store_mappings.c.is_active,
                models.channel_store_mappings.c.created_at,
                models.branches.c.name.label("branch_name"),
                models.branches.c.code.label("branch_code"),
            )
            .join(
                models.branches, models.channel_store_mappings.c.branch_id == models.branches.c.id
            )
            .where(
                models.channel_store_mappings.c.organization_id == organization_id,
                models.channel_store_mappings.c.provider == provider,
            )
            .order_by(models.branches.c.name.asc())
        )
        return [dict(r) for r in session.execute(query).mappings().all()]

    def save_store_mapping(
        self,
        session: Session,
        organization_id: str,
        provider: str,
        branch_id: str,
        external_store_id: str,
        is_active: bool = True,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        existing = (
            session.execute(
                sa.select(models.channel_store_mappings).where(
                    models.channel_store_mappings.c.organization_id == organization_id,
                    models.channel_store_mappings.c.provider == provider,
                    models.channel_store_mappings.c.branch_id == branch_id,
                )
            )
            .mappings()
            .first()
        )

        if existing:
            session.execute(
                sa.update(models.channel_store_mappings)
                .where(models.channel_store_mappings.c.id == existing["id"])
                .values(
                    external_store_id=external_store_id.strip(),
                    is_active=is_active,
                    updated_at=now,
                )
            )
            mapping_id = existing["id"]
        else:
            mapping_id = str(uuid.uuid4())
            session.execute(
                models.channel_store_mappings.insert().values(
                    id=mapping_id,
                    organization_id=organization_id,
                    branch_id=branch_id,
                    provider=provider,
                    external_store_id=external_store_id.strip(),
                    is_active=is_active,
                    created_at=now,
                    updated_at=now,
                )
            )

        session.commit()
        return {
            "id": mapping_id,
            "branch_id": branch_id,
            "external_store_id": external_store_id,
            "is_active": is_active,
        }

    def delete_store_mapping(self, session: Session, organization_id: str, mapping_id: str) -> bool:
        session.execute(
            sa.delete(models.channel_store_mappings).where(
                models.channel_store_mappings.c.id == mapping_id,
                models.channel_store_mappings.c.organization_id == organization_id,
            )
        )
        session.commit()
        return True

    def list_webhook_logs(
        self, session: Session, organization_id: str, provider: str, limit: int = 50
    ) -> list[dict[str, Any]]:
        query = (
            sa.select(models.integration_webhook_logs)
            .where(
                models.integration_webhook_logs.c.organization_id == organization_id,
                models.integration_webhook_logs.c.provider == provider,
            )
            .order_by(models.integration_webhook_logs.c.created_at.desc())
            .limit(limit)
        )
        return [dict(r) for r in session.execute(query).mappings().all()]

    def log_webhook(
        self,
        session: Session,
        organization_id: str,
        provider: str,
        event_type: str,
        event_id: str | None,
        signature: str | None,
        payload_raw: dict[str, Any],
        status: str,
        error_message: str | None = None,
    ) -> str:
        now = datetime.now(timezone.utc)
        log_id = str(uuid.uuid4())
        session.execute(
            models.integration_webhook_logs.insert().values(
                id=log_id,
                organization_id=organization_id,
                provider=provider,
                event_type=event_type,
                event_id=event_id,
                signature=signature,
                payload_raw=payload_raw,
                status=status,
                error_message=error_message,
                processed_at=now if status == "processed" else None,
                created_at=now,
            )
        )
        session.commit()
        return log_id

    def process_webhook_order(
        self,
        session: Session,
        organization_id: str,
        provider: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        adapter = self.get_adapter(provider)
        config = self.get_config(session, organization_id, provider)

        # Get product mappings
        product_mappings_rows = session.execute(
            sa.select(
                models.channel_product_mappings.c.external_item_id,
                models.channel_product_mappings.c.product_id,
            ).where(
                models.channel_product_mappings.c.organization_id == organization_id,
                models.channel_product_mappings.c.provider == provider,
                models.channel_product_mappings.c.is_active.is_(True),
            )
        ).all()
        product_mappings = {r[0]: r[1] for r in product_mappings_rows}

        # Default products in catalog for fallback
        products_query = (
            sa.select(
                models.products.c.id,
                models.products.c.name,
                models.products.c.category_id,
                models.products.c.station,
            )
            .where(
                models.products.c.organization_id == organization_id,
                models.products.c.status == "active",
            )
            .limit(10)
        )
        default_products = [dict(r) for r in session.execute(products_query).mappings().all()]
        if not default_products:
            any_prods = (
                session.execute(
                    sa.select(
                        models.products.c.id,
                        models.products.c.name,
                        models.products.c.category_id,
                        models.products.c.station,
                    ).limit(10)
                )
                .mappings()
                .all()
            )
            default_products = [dict(r) for r in any_prods]

        # Normalize order
        normalized: NormalizedOrder = adapter.normalize_order(
            payload, product_mappings, default_products
        )

        # Idempotency check: if order with this external_order_id already exists
        existing_meta = (
            session.execute(
                sa.select(models.channel_orders_meta).where(
                    models.channel_orders_meta.c.provider == provider,
                    models.channel_orders_meta.c.external_order_id == normalized.external_order_id,
                )
            )
            .mappings()
            .first()
        )

        if existing_meta:
            return {
                "status": "already_processed",
                "order_id": existing_meta["order_id"],
                "external_order_id": normalized.external_order_id,
            }

        # Resolve target branch from external_store_id
        target_branch_id = None
        if normalized.external_store_id:
            store_mapping = session.execute(
                sa.select(models.channel_store_mappings.c.branch_id).where(
                    models.channel_store_mappings.c.organization_id == organization_id,
                    models.channel_store_mappings.c.provider == provider,
                    models.channel_store_mappings.c.external_store_id
                    == normalized.external_store_id,
                    models.channel_store_mappings.c.is_active.is_(True),
                )
            ).scalar_one_or_none()
            if store_mapping:
                target_branch_id = str(store_mapping)

        if not target_branch_id:
            # Fallback to first active branch in organization or any branch
            first_branch = session.execute(
                sa.select(models.branches.c.id)
                .where(
                    models.branches.c.organization_id == organization_id,
                    models.branches.c.status == "active",
                )
                .order_by(models.branches.c.created_at.asc())
            ).scalar_one_or_none()
            if not first_branch:
                first_branch = session.execute(
                    sa.select(models.branches.c.id)
                    .where(models.branches.c.status == "active")
                    .order_by(models.branches.c.created_at.asc())
                ).scalar_one_or_none()
            if not first_branch:
                first_branch = session.execute(
                    sa.select(models.branches.c.id).order_by(models.branches.c.created_at.asc())
                ).scalar_one_or_none()
            if not first_branch:
                raise ValueError("No hay sucursales registradas para enrutar el pedido.")
            target_branch_id = str(first_branch)

        # Create order record in orders table
        now = datetime.now(timezone.utc)
        order_id = str(uuid.uuid4())
        short_suffix = uuid.uuid4().hex[:4].upper()
        daily_folio = f"UBER-{normalized.display_code.replace('#', '')}-{short_suffix}"

        # Category for line items
        cat_id = default_products[0]["category_id"] if default_products else None
        cat_name = "Marketplace"
        if cat_id:
            cat_row = session.execute(
                sa.select(models.product_categories.c.name).where(
                    models.product_categories.c.id == cat_id
                )
            ).scalar_one_or_none()
            if cat_row:
                cat_name = str(cat_row)
        if not cat_id:
            any_cat = session.execute(
                sa.select(models.product_categories.c.id, models.product_categories.c.name).limit(1)
            ).first()
            if any_cat:
                cat_id = str(any_cat[0])
                cat_name = str(any_cat[1])
            else:
                cat_id = "00000000-0000-0000-0000-000000000001"
                cat_name = "General"

        order_status = "ACCEPTED" if (config and config.get("auto_accept")) else "PENDING"

        session.execute(
            models.orders.insert().values(
                id=order_id,
                organization_id=organization_id,
                branch_id=target_branch_id,
                cash_shift_id=None,
                public_order_intent_id=None,
                public_order_intent_status=None,
                customer_id=None,
                customer_snapshot={
                    "name": normalized.customer_name,
                    "phone": normalized.customer_phone or "",
                },
                delivery_address_snapshot={
                    "notes": normalized.delivery_notes or "",
                    "channel": provider,
                },
                folio=daily_folio,
                channel=provider,
                status=order_status,
                total_cents=normalized.total_cents,
                currency=normalized.currency,
                owner_name=normalized.customer_name,
                order_type="delivery",
                payment_method_intent="marketplace_uber",
                version=1,
                created_at=now,
                accepted_at=now if order_status == "ACCEPTED" else None,
            )
        )

        # Fallback product ID from existing catalog if line.product_id is missing
        fallback_prod_id = default_products[0]["id"] if default_products else None
        if not fallback_prod_id:
            any_p = session.execute(sa.select(models.products.c.id).limit(1)).scalar_one_or_none()
            fallback_prod_id = str(any_p) if any_p else str(uuid.uuid4())

        # Insert lines
        for line in normalized.items:
            line_id = str(uuid.uuid4())
            prod_id = line.product_id or fallback_prod_id
            session.execute(
                models.order_lines.insert().values(
                    id=line_id,
                    order_id=order_id,
                    product_id=prod_id,
                    product_name=line.product_name,
                    quantity=line.quantity,
                    unit_price_cents=line.unit_price_cents,
                    line_total_cents=line.line_total_cents,
                    station="kitchen",
                    selected_modifiers=line.selected_modifiers,
                    modifier_total_cents=0,
                    line_notes=line.special_instructions,
                    status="active",
                    revision=1,
                    family_id_snapshot=cat_id,
                    family_name_snapshot=cat_name,
                    family_snapshot_source="captured",
                    created_at=now,
                )
            )

        # Insert channel_orders_meta
        session.execute(
            models.channel_orders_meta.insert().values(
                id=str(uuid.uuid4()),
                order_id=order_id,
                provider=provider,
                external_order_id=normalized.external_order_id,
                display_code=normalized.display_code,
                customer_name=normalized.customer_name,
                driver_name=None,
                driver_phone=None,
                external_status="ACCEPTED" if order_status == "ACCEPTED" else "CREATED",
                estimated_ready_at=None,
                raw_payload=payload,
                created_at=now,
                updated_at=now,
            )
        )

        session.commit()
        return {
            "status": "created",
            "order_id": order_id,
            "folio": daily_folio,
            "display_code": normalized.display_code,
            "branch_id": target_branch_id,
            "order_status": order_status,
        }

    def list_pos_orders(
        self,
        session: Session,
        branch_id: str,
        provider: str = "UBER_EATS",
        status_filter: str | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            sa.select(
                models.orders.c.id,
                models.orders.c.folio,
                models.orders.c.channel,
                models.orders.c.status,
                models.orders.c.total_cents,
                models.orders.c.currency,
                models.orders.c.created_at,
                models.orders.c.accepted_at,
                models.orders.c.customer_snapshot,
                models.orders.c.delivery_address_snapshot,
                models.channel_orders_meta.c.external_order_id,
                models.channel_orders_meta.c.display_code,
                models.channel_orders_meta.c.customer_name,
                models.channel_orders_meta.c.driver_name,
                models.channel_orders_meta.c.driver_phone,
                models.channel_orders_meta.c.external_status,
                models.channel_orders_meta.c.estimated_ready_at,
            )
            .join(
                models.channel_orders_meta,
                models.orders.c.id == models.channel_orders_meta.c.order_id,
            )
            .where(
                models.orders.c.branch_id == branch_id,
                models.orders.c.channel == provider,
            )
            .order_by(models.orders.c.created_at.desc())
            .limit(100)
        )

        rows = session.execute(query).mappings().all()
        results: list[dict[str, Any]] = []

        for row in rows:
            # Fetch lines for each order
            lines_rows = (
                session.execute(
                    sa.select(
                        models.order_lines.c.id,
                        models.order_lines.c.product_name,
                        models.order_lines.c.quantity,
                        models.order_lines.c.unit_price_cents,
                        models.order_lines.c.line_total_cents,
                        models.order_lines.c.line_notes,
                        models.order_lines.c.selected_modifiers,
                    )
                    .where(models.order_lines.c.order_id == row["id"])
                    .order_by(models.order_lines.c.created_at.asc())
                )
                .mappings()
                .all()
            )

            order_data = dict(row)
            order_data["lines"] = [dict(item_line) for item_line in lines_rows]
            results.append(order_data)

        return results

    def update_order_status(
        self,
        session: Session,
        order_id: str,
        new_status: str,
        actor_id: str | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        order = (
            session.execute(sa.select(models.orders).where(models.orders.c.id == order_id))
            .mappings()
            .first()
        )

        if not order:
            raise ValueError(f"Orden no encontrada: {order_id}")

        session.execute(
            sa.update(models.orders)
            .where(models.orders.c.id == order_id)
            .values(
                status=new_status,
                accepted_at=now if new_status == "ACCEPTED" else order["accepted_at"],
            )
        )

        session.execute(
            sa.update(models.channel_orders_meta)
            .where(models.channel_orders_meta.c.order_id == order_id)
            .values(external_status=new_status, updated_at=now)
        )

        session.commit()
        return {"order_id": order_id, "status": new_status, "updated_at": now.isoformat()}


channel_service = ChannelIntegrationService()
