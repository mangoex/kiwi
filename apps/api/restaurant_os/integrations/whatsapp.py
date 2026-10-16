"""WhatsApp integration adapter via Asistto Tech Provider.

Implements IOrderChannelAdapter and conversational restaurant AI handler,
customer lookup, address validation, and cash-shift-independent order persistence.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

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
        (
            'Extract (sender_phone, message_text, is_status_receipt) '
            'from Meta/Asistto webhook formats.'
        )
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
        incoming_text = payload.get("message") or payload.get("text") or payload.get("body")

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
                                incoming_text = msg["interactive"].get("button_reply", {}).get(
                                    "title"
                                ) or msg["interactive"].get("list_reply", {}).get("title")
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

    def extract_contact_name(self, payload: dict[str, Any]) -> str | None:
        """Extract WhatsApp profile name from Meta/Asistto webhook payload if present."""
        if not isinstance(payload, dict):
            return None
        for key in ("contact_name", "profile_name", "customer_name"):
            val = payload.get(key)
            if isinstance(val, str) and val.strip():
                return val.strip()
        entries = payload.get("entry", [])
        if isinstance(entries, list):
            for entry in entries:
                for change in entry.get("changes", []):
                    val = change.get("value", {})
                    contacts = val.get("contacts", [])
                    if isinstance(contacts, list) and contacts:
                        profile = contacts[0].get("profile") or {}
                        name = profile.get("name")
                        if isinstance(name, str) and name.strip():
                            return name.strip()
        return None

    def build_runtime_context(
        self,
        session: Session,
        organization_id: str,
        sender_phone: str | None,
        payload: dict[str, Any] | None = None,
        default_prep_time_minutes: int = 25,
    ) -> dict[str, Any]:
        (
            'Build full live context from DB: customer profile, menu '
            'with prices, branches, and conversation history.'
        )
        customer: dict[str, Any] = {
            "found": False,
            "normalized_phone": normalize_mexican_phone(sender_phone or ""),
        }
        if sender_phone:
            try:
                customer = self.lookup_customer(session, organization_id, sender_phone)
            except Exception as exc:
                logger.warning("Error consultando cliente en build_runtime_context: %s", exc)

        contact_name = self.extract_contact_name(payload or {})
        customer_found = bool(customer and customer.get("found"))
        if customer_found:
            customer_name = str(customer.get("name") or contact_name or "Estimado cliente").strip()
        else:
            customer_name = ""

        # Format saved addresses
        addresses = (customer.get("addresses") if customer else None) or []
        if addresses:
            addr_lines = []
            for addr in addresses:
                alias = addr.get("alias") or "Domicilio"
                street = addr.get("street") or ""
                ext = addr.get("exterior_number") or ""
                col = addr.get("neighborhood") or ""
                city = addr.get("city") or ""
                refs = f" (Ref: {addr['references']})" if addr.get("references") else ""
                default_tag = " [Predeterminada]" if addr.get("is_default") else ""
                addr_lines.append(
                    f"{alias}: {street} #{ext}, Col. {col}, {city}{refs}{default_tag}".strip()
                )
            delivery_address_str = " | ".join(addr_lines)
        else:
            delivery_address_str = (
                "Sin domicilio registrado en el sistema (preguntar dirección o si pasa a recoger)"
            )

        # Format favorite dishes
        favorites = (customer.get("favorites") if customer else None) or []
        if favorites:
            fav_parts = [
                f"{f['product_name']} (pedido {f['times_ordered']} "
                f"{'vez' if f['times_ordered'] == 1 else 'veces'})"
                for f in favorites
                if f.get("product_name")
            ]
            favorite_dishes_str = (
                ", ".join(fav_parts) if fav_parts else "Sin platillos favoritos registrados aún"
            )
        else:
            favorite_dishes_str = "Sin platillos favoritos registrados aún"

        # Format past orders
        past_orders_list = (customer.get("past_orders") if customer else None) or []
        if past_orders_list:
            past_orders_str = " | ".join(past_orders_list)
        else:
            past_orders_str = "Sin pedidos previos registrados"

        # Fetch active branches
        branches_str = ""
        try:
            branch_rows = list(
                session.execute(
                    sa.select(
                        models.branches.c.id,
                        models.branches.c.name,
                        models.branches.c.code,
                        models.branches.c.street,
                        models.branches.c.exterior_number,
                        models.branches.c.neighborhood,
                        models.branches.c.city,
                        models.branches.c.phone,
                    )
                    .where(
                        models.branches.c.organization_id == organization_id,
                        models.branches.c.status == "active",
                    )
                    .order_by(models.branches.c.name.asc())
                )
                .mappings()
                .all()
            )
            if branch_rows:
                b_lines = []
                for b in branch_rows:
                    addr_parts = [
                        p
                        for p in (
                            b.get("street"),
                            f"#{b['exterior_number']}" if b.get("exterior_number") else None,
                            b.get("neighborhood"),
                            b.get("city"),
                        )
                        if p
                    ]
                    addr_txt = f" — Dirección: {', '.join(addr_parts)}" if addr_parts else ""
                    phone_txt = f" — Tel: {b['phone']}" if b.get("phone") else ""
                    b_lines.append(f"• {b['name']} ({b['code']}){addr_txt}{phone_txt}")
                branches_str = "\n".join(b_lines)
        except Exception as exc:
            logger.warning("Error consultando sucursales para WhatsApp: %s", exc)
        if not branches_str:
            branches_str = "• Sucursal Principal Kiwi (Activa)"

        # Fetch full active menu with categories and official prices
        menu_items_str = ""
        try:
            prod_rows = list(
                session.execute(
                    sa.select(
                        models.products.c.id,
                        models.products.c.name,
                        models.products.c.description,
                        models.product_categories.c.name.label("category_name"),
                        models.product_categories.c.display_order.label("cat_order"),
                    )
                    .select_from(
                        models.products.outerjoin(
                            models.product_categories,
                            models.products.c.category_id == models.product_categories.c.id,
                        )
                    )
                    .where(
                        models.products.c.organization_id == organization_id,
                        models.products.c.status == "active",
                    )
                    .order_by(
                        sa.func.coalesce(models.product_categories.c.display_order, 999).asc(),
                        models.product_categories.c.name.asc(),
                        models.products.c.name.asc(),
                    )
                )
                .mappings()
                .all()
            )

            price_map: dict[str, int] = {}
            if prod_rows:
                prod_ids = [str(r["id"]) for r in prod_rows]
                price_rows = list(
                    session.execute(
                        sa.select(
                            models.price_versions.c.product_id,
                            models.price_versions.c.price_cents,
                            models.price_versions.c.valid_from,
                        )
                        .where(
                            models.price_versions.c.organization_id == organization_id,
                            models.price_versions.c.product_id.in_(prod_ids),
                            models.price_versions.c.valid_to.is_(None),
                        )
                        .order_by(models.price_versions.c.valid_from.desc())
                    )
                    .mappings()
                    .all()
                )
                for pr in price_rows:
                    pid = str(pr["product_id"])
                    if pid not in price_map and pr["price_cents"] is not None:
                        price_map[pid] = int(pr["price_cents"])

                by_category: dict[str, list[str]] = {}
                for r in prod_rows:
                    pid = str(r["id"])
                    cat = str(r.get("category_name") or "Menú General")
                    pname = str(r["name"])
                    pdesc = str(r.get("description") or "").strip()
                    price_cents = price_map.get(pid)
                    price_txt = (
                        f" — ${price_cents / 100:,.2f} MXN" if price_cents is not None else ""
                    )
                    desc_txt = f" ({pdesc})" if pdesc else ""
                    by_category.setdefault(cat, []).append(f"• {pname}{price_txt}{desc_txt}")

                cat_blocks = []
                for cat, lines in by_category.items():
                    cat_blocks.append(f"*{cat}*:\n" + "\n".join(lines))
                menu_items_str = "\n\n".join(cat_blocks)
        except Exception as exc:
            logger.warning("Error consultando catálogo completo para WhatsApp: %s", exc)

        # Fetch recent conversation history for this sender_phone
        conversation_history: list[dict[str, str]] = []
        phone_10 = normalize_mexican_phone(sender_phone or "")
        if phone_10:
            try:
                recent_logs = list(
                    session.execute(
                        sa.select(
                            models.integration_webhook_logs.c.event_type,
                            models.integration_webhook_logs.c.payload_raw,
                            models.integration_webhook_logs.c.created_at,
                        )
                        .where(
                            models.integration_webhook_logs.c.organization_id == organization_id,
                            models.integration_webhook_logs.c.provider == "WHATSAPP",
                        )
                        .order_by(models.integration_webhook_logs.c.created_at.desc())
                        .limit(40)
                    )
                    .mappings()
                    .all()
                )
                # Skip the very first log if it is the current incoming message just logged
                skipped_current = False
                turns: list[dict[str, str]] = []
                for log_row in recent_logs:
                    ev_type = str(log_row.get("event_type") or "")
                    raw = log_row.get("payload_raw")
                    if not isinstance(raw, dict):
                        continue
                    if ev_type == "assistant_reply":
                        to_phone = normalize_mexican_phone(str(raw.get("to") or ""))
                        reply_msg = str(raw.get("reply") or "").strip()
                        if to_phone == phone_10 and reply_msg:
                            turns.append({"role": "assistant", "content": reply_msg})
                    else:
                        msg_phone, msg_text, is_status = self.extract_incoming_message(raw)
                        if not is_status and msg_phone == phone_10 and msg_text:
                            if not skipped_current:
                                skipped_current = True
                                continue
                            turns.append({"role": "user", "content": msg_text})
                    if len(turns) >= 10:
                        break
                conversation_history = list(reversed(turns))
            except Exception as exc:
                logger.warning("Error cargando historial conversacional de WhatsApp: %s", exc)

        return {
            "customer": customer,
            "customer_found": customer_found,
            "customer_name": customer_name or "Estimado cliente",
            "customer_name_for_prompt": customer_name
            if customer_found
            else (
                f"{contact_name} (Cliente nuevo no registrado aún en BD)"
                if contact_name
                else "Cliente nuevo (no registrado aún en BD)"
            ),
            "customer_phone": phone_10,
            "delivery_address": delivery_address_str,
            "favorite_dishes": favorite_dishes_str,
            "past_orders": past_orders_str,
            "menu_items": menu_items_str,
            "branches": branches_str,
            "active_branch": branches_str,
            "default_prep_time_minutes": str(default_prep_time_minutes),
            "conversation_history": conversation_history,
        }

    def render_system_prompt(
        self,
        system_prompt: str,
        customer_name: str,
        menu_items: str,
        context: dict[str, Any] | None = None,
    ) -> str:
        """Interpolate all runtime variables into the master prompt and append live DB context."""
        ctx = context or {}
        customer_found = bool(
            ctx.get("customer_found", customer_name and customer_name != "Estimado cliente")
        )
        prompt_customer_name = str(
            ctx.get("customer_name_for_prompt")
            or (customer_name if customer_found else "Cliente nuevo (no registrado aún en BD)")
        )
        menu_str = str(ctx.get("menu_items") or menu_items or "Catálogo en actualización")
        fav_str = str(ctx.get("favorite_dishes") or "Sin platillos favoritos registrados aún")
        past_str = str(ctx.get("past_orders") or "Sin pedidos previos registrados")
        addr_str = str(ctx.get("delivery_address") or "Sin domicilio registrado aún")
        branches_str = str(
            ctx.get("branches") or ctx.get("active_branch") or "• Sucursal Principal Kiwi"
        )
        prep_str = str(ctx.get("default_prep_time_minutes") or "25")
        phone_str = str(ctx.get("customer_phone") or "")

        base_prompt = (system_prompt or "").strip()
        if not base_prompt:
            base_prompt = (
                "Eres KiwiBot, el anfitrión y sommelier virtual de Kiwi - Comida Saludable. "
                'Atiende con calidez, ofrece el menú oficial con sus precios '
                'reales, identifica al cliente '
                'y confirma sucursal y modalidad (recoger o domicilio) antes '
                'de registrar su pedido.'
            )

        replacements = {
            "{customer_name}": prompt_customer_name,
            "{menu_items}": menu_str,
            "{favorite_dishes}": fav_str,
            "{past_orders}": past_str,
            "{delivery_address}": addr_str,
            "{active_branch}": branches_str,
            "{branches}": branches_str,
            "{default_prep_time_minutes}": prep_str,
            "{customer_phone}": phone_str,
        }
        rendered = base_prompt
        for placeholder, value in replacements.items():
            rendered = rendered.replace(placeholder, value)

        # Always append the authoritative live database snapshot so the AI has full visibility
        # even if the user's custom master_prompt omitted some placeholders.
        customer_status_line = (
            f"Cliente registrado en BD: SÍ — Nombre: {customer_name} (Tel: {phone_str})"
            if customer_found
            else f"Cliente registrado en BD: NO (Teléfono: {phone_str}). "
            "Es cliente nuevo; salúdalo cálidamente y pregúntale su nombre."
        )
        live_block = (
            "\n\n=== DATOS EN TIEMPO REAL DE LA BASE DE DATOS (KIWI POS) ===\n"
            f"- {customer_status_line}\n"
            f"- Domicilios guardados del cliente: {addr_str}\n"
            f"- Platillos favoritos del cliente: {fav_str}\n"
            f"- Historial de pedidos recientes: {past_str}\n"
            f"- Tiempo estimado de preparación: {prep_str} minutos\n"
            f"- Sucursales activas:\n{branches_str}\n\n"
            f"- MENÚ OFICIAL ACTIVO CON PRECIOS:\n{menu_str}\n"
            "============================================================"
        )
        return rendered + live_block

    def generate_ai_reply(
        self,
        incoming_text: str,
        system_prompt: str,
        customer_name: str,
        menu_items: str,
        settings: Any,
        context: dict[str, Any] | None = None,
        conversation_history: list[dict[str, str]] | None = None,
    ) -> str:
        (
            'Generate conversational reply using OpenRouter/Gemini with '
            'interpolated live DB context.'
        )
        rendered_prompt = self.render_system_prompt(
            system_prompt=system_prompt,
            customer_name=customer_name,
            menu_items=menu_items,
            context=context,
        )
        history = (
            conversation_history
            if conversation_history is not None
            else (context.get("conversation_history") if isinstance(context, dict) else None) or []
        )

        api_key = (
            getattr(settings, "openrouter_api_key", None)
            or os.environ.get("OPENROUTER_API_KEY")
            or os.environ.get("RESTAURANTOS_OPENROUTER_API_KEY")
            or os.environ.get("GEMINI_API_KEY")
        )
        if api_key:
            try:
                base_url = getattr(
                    settings, "openrouter_base_url", "https://openrouter.ai/api/v1"
                ).rstrip("/")
                messages: list[dict[str, str]] = [{"role": "system", "content": rendered_prompt}]
                for turn in history[-10:]:
                    if (
                        isinstance(turn, dict)
                        and turn.get("role") in ("user", "assistant")
                        and turn.get("content")
                    ):
                        messages.append({"role": turn["role"], "content": str(turn["content"])})
                messages.append({"role": "user", "content": incoming_text})

                body = {
                    "model": getattr(settings, "openrouter_model", "google/gemini-3.1-flash-lite"),
                    "messages": messages,
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
                with urlopen(req, timeout=12.0) as resp:
                    envelope = json.loads(resp.read().decode("utf-8"))
                    content: object = envelope["choices"][0]["message"]["content"]
                    if content and isinstance(content, str):
                        return content.strip()
            except Exception as e:
                logger.warning("Error invocando OpenRouter para WhatsApp: %s", e)

        # Conversational fallback for Kiwi Healthy Food using live DB data
        ctx = context or {}
        effective_menu = str(ctx.get("menu_items") or menu_items or "").strip()
        effective_branches = str(ctx.get("branches") or "").strip()
        effective_favs = str(ctx.get("favorite_dishes") or "").strip()
        effective_addr = str(ctx.get("delivery_address") or "").strip()
        text_lower = incoming_text.lower().strip()
        has_known_name = bool(customer_name and customer_name != "Estimado cliente")
        greeting_name = f" {customer_name}" if has_known_name else ""

        if any(
            w in text_lower
            for w in (
                "menu",
                "menú",
                "carta",
                "platillo",
                "que tienen",
                "qué tienen",
                "opciones",
                "comida",
                "precio",
                "precios",
                "venden",
            )
        ):
            preview = (
                effective_menu
                if effective_menu
                else '• Bowls de Proteína Limpia\n• Ensaladas Frescas\n• Wraps '
                'Saludables\n• Jugos Verdes y Smoothies'
            )
            fav_note = (
                f"\n\n⭐ *Tus favoritos registrados:* {effective_favs}"
                if has_known_name and effective_favs and "Sin platillos" not in effective_favs
                else ""
            )
            return (
                f"¡Hola{greeting_name}! 🥑 Aquí tienes nuestro *Menú Saludable de Kiwi*:\n\n"
                f"{preview}{fav_note}\n\n"
                '¿Cuál se te antoja ordenar hoy? Dime si prefieres entrega a '
                'domicilio o pasar a recoger a sucursal.'
            )
        if any(
            w in text_lower
            for w in (
                "sucursal",
                "sucursales",
                "donde",
                "dónde",
                "ubicacion",
                "ubicación",
                "dirección",
                "direccion",
            )
        ):
            branch_info = (
                effective_branches if effective_branches else "• Sucursal Principal Kiwi (Activa)"
            )
            return (
                f"📍 *Nuestras Sucursales Kiwi:*\n{branch_info}\n\n"
                "¿En qué sucursal prefieres recoger tu pedido o a qué dirección te lo enviamos?"
            )
        if any(w in text_lower for w in ("hola", "buen", "buenas", "que tal", "qué tal", "inicio")):
            if has_known_name:
                addr_hint = (
                    f"\n📍 Domicilio registrado: {effective_addr}"
                    if effective_addr and "Sin domicilio" not in effective_addr
                    else ""
                )
                return (
                    f"¡Hola {customer_name}! 🥑 Qué gusto saludarte de nuevo en "
                    f"*Kiwi - Comida Saludable* 🥝{addr_hint}\n\n"
                    '¿Te gustaría ver nuestro menú saludable de hoy o repetir '
                    'alguno de tus platillos favoritos?'
                )
            return (
                "¡Hola! 🥗 Bienvenido a *Kiwi - Comida Saludable* 🥝\n\n"
                '¿Con quién tengo el gusto hoy? Puedo mostrarte nuestro menú '
                'con precios, sucursales disponibles o tomar tu pedido para '
                'recoger o a domicilio.'
            )
        if any(w in text_lower for w in ("horario", "horarios", "abren", "cierran", "abierto")):
            branch_info = (
                f"\n\n📍 *Sucursales:*\n{effective_branches}" if effective_branches else ""
            )
            return (
                f"⏰ *Horarios de Atención Kiwi:*\n"
                "Nuestra cocina saludable está lista para preparar tus alimentos frescos."
                f"{branch_info}\n\n"
                "¿Deseas conocer el menú o levantar tu pedido?"
            )

        menu_snippet = f"\n\n📋 *Menú disponible:*\n{effective_menu}" if effective_menu else ""
        return (
            f"¡Con gusto{greeting_name}! 🥝\n\n"
            f'Recibí tu mensaje: *"{incoming_text}"*.{menu_snippet}\n\n'
            '¿Qué platillos te gustaría incluir en tu pedido y en qué '
            'sucursal o domicilio lo prefieres?'
        )

    def normalize_order(
        self,
        payload: dict[str, Any],
        product_mappings: dict[str, str],
        default_products: list[dict[str, Any]] | None = None,
    ) -> NormalizedOrder:
        """Convert a structured order payload into a canonical NormalizedOrder."""
        external_order_id = str(
            payload.get("external_order_id") or payload.get("order_id") or uuid.uuid4()
        )
        customer = payload.get("customer") or {}
        customer_name = str(
            customer.get("name") or payload.get("customer_name") or "Cliente WhatsApp"
        ).strip()
        raw_phone = str(
            customer.get("phone") or payload.get("customer_phone") or payload.get("wa_id") or ""
        )
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
            external_store_id=str(
                payload.get("external_store_id") or payload.get("bot_id") or "default"
            ),
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

        phone_variants = [
            phone_10,
            f"52{phone_10}",
            f"521{phone_10}",
            f"+52{phone_10}",
            f"+521{phone_10}",
        ]

        # Join customer_phones with customers scoped to organization_id first
        joined_row = (
            session.execute(
                sa.select(
                    models.customers.c.id.label("customer_id"),
                    models.customers.c.name,
                    models.customers.c.customer_segment,
                    models.customer_phones.c.normalized_number,
                )
                .select_from(
                    models.customer_phones.join(
                        models.customers,
                        models.customer_phones.c.customer_id == models.customers.c.id,
                    )
                )
                .where(
                    models.customers.c.organization_id == organization_id,
                    models.customers.c.status == "active",
                    models.customer_phones.c.status == "active",
                    sa.or_(
                        models.customer_phones.c.normalized_number.in_(phone_variants),
                        models.customer_phones.c.normalized_number.like(f"%{phone_10}"),
                        models.customer_phones.c.captured_number.like(f"%{phone_10}%"),
                    ),
                )
                .order_by(models.customer_phones.c.is_primary.desc())
            )
            .mappings()
            .first()
        )

        if not joined_row:
            return {"found": False, "normalized_phone": phone_10}

        customer_id = str(joined_row["customer_id"])

        # Retrieve saved addresses
        addresses = list(
            session.execute(
                sa.select(models.customer_addresses)
                .where(
                    models.customer_addresses.c.customer_id == customer_id,
                    models.customer_addresses.c.status == "active",
                )
                .order_by(models.customer_addresses.c.is_default.desc())
            )
            .mappings()
            .all()
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
            )
            .mappings()
            .all()
        )

        favorites = [
            {
                "product_id": str(r["product_id"]),
                "product_name": str(r["product_name"]),
                "times_ordered": int(r["times_ordered"]),
            }
            for r in favorite_rows
        ]

        # Retrieve last 5 orders summary for {past_orders}
        past_orders: list[str] = []
        try:
            recent_order_rows = list(
                session.execute(
                    sa.select(
                        models.orders.c.id,
                        models.orders.c.folio,
                        models.orders.c.total_cents,
                        models.orders.c.order_type,
                        models.orders.c.created_at,
                    )
                    .where(
                        models.orders.c.organization_id == organization_id,
                        models.orders.c.customer_id == customer_id,
                        models.orders.c.status != "cancelled",
                    )
                    .order_by(models.orders.c.created_at.desc())
                    .limit(5)
                )
                .mappings()
                .all()
            )
            for orow in recent_order_rows:
                total_mxn = (int(orow.get("total_cents") or 0)) / 100.0
                folio_str = str(orow.get("folio") or "")
                past_orders.append(f"Pedido {folio_str} (${total_mxn:,.2f} MXN)")
        except Exception:
            past_orders = []

        return {
            "found": True,
            "customer_id": customer_id,
            "name": str(joined_row["name"]),
            "normalized_phone": phone_10,
            "customer_segment": joined_row.get("customer_segment"),
            "addresses": formatted_addresses,
            "favorites": favorites,
            "past_orders": past_orders,
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
        if return_url.startswith("https://mock.localhost") or return_url.startswith(
            "http://mock.localhost"
        ):
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
