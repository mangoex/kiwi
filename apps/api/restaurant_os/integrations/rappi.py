from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any

from .base import IOrderChannelAdapter, NormalizedOrder, NormalizedOrderItem


class RappiAdapter(IOrderChannelAdapter):
    PROVIDER_NAME = "RAPPI"

    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str | None,
        secret: str | None,
    ) -> bool:
        """
        Valida la firma criptográfica HMAC-SHA256 enviada por Rappi en el encabezado
        'Rappi-Signature', 'X-Rappi-Signature' o 'sign'.
        """
        if not secret or not signature_header:
            return False

        signature = signature_header.strip()
        if signature.startswith("sha256="):
            signature = signature[7:]

        expected_hmac = hmac.new(
            secret.encode("utf-8"),
            payload_bytes,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(expected_hmac.lower(), signature.lower())

    def parse_webhook_event(self, payload: dict[str, Any]) -> tuple[str, str | None]:
        """
        Extrae el tipo de evento y el identificador de orden de Rappi.
        """
        event_type = str(
            payload.get("event_type")
            or payload.get("event")
            or payload.get("type")
            or payload.get("action")
            or "NEW_ORDER"
        )
        resource_id = None

        meta = payload.get("meta")
        if isinstance(meta, dict):
            resource_id = meta.get("resource_id") or meta.get("order_id")

        if not resource_id:
            order_obj = payload.get("order")
            if isinstance(order_obj, dict):
                resource_id = order_obj.get("order_id") or order_obj.get("id")

        if not resource_id:
            resource_id = payload.get("order_id") or payload.get("id") or payload.get("orderId")

        return event_type, str(resource_id) if resource_id else None

    def normalize_order(
        self,
        payload: dict[str, Any],
        product_mappings: dict[str, str],
        default_products: list[dict[str, Any]] | None = None,
    ) -> NormalizedOrder:
        """
        Convierte el payload del webhook de Rappi Partners a NormalizedOrder canónica.
        """
        # Rappi puede anidar los datos en 'order' o enviarlos en la raíz
        order_data = payload.get("order") if isinstance(payload.get("order"), dict) else payload

        order_id = str(
            order_data.get("order_id")
            or order_data.get("id")
            or order_data.get("orderId")
            or "RAPPI-ORD-UNKNOWN"
        )
        display_code = str(
            order_data.get("display_id")
            or order_data.get("order_display_id")
            or order_data.get("order_number")
            or order_id[:6].upper()
        )
        if not display_code.startswith("#"):
            display_code = f"#{display_code}"

        store = order_data.get("store") or payload.get("store") or {}
        store_id = (
            order_data.get("store_id")
            or payload.get("store_id")
            or (store.get("id") if isinstance(store, dict) else "")
            or (store.get("store_id") if isinstance(store, dict) else "")
            or ""
        )
        external_store_id = str(store_id)

        customer = (
            order_data.get("customer") or order_data.get("client") or payload.get("customer") or {}
        )
        customer_name = "Cliente Rappi"
        customer_phone = None
        if isinstance(customer, dict):
            first_name = customer.get("first_name") or customer.get("name") or "Cliente Rappi"
            last_name = customer.get("last_name") or ""
            customer_name = f"{first_name} {last_name}".strip()
            customer_phone = customer.get("phone") or customer.get("phone_number")
        elif isinstance(customer, str):
            customer_name = customer

        delivery = order_data.get("delivery") or payload.get("delivery") or {}
        delivery_notes = None
        if isinstance(delivery, dict):
            delivery_notes = delivery.get("notes") or delivery.get("instructions")
        if not delivery_notes:
            delivery_notes = (
                order_data.get("delivery_notes")
                or order_data.get("order_notes")
                or order_data.get("notes")
            )

        # Parsing items
        cart = order_data.get("cart") or {}
        raw_items = (
            (cart.get("items") if isinstance(cart, dict) else None)
            or order_data.get("items")
            or order_data.get("products")
            or payload.get("items")
            or []
        )

        normalized_items: list[NormalizedOrderItem] = []
        calculated_total_cents = 0

        fallback_product_id = ""
        fallback_product_name = "Producto Rappi"
        if default_products and len(default_products) > 0:
            fallback_product_id = default_products[0].get("id", "")
            fallback_product_name = default_products[0].get("name", "Producto Rappi")

        for item in raw_items:
            item_id = str(item.get("id") or item.get("item_id") or item.get("product_id") or "")
            title = str(
                item.get("title")
                or item.get("name")
                or item.get("product_name")
                or fallback_product_name
            )
            external_sku = str(
                item.get("sku") or item.get("external_data") or item.get("external_id") or item_id
            )
            quantity = int(item.get("quantity") or item.get("units") or 1)

            # Resolve internal product_id
            product_id = (
                product_mappings.get(external_sku)
                or product_mappings.get(item_id)
                or fallback_product_id
            )

            # Resolve price in cents
            price_info = item.get("price") or item.get("unit_price")
            unit_price_cents = 0
            if isinstance(price_info, dict) and "amount" in price_info:
                unit_price_cents = int(price_info["amount"])
            elif isinstance(item.get("unit_price_cents"), (int, float)):
                unit_price_cents = int(item["unit_price_cents"])
            elif isinstance(item.get("price"), (int, float)):
                unit_price_cents = int(float(item["price"]) * 100)
            elif isinstance(item.get("unit_price"), (int, float)):
                unit_price_cents = int(float(item["unit_price"]) * 100)

            line_total_cents = unit_price_cents * quantity
            calculated_total_cents += line_total_cents

            instructions = (
                item.get("special_instructions")
                or item.get("instructions")
                or item.get("notes")
                or item.get("comments")
            )
            modifiers = (
                item.get("selected_modifier_groups")
                or item.get("modifiers")
                or item.get("toppings")
                or item.get("options")
                or []
            )

            normalized_items.append(
                NormalizedOrderItem(
                    product_id=product_id,
                    product_name=title,
                    quantity=quantity,
                    unit_price_cents=unit_price_cents,
                    line_total_cents=line_total_cents,
                    special_instructions=str(instructions) if instructions else None,
                    selected_modifiers=list(modifiers) if isinstance(modifiers, list) else [],
                )
            )

        # Resolve total
        payment = order_data.get("payment") or payload.get("payment") or {}
        charges = payment.get("charges") if isinstance(payment, dict) else None
        total_info = charges.get("total") if isinstance(charges, dict) else None
        total_cents = calculated_total_cents

        if isinstance(total_info, dict) and "amount" in total_info:
            total_cents = int(total_info["amount"])
        elif isinstance(order_data.get("total_cents"), int):
            total_cents = order_data["total_cents"]
        elif isinstance(order_data.get("total"), (int, float)):
            total_cents = int(float(order_data["total"]) * 100)
        elif isinstance(payload.get("total_cents"), int):
            total_cents = payload["total_cents"]
        elif isinstance(payload.get("total"), (int, float)):
            total_cents = int(float(payload["total"]) * 100)

        placed_at = datetime.now(timezone.utc)
        raw_placed = (
            order_data.get("placed_at") or order_data.get("created_at") or payload.get("created_at")
        )
        if raw_placed:
            try:
                placed_at = datetime.fromisoformat(str(raw_placed).replace("Z", "+00:00"))
            except Exception:
                pass

        return NormalizedOrder(
            external_order_id=order_id,
            provider=self.PROVIDER_NAME,
            display_code=display_code,
            external_store_id=external_store_id,
            customer_name=customer_name,
            customer_phone=str(customer_phone) if customer_phone else None,
            delivery_notes=str(delivery_notes) if delivery_notes else None,
            items=normalized_items,
            total_cents=total_cents,
            currency=str(order_data.get("currency") or payload.get("currency") or "MXN"),
            placed_at=placed_at,
            raw_payload=payload,
        )
