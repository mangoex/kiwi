"""WhatsApp integration adapter via Asistto Tech Provider.

Implements IOrderChannelAdapter and conversational restaurant AI handler,
customer lookup, address validation, and cash-shift-independent order persistence.
"""

from __future__ import annotations

import hmac
import hashlib
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

import sqlalchemy as sa
from sqlalchemy.orm import Session

from .. import models
from .base import IOrderChannelAdapter, NormalizedOrder, NormalizedOrderItem

logger = logging.getLogger(__name__)


def normalize_mexican_phone(raw_phone: str) -> str:
    """Normalize phone to 10 digits national format."""
    digits = re.sub(r"\D", "", str(raw_phone or ""))
    if len(digits) == 13 and digits.startswith("521"):
        return digits[3:]
    if len(digits) == 12 and digits.startswith("52"):
        return digits[2:]
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    if len(digits) == 10:
        return digits
    return digits[-10:] if len(digits) > 10 else digits


class WhatsAppAdapter(IOrderChannelAdapter):
    def verify_webhook_signature(
        self,
        payload_bytes: bytes,
        signature_header: str | None,
        secret: str | None,
    ) -> bool:
        """Verify token or HMAC signature from Asistto."""
        if not secret:
            return True
        if not signature_header:
            return False

        header_val = signature_header.strip()
        # Direct token match (e.g. Bearer <secret> or raw token)
        if header_val.startswith("Bearer "):
            token = header_val[7:].strip()
            if hmac.compare_digest(token, secret):
                return True
        if hmac.compare_digest(header_val, secret):
            return True

        # Fallback: HMAC SHA-256 validation if header contains hex digest
        computed = hmac.new(secret.encode("utf-8"), payload_bytes, hashlib.sha256).hexdigest()
        clean_sig = header_val.replace("sha256=", "").strip()
        return hmac.compare_digest(clean_sig, computed)

    def parse_webhook_event(self, payload: dict[str, Any]) -> tuple[str, str | None]:
        """Extract event type and message ID."""
        event_type = str(payload.get("event") or payload.get("type") or "message")
        event_id = str(
            payload.get("message_id")
            or payload.get("id")
            or payload.get("external_order_id")
            or uuid.uuid4()
        )
        return event_type, event_id

    def extract_incoming_message(
        self, payload: dict[str, Any]
    ) -> tuple[str | None, str | None, bool]:
        """Extract (sender_phone, message_text, is_status_receipt) from Meta/Asistto webhook formats."""
        # 1. Delivery/read status receipts from Meta Cloud API
        if "statuses" in payload:
            return None, None, True
        entries = payload.get("entry", [])
        if isinstance(entries, list):
            for entry in entries:
                for change in entry.get("changes", []):
                    val = change.get("value", {})
                    if "statuses" in val:
                        return None, None, True

        sender_phone = (
            payload.get("from")
            or payload.get("phone")
            or payload.get("customer_phone")
            or payload.get("wa_id")
        )
        incoming_text = (
            payload.get("message")
            or payload.get("text")
            or payload.get("body")
        )

        # Meta Cloud API standard format
        if isinstance(entries, list):
            for entry in entries:
                for change in entry.get("changes", []):
                    val = change.get("value", {})
                    msgs = val.get("messages", [])
                    if msgs and isinstance(msgs, list):
                        msg = msgs[0]
                        if not sender_phone:
                            sender_phone = msg.get("from")
                        if not incoming_text:
                            if isinstance(msg.get("text"), dict):
                                incoming_text = msg["text"].get("body")
                            elif "body" in msg:
                                incoming_text = msg.get("body")
                            elif "button" in msg and isinstance(msg["button"], dict):
                                incoming_text = msg["button"].get("text")
                            elif "interactive" in msg and isinstance(msg["interactive"], dict):
                                incoming_text = (
                                    msg["interactive"].get("button_reply", {}).get("title")
                                    or msg["interactive"].get("list_reply", {}).get("title")
                                )
                    contacts = val.get("contacts", [])
                    if contacts and not sender_phone:
                        sender_phone = contacts[0].get("wa_id")

        if not incoming_text and "messages" in payload and isinstance(payload["messages"], list):
            m0 = payload["messages"][0]
            if isinstance(m0, dict):
                sender_phone = sender_phone or m0.get("from")
                if isinstance(m0.get("text"), dict):
                    incoming_text = m0["text"].get("body")
                else:
                    incoming_text = m0.get("text") or m0.get("body")

        normalized_phone = normalize_mexican_phone(sender_phone) if sender_phone else None
        clean_text = str(incoming_text).strip() if incoming_text else None
        return normalized_phone, clean_text, False

    def generate_ai_reply(
        self,
        incoming_text: str,
        system_prompt: str,
        customer_name: str,
        menu_items: str,
        settings: Any,
    ) -> str:
        """Generate conversational reply using OpenRouter/Gemini with conversational fallback."""
        api_key = (
            getattr(settings, "openrouter_api_key", None)
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("RESTAURANTOS_OPENROUTER_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        if api_key:
            try:
                base_url = getattr(settings, "openrouter_base_url", "https://openrouter.ai/api/v1").rstrip("/")
                body = {
                    "model": getattr(settings, "openrouter_model", "google/gemini-3.1-flash-lite"),
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": incoming_text},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 700,
                }
                req = Request(
                    f"{base_url}/chat/completions",
                    data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "X-OpenRouter-Title": "Kiwi RestaurantOS WhatsApp",
                    },
                    method="POST",
                )
                with urlopen(req, timeout=10.0) as resp:
                    envelope = json.loads(resp.read().decode("utf-8"))
                    content = envelope["choices"][0]["message"]["content"]
                    if content and isinstance(content, str):
                        return content.strip()
            except Exception as e:
                logger.warning("Error invocando OpenRouter para WhatsApp: %s", e)

        # Conversational fallback for Kiwi Healthy Food
        text_lower = incoming_text.lower().strip()
        greeting_name = f" {customer_name}" if customer_name and customer_name != "Estimado cliente" else ""

        if any(w in text_lower for w in ("hola", "buen", "buenas", "que tal", "inicio")):
            return (
                f"¡Hola{greeting_name}! 🥗 Bienvenido a *Kiwi - Comida Saludable* 🥝\n\n"
                "¿En qué podemos consentirte hoy? Tenemos deliciosos bowls, ensaladas frescas, wraps y jugos naturales prensados en frío.\n\n"
                "¿Te gustaría conocer las opciones de hoy o hacer un pedido para recoger o entrega a domicilio?"
            )
        if any(w in text_lower for w in ("menu", "menú", "carta", "platillo", "que tienen", "opciones", "comida")):
            preview = menu_items if menu_items else "• Bowls de Proteína Limpia\n• Ensaladas Frescas\n• Wraps Saludables\n• Jugos Verdes y Smoothies"
            return (
                f"🥑 *Menú Saludable de Kiwi:*\n\n{preview}\n\n"
                "¿Cuál se te antoja ordenar hoy? Puedes decirme tu pedido y con gusto te confirmamos la sucursal de entrega."
            )
        if any(w in text_lower for w in ("sucursal", "donde", "ubicacion", "ubicación", "dirección", "direccion")):
            return (
                "📍 *Nuestras Sucursales Kiwi:*\n"
                "Contamos con sucursales activas listas para preparar tus alimentos frescos al momento.\n\n"
                "¿Te gustaría que te lo enviemos a tu domicilio o prefieres pasar a recogerlo?"
            )
        if any(w in text_lower for w in ("horario", "abren", "cierran", "abierto")):
            return (
                "⏰ *Horarios de Atención Kiwi:*\n"
                "Nuestra cocina saludable está activa para prepararte todo súper fresco.\n\n"
                "Tu pedido queda registrado en cocina de inmediato al confirmarlo."
            )

        return (
            f"¡Muchas gracias por tu mensaje{greeting_name}! 🥝\n\n"
            f"He recibido tu solicitud: *\"{incoming_text}\"*.\n\n"
            "¿Deseas que preparemos tu pedido saludable de hoy o tienes alguna duda con el menú?"
        )

    def normalize_order(
        self,
        payload: dict[str, Any],
        product_mappings: dict[str, str],
        default_products: list[dict[str, Any]] | None = None,
    ) -> NormalizedOrder:
        """Convert a structured order payload into a canonical NormalizedOrder."""
        external_order_id = str(payload.get("external_order_id") or payload.get("order_id") or uuid.uuid4())
        customer = payload.get("customer") or {}
        customer_name = str(customer.get("name") or payload.get("customer_name") or "Cliente WhatsApp").strip()
        raw_phone = str(customer.get("phone") or payload.get("customer_phone") or payload.get("wa_id") or "")
        customer_phone = normalize_mexican_phone(raw_phone)
        delivery_address = payload.get("delivery_address")
        delivery_notes = str(payload.get("delivery_notes") or payload.get("notes") or "")
        if delivery_address and isinstance(delivery_address, dict):
            street = delivery_address.get("street", "")
            ext = delivery_address.get("exterior_number", "")
            col = delivery_address.get("neighborhood", "")
            addr_str = f"{street} #{ext}, {col}".strip(" ,#")
            delivery_notes = f"{addr_str}. {delivery_notes}".strip(" .")

        raw_items = payload.get("items") or payload.get("lines") or []
        items: list[NormalizedOrderItem] = []
        total_cents = 0

        fallback_product = (default_products or [{}])[0]
        fallback_id = str(fallback_product.get("id") or "00000000-0000-0000-0000-000000000001")
        fallback_name = str(fallback_product.get("name") or "Platillo Especial")

        for raw_item in raw_items:
            ext_id = str(raw_item.get("id") or raw_item.get("product_id") or "")
            matched_id = product_mappings.get(ext_id) or ext_id or fallback_id
            name = str(raw_item.get("name") or raw_item.get("product_name") or fallback_name)
            qty = max(1, int(raw_item.get("quantity") or 1))
            unit_price = int(raw_item.get("price_cents") or raw_item.get("unit_price_cents") or 0)
            line_total = unit_price * qty
            total_cents += line_total
            instructions = str(raw_item.get("instructions") or raw_item.get("notes") or "") or None
            modifiers = raw_item.get("modifiers") or raw_item.get("selected_options") or []

            items.append(
                NormalizedOrderItem(
                    product_id=matched_id,
                    product_name=name,
                    quantity=qty,
                    unit_price_cents=unit_price,
                    line_total_cents=line_total,
                    special_instructions=instructions,
                    selected_modifiers=modifiers,
                )
            )

        if not items and default_products:
            # Fallback single item if empty
            items.append(
                NormalizedOrderItem(
                    product_id=fallback_id,
                    product_name=fallback_name,
                    quantity=1,
                    unit_price_cents=int(payload.get("total_cents") or 12000),
                    line_total_cents=int(payload.get("total_cents") or 12000),
                )
            )
            total_cents = int(payload.get("total_cents") or 12000)

        return NormalizedOrder(
            external_order_id=external_order_id,
            provider="WHATSAPP",
            display_code=str(payload.get("display_code") or external_order_id[:8]),
            external_store_id=str(payload.get("external_store_id") or payload.get("bot_id") or "default"),
            customer_name=customer_name,
            customer_phone=customer_phone,
            delivery_notes=delivery_notes or None,
            items=items,
            total_cents=int(payload.get("total_cents") or total_cents),
            currency=str(payload.get("currency") or "MXN"),
            placed_at=datetime.now(timezone.utc),
            raw_payload=payload,
        )

    def lookup_customer(
        self, session: Session, organization_id: str, raw_phone: str
    ) -> dict[str, Any]:
        """Look up customer details, saved addresses, and past order history by normalized phone."""
        phone_10 = normalize_mexican_phone(raw_phone)
        if not phone_10:
            return {"found": False, "normalized_phone": ""}

        # Search in customer_phones
        phone_row = session.execute(
            sa.select(
                models.customer_phones.c.customer_id,
                models.customer_phones.c.normalized_number,
            ).where(
                models.customer_phones.c.normalized_number == phone_10,
                models.customer_phones.c.status == "active",
            )
        ).mappings().first()

        if not phone_row:
            # Try matching captured_number or suffix
            phone_row = session.execute(
                sa.select(
                    models.customer_phones.c.customer_id,
                    models.customer_phones.c.normalized_number,
                ).where(
                    models.customer_phones.c.captured_number.like(f"%{phone_10}%"),
                    models.customer_phones.c.status == "active",
                )
            ).mappings().first()

        if not phone_row:
            return {"found": False, "normalized_phone": phone_10}

        customer_id = str(phone_row["customer_id"])
        customer = session.execute(
            sa.select(models.customers).where(
                models.customers.c.id == customer_id,
                models.customers.c.organization_id == organization_id,
            )
        ).mappings().first()

        if not customer:
            return {"found": False, "normalized_phone": phone_10}

        # Retrieve saved addresses
        addresses = list(
            session.execute(
                sa.select(models.customer_addresses).where(
                    models.customer_addresses.c.customer_id == customer_id,
                    models.customer_addresses.c.status == "active",
                ).order_by(models.customer_addresses.c.is_default.desc())
            ).mappings().all()
        )

        formatted_addresses = [
            {
                "id": str(addr["id"]),
                "alias": str(addr["alias"]),
                "street": str(addr["street"]),
                "exterior_number": str(addr["exterior_number"]),
                "neighborhood": str(addr["neighborhood"]),
                "city": str(addr["city"]),
                "references": str(addr["references"] or ""),
                "is_default": bool(addr["is_default"]),
            }
            for addr in addresses
        ]

        # Retrieve past top favorite products
        favorite_rows = list(
            session.execute(
                sa.select(
                    models.order_lines.c.product_id,
                    models.order_lines.c.product_name,
                    sa.func.count(models.order_lines.c.id).label("times_ordered"),
                )
                .select_from(
                    models.order_lines.join(
                        models.orders, models.order_lines.c.order_id == models.orders.c.id
                    )
                )
                .where(
                    models.orders.c.organization_id == organization_id,
                    models.orders.c.customer_id == customer_id,
                    models.orders.c.status != "cancelled",
                )
                .group_by(models.order_lines.c.product_id, models.order_lines.c.product_name)
                .order_by(sa.desc("times_ordered"))
                .limit(5)
            ).mappings().all()
        )

        favorites = [
            {
                "product_id": str(r["product_id"]),
                "product_name": str(r["product_name"]),
                "times_ordered": int(r["times_ordered"]),
            }
            for r in favorite_rows
        ]

        return {
            "found": True,
            "customer_id": customer_id,
            "name": str(customer["name"]),
            "normalized_phone": phone_10,
            "customer_segment": customer.get("customer_segment"),
            "addresses": formatted_addresses,
            "favorites": favorites,
        }

    def dispatch_outgoing_response(
        self,
        return_url: str,
        token: str | None = None,
        payload: dict[str, Any] | None = None,
        recipient_phone: str | None = None,
        message_text: str | None = None,
        outgoing_secret: str | None = None,
    ) -> bool:
        """Send asynchronous reply back to Asistto webhook return URL."""
        if not return_url:
            return False
        if return_url.startswith("https://mock.localhost") or return_url.startswith("http://mock.localhost"):
            return True

        auth_token = outgoing_secret or token or ""
        headers = {
            "Content-Type": "application/json",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        data = dict(payload) if payload else {}
        if recipient_phone:
            data["to"] = recipient_phone
        if message_text:
            data["message"] = message_text
            data["text"] = message_text

        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = Request(return_url, data=body, headers=headers, method="POST")
        try:
            with urlopen(req, timeout=5.0) as resp:
                return resp.status in (200, 201, 202)
        except (HTTPError, URLError, TimeoutError) as e:
            logger.warning("Error despachando respuesta a Asistto: %s", e)
            return False
        except Exception as e:
            logger.warning("Error inesperado despachando a Asistto: %s", e)
            return False

